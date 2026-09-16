"""Serving the phase refinement network.

Two things here are worth more than the rest of the file.

Tiling. The network was trained on 256 pixel crops but a microscope field is
whatever the camera is. Running a convolutional network over a much larger
input than it was trained on changes the statistics its normalisation layers
see, so inference is tiled at the training size. Tiles are blended with a raised
cosine window rather than butted together, because a hard join leaves a seam,
and a seam in a phase map is a step in optical path length that will be
integrated into a cell's dry mass and reported as real material.

Runtime. Training happens in PyTorch; serving prefers ONNX Runtime, which is
substantially faster on CPU and does not pull a deep learning framework into
the container. The torch path is kept as a fallback so the service still works
from a raw checkpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _window(size: int, overlap: int) -> np.ndarray:
    """Raised cosine ramp over the overlap region, flat elsewhere."""
    w = np.ones(size, dtype=np.float32)
    if overlap > 0:
        ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, overlap, dtype=np.float32)))
        w[:overlap] = ramp
        w[-overlap:] = ramp[::-1]
    return w


class PhaseModel:
    """Loads a trained refiner and applies it to arbitrary sized fields."""

    def __init__(self, path: str | Path, tile: int = 256, overlap: int = 64):
        self.path = Path(path)
        self.tile = tile
        self.overlap = overlap
        self.runtime = "none"
        self._session = None
        self._torch_model = None
        self.card: dict = {}

        card_path = self.path.parent / "model-card.json"
        if card_path.exists():
            self.card = json.loads(card_path.read_text())

        if self.path.suffix == ".onnx":
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = ort.InferenceSession(str(self.path), options, providers=["CPUExecutionProvider"])
            self.runtime = "onnxruntime"
        else:
            import torch
            from velos.training.model import PhaseRefiner
            blob = torch.load(self.path, map_location="cpu")
            model = PhaseRefiner(base=blob.get("base", 24), in_channels=blob.get("in_channels", 4))
            model.load_state_dict(blob["state_dict"])
            model.eval()
            torch.set_grad_enabled(False)
            self._torch_model = model
            self.runtime = "torch-cpu"

    # ------------------------------------------------------------------ infer

    def _forward(self, batch: np.ndarray) -> np.ndarray:
        """(n, 4, h, w) float32 in, (n, 1, h, w) out."""
        if self._session is not None:
            name = self._session.get_inputs()[0].name
            return self._session.run(None, {name: batch})[0]
        import torch
        with torch.no_grad():
            return self._torch_model(torch.from_numpy(batch)).numpy()

    def predict(self, measured: np.ndarray, classical: np.ndarray) -> np.ndarray:
        """Refine `classical` using the three camera planes that produced it."""
        stack = np.concatenate(
            [measured.astype(np.float32), classical.astype(np.float32)[None]], axis=0
        )[None]                                            # (1, 4, h, w)

        _, _, height, width = stack.shape
        tile, overlap = self.tile, self.overlap
        if height <= tile and width <= tile:
            padded, (ph, pw) = self._pad_to(stack, tile)
            out = self._forward(padded)[0, 0]
            return out[:height, :width].astype(np.float64)

        step = tile - overlap
        accum = np.zeros((height, width), np.float32)
        weight = np.zeros((height, width), np.float32)
        window = np.outer(_window(tile, overlap), _window(tile, overlap))

        for top in range(0, max(height - overlap, 1), step):
            for left in range(0, max(width - overlap, 1), step):
                t = min(top, max(height - tile, 0))
                l = min(left, max(width - tile, 0))
                patch = stack[:, :, t : t + tile, l : l + tile]
                padded, _ = self._pad_to(patch, tile)
                out = self._forward(padded)[0, 0]
                h = min(tile, height - t)
                w = min(tile, width - l)
                accum[t : t + h, l : l + w] += out[:h, :w] * window[:h, :w]
                weight[t : t + h, l : l + w] += window[:h, :w]

        # Anywhere the tiling did not reach, fall back to the physics rather
        # than dividing by zero and emitting NaN into a measurement.
        gap = weight <= 1e-6
        result = np.where(gap, classical.astype(np.float32), accum / np.maximum(weight, 1e-6))
        return result.astype(np.float64)

    @staticmethod
    def _pad_to(batch: np.ndarray, size: int) -> tuple[np.ndarray, tuple[int, int]]:
        _, _, h, w = batch.shape
        ph, pw = max(size - h, 0), max(size - w, 0)
        if ph or pw:
            batch = np.pad(batch, ((0, 0), (0, 0), (0, ph), (0, pw)), mode="reflect")
        return np.ascontiguousarray(batch, dtype=np.float32), (ph, pw)


def load(directory: str | Path = "models") -> PhaseModel | None:
    """Find a servable model, preferring ONNX. Returns None if there is none."""
    directory = Path(directory)
    for name in ("phase_refiner.onnx", "phase_refiner.pt"):
        candidate = directory / name
        if candidate.exists():
            try:
                return PhaseModel(candidate)
            except Exception:
                continue
    return None
