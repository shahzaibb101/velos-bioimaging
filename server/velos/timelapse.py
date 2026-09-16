"""Time-lapse specimens: the same cells, imaged repeatedly.

A single reconstructed frame proves the optics work. A time-lapse proves the
instrument is worth owning, because watching one unstained cell accumulate mass
over hours without ever touching it is the thing fluorescence cannot do.

The sequence is built to loop seamlessly: every per-cell parameter is driven by
a sinusoid over the frame index, so the last frame returns to the first. That
lets the hero play continuously without a visible cut.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .optics import Optics
from .phantom import SpecimenConfig, _cell_thickness, _place, _smooth_noise


@dataclass
class Track:
    """One cell followed across the sequence."""
    y: float
    x: float
    radius: float
    height: float
    flatness: float
    elongation: float
    orientation: float
    roughness: float
    contrast: float
    drift: tuple[float, float]
    growth: float
    phase_offset: float
    seed: int


def plan(shape: tuple[int, int], optics: Optics, config: SpecimenConfig | None = None,
         seed: int | None = None) -> list[Track]:
    config = config or SpecimenConfig()
    rng = np.random.default_rng(seed)
    pixel = optics.pixel_size
    area = shape[0] * shape[1] * pixel**2
    n = max(1, rng.poisson(config.density * area))

    tracks: list[Track] = []
    placed: list[tuple[float, float, float]] = []
    for _ in range(n):
        radius = rng.uniform(*config.radius_range)
        radius_px = radius / pixel
        y, x = rng.uniform(0, shape[0]), rng.uniform(0, shape[1])
        elong = rng.uniform(1.0, 2.9)
        if any(np.hypot(y - cy, x - cx) < 0.72 * (radius_px * elong + r) for cy, cx, r in placed):
            continue
        placed.append((y, x, radius_px))
        tracks.append(Track(
            y=y, x=x, radius=radius,
            height=rng.uniform(*config.thickness_range),
            flatness=rng.uniform(0.22, 0.38),
            elongation=elong,
            orientation=rng.uniform(0, np.pi),
            roughness=rng.uniform(0.75, 1.15),
            contrast=rng.uniform(*config.cytoplasm_contrast),
            drift=(rng.uniform(-7.0, 7.0), rng.uniform(-7.0, 7.0)),
            growth=rng.uniform(0.18, 0.48),
            phase_offset=rng.uniform(0, 2 * np.pi),
            seed=int(rng.integers(0, 2**31)),
        ))
    return tracks


def frame(tracks: list[Track], shape: tuple[int, int], optics: Optics, t: float,
          background_drift: float = 0.035) -> np.ndarray:
    """Render the true phase of the culture at loop position `t` in [0, 1)."""
    pixel = optics.pixel_size
    wavenumber = 2.0 * np.pi / optics.wavelength
    phase = np.zeros(shape, dtype=np.float64)
    angle = 2.0 * np.pi * t

    for track in tracks:
        rng = np.random.default_rng(track.seed)   # same shape every frame
        # Mass accumulates and returns, so the loop closes.
        swell = 1.0 + track.growth * (1.0 - np.cos(angle + track.phase_offset)) / 2.0
        cy = track.y + track.drift[0] * np.sin(angle + track.phase_offset)
        cx = track.x + track.drift[1] * np.sin(angle + track.phase_offset * 1.3)

        radius_px = (track.radius / pixel) * (1.0 + 0.04 * (swell - 1.0) * 10)
        size = int(np.ceil(2.2 * radius_px * max(track.elongation, 1.0) * 1.35)) | 1
        thickness = _cell_thickness(size, radius_px, track.height * swell, track.flatness,
                                    track.elongation, track.orientation, track.roughness, rng)
        if thickness.max() <= 0:
            continue

        coords = np.arange(size) - (size - 1) / 2.0
        gx, gy = np.meshgrid(coords, coords, indexing="xy")
        cos_t, sin_t = np.cos(track.orientation), np.sin(track.orientation)
        nucleus_radius = radius_px * 0.42
        na = (gx * cos_t + gy * sin_t) / (1.0 + 0.55 * (track.elongation - 1.0))
        nb = -gx * sin_t + gy * cos_t
        nucleus = np.clip(1.0 - (np.hypot(na, nb) / max(nucleus_radius, 1e-6)) ** 2, 0.0, None) ** 0.5

        index_map = track.contrast * (1.0 + 0.45 * nucleus)
        index_map *= 1.0 + 0.16 * _smooth_noise((size, size), max(radius_px * 0.11, 1.0), rng)
        thickness = thickness * (1.0 + 0.28 * nucleus)

        _place(phase, wavenumber * index_map * thickness,
               int(round(cy - size / 2)), int(round(cx - size / 2)))

    phase += background_drift * _smooth_noise(shape, min(shape) / 6.0, np.random.default_rng(7))
    return phase
