"""Render the full chain to a figure so it can be judged by eye.

Numbers confirm the maths. Only looking at the images confirms that the
simulated specimen resembles a culture and that the simulated camera frames
resemble microscopy.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from velos import camera as cam
from velos import phantom, tie
from velos.optics import Optics, through_focus_stack

SHAPE = (512, 512)


def main() -> None:
    optics = Optics()
    specimen = phantom.generate(SHAPE, optics, seed=7)
    clean = through_focus_stack(specimen.phase, optics, specimen.absorption)

    rng = np.random.default_rng(11)
    camera = cam.Camera.preset("standard")
    measured = cam.normalise(cam.expose(clean, camera, rng), camera)

    recovered = tie.level(tie.solve(measured, optics, method="uniform"))
    truth = tie.level(specimen.phase)

    masses = [c["dry_mass_pg"] for c in specimen.cells]
    print(f"{len(specimen.cells)} cells, dry mass {np.min(masses):.0f} to "
          f"{np.max(masses):.0f} pg, median {np.median(masses):.0f} pg")
    print(f"phase range {truth.min():.2f} to {truth.max():.2f} rad")

    extent = [0, SHAPE[1] * optics.pixel_size, 0, SHAPE[0] * optics.pixel_size]
    panels = [
        ("camera, under focus", measured[0], "gray", None),
        ("camera, at focus", measured[1], "gray", None),
        ("camera, over focus", measured[2], "gray", None),
        ("ground truth phase", truth, "inferno", (truth.min(), truth.max())),
        ("transport of intensity", recovered, "inferno", (truth.min(), truth.max())),
        ("error", recovered - truth, "coolwarm", (-1.2, 1.2)),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    for ax, (title, image, cmap, limits) in zip(axes.ravel(), panels):
        kwargs = {"cmap": cmap, "extent": extent}
        if limits:
            kwargs["vmin"], kwargs["vmax"] = limits
        handle = ax.imshow(image, **kwargs)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("micrometres", fontsize=8)
        fig.colorbar(handle, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig("out/round_trip.png", dpi=110)
    print("wrote out/round_trip.png")


if __name__ == "__main__":
    main()
