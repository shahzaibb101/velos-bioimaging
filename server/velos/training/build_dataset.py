"""Generate a paired dataset of camera stacks and true phase.

Each sample is a whole 512 by 512 field rather than a crop, because the
classical solver's worst artifact is a slowly varying background and its Fourier
boundary conditions are set by the size of the array it is handed. Running the
solver on a crop would produce a different artifact than running it on a full
frame and cropping afterwards, and the second is what happens on the instrument.
Crops for training are taken later, from the already-solved field.

Every sample draws its own exposure, its own specimen statistics and a small
error in the assumed defocus distance. That last one matters more than it
sounds: on a real instrument the focus drive is never exactly where the
metadata claims, and a model trained at one exact defocus learns a calibration
rather than a physical inversion.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from velos import camera as cam
from velos import phantom, tie
from velos.optics import Optics, through_focus_stack

CHANNELS = 5          # three camera planes, the classical solve, then the target
FIELD = 512
EXPOSURES = ("bright", "standard", "standard", "low_light", "low_light", "very_low_light")


def _make_one(task: tuple[int, str, bool]) -> tuple[np.ndarray, np.ndarray]:
    """Build a single field. Returns (stacked planes, instance labels)."""
    seed, variant, want_labels = task
    rng = np.random.default_rng(seed)

    # The instrument is not perfectly calibrated and never twice the same.
    true_defocus = float(rng.uniform(1.15, 1.95))
    optics = Optics(
        defocus=true_defocus,
        na_objective=float(rng.uniform(0.37, 0.43)),
        na_illumination=float(rng.uniform(0.09, 0.16)),
        source_points=13,
    )

    config = phantom.SpecimenConfig.variant(variant)
    specimen = phantom.generate((FIELD, FIELD), optics, config, seed=seed)

    clean = through_focus_stack(specimen.phase, optics, specimen.absorption)
    camera = cam.Camera.preset(str(rng.choice(EXPOSURES)))
    measured = cam.normalise(cam.expose(clean, camera, rng), camera)

    # The solver is told the nominal defocus, not the true one, so the residual
    # calibration error is part of what the network has to absorb.
    assumed = Optics(
        defocus=1.5,
        na_objective=optics.na_objective,
        na_illumination=optics.na_illumination,
    )
    classical = tie.level(tie.solve(measured, assumed, method="uniform"))
    target = tie.level(specimen.phase)

    planes = np.concatenate(
        [measured.astype(np.float32), classical[None].astype(np.float32), target[None].astype(np.float32)]
    ).astype(np.float16)
    labels = specimen.labels.astype(np.int16) if want_labels else np.zeros((1, 1), np.int16)
    return planes, labels


def build(split: str, count: int, variant: str, seed0: int, out: Path, labels: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)
    planes_path = out / f"{split}_planes.npy"
    store = np.lib.format.open_memmap(
        planes_path, mode="w+", dtype=np.float16, shape=(count, CHANNELS, FIELD, FIELD)
    )
    label_store = (
        np.lib.format.open_memmap(
            out / f"{split}_labels.npy", mode="w+", dtype=np.int16, shape=(count, FIELD, FIELD)
        )
        if labels
        else None
    )

    tasks = [(seed0 + i, variant, labels) for i in range(count)]
    started = time.perf_counter()
    done = 0
    with ProcessPoolExecutor() as pool:
        for index, (planes, cell_labels) in enumerate(pool.map(_make_one, tasks, chunksize=2)):
            store[index] = planes
            if label_store is not None:
                label_store[index] = cell_labels
            done += 1
            if done % 25 == 0 or done == count:
                rate = done / (time.perf_counter() - started)
                print(
                    f"  {split}: {done}/{count} fields  ({rate:.1f}/s, "
                    f"{(count - done) / max(rate, 1e-6):.0f}s left)",
                    flush=True,
                )
    store.flush()
    if label_store is not None:
        label_store.flush()

    (out / f"{split}_meta.json").write_text(
        json.dumps(
            {
                "split": split,
                "count": count,
                "variant": variant,
                "field": FIELD,
                "channels": ["under_focus", "in_focus", "over_focus", "classical_phase", "true_phase"],
                "exposures": list(EXPOSURES),
                "seed0": seed0,
            },
            indent=2,
        )
    )
    print(f"  {split}: wrote {planes_path} ({planes_path.stat().st_size / 1e9:.2f} GB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--train", type=int, default=520)
    parser.add_argument("--val", type=int, default=60)
    parser.add_argument("--test", type=int, default=90)
    args = parser.parse_args()

    print("Building paired dataset.")
    print("  train and validation are drawn from the same culture statistics.")
    print("  test is drawn from the shifted 'evaluation' statistics: denser, thicker,")
    print("  more dividing cells, more debris. A model that only learned the training")
    print("  distribution will show up there and not in validation.\n")

    build("train", args.train, "train", 100_000, args.out, labels=False)
    build("val", args.val, "train", 500_000, args.out, labels=True)
    build("test", args.test, "evaluation", 900_000, args.out, labels=True)


if __name__ == "__main__":
    main()
