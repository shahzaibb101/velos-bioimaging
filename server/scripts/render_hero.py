"""Render the hero loop: a live-cell time-lapse, actually reconstructed.

Every frame goes through the whole instrument. A specimen is defined in
physical units, imaged through the partially coherent forward model at three
focal planes, exposed on a simulated sCMOS with shot and read noise, and then
inverted back to phase. What the hero plays is reconstruction output, not a
motion graphic, which is the entire reason for putting it there.
"""

import argparse
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from velos import camera as cam
from velos import colormap, tie, timelapse
from velos.optics import Optics, through_focus_stack

SIZE = 1152
FRAMES = 120
OPTICS = Optics(source_points=13)
TRACKS = None


def _init():
    global TRACKS
    TRACKS = timelapse.plan((SIZE, SIZE), OPTICS, seed=3)


def _render(index: int) -> tuple[int, np.ndarray]:
    t = index / FRAMES
    truth = timelapse.frame(TRACKS, (SIZE, SIZE), OPTICS, t)
    clean = through_focus_stack(truth, OPTICS)
    camera = cam.Camera.preset("standard")
    # Seeded per frame so the noise differs frame to frame, as a real camera's
    # would, rather than freezing into a fixed pattern that reads as texture.
    measured = cam.normalise(cam.expose(clean, camera, np.random.default_rng(1000 + index)), camera)
    phase = tie.level(tie.solve(measured, OPTICS, method="uniform"))
    return index, phase


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("out/hero"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    frames: dict[int, np.ndarray] = {}
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init) as pool:
        for done, (index, phase) in enumerate(pool.map(_render, range(FRAMES)), start=1):
            frames[index] = phase
            if done % 10 == 0 or done == FRAMES:
                rate = done / (time.perf_counter() - started)
                print(f"  {done}/{FRAMES} frames ({rate:.2f}/s, {(FRAMES-done)/max(rate,1e-6):.0f}s left)", flush=True)

    # One set of display limits for the whole sequence. Per-frame autoscaling
    # would make the background pulse as cells grow, which would be an artefact
    # of the rendering rather than anything in the specimen.
    stack = np.stack([frames[i] for i in range(FRAMES)])
    low, high = float(np.percentile(stack, 1.0)), float(np.percentile(stack, 99.6))
    print(f"display range {low:.3f} to {high:.3f} rad (fixed across the sequence)")

    for index in range(FRAMES):
        Image.fromarray(colormap.apply(frames[index], low, high)).save(args.out / f"{index:04d}.png")

    mp4 = args.out.parent / "hero-reconstruction.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", str(args.fps),
        "-i", str(args.out / "%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
        "-movflags", "+faststart", "-an", str(mp4),
    ], check=True)
    print(f"wrote {mp4} ({mp4.stat().st_size/1e6:.1f} MB) in {time.perf_counter()-started:.0f}s")


if __name__ == "__main__":
    main()
