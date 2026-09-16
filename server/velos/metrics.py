"""Scoring a reconstruction.

Image similarity scores are necessary but they are not sufficient here. A model
can post an excellent peak signal to noise ratio while getting the one number
the instrument exists to produce, the dry mass of a cell, quietly wrong. So the
per-cell mass error is reported alongside, and it is the one to argue about.
"""

from __future__ import annotations

import numpy as np
from skimage.metrics import structural_similarity

from .optics import Optics, REFRACTIVE_INCREMENT


def rmse(truth: np.ndarray, estimate: np.ndarray) -> float:
    """Root mean squared error in radians."""
    return float(np.sqrt(np.mean((truth - estimate) ** 2)))


def psnr(truth: np.ndarray, estimate: np.ndarray) -> float:
    """Peak signal to noise ratio, referenced to the true phase range."""
    peak = float(truth.max() - truth.min())
    if peak <= 0:
        return float("inf")
    error = rmse(truth, estimate)
    return float("inf") if error == 0 else float(20.0 * np.log10(peak / error))


def ssim(truth: np.ndarray, estimate: np.ndarray) -> float:
    """Structural similarity over the shared dynamic range."""
    low = float(min(truth.min(), estimate.min()))
    high = float(max(truth.max(), estimate.max()))
    span = high - low
    if span <= 0:
        return 1.0
    return float(structural_similarity(truth, estimate, data_range=span))


def correlation(truth: np.ndarray, estimate: np.ndarray) -> float:
    return float(np.corrcoef(truth.ravel(), estimate.ravel())[0, 1])


def mass_error(
    truth: np.ndarray,
    estimate: np.ndarray,
    labels: np.ndarray,
    optics: Optics,
) -> dict[str, float]:
    """Per-cell dry mass agreement, which is the measurement that matters.

    Returns the median absolute percentage error across cells and the bias,
    which says whether the method systematically under or over reports mass.
    A negative bias on a Transport of Intensity reconstruction is expected,
    because the regularisation that suppresses its low frequency noise takes
    real low frequency signal with it.
    """
    scale = optics.wavelength / (2.0 * np.pi * REFRACTIVE_INCREMENT) * optics.pixel_size**2
    identifiers = [i for i in np.unique(labels) if i != 0]
    if not identifiers:
        return {"median_abs_pct": float("nan"), "bias_pct": float("nan"), "cells": 0}

    errors = []
    for identifier in identifiers:
        mask = labels == identifier
        true_mass = float(truth[mask].sum()) * scale
        if abs(true_mass) < 1e-6:
            continue
        estimated = float(estimate[mask].sum()) * scale
        errors.append(100.0 * (estimated - true_mass) / true_mass)

    if not errors:
        return {"median_abs_pct": float("nan"), "bias_pct": float("nan"), "cells": 0}

    errors_array = np.array(errors)
    return {
        "median_abs_pct": float(np.median(np.abs(errors_array))),
        "bias_pct": float(np.median(errors_array)),
        "cells": len(errors),
    }


def compare(
    truth: np.ndarray,
    estimate: np.ndarray,
    optics: Optics,
    labels: np.ndarray | None = None,
) -> dict[str, float]:
    """Full scorecard for one reconstruction against its ground truth."""
    result = {
        "psnr_db": psnr(truth, estimate),
        "ssim": ssim(truth, estimate),
        "rmse_rad": rmse(truth, estimate),
        "correlation": correlation(truth, estimate),
    }
    if labels is not None:
        mass = mass_error(truth, estimate, labels, optics)
        result["mass_median_abs_pct"] = mass["median_abs_pct"]
        result["mass_bias_pct"] = mass["bias_pct"]
        result["mass_cells"] = mass["cells"]
    return result
