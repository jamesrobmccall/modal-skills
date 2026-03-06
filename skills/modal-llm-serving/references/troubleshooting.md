# Troubleshooting

Use this reference when the serving architecture is already chosen and the remaining work is debugging the deployment.

## Model download fails or hangs

- Ensure `HF_XET_HIGH_PERFORMANCE=1` is set when downloading from Hugging Face.
- Recheck that the token has access to gated models and that the weight-cache Volume is mounted at the expected path.

## GPU out-of-memory errors

- Lower `gpu_memory_utilization` before changing more than one variable at a time.
- Reduce `max_model_len`, use a quantized model, or move to a larger GPU when the current shape still does not fit.

## Cold starts still slow after adding snapshots

- Confirm that the snapshot was actually created in Modal.
- Recheck the sequencing of `@modal.enter(snap=True)` and `@modal.enter(snap=False)` and ensure the warmup path is deterministic.

## `503 Service Unavailable` from the endpoint

- Expect this when all containers have scaled to zero and the first request is waking the service.
- Keep a warm replica or retry through the cold-start window when the workload cannot tolerate first-request latency.

## Inconsistent or incorrect model output

- Recheck that the model revision is pinned and the prompt format matches the model's chat template.
- Verify model-specific kwargs such as `enable_thinking` before treating the issue as an engine bug.
