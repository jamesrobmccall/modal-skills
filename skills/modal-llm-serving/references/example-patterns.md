# Example Patterns

Use this reference when the workload is already classified and a compact serving template is more helpful than reading the full primary reference first.

## `openai-compatible-vllm-api`

- Start from a CUDA image with `entrypoint([])`.
- Install `vllm` and `huggingface-hub`, mount separate Volumes for Hugging Face weights and vLLM compile artifacts, and pin the model revision.
- Expose the server with `@modal.web_server` and keep a readiness check plus one chat-completions smoke test close to the app.

## `cold-start-sensitive-vllm`

- Keep the public serving path on `@modal.web_server`.
- Start the server in `@modal.enter(snap=True)`, wait for readiness, warm it with a small deterministic request, then put it into the snapshot-friendly state before capture.
- Add a second `@modal.enter(snap=False)` hook to wake the service and block on readiness after restore.

## `low-latency-sglang`

- Start from the official SGLang runtime image and precompile kernels when the stack benefits from it.
- Use `modal.experimental.http_server`, explicit `region` and `proxy_regions`, and at least one warm replica when cold starts are unacceptable.
- Send sticky session headers from clients when multi-turn workloads should stay on the same replica.

## `throughput-benchmark-worker`

- Create the engine once in `@modal.enter`, warm it before timing, and process benchmark batches through a stable `@modal.method`.
- Log prompt tokens, completion tokens, and wall-clock duration for every batch so tuning has concrete feedback.
- Keep one local benchmark entrypoint near the worker code so the same workload can be rerun after changing model, GPU, or batch shape.
