"""Sensor model for a scientific CMOS camera.

Reconstruction quality on a real instrument is set by photon budget, not by the
algorithm. A live cell can only absorb so much light before the illumination
itself starts to damage it, so a label-free system is always working at lower
exposure than it would like. Simulating that honestly is the difference between
a model that works on clean synthetic data and one that survives contact with a
real camera.

Modelled here, in the order the photons meet them:

  * shot noise, which is Poisson and therefore signal dependent
  * pixel response non-uniformity, the fixed multiplicative pattern of a sensor
  * dark offset and read noise, which dominate when the signal is weak
  * uneven illumination across the field, which no condenser fully avoids
  * discretisation to sixteen bit integers
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class Camera:
    """Sensor and exposure parameters."""

    photons: float = 6000.0          # mean photoelectrons per pixel in the background
    read_noise: float = 1.6          # electrons rms
    dark_offset: float = 100.0       # digital counts
    gain: float = 0.5                # electrons per digital count
    response_spread: float = 0.006   # pixel response non-uniformity, fractional
    illumination_spread: float = 0.05  # slow shading across the field
    bit_depth: int = 16

    @staticmethod
    def preset(name: str) -> "Camera":
        """Named exposure conditions.

        `low_light` is the interesting one. It is what the instrument actually
        runs at when the biologist wants to image the same cells every two
        minutes for a day without killing them.
        """
        if name == "bright":
            return Camera(photons=18000.0)
        if name == "standard":
            return Camera()
        if name == "low_light":
            return Camera(photons=650.0)
        if name == "very_low_light":
            return Camera(photons=180.0)
        raise ValueError(f"unknown camera preset: {name!r}")


def expose(
    intensity: np.ndarray,
    camera: Camera | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Turn noiseless relative intensity into digital counts.

    Input is normalised so that an empty field reads 1.0. Output is float valued
    digital counts, quantised but not cast, so that downstream code can keep
    working in floating point without a second rounding step.
    """
    camera = camera or Camera()
    rng = rng or np.random.default_rng()

    shape = intensity.shape[-2:]

    # Illumination shading is fixed for the acquisition, not per frame, so it is
    # generated once and applied to every plane in the stack.
    shading = 1.0 + camera.illumination_spread * ndimage.gaussian_filter(
        rng.normal(size=shape), sigma=min(shape) / 5.0, mode="reflect"
    ) / 0.12
    response = 1.0 + camera.response_spread * rng.normal(size=shape)

    electrons = np.clip(intensity, 0.0, None) * camera.photons * shading * response
    detected = rng.poisson(np.clip(electrons, 0.0, None)).astype(np.float64)
    detected += rng.normal(0.0, camera.read_noise, size=detected.shape)

    counts = detected / camera.gain + camera.dark_offset
    saturation = 2**camera.bit_depth - 1
    return np.clip(np.round(counts), 0.0, saturation)


def normalise(counts: np.ndarray, camera: Camera | None = None) -> np.ndarray:
    """Undo the offset and put the stack back on the "empty field reads 1.0" scale.

    This is the only preprocessing the solver and the network both receive, and
    it is deliberately something the instrument can do without knowing anything
    about the specimen.
    """
    camera = camera or Camera()
    signal = np.clip(counts.astype(np.float64) - camera.dark_offset, 0.0, None)
    reference = np.percentile(signal[signal.shape[0] // 2] if signal.ndim == 3 else signal, 95)
    return signal / max(float(reference), 1e-9)
