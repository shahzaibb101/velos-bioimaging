"""Physics round trip: define a specimen, image it, invert it, compare.

If the classical solver cannot recover a phase map that the forward model was
given directly, then every constant in the pipeline is suspect and nothing built
on top of it means anything. This runs first and it runs often.
"""

import time

import numpy as np

from velos import camera as cam
from velos import phantom, tie
from velos.optics import Optics

SHAPE = (512, 512)


def report(name: str, truth: np.ndarray, estimate: np.ndarray) -> None:
    truth = tie.level(truth)
    estimate = tie.level(estimate)
    correlation = float(np.corrcoef(truth.ravel(), estimate.ravel())[0, 1])
    rmse = float(np.sqrt(np.mean((truth - estimate) ** 2)))
    # Least squares scale: 1.0 means the solver recovered absolute radians.
    scale = float((truth * estimate).sum() / max((estimate**2).sum(), 1e-12))
    print(
        f"  {name:<28} correlation {correlation:6.3f}   "
        f"rmse {rmse:6.3f} rad   scale {scale:6.3f}"
    )


def main() -> None:
    optics = Optics()
    print(f"Instrument: NA {optics.na_objective}, sigma {optics.coherence_ratio:.2f}, "
          f"resolution {optics.resolution:.3f} um, defocus +/-{optics.defocus} um")
    print(f"Field: {SHAPE[0]*optics.pixel_size:.0f} x {SHAPE[1]*optics.pixel_size:.0f} um\n")

    specimen = phantom.generate(SHAPE, optics, seed=7)
    print(f"Specimen: {len(specimen.cells)} cells, "
          f"phase range {specimen.phase.min():.2f} to {specimen.phase.max():.2f} rad")
    masses = [c["dry_mass_pg"] for c in specimen.cells]
    if masses:
        print(f"Dry mass per cell: {np.min(masses):.0f} to {np.max(masses):.0f} pg, "
              f"median {np.median(masses):.0f} pg  (a real mammalian cell is 100-500 pg)\n")

    started = time.perf_counter()
    clean = phantom_stack(specimen, optics)
    print(f"Forward model: {time.perf_counter() - started:.2f} s for 3 planes "
          f"over {optics.source_points} source points")
    print(f"Intensity modulation at focus: "
          f"{clean[1].min():.3f} to {clean[1].max():.3f} (empty field is 1.0)\n")

    rng = np.random.default_rng(11)
    for preset in ("bright", "standard", "low_light"):
        camera = cam.Camera.preset(preset)
        counts = cam.expose(clean, camera, rng)
        measured = cam.normalise(counts, camera)

        started = time.perf_counter()
        uniform = tie.solve(measured, optics, method="uniform")
        teague = tie.solve(measured, optics, method="teague")
        elapsed = time.perf_counter() - started

        print(f"{preset} ({camera.photons:.0f} photons, solved in {elapsed*1000:.0f} ms)")
        report("transport of intensity", specimen.phase, uniform)
        report("teague two-solve", specimen.phase, teague)
        print()


def phantom_stack(specimen, optics):
    from velos.optics import through_focus_stack
    return through_focus_stack(specimen.phase, optics, specimen.absorption)


if __name__ == "__main__":
    main()
