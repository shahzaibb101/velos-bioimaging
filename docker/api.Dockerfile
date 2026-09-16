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
# than the ~2.5 GB the default CUDA build would drag in. The learned model
# still runs through ONNX Runtime; torch is here for the comparison, not for
# inference, and `velos.baseline` degrades cleanly if it is ever dropped.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.2" \
 && pip install --no-deps "waveorder>=3" \
 && pip install "iohub>=0.2" "click" "pydantic" "numpy>=1.26"

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

# Bind to :: rather than 0.0.0.0. Railway's private network is IPv6-only, so a
# service listening on IPv4 alone resolves over internal DNS and then refuses
# the connection. A dual-stack :: bind serves both the private network and the
# public edge.
CMD ["sh", "-c", "uvicorn velos.service.api:app --host :: --port ${PORT:-8000}"]
