"""The reconstruction pipeline, end to end.

One call takes a three plane through-focus stack and returns every
reconstruction the product can produce, side by side, with timings and per-cell
measurements. Running all of them on every job rather than only the chosen one
is deliberate: a single reconstruction is a claim, and three reconstructions
that agree are evidence. Where they disagree, the user is told rather than
being handed whichever one the software preferred.

Ordering matters. The classical solver runs first because the learned model
takes its output as an input channel. The model never sees raw frames alone.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np

from velos import baseline, cells as cell_analysis, metrics, tie
from velos.camera import Camera, normalise
from velos.optics import Optics


@dataclass
class Reconstruction:
    """One method's output plus what it cost."""
    name: str
    label: str
    phase: np.ndarray
    milliseconds: float
    detail: str = ""
    scores: dict[str, float] | None = None

    def summary(self) -> dict[str, Any]:
        out = {
            "name": self.name,
            "label": self.label,
            "milliseconds": round(self.milliseconds, 1),
            "detail": self.detail,
            "range_rad": [round(float(self.phase.min()), 3), round(float(self.phase.max()), 3)],
        }
        if self.scores:
            out["scores"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.scores.items()}
        return out


@dataclass
class Result:
    optics: Optics
    measured: np.ndarray
    reconstructions: list[Reconstruction]
    disagreement: np.ndarray | None
    labels: np.ndarray
    cells: list[dict]
    truth: np.ndarray | None = None
    notes: list[str] = field(default_factory=list)

    def primary(self) -> Reconstruction:
        """The reconstruction the measurements were taken from."""
        for name in ("model", "tie", "waveorder"):
            for r in self.reconstructions:
                if r.name == name:
                    return r
        return self.reconstructions[0]

    def summary(self) -> dict[str, Any]:
        total = float(sum(c["dry_mass_pg"] for c in self.cells))
        return {
            "optics": {
                "wavelength_um": self.optics.wavelength,
                "pixel_size_um": self.optics.pixel_size,
                "na_objective": self.optics.na_objective,
                "na_illumination": self.optics.na_illumination,
                "defocus_um": self.optics.defocus,
                "resolution_um": round(self.optics.resolution, 3),
            },
            "field": {
                "pixels": list(self.measured.shape[-2:]),
                "micrometres": [round(self.measured.shape[-1] * self.optics.pixel_size, 1),
                                round(self.measured.shape[-2] * self.optics.pixel_size, 1)],
            },
            "reconstructions": [r.summary() for r in self.reconstructions],
            "primary": self.primary().name,
            "cell_count": len(self.cells),
            "total_dry_mass_pg": round(total, 1),
            "median_dry_mass_pg": round(float(np.median([c["dry_mass_pg"] for c in self.cells])), 1) if self.cells else None,
            "has_ground_truth": self.truth is not None,
            "notes": self.notes,
        }


def _time(fn) -> tuple[Any, float]:
    started = time.perf_counter()
    value = fn()
    return value, (time.perf_counter() - started) * 1000.0


def run(
    stack: np.ndarray,
    optics: Optics | None = None,
    camera: Camera | None = None,
    truth: np.ndarray | None = None,
    model=None,
    already_normalised: bool = False,
    include_waveorder: bool = True,
) -> Result:
    """Reconstruct, compare, segment and measure.

    `stack` is (3, height, width) ordered under focus, in focus, over focus.
    `model` is anything with `.predict(stack, classical) -> phase`; when absent
    the pipeline still returns both physics reconstructions, so the product
    degrades to its classical behaviour rather than failing.
    """
    optics = optics or Optics()
    notes: list[str] = []

    if stack.ndim != 3 or stack.shape[0] != 3:
        raise ValueError(f"expected a (3, h, w) through-focus stack, got {stack.shape}")

    measured = stack.astype(np.float64) if already_normalised else normalise(stack, camera)

    reconstructions: list[Reconstruction] = []

    classical, ms = _time(lambda: tie.level(tie.solve(measured, optics, method="uniform")))
    reconstructions.append(Reconstruction(
        name="tie", label="Transport of intensity", phase=classical, milliseconds=ms,
        detail="FFT Poisson inverse. Assumes weak absorption, which holds for most live cells.",
    ))

    if include_waveorder and not baseline.available():
        notes.append(
            "waveorder is not installed in this environment, so the published baseline "
            "is not shown. The classical solve and the learned refinement are unaffected."
        )
        include_waveorder = False

    if include_waveorder:
        try:
            published, ms = _time(lambda: tie.level(baseline.phase_only(measured, optics)))
            # waveorder's sign convention can come out inverted depending on how
            # the stack was acquired; trust correlation over convention.
            if metrics.correlation(classical, published) < 0:
                published = -published
                notes.append("waveorder output was sign-inverted relative to the classical solve and has been flipped.")
            reconstructions.append(Reconstruction(
                name="waveorder", label="waveorder (CZ Biohub)", phase=published, milliseconds=ms,
                detail="Published partially coherent inverse, solving absorption and phase jointly.",
            ))
        except Exception as exc:                      # pragma: no cover - defensive
            notes.append(f"waveorder baseline unavailable for this job: {type(exc).__name__}.")

    if model is not None:
        try:
            learned, ms = _time(lambda: model.predict(measured, classical))
            reconstructions.append(Reconstruction(
                name="model", label="Physics-guided refinement", phase=tie.level(learned), milliseconds=ms,
                detail="Learned correction applied on top of the classical solve, never replacing it.",
            ))
        except Exception as exc:                      # pragma: no cover - defensive
            notes.append(f"Learned model unavailable for this job: {type(exc).__name__}. Showing physics only.")

    # Where the learned correction departs from the physics, say so. This is the
    # map that answers "did the network invent that?".
    disagreement = None
    learned_map = next((r.phase for r in reconstructions if r.name == "model"), None)
    if learned_map is not None:
        disagreement = learned_map - classical

    primary = learned_map if learned_map is not None else classical
    labels, found = cell_analysis.analyse(primary, optics)

    if truth is not None:
        levelled = tie.level(truth)
        for r in reconstructions:
            r.scores = metrics.compare(levelled, r.phase, optics, labels if labels.any() else None)

    return Result(
        optics=optics, measured=measured, reconstructions=reconstructions,
        disagreement=disagreement, labels=labels, cells=found,
        truth=truth, notes=notes,
    )
