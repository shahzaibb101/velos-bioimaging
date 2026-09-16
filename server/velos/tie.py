"""The classical Transport of Intensity solver.

This is the physics baseline. It is the method the instrument would ship with
if there were no learned component at all, and the learned model has to be
measured against it rather than against nothing.

The Transport of Intensity Equation relates how the recorded intensity changes
with defocus to the lateral phase gradient of the specimen,

    dI/dz = -(1/k) * div( I * grad(phase) )

Take one image slightly above focus and one slightly below, estimate dI/dz by a
central difference, and the equation becomes a Poisson problem that an FFT
solves directly.

Two things about it are worth knowing, because they are what the learned model
is being asked to fix:

  * The inversion divides by spatial frequency squared, so it amplifies low
    frequency noise without bound. That is the origin of the slowly varying
    "cloud" that every Transport of Intensity reconstruction suffers from, and
    the regularisation that suppresses it also removes real low frequency
    signal from the specimen.
  * The derivation is for coherent illumination and a weakly absorbing object.
    A real microscope is partially coherent and a real cell absorbs a little,
    so the equation is already an approximation before any noise is added.
"""

from __future__ import annotations

import numpy as np

from .optics import Optics, frequency_grid


def _inverse_laplacian(
    source: np.ndarray,
    pixel_size: float,
    regularization: float,
) -> np.ndarray:
    """Solve the Poisson equation laplacian(u) = source by FFT.

    `regularization` is a Tikhonov term added to the denominator, expressed in
    the same units as the squared angular frequency so that it is independent of
    image size.
    """
    fx, fy = frequency_grid(source.shape, pixel_size)
    denominator = 4.0 * np.pi**2 * (fx**2 + fy**2) + regularization
    solution = np.fft.ifft2(-np.fft.fft2(source) / denominator)
    return np.real(solution)


def _gradient(field: np.ndarray, pixel_size: float) -> tuple[np.ndarray, np.ndarray]:
    """Spectral gradient, which stays consistent with the spectral Poisson solve."""
    fx, fy = frequency_grid(field.shape, pixel_size)
    spectrum = np.fft.fft2(field)
    dx = np.real(np.fft.ifft2(spectrum * 2j * np.pi * fx))
    dy = np.real(np.fft.ifft2(spectrum * 2j * np.pi * fy))
    return dx, dy


def _divergence(vx: np.ndarray, vy: np.ndarray, pixel_size: float) -> np.ndarray:
    fx, fy = frequency_grid(vx.shape, pixel_size)
    return np.real(
        np.fft.ifft2(np.fft.fft2(vx) * 2j * np.pi * fx)
        + np.fft.ifft2(np.fft.fft2(vy) * 2j * np.pi * fy)
    )


def solve(
    stack: np.ndarray,
    optics: Optics,
    regularization: float = 5.0e-3,
    method: str = "teague",
    intensity_floor: float = 0.06,
) -> np.ndarray:
    """Recover phase in radians from a three plane through-focus stack.

    `stack` is ordered (under focus, in focus, over focus).

    `method` is either "uniform", which assumes the in-focus intensity is flat
    and needs a single Poisson solve, or "teague", which keeps the measured
    intensity and needs two. Teague's form is the fairer baseline on a specimen
    that absorbs at all, so it is the default.
    """
    if stack.shape[0] != 3:
        raise ValueError("Transport of Intensity needs exactly three planes")

    under, focus, over = stack.astype(np.float64)
    pixel = optics.pixel_size
    wavenumber = 2.0 * np.pi * optics.n_medium / optics.wavelength

    dI_dz = (over - under) / (2.0 * optics.defocus)

    if method == "uniform":
        background = float(np.percentile(focus, 95))
        source = -wavenumber * dI_dz / max(background, 1e-9)
        return _inverse_laplacian(source, pixel, regularization)

    if method != "teague":
        raise ValueError(f"unknown method: {method!r}")

    # Teague's auxiliary function: solve for a potential, divide its gradient by
    # the measured intensity, then solve once more.
    auxiliary = _inverse_laplacian(-wavenumber * dI_dz, pixel, regularization)
    aux_dx, aux_dy = _gradient(auxiliary, pixel)

    safe_intensity = np.maximum(focus, intensity_floor * float(np.percentile(focus, 95)))
    source = _divergence(aux_dx / safe_intensity, aux_dy / safe_intensity, pixel)
    return _inverse_laplacian(source, pixel, regularization)


def level(phase: np.ndarray, percentile: float = 12.0, order: int = 2) -> np.ndarray:
    """Remove the slowly varying background from a phase map.

    Every phase imaging pipeline does some version of this, because the absolute
    phase offset is not observable and because the coverslip and the medium
    contribute a smooth tilt. Fitting only to the background pixels keeps the
    cells from dragging the surface upward.

    Applied identically to the classical and the learned reconstruction, so the
    comparison between them stays honest.
    """
    ny, nx = phase.shape
    y, x = np.mgrid[0:ny, 0:nx].astype(np.float64)
    y = (y - ny / 2) / max(ny, 1)
    x = (x - nx / 2) / max(nx, 1)

    threshold = np.percentile(phase, percentile)
    background = phase <= threshold
    if background.sum() < 64:
        background = np.ones_like(phase, dtype=bool)

    terms = [np.ones_like(x)]
    for total in range(1, order + 1):
        for power_x in range(total + 1):
            terms.append(x**power_x * y ** (total - power_x))
    design = np.stack([t[background] for t in terms], axis=1)

    coefficients, *_ = np.linalg.lstsq(design, phase[background], rcond=None)
    surface = sum(c * t for c, t in zip(coefficients, terms))
    return phase - surface
