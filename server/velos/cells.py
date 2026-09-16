"""Finding individual cells in a phase map and measuring them.

This is the step where the reconstruction stops being an image and becomes a
measurement. The quantity of interest is dry mass, which follows from phase by a
constant, so once cells are separated from each other the biology falls out:
how much material each cell carries, and how that changes over time.

Segmentation here is deliberately classical, a threshold followed by a distance
transform and a watershed. Nothing is learned. That keeps the one learned
component in the pipeline confined to the reconstruction itself, so when a
result looks wrong there is only one place it can have come from.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from skimage import measure, morphology, segmentation
from skimage.feature import peak_local_max

from .optics import Optics, REFRACTIVE_INCREMENT


@dataclass(frozen=True)
class SegmentationConfig:
    min_area_um2: float = 28.0        # below this it is debris, not a cell
    max_area_um2: float = 2600.0      # above this it is a clump that failed to split
    threshold_sigma: float = 4.0      # background noise multiples
    min_phase: float = 0.12           # radians, a floor independent of noise
    smoothing_um: float = 0.8
    peak_separation_um: float = 6.0   # closest two nuclei may be and still split


def _drop_small(labels: np.ndarray, min_pixels: int) -> np.ndarray:
    """Remove labelled regions below a pixel count.

    Written out rather than taken from scikit-image, whose `remove_small_objects`
    changed both its parameter name and its comparison from strictly-smaller to
    smaller-or-equal in 0.26. Pinning behaviour that the segmentation depends on
    is worth six lines.
    """
    counts = np.bincount(labels.ravel())
    too_small = np.flatnonzero(counts < min_pixels)
    if too_small.size:
        labels = np.where(np.isin(labels, too_small), 0, labels)
    return labels


def _background_scale(phase: np.ndarray) -> float:
    """Robust noise estimate from the lower half of the histogram.

    The median absolute deviation is used rather than a standard deviation
    because most of a confluent field is cells, and cells would otherwise
    inflate the estimate of how noisy the background is.
    """
    low = phase[phase <= np.percentile(phase, 50)]
    if low.size == 0:
        return float(phase.std())
    deviation = np.median(np.abs(low - np.median(low)))
    return float(1.4826 * deviation)


def segment(
    phase: np.ndarray,
    optics: Optics,
    config: SegmentationConfig | None = None,
) -> np.ndarray:
    """Split a phase map into labelled single cells."""
    config = config or SegmentationConfig()
    pixel_area = optics.pixel_size**2

    smoothed = ndimage.gaussian_filter(phase, sigma=config.smoothing_um / optics.pixel_size)

    threshold = max(config.threshold_sigma * _background_scale(phase), config.min_phase)
    mask = smoothed > threshold

    min_pixels = max(int(config.min_area_um2 / pixel_area), 1)
    components, _ = ndimage.label(mask)
    mask = _drop_small(components, min_pixels) > 0
    mask = ndimage.binary_fill_holes(mask)
    mask = morphology.opening(mask, morphology.disk(2))

    if not mask.any():
        return np.zeros_like(phase, dtype=np.int32)

    # Touching cells share a boundary in the mask. The distance transform peaks
    # once per cell body, which gives the watershed one seed per cell.
    distance = ndimage.distance_transform_edt(mask)
    separation = max(int(config.peak_separation_um / optics.pixel_size), 3)
    coordinates = peak_local_max(
        distance, min_distance=separation, labels=mask, exclude_border=False
    )
    markers = np.zeros_like(distance, dtype=np.int32)
    for index, (row, column) in enumerate(coordinates, start=1):
        markers[row, column] = index

    if markers.max() == 0:
        markers, _ = ndimage.label(mask)

    labels = segmentation.watershed(-distance, markers, mask=mask)
    return _drop_small(labels, min_pixels).astype(np.int32)


def measure_cells(
    phase: np.ndarray,
    labels: np.ndarray,
    optics: Optics,
    config: SegmentationConfig | None = None,
) -> list[dict]:
    """Per-cell measurements in physical units.

    Dry mass is the integral of phase over the cell, converted by the specific
    refractive increment of protein. `rounded` flags a compact, optically dense
    cell, which is the morphology of a cell that has detached to divide. It is a
    shape observation and not a confirmation of mitosis, which is why it is not
    named as one.
    """
    config = config or SegmentationConfig()
    pixel_area = optics.pixel_size**2
    mass_scale = optics.wavelength / (2.0 * np.pi * REFRACTIVE_INCREMENT) * pixel_area

    records: list[dict] = []
    for region in measure.regionprops(labels, intensity_image=phase):
        area = region.area * pixel_area
        if area < config.min_area_um2 or area > config.max_area_um2:
            continue

        values = phase[tuple(region.coords.T)]
        perimeter = max(region.perimeter * optics.pixel_size, 1e-6)
        circularity = float(min(4.0 * np.pi * area / perimeter**2, 1.0))
        mean_phase = float(values.mean())

        records.append(
            {
                "label": int(region.label),
                "centroid_x_um": float(region.centroid[1] * optics.pixel_size),
                "centroid_y_um": float(region.centroid[0] * optics.pixel_size),
                "area_um2": float(area),
                "mean_phase_rad": mean_phase,
                "max_phase_rad": float(values.max()),
                "dry_mass_pg": float(values.sum()) * mass_scale,
                "circularity": circularity,
                "rounded": bool(circularity > 0.82 and mean_phase > 1.1),
            }
        )

    records.sort(key=lambda record: record["dry_mass_pg"], reverse=True)
    return records


def analyse(
    phase: np.ndarray,
    optics: Optics,
    config: SegmentationConfig | None = None,
) -> tuple[np.ndarray, list[dict]]:
    """Segment and measure in one call."""
    labels = segment(phase, optics, config)
    return labels, measure_cells(phase, labels, optics, config)
