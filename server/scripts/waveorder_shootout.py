"""Head to head: my hand-written TIE solver against waveorder's published solver.

Same simulated specimen, same simulated camera, same leveling and the same
scoring. The point is not to win. The point is to find out whether a published,
peer reviewed, actively maintained reconstruction library beats three hundred
lines I wrote this afternoon, because if it does then it belongs in the product
and mine does not.
"""

import time
import numpy as np
import torch

from velos import camera as cam
from velos import metrics, phantom, tie
from velos.optics import Optics, through_focus_stack
from waveorder.models import isotropic_thin_3d as wo

SHAPE = (512, 512)
optics = Optics()
specimen = phantom.generate(SHAPE, optics, seed=7)
truth = tie.level(specimen.phase)
labels = specimen.labels
clean = through_focus_stack(specimen.phase, optics, specimen.absorption)

print(f"specimen: {len(specimen.cells)} cells, phase to {truth.max():.2f} rad\n")
header = f"{'exposure':<12}{'method':<26}{'psnr':>7}{'ssim':>7}{'rmse':>8}{'corr':>7}{'mass err%':>11}{'bias%':>8}{'ms':>7}"
print(header); print("-" * len(header))

for preset in ("bright", "standard", "low_light"):
    camera = cam.Camera.preset(preset)
    rng = np.random.default_rng(11)
    measured = cam.normalise(cam.expose(clean, camera, rng), camera)

    results = {}

    t = time.perf_counter()
    mine = tie.level(tie.solve(measured, optics, method="uniform"))
    results["velos TIE (Poisson/FFT)"] = (mine, (time.perf_counter() - t) * 1000)

    for strength in (1e-3, 1e-2):
        t = time.perf_counter()
        _, phase = wo.reconstruct(
            zyx_data=torch.from_numpy(measured).float(),
            yx_pixel_size=optics.pixel_size,
            z_position_list=[-optics.defocus, 0.0, optics.defocus],
            wavelength_illumination=optics.wavelength,
            index_of_refraction_media=optics.n_medium,
            numerical_aperture_illumination=optics.na_illumination,
            numerical_aperture_detection=optics.na_objective,
            reconstruction_algorithm="Tikhonov",
            regularization_strength=strength,
        )
        elapsed = (time.perf_counter() - t) * 1000
        results[f"waveorder Tikhonov {strength:g}"] = (tie.level(phase.numpy()), elapsed)

    for name, (estimate, ms) in results.items():
        # Allow either sign convention, take whichever correlates positively.
        if metrics.correlation(truth, estimate) < 0:
            estimate = -estimate
            name += " (sign flipped)"
        s = metrics.compare(truth, estimate, optics, labels)
        print(f"{preset:<12}{name:<26}{s['psnr_db']:>7.2f}{s['ssim']:>7.3f}"
              f"{s['rmse_rad']:>8.3f}{s['correlation']:>7.3f}"
              f"{s['mass_median_abs_pct']:>11.1f}{s['mass_bias_pct']:>8.1f}{ms:>7.0f}")
    print()
