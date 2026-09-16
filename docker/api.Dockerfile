# Reconstruction service.
#
# Build context is the repository root so this image can take the science
# package and the service layer together; they are one Python package and
# splitting them across build contexts would mean vendoring one into the other.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Each request already runs on its own worker thread. Letting BLAS spawn a
    # full thread pool per request as well oversubscribes the container and
    # makes everything slower under any concurrency at all.
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2

WORKDIR /srv

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl \
 && rm -rf /var/lib/apt/lists/*

COPY server/pyproject.toml ./
COPY server/velos ./velos

# Serving needs numpy, scipy, scikit-image and onnxruntime. It deliberately
# does not need PyTorch: the model ships as ONNX, which keeps this image about
# a gigabyte smaller than it would otherwise be.
RUN pip install --upgrade pip \
 && pip install "numpy>=1.26" "scipy>=1.11" "scikit-image>=0.22" \
                "tifffile>=2024.1.30" "imagecodecs>=2024.1.1" "Pillow>=10.2" \
                "fastapi>=0.110" "uvicorn[standard]>=0.27" "onnxruntime>=1.17" \
                "python-multipart>=0.0.9"

# waveorder is the published baseline and is built on PyTorch, so the CPU-only
# wheel comes in for it alone. From the CPU index this is roughly 200 MB rather
# than the ~2.5 GB the default CUDA build would drag in.
#
# Installed with --no-deps deliberately. waveorder declares seventeen
# dependencies including pyqtgraph, qtpy, ipywidgets, tensorboard and matplotlib
# — a Qt and notebook stack for its GUI that a headless reconstruction service
# will never touch. Tracing the actual import chain for the phase model shows it
# needs numpy, scipy, torch, pywt and tqdm, so those are what get installed.
#
# The learned model still runs through ONNX Runtime; torch is here for the
# comparison, not for inference, and velos.baseline degrades cleanly without it.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2" \
 && pip install --no-deps "waveorder>=3" \
 && pip install "pywavelets>=1.1.1" "tqdm"

RUN pip install --no-deps -e .

COPY server/models ./models
COPY server/data/samples ./data/samples

ENV VELOS_DATA=/srv/data/samples \
    VELOS_MODELS=/srv/models \
    VELOS_WORKERS=2 \
    PORT=8000

EXPOSE 8000

# No Docker HEALTHCHECK here. The platform runs its own probe, and a
# container-level check that curls 127.0.0.1 against a socket bound to :: can
# report the container unhealthy while the service is answering perfectly well
# on every address that matters.

# Bind on IPv4. Railway's private network is IPv6, so an IPv6-only bind is the
# tidier answer in principle, but uvicorn sets IPV6_V6ONLY on that socket and
# the public edge then cannot reach the service at all. The site talks to this
# over its public domain, so IPv4 is what actually matters here.
CMD ["sh", "-c", "uvicorn velos.service.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
