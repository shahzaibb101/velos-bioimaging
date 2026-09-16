# Velos BioImaging

Label-free quantitative phase imaging for live cells: a marketing site and a
working reconstruction application, sharing one design system.

Living cells are almost perfectly transparent, so an ordinary microscope shows
almost nothing. They do slow light down, and that delay carries the cell's
structure — but a camera records intensity, so the delay is thrown away at the
sensor. This reconstructs it, and turns it into calibrated numbers: phase in
radians, and dry mass in picograms for every cell in the field.

```
web/       Next.js site and reconstruction UI
server/    Python: optics, reconstruction, training, and the HTTP service
docker/    Container builds for both services
docs/      Notes
```

## What is real, and what is not

**Real.** The optics, the forward model, the reconstruction, the network, the
segmentation and every measurement. The classical solver recovers absolute
radians. The network is trained, evaluated on a held-out shifted distribution,
exported to ONNX and served on CPU.

**Simulated.** The specimens. That is deliberate: a real quantitative phase
dataset has no ground truth, because the only reference available is the
instrument's own reconstruction — the thing under test. Defining the specimen
first, in physical units, and then imaging it through the forward model is the
only way to obtain paired data where the answer is known. Point the pipeline at
real microscope data and nothing about it changes.

## Running it

```bash
# Service
cd server
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[train,serve]"
python -m velos.service.samples_build          # sample acquisitions
uvicorn velos.service.api:app --port 8000

# Site
cd web && npm install && npm run dev
```

The site proxies `/api/*` to the service, so both run under one origin.

## Reproducing the model

```bash
cd server
python -m velos.training.build_dataset          # ~2.4 GB, a few minutes
python -m velos.training.train --epochs 30
python -m velos.training.evaluate               # held-out, shifted distribution
python -m velos.training.export                 # ONNX + model card
```

`velos/training/export.py` refuses to write a model whose ONNX graph disagrees
with its checkpoint, and generates `models/model-card.json` from the same run
that produced the weights, so the card cannot drift from what is being served.

## The reconstruction

Three methods run on every job, and all three are shown:

| Method | What it is |
|---|---|
| Transport of intensity | FFT Poisson inverse. Fast, assumes weak absorption. |
| [waveorder](https://github.com/mehta-lab/waveorder) | Published partially coherent inverse from CZ Biohub (BSD-3). |
| Physics-guided refinement | A network that corrects the classical solve rather than replacing it. |

A single reconstruction is a claim; three that agree are evidence. Where they
disagree, the app says so rather than quietly picking one.

The learned model predicts a *correction* added to the classical solve, and its
final convolution is zero-initialised — before training it reproduces the
classical solver exactly. The **model minus physics** layer shows exactly what
it changed, which is the layer that answers "did the network invent that?".

### One thing worth knowing about waveorder

Its default `regularization_strength` of `1e-3` is roughly two orders of
magnitude too strong for a well-exposed stack and costs about 0.3 in
correlation. `velos/baseline.py` picks a strength from the measured shot noise
using `0.39 * noise**2.56`, fitted against ground truth across four exposures
spanning a hundredfold in photon count.

## Licences

Aspekta is SIL OFL-1.1 ([ivodolenc/aspekta](https://github.com/ivodolenc/aspekta)),
Roboto Mono is Apache-2.0, waveorder is BSD-3-Clause, GSAP and Lenis are free
for this use.
