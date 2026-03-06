# vLLM Throughput

Use this reference for offline or batch inference where the goal is maximum tokens per second or tokens per dollar, not a public HTTP API.

## Engine Choice

- Use the vLLM Python `LLM` interface inside Modal, not `vllm serve`, when you want synchronous batch processing with minimal request-management overhead.
- Wrap the engine in `@app.cls(...)` so initialization and teardown happen once per replica.
- Create and warm the engine in `@modal.enter`.
- Process batches in a `@modal.method`.
- Release the engine in `@modal.exit`.
- Pin mutable Hugging Face inputs directly in `vllm.LLM(...)` with `revision=` and `tokenizer_revision=` when the model repo can change over time.

## Hardware Defaults

- Default to one GPU per replica for throughput per dollar unless the model does not fit.
- Add more GPUs when the model requires it or when single-request latency matters more than efficiency.
- Prefer Hopper-class GPUs for FP8-friendly models when the model and workload support them.
- For small FP8 models, start with a single H100 before exploring multi-GPU replicas to keep the deployment compute-bound.

## Throughput Knobs

- Set `max_model_len` from the actual prompt distribution instead of leaving it overly large.
- Use `attention_backend="flashinfer"` when targeting throughput-oriented offline serving.
- Enable `async_scheduling=True` when the model and feature set support it.
- Consider `gpu_memory_utilization` explicitly once you know the prompt and output length distribution; keep it conservative until the workload is stable.
- Warm the engine with a small request before timing production batches.
- For Qwen3 chat workloads where reasoning quality is not the goal, prefer `chat_template_kwargs={"enable_thinking": False}` in `LLM.chat(...)`; prompt-level `/no_think` can still leave an empty `<think></think>` wrapper in the output.

## Orchestration Pattern

- Fan work out into batches that are large enough to expose parallelism but still fit comfortably in memory.
- Use `.spawn` and `modal.FunctionCall.gather` or an equivalent orchestration path for detached batch processing.
- Log prompt-token and output-token counts with wall-clock duration so tuning has concrete feedback.
- Keep the output contract simple and stable so batching changes do not force upstream code changes.
- Keep a local benchmark harness close to the worker code so you can rerun the same batch shape after changing model, GPU, or sequence-length settings.
- For a single-GPU throughput benchmark, let one warm worker process all benchmark batches sequentially; spawning a fresh worker per batch mostly measures cold starts and compile overhead.

## When Not to Use This Path

- Use the standard vLLM HTTP path when users need an API endpoint.
- Avoid speculative or low-latency-specific tuning here; those knobs solve a different objective.

## Example Artifact

- See `scripts/qwen3_throughput.py` for a throughput-oriented Modal example built around `Qwen/Qwen3-1.7B-FP8`, a pinned model revision, one H100 GPU, FlashInfer, async scheduling, warm-up, and an end-to-end benchmark entrypoint.
