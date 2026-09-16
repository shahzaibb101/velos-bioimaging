"""Forward model for a partially coherent transmission microscope.

Everything in this module works in object space and in micrometres. Spatial
frequencies are cycles per micrometre.

The model is the standard Abbe (source-point summation) picture of partially
coherent imaging:

    for every point in the condenser aperture
        a tilted plane wave illuminates the specimen
        the transmitted field is low-pass filtered by the objective pupil
        the pupil carries a defocus phase when the camera is not at focus
        the detector records the squared modulus

    the detector sums those intensities incoherently over the source

That summation is what makes a real microscope image differ from a textbook
coherent one, and it is also the reason the classical Transport of Intensity
solver in `velos.tie` can only ever be an approximation of this data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

# Specific refractive increment of protein, in cubic micrometres per picogram.
# This is the constant that turns an optical path length into a dry mass, and it
# is the reason phase imaging is called *quantitative*.
REFRACTIVE_INCREMENT = 0.19


@dataclass(frozen=True)
class Optics:
    """Geometry and illumination of the simulated instrument."""

    wavelength: float = 0.532          # micrometres, green LED
    pixel_size: float = 0.325          # micrometres in object space (20x onto 6.5um sCMOS)
    na_objective: float = 0.40         # 20x air objective
    na_illumination: float = 0.12      # condenser, kept low for phase contrast
    n_medium: float = 1.334            # aqueous culture medium
    defocus: float = 1.5               # micrometres, the +/- of the through-focus stack
    source_points: int = 13            # condenser samples; higher is slower and more faithful

    @property
    def coherence_ratio(self) -> float:
        """Partial coherence factor, conventionally sigma = NA_illum / NA_obj."""
        return self.na_illumination / self.na_objective

    @property
    def cutoff_frequency(self) -> float:
        """Incoherent diffraction limit, cycles per micrometre."""
        return (self.na_objective + self.na_illumination) / self.wavelength

    @property
    def resolution(self) -> float:
        """Smallest resolvable period in micrometres."""
        return 1.0 / self.cutoff_frequency

    def with_defocus(self, defocus: float) -> "Optics":
        return replace(self, defocus=defocus)


def frequency_grid(shape: tuple[int, int], pixel_size: float) -> tuple[np.ndarray, np.ndarray]:
    """Spatial frequency coordinates in cycles per micrometre, FFT ordered."""
    ny, nx = shape
    fy = np.fft.fftfreq(ny, d=pixel_size)
    fx = np.fft.fftfreq(nx, d=pixel_size)
    return np.meshgrid(fx, fy, indexing="xy")


def spatial_grid(shape: tuple[int, int], pixel_size: float) -> tuple[np.ndarray, np.ndarray]:
    """Real space coordinates in micrometres, centred on the field."""
    ny, nx = shape
    y = (np.arange(ny) - ny / 2) * pixel_size
    x = (np.arange(nx) - nx / 2) * pixel_size
    return np.meshgrid(x, y, indexing="xy")


def objective_pupil(shape: tuple[int, int], optics: Optics) -> np.ndarray:
    """Binary transfer support of the objective lens."""
    fx, fy = frequency_grid(shape, optics.pixel_size)
    return (np.hypot(fx, fy) <= optics.na_objective / optics.wavelength).astype(np.float64)


def defocus_kernel(shape: tuple[int, int], optics: Optics, distance: float) -> np.ndarray:
    """Exact angular spectrum propagation phase over `distance` micrometres.

    Evanescent components are discarded. In practice the objective pupil cuts
    the spectrum far below that limit, so this only matters for robustness.
    """
    fx, fy = frequency_grid(shape, optics.pixel_size)
    k_index = optics.n_medium / optics.wavelength
    under_root = k_index**2 - fx**2 - fy**2
    propagating = under_root > 0
    kz = np.zeros_like(under_root)
    kz[propagating] = np.sqrt(under_root[propagating])
    return np.where(propagating, np.exp(2j * np.pi * distance * kz), 0.0)


def condenser_samples(optics: Optics) -> np.ndarray:
    """Illumination directions sampled over the condenser aperture.

    Returns an (n, 2) array of (fx, fy) in cycles per micrometre. A sunflower
    spiral is used so that a modest number of points still covers the disc
    evenly, which matters because every extra point costs a pair of FFTs.
    """
    n = max(1, optics.source_points)
    if n == 1:
        return np.zeros((1, 2))

    radius_max = optics.na_illumination / optics.wavelength
    golden = np.pi * (3.0 - np.sqrt(5.0))
    index = np.arange(n)
    radius = radius_max * np.sqrt((index + 0.5) / n)
    angle = index * golden
    return np.stack([radius * np.cos(angle), radius * np.sin(angle)], axis=1)


def transmittance(phase: np.ndarray, absorption: np.ndarray | None = None) -> np.ndarray:
    """Complex transmission function of a thin specimen.

    `absorption` is an optical density map. Cells are close to pure phase
    objects but not exactly, and leaving a little amplitude in makes the
    classical solver's weak-absorption assumption imperfect in the same way it
    is imperfect on real data.
    """
    amplitude = 1.0 if absorption is None else np.exp(-0.5 * absorption)
    return amplitude * np.exp(1j * phase)


def image_at_planes(
    phase: np.ndarray,
    optics: Optics,
    planes: tuple[float, ...],
    absorption: np.ndarray | None = None,
) -> np.ndarray:
    """Noiseless partially coherent intensities at the given defocus planes.

    Returns an array of shape (len(planes), ny, nx), normalised so that an
    empty field reads 1.0.
    """
    shape = phase.shape
    obj = transmittance(phase, absorption)
    pupil = objective_pupil(shape, optics)
    x, y = spatial_grid(shape, optics.pixel_size)

    kernels = [pupil * defocus_kernel(shape, optics, z) for z in planes]
    stack = np.zeros((len(planes), *shape), dtype=np.float64)

    sources = condenser_samples(optics)
    for source_fx, source_fy in sources:
        tilt = np.exp(2j * np.pi * (source_fx * x + source_fy * y))
        spectrum = np.fft.fft2(obj * tilt)
        for index, kernel in enumerate(kernels):
            field = np.fft.ifft2(spectrum * kernel)
            stack[index] += np.abs(field) ** 2

    stack /= len(sources)

    # Normalise on the background rather than the mean, so that a densely
    # populated field and a sparse one are on the same intensity scale.
    background = np.percentile(stack[len(planes) // 2], 95)
    if background > 0:
        stack /= background
    return stack


def through_focus_stack(
    phase: np.ndarray,
    optics: Optics,
    absorption: np.ndarray | None = None,
) -> np.ndarray:
    """The three plane acquisition the Transport of Intensity method needs."""
    planes = (-optics.defocus, 0.0, optics.defocus)
    return image_at_planes(phase, optics, planes, absorption)


def phase_to_dry_mass_density(phase: np.ndarray, wavelength: float) -> np.ndarray:
    """Convert phase in radians to dry mass surface density in pg per square micrometre."""
    return phase * wavelength / (2.0 * np.pi * REFRACTIVE_INCREMENT)


def dry_mass(phase: np.ndarray, optics: Optics, mask: np.ndarray | None = None) -> float:
    """Total dry mass in picograms over `mask`, or over the whole field."""
    density = phase_to_dry_mass_density(phase, optics.wavelength)
    if mask is not None:
        density = density * mask
    return float(density.sum() * optics.pixel_size**2)
