"""Turning arrays into pictures the browser can show.

Display choices here are measurement decisions, not styling. Every phase layer
in a job is rendered against the *same* limits, because two phase maps shown
side by side with independent autoscaling will look similar no matter how
different their values are, which defeats the entire purpose of comparing them.
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from velos import colormap

# Diverging ramp for the model-minus-physics map. Zero has to be the neutral
# midpoint or the eye reads a bias that is not there.
_DIVERGING = [
    (0.00, "#7fd4ff"), (0.25, "#2b6f8f"), (0.50, "#101617"),
    (0.75, "#8fae55"), (1.00, "#cef79e"),
]


def _ramp(stops: list[tuple[float, str]], samples: int = 256) -> np.ndarray:
    positions = np.array([p for p, _ in stops])
    colours = np.array([
        tuple(int(c.lstrip("#")[i : i + 2], 16) / 255.0 for i in (0, 2, 4)) for _, c in stops
    ])
    x = np.linspace(0, 1, samples)
    return np.stack([np.interp(x, positions, colours[:, i]) for i in range(3)], axis=1)


def _encode(rgb: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(rgb).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def phase_png(phase: np.ndarray, low: float, high: float) -> bytes:
    return _encode(colormap.apply(phase, low, high))


def intensity_png(plane: np.ndarray) -> bytes:
    """A camera frame, shown as the camera saw it.

    Deliberately greyscale and near-flat. This is the point of the product: the
    raw frame genuinely looks like almost nothing, and dressing it up would
    misrepresent how little is visible before reconstruction.
    """
    low, high = np.percentile(plane, [0.5, 99.5])
    norm = np.clip((plane - low) / max(high - low, 1e-9), 0, 1)
    grey = (norm * 255 + 0.5).astype(np.uint8)
    return _encode(np.stack([grey] * 3, axis=-1))


def disagreement_png(delta: np.ndarray, limit: float | None = None) -> bytes:
    """Model minus physics, on a symmetric diverging scale centred at zero."""
    limit = limit or float(np.percentile(np.abs(delta), 99.0)) or 1e-6
    norm = np.clip(delta / (2 * limit) + 0.5, 0, 1)
    table = _ramp(_DIVERGING)
    idx = np.clip((norm * (len(table) - 1)).astype(np.int32), 0, len(table) - 1)
    return _encode((table[idx] * 255 + 0.5).astype(np.uint8))


def outlines_png(phase: np.ndarray, labels: np.ndarray, low: float, high: float) -> bytes:
    """Phase with segmented cell boundaries drawn in the accent colour."""
    rgb = colormap.apply(phase, low, high)
    edge = np.zeros(labels.shape, bool)
    edge[:-1, :] |= labels[:-1, :] != labels[1:, :]
    edge[:, :-1] |= labels[:, :-1] != labels[:, 1:]
    edge &= labels > 0
    rgb[edge] = (206, 247, 158)
    return _encode(rgb)


def display_limits(layers: list[np.ndarray]) -> tuple[float, float]:
    """One pair of limits for every phase layer in a job."""
    pooled = np.concatenate([layer.ravel() for layer in layers])
    return float(np.percentile(pooled, 1.0)), float(np.percentile(pooled, 99.6))
