"""Train the phase refinement network."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from velos.optics import Optics
from velos.training.dataset import PhaseFields
from velos.training.losses import PhaseLoss
from velos.training.model import PhaseRefiner, parameter_count
from velos.training.physics import DifferentiableMicroscope


def pick_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


@torch.no_grad()
def validate(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> dict[str, float]:
    """Score the model and the classical solver on the same fields.

    Both numbers are reported every epoch. A model improving in isolation says
    nothing; what matters is the gap to the method it is meant to replace.
    """
    model.eval()
    model_error, classical_error, count = 0.0, 0.0, 0
    for inputs, target, _ in loader:
        inputs, target = inputs.to(device), target.to(device)
        prediction = model(inputs)
        classical = inputs[:, 3:4]
        batch = inputs.shape[0]
        model_error += torch.sqrt(((prediction - target) ** 2).mean(dim=(1, 2, 3))).sum().item()
        classical_error += torch.sqrt(((classical - target) ** 2).mean(dim=(1, 2, 3))).sum().item()
        count += batch
    model.train()
    model_rmse = model_error / max(count, 1)
    classical_rmse = classical_error / max(count, 1)
    return {
        "model_rmse": model_rmse,
        "classical_rmse": classical_rmse,
        "improvement_pct": 100.0 * (1.0 - model_rmse / max(classical_rmse, 1e-9)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("checkpoints"))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--patch", type=int, default=256)
    parser.add_argument("--base", type=int, default=24)
    parser.add_argument("--lr", type=float, default=2e-3)
    parser.add_argument("--physics-weight", type=float, default=0.5)
    parser.add_argument("--physics-from", type=int, default=6,
                        help="epoch at which the physics term switches on")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    device = pick_device(args.device)
    args.out.mkdir(parents=True, exist_ok=True)

    train_set = PhaseFields(args.data, "train", patch=args.patch, crops_per_field=4, augment=True)
    val_set = PhaseFields(args.data, "val", patch=None, augment=False)
    train_loader = DataLoader(
        train_set, batch_size=args.batch, shuffle=True,
        num_workers=args.workers, drop_last=True, persistent_workers=args.workers > 0,
    )
    val_loader = DataLoader(val_set, batch_size=2, num_workers=2)

    model = PhaseRefiner(base=args.base).to(device)
    microscope = DifferentiableMicroscope(Optics(), (args.patch, args.patch), source_points=5).to(device)
    criterion = PhaseLoss(microscope=microscope, gradient_weight=0.5, physics_weight=0.0)

    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * (len(train_set) // args.batch)
    schedule = torch.optim.lr_scheduler.OneCycleLR(
        optimiser, max_lr=args.lr, total_steps=steps, pct_start=0.15
    )

    print(f"device {device}   {parameter_count(model)/1e6:.2f} M parameters")
    print(f"{len(train_set)} training crops, {len(val_set)} validation fields, {steps} steps\n")

    history, best = [], float("inf")
    for epoch in range(1, args.epochs + 1):
        if epoch == args.physics_from:
            criterion.physics_weight = args.physics_weight
            print(f"  physics consistency term on, weight {args.physics_weight}")

        started = time.perf_counter()
        running: dict[str, float] = {}
        for inputs, target, measured in train_loader:
            inputs = inputs.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            measured = measured.to(device, non_blocking=True)

            loss, parts = criterion(model(inputs), target, measured)
            optimiser.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
            schedule.step()
            for key, value in parts.items():
                running[key] = running.get(key, 0.0) + value

        batches = max(len(train_loader), 1)
        scores = validate(model, val_loader, device)
        elapsed = time.perf_counter() - started
        entry = {
            "epoch": epoch,
            "seconds": elapsed,
            **{f"train_{k}": v / batches for k, v in running.items()},
            **scores,
        }
        history.append(entry)

        print(
            f"epoch {epoch:>3}/{args.epochs}  {elapsed:5.0f}s  "
            f"loss {entry['train_total']:.4f}  "
            f"val rmse {scores['model_rmse']:.4f} vs classical {scores['classical_rmse']:.4f}  "
            f"({scores['improvement_pct']:+.1f}%)"
        )

        if scores["model_rmse"] < best:
            best = scores["model_rmse"]
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "base": args.base,
                    "in_channels": 4,
                    "epoch": epoch,
                    "val": scores,
                },
                args.out / "phase_refiner.pt",
            )
        (args.out / "history.json").write_text(json.dumps(history, indent=2))

    print(f"\nbest validation rmse {best:.4f} rad, checkpoint at {args.out / 'phase_refiner.pt'}")


if __name__ == "__main__":
    main()
