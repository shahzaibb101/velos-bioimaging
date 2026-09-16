"""Export a trained refiner to ONNX, and write the card that goes with it.

Two reasons this is not just a torch.onnx.export call.

The container. Serving through ONNX Runtime means the production image does not
carry PyTorch, which is most of a gigabyte of dependency for a four million
parameter model, and it is substantially faster on CPU besides.

The card. A model handed over without a written account of what it was trained
on, what it scores, and where it fails is a black box, and the brief for this
project says a small team has to own it afterwards. The card is generated from
the same run that produced the weights, so it cannot drift from them.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from velos.training.model import PhaseRefiner, parameter_count


def export(checkpoint: Path, out_dir: Path, tile: int = 256, opset: int = 17) -> Path:
    blob = torch.load(checkpoint, map_location="cpu")
    model = PhaseRefiner(base=blob.get("base", 24), in_channels=blob.get("in_channels", 4))
    model.load_state_dict(blob["state_dict"])
    model.eval()

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "phase_refiner.onnx"

    dummy = torch.randn(1, blob.get("in_channels", 4), tile, tile)
    torch.onnx.export(
        model, dummy, str(target),
        input_names=["stack"], output_names=["phase"],
        # Height and width stay dynamic so the same graph serves a tile and a
        # whole small field without re-exporting.
        dynamic_axes={"stack": {0: "batch", 2: "height", 3: "width"},
                      "phase": {0: "batch", 2: "height", 3: "width"}},
        opset_version=opset, do_constant_folding=True,
    )

    # Torch's exporter writes the weights beside the graph as external data.
    # Two files that must travel together is a deployment hazard: ship the
    # graph alone and the service loads a model with no weights in it. Fold
    # everything back into one self-contained file.
    import onnx

    model = onnx.load(str(target))                     # resolves the sidecar
    onnx.save_model(model, str(target), save_as_external_data=False)
    sidecar = target.with_suffix(".onnx.data")
    if sidecar.exists():
        sidecar.unlink()

    return target


def verify(checkpoint: Path, onnx_path: Path, tile: int = 256) -> dict:
    """The exported graph has to agree with the checkpoint it came from."""
    import onnxruntime as ort

    blob = torch.load(checkpoint, map_location="cpu")
    model = PhaseRefiner(base=blob.get("base", 24), in_channels=blob.get("in_channels", 4))
    model.load_state_dict(blob["state_dict"])
    model.eval()

    rng = np.random.default_rng(0)
    sample = rng.normal(1.0, 0.15, (1, 4, tile, tile)).astype(np.float32)
    sample[:, 3] = rng.normal(0.0, 1.0, (1, tile, tile))     # classical channel is phase, not intensity

    with torch.no_grad():
        reference = model(torch.from_numpy(sample)).numpy()

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    exported = session.run(None, {"stack": sample})[0]

    started = time.perf_counter()
    for _ in range(5):
        session.run(None, {"stack": sample})
    onnx_ms = (time.perf_counter() - started) / 5 * 1000

    started = time.perf_counter()
    with torch.no_grad():
        for _ in range(5):
            model(torch.from_numpy(sample))
    torch_ms = (time.perf_counter() - started) / 5 * 1000

    return {
        "max_abs_difference": float(np.abs(reference - exported).max()),
        "onnx_ms_per_tile": round(onnx_ms, 1),
        "torch_ms_per_tile": round(torch_ms, 1),
        "speedup": round(torch_ms / max(onnx_ms, 1e-6), 2),
    }


def card(checkpoint: Path, history_path: Path, check: dict, evaluation: dict | None) -> dict:
    blob = torch.load(checkpoint, map_location="cpu")
    model = PhaseRefiner(base=blob.get("base", 24), in_channels=blob.get("in_channels", 4))
    history = json.loads(history_path.read_text()) if history_path.exists() else []
    best = min(history, key=lambda e: e["model_rmse"]) if history else {}

    return {
        "name": "Velos phase refiner",
        "version": datetime.now(timezone.utc).strftime("%Y.%m.%d"),
        "exported": datetime.now(timezone.utc).isoformat(),
        "purpose": (
            "Corrects a Transport of Intensity phase reconstruction using the three camera "
            "planes that produced it. Outputs phase in radians."
        ),
        "architecture": {
            "type": "U-Net, 4 levels, GroupNorm, bilinear upsampling",
            "parameters": parameter_count(model),
            "inputs": "4 channels: under focus, in focus, over focus, classical phase estimate",
            "output": "1 channel: phase in radians",
            "residual": (
                "The network predicts a correction added to the classical solve, and its final "
                "convolution is zero-initialised. Before training it reproduces the classical "
                "solver exactly, so every learned change is a departure from a solution already "
                "anchored in the measurement."
            ),
        },
        "training": {
            "data": (
                "Simulated specimens imaged through a partially coherent forward model and a "
                "simulated sCMOS. Ground truth exists because the specimen is defined in physical "
                "units before it is imaged."
            ),
            "fields": 900, "crops_per_field": 4, "patch": 256,
            "exposures": "bright through very low light, sampled per field",
            "jitter": "defocus 1.15-1.95um, NA 0.37-0.43, condenser NA 0.09-0.16 per field",
            "loss": "L1 on phase + 0.5 gradient L1 + physics consistency against re-simulated intensity",
            "epochs_run": len(history),
            "best_epoch": best.get("epoch"),
            "best_val_rmse_rad": round(best.get("model_rmse", float("nan")), 4) if best else None,
            "classical_val_rmse_rad": round(best.get("classical_rmse", float("nan")), 4) if best else None,
            "improvement_pct": round(best.get("improvement_pct", float("nan")), 1) if best else None,
        },
        "evaluation": evaluation or {},
        "serving": {
            "runtime": "onnxruntime, CPU",
            "tiling": "256px tiles, 64px overlap, raised cosine blend",
            **check,
        },
        "limitations": [
            "Trained entirely on simulated specimens. Behaviour on real microscope data is "
            "unverified and is the first thing that should be checked.",
            "Assumes a three plane through-focus acquisition with roughly the modelled geometry. "
            "A markedly different objective, condenser or defocus is out of distribution.",
            "Phase beyond about 2*pi is rare in the training distribution, so very thick or "
            "optically dense bodies are the least reliable region of the output.",
            "The model corrects the classical solve and inherits its failure modes where they "
            "are severe. Where it departs strongly from the physics, check the disagreement map.",
        ],
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "platform": platform.platform(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/phase_refiner.pt"))
    parser.add_argument("--history", type=Path, default=Path("checkpoints/history.json"))
    parser.add_argument("--evaluation", type=Path, default=Path("checkpoints/evaluation.json"))
    parser.add_argument("--out", type=Path, default=Path("models"))
    args = parser.parse_args()

    print(f"exporting {args.checkpoint} -> ONNX")
    onnx_path = export(args.checkpoint, args.out)
    print(f"  wrote {onnx_path} ({onnx_path.stat().st_size / 1e6:.1f} MB)")

    check = verify(args.checkpoint, onnx_path)
    print(f"  torch vs onnx max |diff| = {check['max_abs_difference']:.2e}")
    print(f"  {check['torch_ms_per_tile']} ms torch -> {check['onnx_ms_per_tile']} ms onnx "
          f"({check['speedup']}x per 256px tile)")
    if check["max_abs_difference"] > 1e-3:
        raise SystemExit("ONNX export does not match the checkpoint; refusing to ship it.")

    evaluation = json.loads(args.evaluation.read_text()) if args.evaluation.exists() else None
    written = card(args.checkpoint, args.history, check, evaluation)
    (args.out / "model-card.json").write_text(json.dumps(written, indent=2))
    print(f"  wrote {args.out / 'model-card.json'}")


if __name__ == "__main__":
    main()
