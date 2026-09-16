"""A differentiable copy of the forward model, for use inside the loss.

Supervising a reconstruction only against ground truth teaches it to match the
training specimens. Supervising it additionally against the measurement teaches
it to obey the instrument. The second signal is available without any ground
truth at all, which is what makes it useful later: the same term can fine tune
the model on real microscope data that has no labels.

The model implemented here is the same Abbe summation as `velos.optics`, ported
to torch so gradients flow back through it to the predicted phase.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from velos.optics import Optics, condenser_samples, frequency_grid, spatial_grid


class DifferentiableMicroscope(nn.Module):
    """Predicted phase in, simulated camera planes out, gradients intact."""

    def __init__(
        self,
        optics: Optics,
        shape: tuple[int, int],
        source_points: int = 5,
    ):
        super().__init__()
        self.shape = shape
        planes = (-optics.defocus, 0.0, optics.defocus)

        fx, fy = frequency_grid(shape, optics.pixel_size)
        radius = np.hypot(fx, fy)
        pupil = (radius <= optics.na_objective / optics.wavelength).astype(np.float64)

        k_index = optics.n_medium / optics.wavelength
        under_root = np.clip(k_index**2 - fx**2 - fy**2, 0.0, None)
        kz = np.sqrt(under_root)
        kernels = np.stack(
            [pupil * np.exp(2j * np.pi * distance * kz) for distance in planes]
        ).astype(np.complex64)

        x, y = spatial_grid(shape, optics.pixel_size)
        sources = condenser_samples(
            Optics(**{**optics.__dict__, "source_points": source_points})
        )
        tilts = np.stack(
            [np.exp(2j * np.pi * (sx * x + sy * y)) for sx, sy in sources]
        ).astype(np.complex64)

        self.register_buffer("kernels", torch.from_numpy(kernels))
        self.register_buffer("tilts", torch.from_numpy(tilts))

    def forward(self, phase: torch.Tensor) -> torch.Tensor:
        """`phase` is (batch, 1, height, width) in radians.

        Returns (batch, 3, height, width) of intensity, normalised so that an
        empty field reads about 1.0.
        """
        transmittance = torch.exp(1j * phase.to(torch.float32))
        total = torch.zeros(
            phase.shape[0], self.kernels.shape[0], *self.shape,
            device=phase.device, dtype=torch.float32,
        )

        for tilt in self.tilts:
            spectrum = torch.fft.fft2(transmittance * tilt)
            for index in range(self.kernels.shape[0]):
                field = torch.fft.ifft2(spectrum * self.kernels[index])
                total[:, index] = total[:, index] + field.real.pow(2).squeeze(1) + field.imag.pow(2).squeeze(1)

        total = total / self.tilts.shape[0]

        # Same 95th percentile reference the numpy forward model and the camera
        # normalisation use. Done by sort rather than torch.quantile because
        # quantile is not implemented on every backend this trains on.
        flat = total[:, 1].flatten(1)
        index = min(int(0.95 * flat.shape[1]), flat.shape[1] - 1)
        background = flat.sort(dim=1).values[:, index]
        return total / background.clamp_min(1e-6).view(-1, 1, 1, 1)


def differential(stack: torch.Tensor) -> torch.Tensor:
    """The over minus under focus difference, which is the signal TIE inverts.

    Comparing this rather than the raw planes makes the physics term largely
    blind to the smooth multiplicative shading of the illumination, which the
    simulation has no way of knowing about.
    """
    return stack[:, 2:3] - stack[:, 0:1]
