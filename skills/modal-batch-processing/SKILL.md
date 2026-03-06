---
name: modal-batch-processing
description: Design, implement, debug, and validate Modal batch-processing workflows for CPU or GPU jobs, including `.map` and `.starmap` fan-out, `.spawn` job queues, `.spawn_map` detached runs, and `@modal.batched` dynamic batching. Use when Codex needs to orchestrate large or bursty workloads on Modal, choose between ephemeral and deployed apps, retrieve async results, or tune retries, timeouts, `max_containers`, Volumes, or external result sinks. Do not use this skill for vLLM or SGLang serving architecture; use `modal-llm-serving` for LLM-serving-specific work.
---

# Modal Batch Processing

## Overview

Use this skill to choose the correct Modal batch primitive before writing code. Keep it focused on orchestration and batch execution patterns rather than model-serving internals.

If the task is really about vLLM throughput, SGLang latency, OpenAI-compatible endpoints, or LLM cold starts, switch to `modal-llm-serving` instead of expanding this skill’s scope.

## Quick Start

1. Verify the actual local Modal environment before writing code.

```bash
modal --version
/Users/jmccall/.local/pipx/venvs/modal/bin/python -c "import modal,sys; print(modal.__version__); print(sys.executable)"
modal profile current
```

- Do not assume `python3` can import `modal` just because the `modal` CLI exists.
- In this repo, prefer `/Users/jmccall/.local/pipx/venvs/modal/bin/python` unless the active project venv already imports `modal`.
- Use `with modal.enable_output():` around `with app.run():` when local provisioning logs or remote prints are needed for debugging.

2. Pick the workflow before writing code.

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

## Example Anchors

- Use Modal’s document OCR jobs example as the reference pattern for deployed `.spawn` workflows that are triggered from an external application.
- Use Modal’s batched Whisper example as the reference pattern for `@modal.batched` on `@app.cls`.
- Use Modal’s vLLM throughput example only as a cross-reference when the workload is actually LLM throughput or serving; in that case, switch to `modal-llm-serving`.

## Validate

- Run [scripts/smoke_test.py](scripts/smoke_test.py) with the Modal-importing interpreter to verify `.map`, `.starmap`, `.spawn`, `FunctionCall.from_id(...).get()`, and a CPU-only `@modal.batched` class method.
- Run the validator after editing:

```bash
python3 /Users/jmccall/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/modal-batch-processing
```

## References

- Read [references/map-and-gather.md](references/map-and-gather.md) for synchronous fan-out and in-process result collection.
- Read [references/job-queues-and-detached-runs.md](references/job-queues-and-detached-runs.md) for deployed job queues, job IDs, detached runs, and external result sinks.
- Read [references/dynamic-batching.md](references/dynamic-batching.md) for `@modal.batched` contracts and tuning.
