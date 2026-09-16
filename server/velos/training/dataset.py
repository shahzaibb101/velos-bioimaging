"""Torch dataset over the pre-generated fields.

The generated file holds whole 512 pixel fields. Training happens on random
crops of them, which is both an augmentation and a necessity, since the network
has to work on arbitrary image sizes at inference and must not learn anything
that depends on the field being a particular size.

Only transverse symmetries are used for augmentation. Flips and quarter turns
are genuine symmetries of this instrument, because the pupil and the condenser
are both circular, so a rotated specimen produces exactly the rotated image.
Anything that changes the sign of the defocus is deliberately left out, since
that would teach the model specimens that are optically thinner than the medium
they sit in, which is not what it will be asked to measure.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class PhaseFields(Dataset):
    """Yields (input, target, measured) triples.

    input     (4, h, w)  three camera planes then the classical reconstruction
    target    (1, h, w)  true phase in radians
    measured  (3, h, w)  the camera planes alone, for the physics term
    """

    def __init__(
        self,
        root: Path | str,
        split: str,
        patch: int | None = 256,
        crops_per_field: int = 4,
        augment: bool = True,
        seed: int = 0,
    ):
        self.path = Path(root) / f"{split}_planes.npy"
        if not self.path.exists():
            raise FileNotFoundError(f"{self.path} not found. Run velos.training.build_dataset first.")
        self.patch = patch
        self.augment = augment
        self.crops_per_field = crops_per_field if patch else 1
        self.seed = seed
        self._store: np.ndarray | None = None

        header = np.load(self.path, mmap_mode="r")
        self.count, self.channels, self.field, _ = header.shape
        del header

    def __len__(self) -> int:
        return self.count * self.crops_per_field

    def _data(self) -> np.ndarray:
        # Opened lazily so that each dataloader worker gets its own handle.
        if self._store is None:
            self._store = np.load(self.path, mmap_mode="r")
        return self._store

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        field_index = index // self.crops_per_field
        # Fresh entropy when augmenting, so a field is cropped somewhere new on
        # every pass rather than the same place every epoch. Seeded when not,
        # so evaluation is repeatable.
        rng = np.random.default_rng() if self.augment else np.random.default_rng((self.seed, index))
        planes = self._data()[field_index]

        if self.patch and self.patch < self.field:
            top = int(rng.integers(0, self.field - self.patch + 1))
            left = int(rng.integers(0, self.field - self.patch + 1))
            planes = planes[:, top : top + self.patch, left : left + self.patch]

        planes = np.ascontiguousarray(planes, dtype=np.float32)

        if self.augment:
            if rng.random() < 0.5:
                planes = planes[:, ::-1, :]
            if rng.random() < 0.5:
                planes = planes[:, :, ::-1]
            turns = int(rng.integers(0, 4))
            if turns:
                planes = np.rot90(planes, turns, axes=(1, 2))
            planes = np.ascontiguousarray(planes)

        tensor = torch.from_numpy(planes)
        return tensor[:4], tensor[4:5], tensor[:3]
