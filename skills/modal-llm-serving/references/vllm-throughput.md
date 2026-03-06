# vLLM Throughput

Use this reference for offline or batch inference where the goal is maximum tokens per second or tokens per dollar, not a public HTTP API.

## Engine Choice

- Use the vLLM Python `LLM` interface inside Modal, not `vllm serve`, when you want synchronous batch processing with minimal request-management overhead.
- Wrap the engine in `@app.cls(...)` so initialization and teardown happen once per replica.
- Create and warm the engine in `@modal.enter`.
- Process batches in a `@modal.method`.
- Release the engine in `@modal.exit`.

## Hardware Defaults

- Default to one GPU per replica for throughput per dollar unless the model does not fit.
- Add more GPUs when the model requires it or when single-request latency matters more than efficiency.
- Prefer Hopper-class GPUs for FP8-friendly models when the model and workload support them.

## Throughput Knobs

- Set `max_model_len` from the actual prompt distribution instead of leaving it overly large.
- Use `attention_backend="flashinfer"` when targeting throughput-oriented offline serving.
- Enable `async_scheduling=True` when the model and feature set support it.
- Warm the engine with a small request before timing production batches.

## Orchestration Pattern

- Fan work out into batches that are large enough to expose parallelism but still fit comfortably in memory.
- Use `.spawn` and `modal.FunctionCall.gather` or an equivalent orchestration path for detached batch processing.
- Log prompt-token and output-token counts with wall-clock duration so tuning has concrete feedback.
- Keep the output contract simple and stable so batching changes do not force upstream code changes.

## When Not to Use This Path

- Use the standard vLLM HTTP path when users need an API endpoint.
- Avoid speculative or low-latency-specific tuning here; those knobs solve a different objective.
