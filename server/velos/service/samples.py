"""Sample acquisitions shipped with the app.

Someone opening the reconstruction app has no microscopy data to hand, and an
empty state that demands a 16-bit through-focus TIFF stack before it will show
anything is a demo nobody completes. These are generated once at build time,
stored as the instrument would store them, and loaded like any upload.

Each one exists to make a different point, which is why the exposures and
densities differ rather than being four views of the same easy case.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile

from velos import phantom
from velos.camera import Camera, expose
from velos.optics import Optics, through_focus_stack


@dataclass(frozen=True)
class Sample:
    slug: str
    title: str
    blurb: str
    exposure: str
    variant: str
    seed: int
    size: int = 512


CATALOGUE: tuple[Sample, ...] = (
    Sample(
        slug="confluent-standard",
        title="Adherent culture, standard exposure",
        blurb="A normally exposed field at moderate confluence. The case everything else is compared against.",
        exposure="standard", variant="train", seed=101,
    ),
    Sample(
        slug="low-light",
        title="Low light, gentle imaging",
        blurb="One tenth the photon budget, as used when the same cells are imaged every few minutes for a day. This is where the classical solver starts to struggle.",
        exposure="low_light", variant="train", seed=202,
    ),
    Sample(
        slug="dense-dividing",
        title="Dense field with dividing cells",
        blurb="Higher confluence and more rounded mitotic cells. Thick, optically dense bodies are where phase wrapping appears.",
        exposure="standard", variant="evaluation", seed=303,
    ),
    Sample(
        slug="sparse-bright",
        title="Sparse field, bright exposure",
        blurb="Few cells and plenty of light. The easiest case, and the one where every method should agree.",
        exposure="bright", variant="sparse", seed=404,
    ),
)


def build(sample: Sample, into: Path, optics: Optics | None = None) -> dict:
    """Generate one sample and write it as the instrument would.

    The stack is saved as a 16-bit OME-TIFF, which is what a real acquisition
    produces, so the upload path and the sample path exercise the same reader.
    Ground truth is stored separately as float32 and is never fed to the
    reconstruction; it exists only so the app can score itself.
    """
    optics = optics or Optics()
    into.mkdir(parents=True, exist_ok=True)

    config = phantom.SpecimenConfig.variant(sample.variant)
    specimen = phantom.generate((sample.size, sample.size), optics, config, seed=sample.seed)
    clean = through_focus_stack(specimen.phase, optics, specimen.absorption)
    camera = Camera.preset(sample.exposure)
    counts = expose(clean, camera, np.random.default_rng(sample.seed + 1))

    tifffile.imwrite(
        into / f"{sample.slug}.ome.tif",
        counts.astype(np.uint16),
        photometric="minisblack",
        metadata={
            "axes": "ZYX",
            "PhysicalSizeX": optics.pixel_size, "PhysicalSizeXUnit": "µm",
            "PhysicalSizeY": optics.pixel_size, "PhysicalSizeYUnit": "µm",
            "PhysicalSizeZ": optics.defocus, "PhysicalSizeZUnit": "µm",
        },
    )
    np.savez_compressed(
        into / f"{sample.slug}.truth.npz",
        phase=specimen.phase.astype(np.float32),
        labels=specimen.labels.astype(np.int16),
    )

    masses = [c["dry_mass_pg"] for c in specimen.cells]
    return {
        "slug": sample.slug,
        "title": sample.title,
        "blurb": sample.blurb,
        "exposure": sample.exposure,
        "photons": camera.photons,
        "size": sample.size,
        "field_um": round(sample.size * optics.pixel_size, 1),
        "cells": len(specimen.cells),
        "median_dry_mass_pg": round(float(np.median(masses)), 1) if masses else None,
        "stack": f"{sample.slug}.ome.tif",
        "truth": f"{sample.slug}.truth.npz",
    }


def build_all(into: Path, optics: Optics | None = None) -> list[dict]:
    return [build(s, into, optics) for s in CATALOGUE]
