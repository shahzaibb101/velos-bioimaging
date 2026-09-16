"""Score the trained model on held-out data it was never shown.

The test split is deliberately *not* a random sample of the training
distribution. It is generated from the "evaluation" specimen statistics:
denser fields, thicker cells, more dividing figures, more debris, stronger
background drift. A model that has memorised the training distribution rather
than learned the inversion will look fine on validation and fall over here,
which is the entire point of building the split that way.

Per-cell dry mass error is reported alongside the image metrics because it is
the number the instrument exists to produce. A model can post an excellent
PSNR while getting the mass wrong.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from velos import metrics
from velos.optics import Optics
from velos.training.model import PhaseRefiner


def evaluate(data: Path, checkpoint: Path, limit: int | None = None) -> dict:
    planes = np.load(data / "test_planes.npy", mmap_mode="r")
    labels = np.load(data / "test_labels.npy", mmap_mode="r")
    count = len(planes) if limit is None else min(limit, len(planes))

    blob = torch.load(checkpoint, map_location="cpu")
    model = PhaseRefiner(base=blob.get("base", 24), in_channels=blob.get("in_channels", 4))
    model.load_state_dict(blob["state_dict"])
    model.eval()

    optics = Optics()
    rows: dict[str, list[dict]] = {"classical": [], "model": []}

    with torch.no_grad():
        for i in range(count):
            field = np.asarray(planes[i], dtype=np.float32)
            inputs = torch.from_numpy(field[:4])[None]
            truth = field[4].astype(np.float64)
            classical = field[3].astype(np.float64)
            learned = model(inputs)[0, 0].numpy().astype(np.float64)
            mask = np.asarray(labels[i], dtype=np.int32)

            rows["classical"].append(metrics.compare(truth, classical, optics, mask))
            rows["model"].append(metrics.compare(truth, learned, optics, mask))

    def gather(name: str) -> dict:
        entries = rows[name]
        keys = ("psnr_db", "ssim", "rmse_rad", "correlation", "mass_median_abs_pct", "mass_bias_pct")
        out = {}
        for key in keys:
            values = np.array([e[key] for e in entries if np.isfinite(e.get(key, np.nan))])
            if values.size:
                out[key] = round(float(values.mean()), 4)
                out[f"{key}_p10"] = round(float(np.percentile(values, 10)), 4)
                out[f"{key}_p90"] = round(float(np.percentile(values, 90)), 4)
        return out

    classical, learned = gather("classical"), gather("model")
    return {
        "fields": count,
        "split": "held-out, shifted distribution (denser, thicker, more dividing cells)",
        "classical": classical,
        "model": learned,
        "improvement": {
            "rmse_pct": round(100 * (1 - learned["rmse_rad"] / classical["rmse_rad"]), 1),
            "psnr_db_gain": round(learned["psnr_db"] - classical["psnr_db"], 2),
            "mass_error_pct_points": round(
                classical["mass_median_abs_pct"] - learned["mass_median_abs_pct"], 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/phase_refiner.pt"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints/evaluation.json"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    report = evaluate(args.data, args.checkpoint, args.limit)
    args.out.write_text(json.dumps(report, indent=2))

    c, m = report["classical"], report["model"]
    print(f"held-out fields: {report['fields']}  ({report['split']})\n")
    print(f"{'metric':<26}{'classical':>12}{'model':>12}{'delta':>12}")
    print("-" * 62)
    for key, label, fmt in (
        ("rmse_rad", "RMSE (rad)", "{:.4f}"),
        ("psnr_db", "PSNR (dB)", "{:.2f}"),
        ("ssim", "SSIM", "{:.4f}"),
        ("correlation", "Correlation", "{:.4f}"),
        ("mass_median_abs_pct", "Dry mass error (%)", "{:.2f}"),
        ("mass_bias_pct", "Dry mass bias (%)", "{:+.2f}"),
    ):
        print(f"{label:<26}{fmt.format(c[key]):>12}{fmt.format(m[key]):>12}"
              f"{fmt.format(m[key]-c[key]):>12}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
