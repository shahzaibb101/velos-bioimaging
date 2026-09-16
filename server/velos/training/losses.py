"""Training objective.

Three terms, and the reason for each:

  data      absolute agreement with the true phase, in radians. This is the term
            that makes the output quantitative, so it is an L1 on the value and
            not on anything normalised.

  gradient  agreement of the spatial derivatives. An L1 alone is happy to
            produce a slightly soft image, and softness in a phase map moves
            material across a cell boundary, which changes a per-cell mass.

  physics   agreement between the measurement that would be produced by the
            predicted phase and the measurement actually recorded. Needs no
            ground truth, so the same term can fine tune on real data later.
"""

from __future__ import annotations

import torch
from torch import nn

from .physics import DifferentiableMicroscope, differential


def gradient_l1(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    pred_dx = prediction[..., :, 1:] - prediction[..., :, :-1]
    pred_dy = prediction[..., 1:, :] - prediction[..., :-1, :]
    true_dx = target[..., :, 1:] - target[..., :, :-1]
    true_dy = target[..., 1:, :] - target[..., :-1, :]
    return (pred_dx - true_dx).abs().mean() + (pred_dy - true_dy).abs().mean()


class PhaseLoss(nn.Module):
    def __init__(
        self,
        microscope: DifferentiableMicroscope | None = None,
        gradient_weight: float = 0.5,
        physics_weight: float = 0.0,
        physics_samples: int = 2,
    ):
        super().__init__()
        self.microscope = microscope
        self.gradient_weight = gradient_weight
        self.physics_weight = physics_weight
        self.physics_samples = physics_samples

    def forward(
        self,
        prediction: torch.Tensor,
        target: torch.Tensor,
        measured: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        data = (prediction - target).abs().mean()
        gradient = gradient_l1(prediction, target)
        total = data + self.gradient_weight * gradient
        parts = {"data": data.item(), "gradient": gradient.item(), "physics": 0.0}

        if self.physics_weight > 0 and self.microscope is not None and measured is not None:
            # Only a couple of samples per batch carry the physics term. It costs
            # a full forward simulation and the signal it provides is a
            # regulariser, not the main objective.
            take = min(self.physics_samples, prediction.shape[0])
            simulated = self.microscope(prediction[:take])
            physics = (
                differential(simulated) - differential(measured[:take])
            ).abs().mean()
            total = total + self.physics_weight * physics
            parts["physics"] = physics.item()

        parts["total"] = total.item()
        return total, parts
