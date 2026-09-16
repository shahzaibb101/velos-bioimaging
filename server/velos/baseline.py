"""The published physics baseline: waveorder's phase-from-defocus reconstruction.

waveorder is the label-agnostic computational microscopy framework from the
Chan Zuckerberg Biohub (BSD-3-Clause, Chandler et al. 2024). Its
`isotropic_thin_3d` model recovers absorption and phase jointly from a
through-focus intensity stack, using a partially coherent transfer function and
a singular-system inverse. That is a considerably more careful instrument model
than the Poisson-solver Transport of Intensity in `velos.tie`, and it is
published and citable, so it is the baseline this product measures itself
against.

One thing is worth knowing before using it, because it is not obvious from the
API and it cost an afternoon to find. The default `regularization_strength` of
1e-3 is tuned for noisy experimental data and badly over-smooths anything
cleaner. On waveorder's own noiseless test phantom the default scores a
correlation of 0.469, while 1e-7 scores 0.999 and recovers the correct absolute
scale. The right value depends on the photon budget, so `regularisation_for`
picks one from the measured shot-noise level rather than using a constant.
"""

from __future__ import annotations

import numpy as np

from .optics import Optics


def _thin_model():
    """Import waveorder on first use, not at module import.

    waveorder is built on PyTorch. Importing it at module scope makes torch a
    hard requirement of the whole service, which would mean a container that
    serves an ONNX model still has to carry a deep learning framework just to
    start up. Deferring it means an environment without waveorder loses the
    published baseline and keeps everything else, which is the correct way for
    an optional comparison to fail.
    """
    from waveorder.models import isotropic_thin_3d as thin
    return thin


def available() -> bool:
    try:
        _thin_model()
        return True
    except Exception:
        return False


def regularisation_for(stack: np.ndarray, floor: float = 2e-6, ceiling: float = 4e-3) -> float:
    """Pick a Tikhonov strength from the noise actually present in the stack.

    The noise estimate is the spread of the difference between the two
    defocused planes over background pixels. The specimen signal is largely
    common to both planes, so what survives the subtraction is dominated by
    shot noise.

    The mapping from that estimate to a regularisation strength was fitted
    rather than guessed. Sweeping eight strengths against ground truth at four
    exposures spanning a hundredfold in photon count gave

        regularisation = 0.39 * noise ** 2.56

    which lands within a factor of 1.3 of the per-exposure optimum at every
    point. Tikhonov theory would suggest an exponent of 2, scaling with noise
    power; the measured exponent is a little steeper, which is why this is
    fitted and not derived.

    Note what this fixes. waveorder's own default is 1e-3, roughly two orders
    of magnitude too strong for a well exposed stack, and using it costs about
    0.3 in correlation.
    """
    difference = stack[2] - stack[0]
    background = difference[np.abs(difference) < np.percentile(np.abs(difference), 70)]
    noise = float(background.std()) if background.size else float(difference.std())
    return float(np.clip(0.3886 * noise**2.562, floor, ceiling))


def reconstruct(
    stack: np.ndarray,
    optics: Optics,
    regularization: float | None = None,
    algorithm: str = "Tikhonov",
) -> tuple[np.ndarray, np.ndarray]:
    """Recover (absorption, phase) in radians from a three plane stack.

    `stack` is ordered (under focus, in focus, over focus) and normalised so an
    empty field reads about 1.0, which is what `velos.camera.normalise` returns.
    """
    if stack.shape[0] != 3:
        raise ValueError("phase from defocus needs exactly three planes")

    import torch

    strength = regularisation_for(stack) if regularization is None else regularization

    absorption, phase = _thin_model().reconstruct(
        zyx_data=torch.from_numpy(np.ascontiguousarray(stack)).float(),
        yx_pixel_size=optics.pixel_size,
        z_position_list=[-optics.defocus, 0.0, optics.defocus],
        wavelength_illumination=optics.wavelength,
        index_of_refraction_media=optics.n_medium,
        numerical_aperture_illumination=optics.na_illumination,
        numerical_aperture_detection=optics.na_objective,
        reconstruction_algorithm=algorithm,
        regularization_strength=strength,
    )
    return absorption.numpy().astype(np.float64), phase.numpy().astype(np.float64)


def phase_only(stack: np.ndarray, optics: Optics, regularization: float | None = None) -> np.ndarray:
    return reconstruct(stack, optics, regularization)[1]
