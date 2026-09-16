"""Synthetic live-cell specimens with known ground truth.

A real quantitative phase dataset has no ground truth. You have the instrument's
own reconstruction, which is the thing you are trying to improve on, so it
cannot serve as a target. Simulation inverts that problem: the specimen is
defined first, in physical units, and the camera data is derived from it. That
gives exactly paired (measurement, truth) samples, and it also gives the true
dry mass of every individual cell, which is what the instrument is ultimately
for.

Phase is produced as the optical path length through the specimen,

    phase = 2 * pi / wavelength * refractive_index_contrast * thickness

so every number in here is a physical quantity rather than a grey level.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from .optics import Optics, REFRACTIVE_INCREMENT


@dataclass
class SpecimenConfig:
    """Statistics of the simulated culture.

    The defaults describe a healthy adherent culture at moderate confluence.
    `evaluation` and `sparse` variants exist so that held out data can be drawn
    from a deliberately different distribution than the training data.
    """

    density: float = 1.8e-3            # cells per square micrometre
    radius_range: tuple[float, float] = (4.5, 13.0)     # micrometres
    thickness_range: tuple[float, float] = (2.6, 6.0)   # micrometres, spread cells
    cytoplasm_contrast: tuple[float, float] = (0.020, 0.032)
    nucleus_contrast_gain: tuple[float, float] = (1.28, 1.62)
    mitotic_fraction: float = 0.09     # rounded up, thick, optically dense
    mitotic_thickness: tuple[float, float] = (5.5, 8.6)
    debris_density: float = 2.2e-4
    texture_strength: float = 0.16
    background_drift: float = 0.035    # radians of slow medium variation
    absorption_gain: float = 0.05      # cells are not quite pure phase objects
    allow_overlap: float = 0.72        # centre spacing as a fraction of radius sum

    @staticmethod
    def variant(name: str) -> "SpecimenConfig":
        if name == "train":
            return SpecimenConfig()
        if name == "sparse":
            return SpecimenConfig(density=6.0e-4, mitotic_fraction=0.04)
        if name == "evaluation":
            # Deliberately shifted: denser, thicker, more mitotic figures, more
            # debris and stronger background drift. A model that only works on
            # the training distribution will show up here.
            return SpecimenConfig(
                density=2.9e-3,
                radius_range=(5.0, 14.0),
                thickness_range=(2.2, 7.0),
                cytoplasm_contrast=(0.015, 0.034),
                mitotic_fraction=0.16,
                mitotic_thickness=(6.0, 9.8),
                debris_density=4.5e-4,
                texture_strength=0.22,
                background_drift=0.06,
                allow_overlap=0.62,
            )
        raise ValueError(f"unknown specimen variant: {name!r}")


@dataclass
class Specimen:
    """A generated field of view and everything known to be true about it."""

    phase: np.ndarray                  # radians, unwrapped
    labels: np.ndarray                 # int32 instance map, 0 is background
    absorption: np.ndarray             # optical density
    optics: Optics
    cells: list[dict] = field(default_factory=list)

    @property
    def shape(self) -> tuple[int, int]:
        return self.phase.shape


def _blob_radius(
    angle: np.ndarray,
    radius: float,
    rng: np.random.Generator,
    roughness: float = 1.0,
) -> np.ndarray:
    """A closed random contour: a circle perturbed by a few angular harmonics.

    The low harmonics carry most of the weight, which is what gives an adherent
    cell its lobed, few-armed outline rather than a crinkled one.
    """
    contour = np.ones_like(angle)
    for harmonic in range(2, 8):
        amplitude = rng.normal(0.0, roughness * 0.30 / harmonic**0.75)
        contour += amplitude * np.cos(harmonic * angle + rng.uniform(0, 2 * np.pi))
    return radius * np.clip(contour, 0.30, 2.10)


def _cell_thickness(
    size: int,
    radius_px: float,
    height: float,
    flatness: float,
    elongation: float,
    orientation: float,
    roughness: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Thickness profile of one cell on a local square grid, in micrometres.

    An adherent cell is not a hemisphere. It spreads thin against the coverslip
    with a raised perinuclear region, so the profile exponent sits well below
    the 0.5 that would give a sphere. It is rarely circular either, so the
    coordinate frame is stretched along a random axis before the outline is
    drawn.
    """
    coords = np.arange(size) - (size - 1) / 2.0
    x, y = np.meshgrid(coords, coords, indexing="xy")

    cos_t, sin_t = np.cos(orientation), np.sin(orientation)
    along = (x * cos_t + y * sin_t) / elongation
    across = -x * sin_t + y * cos_t

    r = np.hypot(along, across)
    angle = np.arctan2(across, along)

    boundary = _blob_radius(angle, radius_px, rng, roughness)
    normalised = np.clip(r / np.maximum(boundary, 1e-6), 0.0, 1.0)
    profile = np.power(np.clip(1.0 - normalised**2, 0.0, None), flatness)
    profile[r > boundary] = 0.0
    return height * profile


def _smooth_noise(shape: tuple[int, int], sigma: float, rng: np.random.Generator) -> np.ndarray:
    """Zero mean band limited noise, normalised to unit standard deviation."""
    raw = rng.normal(size=shape)
    smoothed = ndimage.gaussian_filter(raw, sigma=sigma, mode="reflect")
    deviation = smoothed.std()
    return smoothed / deviation if deviation > 0 else smoothed


def _place(canvas: np.ndarray, patch: np.ndarray, top: int, left: int) -> tuple[slice, slice]:
    """Add `patch` into `canvas` at the given corner, clipping at the edges."""
    height, width = patch.shape
    canvas_h, canvas_w = canvas.shape

    y0, x0 = max(top, 0), max(left, 0)
    y1, x1 = min(top + height, canvas_h), min(left + width, canvas_w)
    if y0 >= y1 or x0 >= x1:
        return slice(0, 0), slice(0, 0)

    canvas[y0:y1, x0:x1] += patch[y0 - top : y1 - top, x0 - left : x1 - left]
    return slice(y0, y1), slice(x0, x1)


def generate(
    shape: tuple[int, int],
    optics: Optics,
    config: SpecimenConfig | None = None,
    seed: int | None = None,
) -> Specimen:
    """Generate one field of view with full ground truth."""
    config = config or SpecimenConfig()
    rng = np.random.default_rng(seed)

    pixel = optics.pixel_size
    wavenumber = 2.0 * np.pi / optics.wavelength
    phase = np.zeros(shape, dtype=np.float64)
    labels = np.zeros(shape, dtype=np.int32)
    absorption = np.zeros(shape, dtype=np.float64)

    area_um2 = shape[0] * shape[1] * pixel**2
    n_cells = max(1, rng.poisson(config.density * area_um2))

    centres: list[tuple[float, float, float]] = []
    records: list[dict] = []

    for index in range(n_cells):
        mitotic = rng.random() < config.mitotic_fraction

        if mitotic:
            radius = rng.uniform(4.0, 7.0)
            height = rng.uniform(*config.mitotic_thickness)
            flatness = rng.uniform(0.42, 0.55)       # close to a sphere
        else:
            radius = rng.uniform(*config.radius_range)
            height = rng.uniform(*config.thickness_range)
            flatness = rng.uniform(0.22, 0.38)       # spread flat

        if mitotic:
            # A cell rounds up to divide, so it loses its spread shape.
            elongation = rng.uniform(1.0, 1.15)
            roughness = rng.uniform(0.10, 0.22)   # a dividing cell is smooth
        else:
            elongation = rng.uniform(1.0, 2.9)
            roughness = rng.uniform(0.75, 1.15)
        orientation = rng.uniform(0, np.pi)
        radius_px = radius / pixel
        centre_y = rng.uniform(0, shape[0])
        centre_x = rng.uniform(0, shape[1])

        # Cells in culture touch, but they do not sit on top of each other.
        too_close = any(
            np.hypot(centre_y - cy, centre_x - cx)
            < config.allow_overlap * (radius_px * elongation + other_r)
            for cy, cx, other_r in centres
        )
        if too_close:
            continue
        centres.append((centre_y, centre_x, radius_px))

        size = int(np.ceil(2.2 * radius_px * max(elongation, 1.0) * 1.35)) | 1
        thickness = _cell_thickness(
            size, radius_px, height, flatness, elongation, orientation, roughness, rng
        )
        if thickness.max() <= 0:
            continue

        contrast = rng.uniform(*config.cytoplasm_contrast)
        index_map = np.full_like(thickness, contrast)

        # Nucleus: an offset, denser, thicker inner body.
        nucleus_radius = radius_px * rng.uniform(0.34, 0.52)
        cos_t, sin_t = np.cos(orientation), np.sin(orientation)
        offset_y = rng.normal(0, radius_px * 0.13)
        offset_x = rng.normal(0, radius_px * 0.13)
        coords = np.arange(size) - (size - 1) / 2.0
        gx, gy = np.meshgrid(coords, coords, indexing="xy")
        nuc_along = ((gx - offset_x) * cos_t + (gy - offset_y) * sin_t) / (
            1.0 + 0.55 * (elongation - 1.0)
        )
        nuc_across = -(gx - offset_x) * sin_t + (gy - offset_y) * cos_t
        nucleus_r = np.hypot(nuc_along, nuc_across)
        nucleus = np.clip(1.0 - (nucleus_r / max(nucleus_radius, 1e-6)) ** 2, 0.0, None) ** 0.5
        index_map += contrast * (rng.uniform(*config.nucleus_contrast_gain) - 1.0) * nucleus
        thickness = thickness * (1.0 + 0.28 * nucleus)

        # One or two nucleoli, which are the densest thing in a normal cell.
        for _ in range(rng.integers(1, 3)):
            spot_r = nucleus_radius * rng.uniform(0.14, 0.26)
            sy = offset_y + rng.normal(0, nucleus_radius * 0.34)
            sx = offset_x + rng.normal(0, nucleus_radius * 0.34)
            spot = np.clip(1.0 - (np.hypot(gx - sx, gy - sy) / max(spot_r, 1e-6)) ** 2, 0.0, None)
            index_map += contrast * 0.55 * spot

        # Internal structure, so the result is not a smooth cartoon.
        texture = _smooth_noise((size, size), sigma=max(radius_px * 0.11, 1.0), rng=rng)
        index_map *= 1.0 + config.texture_strength * texture

        cell_phase = wavenumber * index_map * thickness
        support = thickness > 1e-3

        top = int(round(centre_y - size / 2))
        left = int(round(centre_x - size / 2))
        rows, cols = _place(phase, cell_phase, top, left)
        if rows.stop - rows.start <= 0:
            centres.pop()
            continue

        _place(absorption, config.absorption_gain * cell_phase, top, left)

        local = support[
            rows.start - top : rows.stop - top,
            cols.start - left : cols.stop - left,
        ]
        label_id = index + 1
        labels[rows, cols][local] = label_id

        visible = cell_phase[
            rows.start - top : rows.stop - top,
            cols.start - left : cols.stop - left,
        ]
        cell_area = float(local.sum()) * pixel**2
        mass = float(visible[local].sum()) * optics.wavelength / (
            2.0 * np.pi * REFRACTIVE_INCREMENT
        ) * pixel**2

        records.append(
            {
                "label": label_id,
                "centroid_y": float(centre_y),
                "centroid_x": float(centre_x),
                "area_um2": cell_area,
                "mean_phase": float(visible[local].mean()) if local.any() else 0.0,
                "max_phase": float(visible.max()),
                "dry_mass_pg": mass,
                "mitotic": bool(mitotic),
            }
        )

    # Sub-cellular debris: small, dense, and a genuine nuisance for any solver.
    n_debris = rng.poisson(config.debris_density * area_um2)
    for _ in range(int(n_debris)):
        spot_radius = rng.uniform(0.4, 1.4) / pixel
        size = max(3, int(np.ceil(3 * spot_radius)) | 1)
        coords = np.arange(size) - (size - 1) / 2.0
        gx, gy = np.meshgrid(coords, coords, indexing="xy")
        blob = np.clip(1.0 - (np.hypot(gx, gy) / max(spot_radius, 1e-6)) ** 2, 0.0, None) ** 0.5
        amplitude = rng.uniform(0.35, 1.5)
        _place(
            phase,
            amplitude * blob,
            int(rng.uniform(0, shape[0])) - size // 2,
            int(rng.uniform(0, shape[1])) - size // 2,
        )

    # Slow optical drift of the medium and the coverslip.
    phase += config.background_drift * _smooth_noise(shape, sigma=min(shape) / 6.0, rng=rng)

    return Specimen(
        phase=phase,
        labels=labels,
        absorption=absorption,
        optics=optics,
        cells=records,
    )
