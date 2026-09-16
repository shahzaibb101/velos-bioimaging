"""Phase colormap in the Velos palette.

Scientific colormaps have to be monotonic in luminance, otherwise the eye
invents structure that is not in the data — which is exactly the failure mode a
measurement instrument cannot afford. This ramp rises steadily from black
through the brand's ink and teal into the lime accent, so it satisfies that
constraint while still reading as the product's own.
"""

from __future__ import annotations

import numpy as np

# position, #rrggbb — luminance increases monotonically across the stops
STOPS: list[tuple[float, str]] = [
    (0.00, "#000000"),
    (0.22, "#16211f"),
    (0.42, "#222f30"),
    (0.62, "#445e5f"),
    (0.82, "#a7e26e"),
    (1.00, "#cef79e"),
]


def _rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def ramp(samples: int = 256) -> np.ndarray:
    """(samples, 3) float lookup table."""
    positions = np.array([p for p, _ in STOPS])
    colours = np.array([_rgb(c) for _, c in STOPS])
    x = np.linspace(0.0, 1.0, samples)
    return np.stack([np.interp(x, positions, colours[:, i]) for i in range(3)], axis=1)


def apply(
    phase: np.ndarray,
    low: float | None = None,
    high: float | None = None,
    gamma: float = 0.85,
) -> np.ndarray:
    """Map phase in radians to uint8 RGB.

    `low`/`high` default to robust percentiles so a single bright speck cannot
    flatten the whole field, which is the usual way a phase map gets rendered
    into uselessness.
    """
    low = float(np.percentile(phase, 1.0)) if low is None else low
    high = float(np.percentile(phase, 99.6)) if high is None else high
    span = max(high - low, 1e-9)
    normalised = np.clip((phase - low) / span, 0.0, 1.0) ** gamma
    table = ramp()
    indices = np.clip((normalised * (len(table) - 1)).astype(np.int32), 0, len(table) - 1)
    return (table[indices] * 255.0 + 0.5).astype(np.uint8)
