# Performance Playbook

Use this reference first to classify the serving problem before choosing an engine or deployment pattern.

## Start With the Objective

- Optimize throughput, latency, and cold starts separately; they do not share one best configuration.
- Ask whether the workload is an always-on API, a bursty API that scales from zero, or an offline or batch job.
- Keep tuning tied to representative prompts and concurrency, not generic benchmarks alone.

## Choose the Engine

- Default to vLLM for most Modal LLM serving tasks, especially standard OpenAI-compatible APIs and batch inference.
- Choose SGLang only when the user explicitly needs the lowest possible latency and can accept a more advanced setup.
- Choose the vLLM Python `LLM` interface instead of an HTTP server for offline or batch inference where per-request streaming is not required.

## Choose the Model and GPU Together

- Ensure the model weights and a useful KV cache fit on the chosen GPU.
- Prefer a smaller or lower-precision model before scaling GPU count when cost matters.
- Prefer Hopper-class or newer GPUs for FP8 serving when the model supports it.
- Add GPUs first for model fit or latency, not automatically for throughput per dollar.

## Cache Aggressively

- Cache model weights in a Modal Volume instead of redownloading them on every container start.
- Cache engine compilation artifacts separately when the engine produces them, such as vLLM or DeepGEMM caches.
- Pin model revisions so deploys stay reproducible when upstream repos change.
- Turn on `HF_XET_HIGH_PERFORMANCE=1` for faster Hugging Face transfers when using the Hub.

## Benchmark Before Turning Knobs

- Measure startup time, time to first token, steady-state tokens per second, queueing, and error rate.
- Tune `max_inputs` or `target_inputs` with representative prompts; large settings can hurt latency or stability.
- Set `min_containers` when latency-sensitive traffic cannot tolerate cold starts.
- Keep the benchmark harness close to the actual serving code, such as a `local_entrypoint` or a small client.

## Handle Cold Starts Deliberately

- Use eager mode or similar fast-boot settings when the service often scales from zero.
- Keep one warm replica for latency-sensitive production traffic before reaching for snapshot-based complexity.
- Use memory snapshots only when startup latency is worth the additional operational constraints.
