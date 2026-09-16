"""HTTP surface for the reconstruction service."""

from __future__ import annotations

import csv
import io
import json
import os
import threading
from pathlib import Path

import numpy as np
import tifffile
from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from velos.camera import Camera
from velos.optics import Optics
from velos.service import jobs, model as model_loader, pipeline, render, samples

DATA = Path(os.getenv("VELOS_DATA", "data/samples"))
MODELS = Path(os.getenv("VELOS_MODELS", "models"))
MAX_UPLOAD_MB = int(os.getenv("VELOS_MAX_UPLOAD_MB", "40"))
MAX_PIXELS = int(os.getenv("VELOS_MAX_PIXELS", str(1600 * 1600)))

app = FastAPI(title="Velos BioImaging reconstruction", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("VELOS_CORS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

store = jobs.Store()
queue = jobs.Queue(store, workers=int(os.getenv("VELOS_WORKERS", "2")))
_model = model_loader.load(MODELS)

# Arrays are kept beside the job so layers can be rendered on demand instead of
# base64'd into the status payload, which would make the polling response tens
# of megabytes.
_artifacts: dict[str, dict] = {}
_artifacts_lock = threading.Lock()

_catalogue_path = DATA / "catalogue.json"
_catalogue = json.loads(_catalogue_path.read_text()) if _catalogue_path.exists() else []


# --------------------------------------------------------------------- basics

@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "model": {
            "loaded": _model is not None,
            "runtime": _model.runtime if _model else None,
            "card": _model.card if _model else {},
        },
        "queue": queue.backend,
        "samples": len(_catalogue),
    }


@app.get("/api/samples")
def list_samples() -> list[dict]:
    return _catalogue


@app.get("/api/jobs")
def list_jobs() -> list[dict]:
    return [j.public() for j in store.recent()]


# ---------------------------------------------------------------- submission

def _read_stack(raw: bytes, filename: str) -> np.ndarray:
    try:
        array = tifffile.imread(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(400, f"Could not read {filename} as a TIFF: {exc}") from exc

    array = np.squeeze(np.asarray(array))
    if array.ndim != 3 or array.shape[0] != 3:
        raise HTTPException(
            400,
            "Expected a 3-plane through-focus stack shaped (3, height, width), "
            f"ordered under focus, in focus, over focus. Got {array.shape}.",
        )
    if array.shape[1] * array.shape[2] > MAX_PIXELS:
        raise HTTPException(413, f"Field is larger than this demo accepts ({MAX_PIXELS:,} pixels per plane).")
    return array.astype(np.float64)


def _run(stack: np.ndarray, optics: Optics, camera: Camera | None,
         truth: np.ndarray | None, report) -> tuple[dict, dict]:
    report(0.12, "Normalising camera planes")
    report(0.25, "Solving transport of intensity")
    result = pipeline.run(stack, optics, camera=camera, truth=truth, model=_model)

    report(0.8, "Segmenting and measuring cells")
    phases = [r.phase for r in result.reconstructions]
    if result.truth is not None:
        from velos import tie
        phases.append(tie.level(result.truth))
    low, high = render.display_limits(phases)

    layers: dict[str, bytes] = {
        "raw": render.intensity_png(result.measured[1]),
        "raw-under": render.intensity_png(result.measured[0]),
        "raw-over": render.intensity_png(result.measured[2]),
        "outlines": render.outlines_png(result.primary().phase, result.labels, low, high),
    }
    for r in result.reconstructions:
        layers[r.name] = render.phase_png(r.phase, low, high)
    if result.truth is not None:
        from velos import tie
        layers["truth"] = render.phase_png(tie.level(result.truth), low, high)
    if result.disagreement is not None:
        layers["disagreement"] = render.disagreement_png(result.disagreement)

    report(0.95, "Rendering layers")
    summary = result.summary()
    summary["display_range_rad"] = [round(low, 3), round(high, 3)]
    summary["layers"] = sorted(layers)
    summary["cells"] = result.cells[:400]
    if result.disagreement is not None:
        d = np.abs(result.disagreement)
        summary["disagreement"] = {
            "mean_rad": round(float(d.mean()), 4),
            "max_rad": round(float(d.max()), 4),
            "p99_rad": round(float(np.percentile(d, 99)), 4),
        }

    artifacts = {
        "layers": layers,
        "phase": result.primary().phase,
        "cells": result.cells,
        "pixel_size": optics.pixel_size,
    }
    return summary, artifacts


@app.post("/api/jobs")
async def create_job(
    sample: str | None = Form(None),
    exposure: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> JSONResponse:
    optics = Optics()
    camera: Camera | None = None
    truth: np.ndarray | None = None

    if sample:
        entry = next((c for c in _catalogue if c["slug"] == sample), None)
        if entry is None:
            raise HTTPException(404, f"No sample named {sample!r}.")
        stack = np.asarray(tifffile.imread(DATA / entry["stack"]), dtype=np.float64)
        camera = Camera.preset(entry["exposure"])
        truth_path = DATA / entry["truth"]
        if truth_path.exists():
            truth = np.load(truth_path)["phase"].astype(np.float64)
        label = entry["title"]
    elif file is not None:
        raw = await file.read()
        if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(413, f"Upload exceeds {MAX_UPLOAD_MB} MB.")
        stack = _read_stack(raw, file.filename or "upload.tif")
        camera = Camera.preset(exposure) if exposure else Camera()
        label = file.filename or "Uploaded stack"
    else:
        raise HTTPException(400, "Provide either a sample slug or a TIFF upload.")

    job = store.create({"source": sample or "upload", "label": label,
                        "pixels": list(stack.shape[-2:])})

    def work(_job, report):
        summary, artifacts = _run(stack, optics, camera, truth, report)
        with _artifacts_lock:
            _artifacts[_job.id] = artifacts
            for stale in list(_artifacts)[:-24]:      # keep memory bounded
                _artifacts.pop(stale, None)
        return summary

    queue.submit(job, work)
    return JSONResponse(job.public(), status_code=202)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "No such job.")
    return job.public()


# ------------------------------------------------------------------- outputs

@app.get("/api/jobs/{job_id}/layers/{name}.png")
def layer(job_id: str, name: str) -> Response:
    with _artifacts_lock:
        art = _artifacts.get(job_id)
    if art is None or name not in art["layers"]:
        raise HTTPException(404, "No such layer for this job.")
    return Response(art["layers"][name], media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/jobs/{job_id}/cells.csv")
def cells_csv(job_id: str) -> Response:
    with _artifacts_lock:
        art = _artifacts.get(job_id)
    if art is None:
        raise HTTPException(404, "No such job.")
    buffer = io.StringIO()
    columns = ["label", "centroid_x_um", "centroid_y_um", "area_um2",
               "mean_phase_rad", "max_phase_rad", "dry_mass_pg", "circularity", "rounded"]
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in art["cells"]:
        writer.writerow({k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()})
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="velos-{job_id}-cells.csv"'})


@app.get("/api/jobs/{job_id}/phase.tif")
def phase_tiff(job_id: str) -> Response:
    """The reconstruction as 32-bit float radians, not a picture of it.

    A PNG is for looking at. This is the artefact someone would actually take
    into their own analysis, so it keeps physical units and pixel size.
    """
    with _artifacts_lock:
        art = _artifacts.get(job_id)
    if art is None:
        raise HTTPException(404, "No such job.")
    buffer = io.BytesIO()
    tifffile.imwrite(
        buffer, art["phase"].astype(np.float32), photometric="minisblack",
        metadata={"axes": "YX", "unit": "radians",
                  "PhysicalSizeX": art["pixel_size"], "PhysicalSizeY": art["pixel_size"]},
    )
    return Response(buffer.getvalue(), media_type="image/tiff",
                    headers={"Content-Disposition": f'attachment; filename="velos-{job_id}-phase.tif"'})
