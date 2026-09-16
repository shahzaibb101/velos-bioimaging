"""The phase refinement network.

The network is not asked to invert the microscope. It is handed the three camera
planes and the classical Transport of Intensity reconstruction, and it predicts
a correction to that reconstruction:

    phase = classical_solution + network(camera_planes, classical_solution)

Two consequences follow, and both are the reason it is built this way.

The final convolution is initialised to zero, so before a single gradient step
the network reproduces the classical solver exactly. Training starts at the
baseline rather than at noise, and every improvement is measured from a solution
that is already anchored in the measurement.

And because the output is a correction rather than a free image, the magnitude
of that correction is itself a quantity worth showing a user. Where the network
is barely changing the physics, the two agree. Where it is making a large
correction, the user is told, instead of being handed a confident picture with
no indication of where it came from.
"""

from __future__ import annotations

import torch
from torch import nn


def _groups_for(channels: int, preferred: int = 8) -> int:
    """Largest group count no greater than `preferred` that divides `channels`.

    Group normalisation requires the channel count to be divisible by the number
    of groups, and width multipliers that are not powers of two quietly violate
    that. Falling back to the nearest valid divisor keeps the width a free
    parameter.
    """
    for candidate in range(min(preferred, channels), 0, -1):
        if channels % candidate == 0:
            return candidate
    return 1


class ConvBlock(nn.Module):
    """Two convolutions with group normalisation.

    Group normalisation rather than batch normalisation, because inference runs
    on single images and batch statistics collected during training would not
    transfer to a batch of one.
    """

    def __init__(self, in_channels: int, out_channels: int, groups: int = 8):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(_groups_for(out_channels, groups), out_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(_groups_for(out_channels, groups), out_channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.body(x)


class Up(nn.Module):
    """Bilinear upsample then convolve.

    Transposed convolution would be the alternative, but it leaves a
    checkerboard pattern that is invisible in a photograph and unacceptable in a
    measurement that gets integrated over an area to produce a mass.
    """

    def __init__(self, in_channels: int, skip_channels: int, out_channels: int):
        super().__init__()
        self.reduce = nn.Conv2d(in_channels, out_channels, 1)
        self.block = ConvBlock(out_channels + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = nn.functional.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = self.reduce(x)
        return self.block(torch.cat([x, skip], dim=1))


class PhaseRefiner(nn.Module):
    """Physics guided phase reconstruction.

    Input is (batch, 4, height, width): the three normalised camera planes
    followed by the classical phase estimate in radians.
    Output is (batch, 1, height, width) of phase in radians.
    """

    def __init__(self, base: int = 24, depth: int = 4, in_channels: int = 4):
        super().__init__()
        self.in_channels = in_channels

        # Fixed input scaling. Deliberately constants rather than statistics
        # measured over the training set, so that nothing about deployment
        # depends on the dataset still being around.
        self.register_buffer("intensity_offset", torch.tensor(1.0))
        self.register_buffer("phase_scale", torch.tensor(2.0))

        widths = [base * 2**level for level in range(depth)]
        self.stem = ConvBlock(in_channels, widths[0])
        self.encoders = nn.ModuleList(
            [ConvBlock(widths[i], widths[i + 1]) for i in range(depth - 1)]
        )
        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(widths[-1], widths[-1] * 2)
        self.decoders = nn.ModuleList(
            [
                Up(widths[-1] * 2 if i == depth - 1 else widths[i + 1], widths[i], widths[i])
                for i in reversed(range(depth))
            ]
        )
        self.head = nn.Conv2d(widths[0], 1, 1)

        # Start as the classical solver: zero correction until trained.
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)

    def normalise(self, x: torch.Tensor) -> torch.Tensor:
        intensity = x[:, : self.in_channels - 1] - self.intensity_offset
        phase = x[:, self.in_channels - 1 :] / self.phase_scale
        return torch.cat([intensity, phase], dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        classical = x[:, self.in_channels - 1 : self.in_channels]

        features = self.normalise(x)
        skips = []
        features = self.stem(features)
        for encoder in self.encoders:
            skips.append(features)
            features = encoder(self.pool(features))
        skips.append(features)
        features = self.bottleneck(self.pool(features))
        for decoder, skip in zip(self.decoders, reversed(skips)):
            features = decoder(features, skip)

        return classical + self.head(features)


def parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
