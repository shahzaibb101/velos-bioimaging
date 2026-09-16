# Served model

`phase_refiner.onnx` and `model-card.json` live here. They are produced by

```bash
python -m velos.training.export
```

which refuses to write a model whose ONNX graph disagrees with the checkpoint
it came from, and generates the card from the same run that produced the
weights so the two cannot drift apart.

The torch checkpoint is deliberately not committed: the service loads ONNX, and
shipping both would put a gigabyte of PyTorch into a container that does not
need it.

If no model is present the service still runs. It serves the classical and
waveorder reconstructions and reports that the learned refinement is
unavailable, rather than failing the request.
