"""Does Cellpose-SAM, trained on real microscopy, find cells in my synthetic phase maps?

Two questions in one experiment. Whether segmentation needs building at all, and
whether the simulation is realistic enough that a foundation model trained
entirely on real microscope images recognises it without being told anything.
"""
import time
import numpy as np
from cellpose import models
from velos import cells, phantom, tie
from velos.optics import Optics

optics = Optics()
model = models.CellposeModel(gpu=False)
print(f"loaded Cellpose-SAM\n")

header = f"{'seed':<6}{'placed':>8}{'cellpose':>10}{'velos seg':>11}{'cellpose IoU-match':>20}{'sec':>7}"
print(header); print("-" * len(header))
for seed in (7, 3, 21):
    specimen = phantom.generate((512, 512), optics, seed=seed)
    truth = tie.level(specimen.phase)

    t = time.perf_counter()
    masks, _, _ = model.eval(truth, batch_size=1)
    elapsed = time.perf_counter() - t

    _, mine = cells.analyse(truth, optics)
    found = len(np.unique(masks)) - 1

    # How many true cells does Cellpose recover at IoU > 0.5?
    matched = 0
    for identifier in np.unique(specimen.labels):
        if identifier == 0:
            continue
        true_mask = specimen.labels == identifier
        overlap = masks[true_mask]
        overlap = overlap[overlap > 0]
        if overlap.size == 0:
            continue
        best = np.bincount(overlap).argmax()
        pred = masks == best
        iou = (true_mask & pred).sum() / (true_mask | pred).sum()
        matched += iou > 0.5
    placed = len(specimen.cells)
    print(f"{seed:<6}{placed:>8}{found:>10}{len(mine):>11}"
          f"{matched:>13} / {placed:<6}{elapsed:>7.1f}")
