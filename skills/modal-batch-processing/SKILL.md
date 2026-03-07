---
name: modal-batch-processing
description: Design and debug Modal batch workloads using `.map`, `.starmap`, `.spawn`, `.spawn_map`, and `@modal.batched`. Use this skill whenever the user wants to process many items (images, documents, audio, records) in parallel across Modal workers and collect results, needs to submit a long-running job from a web server without blocking the request and return a job ID the caller can poll, wants to fan out work across Modal containers with .map or spawn tasks in the background with .spawn, needs to handle partial failures or retries in a Modal batch job, wants to rate-limit or cap the number of concurrent Modal containers, needs to coalesce many small requests into fewer GPU calls with @modal.batched, or is asking about the difference between .map, .spawn, and .spawn_map on Modal. Do not use for vLLM or SGLang inference services.
license: MIT
---

# Modal Batch Processing

## Quick Start

1. Verify the actual local Modal environment before writing code.

```bash
modal --version
python -c "import modal,sys; print(modal.__version__); print(sys.executable)"
modal profile current
```

- Do not assume the default `python` interpreter matches the environment behind the `modal` CLI.
- Switch to the project virtualenv or the interpreter behind the installed `modal` CLI before writing examples or running scripts.
- Use `with modal.enable_output():` around `with app.run():` when local provisioning logs or remote prints are needed for debugging.

2. Pick the workflow before writing code and read the matching reference.

## Choose the Workflow

- Use `.map` or `.starmap` when the caller needs results back in-process and can wait for completion. Read [references/map-and-gather.md](references/map-and-gather.md).
- Use `.spawn` when the job should run asynchronously and the caller needs a job ID for polling or later collection. Read [references/job-queues-and-detached-runs.md](references/job-queues-and-detached-runs.md).
- Use `.spawn_map` for detached fire-and-forget fan-out where results are written to a Volume, Cloud Bucket Mount, database, or another external sink. Read [references/job-queues-and-detached-runs.md](references/job-queues-and-detached-runs.md).
- Use `@modal.batched` when many small, homogeneous requests should be coalesced into fewer executions. Read [references/dynamic-batching.md](references/dynamic-batching.md).

## Default Rules

- Start with plain `@app.function` functions for stateless work. Move to `@app.cls` only when the container must reuse loaded state or expensive initialization.
- Keep orchestration local with `@app.local_entrypoint` or a plain Python script plus `with app.run():` when the entire workflow can stay within one session.
- Deploy with `modal deploy` and use `modal.Function.from_name(...)` when another service must submit jobs or look up a stable remote function later.
- Set `timeout=` intentionally on remote work. Add `retries=` only when the work is idempotent and safe to re-run.
- Set `max_containers=` when upstream systems, GPU quotas, or external APIs need a hard concurrency cap.
- Persist outputs externally whenever the job may outlive the caller or when using `.spawn_map`.
- Use Volumes or CloudBucketMounts for durable caches, model weights, and shared intermediates; do not rely on ephemeral container disk.
- Prefer `.map` or `.starmap` over `.spawn` when the caller genuinely needs the results immediately and no durable job handle is required.
- Prefer `.spawn` over `.map` when the caller needs a stable job ID or should return before the remote work finishes.
- Treat `.spawn_map()` as detached fire-and-forget in Modal 1.3.4. The installed SDK docstring says programmatic result retrieval is not supported, so only use it when each task writes its output elsewhere.

## Validate

- Run `npx skills add . --list` after editing the package metadata or skill descriptions.
- Run [scripts/smoke_test.py](scripts/smoke_test.py) with a Python interpreter that can import `modal` when changing the workflow guidance or runnable artifact.

## References

- Read [references/map-and-gather.md](references/map-and-gather.md) for synchronous fan-out and in-process result collection.
- Read [references/job-queues-and-detached-runs.md](references/job-queues-and-detached-runs.md) for deployed job queues, job IDs, detached runs, and external result sinks.
- Read [references/dynamic-batching.md](references/dynamic-batching.md) for `@modal.batched` contracts and tuning.
