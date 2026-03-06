# SGLang Low Latency

Use this reference only when the user explicitly wants the lowest possible latency from a Modal-hosted LLM service.

## Container and Cache Setup

- Start from the official SGLang runtime image instead of assembling the runtime from scratch.
- Add `huggingface-hub` if the image does not already provide it.
- Mount one Volume for Hugging Face weights and a second Volume for DeepGEMM or other JIT-compiled kernels.
- Set `HF_HUB_CACHE` and `HF_XET_HIGH_PERFORMANCE=1` so downloads land in the mounted cache and use fast transfers.

## Compile Ahead of Traffic

- Precompile DeepGEMM kernels during image build with `Image.run_function(..., gpu=...)` so first request latency does not pay that cost.
- Keep the model revision pinned during that compile step and at runtime.
- Treat the compile cache as required infrastructure, not an optional optimization.

## Infrastructure Pattern

- Use `@app.cls(...)` to make GPU, region, cache Volumes, and minimum container count explicit.
- Use `@modal.experimental.http_server(...)` instead of `@modal.web_server` for the low-latency routing path.
- Keep `region` and `proxy_regions` aligned with the client geography.
- Set `min_containers >= 1` in production when cold starts are unacceptable.
- Use `@modal.concurrent(target_inputs=...)` only after benchmarking the intended request shape.

## Latency-Specific Tuning

- Use tensor parallelism when the extra GPUs improve latency enough to justify the cost.
- Consider speculative decoding only for low-concurrency, memory-bound workloads.
- Avoid speculative decoding for large-batch throughput workloads.
- Leave room in GPU memory for speculative models or extra runtime state when the chosen technique requires it.

## Readiness and Client Behavior

- Start the SGLang server in `@modal.enter`, then block until localhost health checks pass.
- Warm the server with a few short requests before sending real traffic.
- Send `Modal-Session-ID` from clients so multi-turn traffic sticks to the same replica and improves KV-cache hit rate.
- Expect `503 Service Unavailable` when no replicas are live; keep warm containers or retry during cold starts.

## When Not to Use This Path

- Prefer the standard vLLM path for simpler deployments and broader serving coverage.
- Prefer the throughput path for offline batch inference.
