---
name: modal-llm-serving
description: Serve open-weight LLMs on Modal with vLLM or SGLang, including OpenAI-compatible HTTP APIs, low-latency regional deployments, cold-start reduction, and throughput-oriented batch inference. Use when Codex needs to deploy, tune, benchmark, or debug Modal-based LLM inference services, especially for vLLM, SGLang, modal.web_server, modal.experimental.http_server, Volumes, snapshots, concurrent inputs, or OpenAI-compatible endpoints. Do not use this skill for fine-tuning, RAG, training, or broader ML pipelines.
---

# Modal LLM Serving

## Overview

Use this skill when the task is to serve an LLM on Modal. Keep it focused on inference and serving architecture; if the real task is fine-tuning, RAG, training, or a broader ML workflow, treat those parts as out of scope.

## Quick Start

1. Confirm the workload goal before writing code:
   - standard online API
   - cold-start-sensitive vLLM deployment
   - low-latency interactive serving
   - high-throughput batch inference
2. Read [references/performance-playbook.md](references/performance-playbook.md).
3. Read exactly one primary reference:
   - Standard online API: [references/vllm-online-serving.md](references/vllm-online-serving.md)
   - Cold starts: [references/vllm-cold-starts.md](references/vllm-cold-starts.md)
   - Low latency: [references/sglang-low-latency.md](references/sglang-low-latency.md)
   - Throughput or batch inference: [references/vllm-throughput.md](references/vllm-throughput.md)
4. Default to vLLM plus `@modal.web_server` unless the user explicitly optimizes for lowest latency or offline throughput.
5. Ground every implementation in the actual workload: target latency or throughput, model size and precision, GPU type and count, region, concurrency target, and cold-start tolerance.

## Default Rules

- Pin model revisions when pulling from Hugging Face or another mutable registry.
- Cache model weights in a Modal Volume. Cache engine compilation artifacts in a separate Volume when the engine produces them.
- Turn on `HF_XET_HIGH_PERFORMANCE=1` for Hub downloads unless there is a specific reason not to.
- Include a readiness check before reporting success. When authoring code, include a smoke-test path such as a `local_entrypoint` or a small client that hits `/health` and one OpenAI-compatible chat request.
- Treat `max_inputs`, `target_inputs`, tensor parallelism, and similar knobs as workload-specific. Start conservative and benchmark before increasing them.
- Expose only the ports and endpoints the task actually needs.
- Keep one serving pattern per file unless the user explicitly asks for a comparison artifact or benchmark harness.
- Use SGLang only when the task explicitly prioritizes lowest latency and can tolerate a more advanced setup.
- Use vLLM `LLM` style batch processing only when the task is offline or batch oriented and does not need per-request HTTP behavior.
- Use snapshot-based cold-start reduction only when startup latency matters enough to justify extra complexity.

## Choose the Workflow

### Standard Online API

Use vLLM with `@modal.web_server` for the default OpenAI-compatible serving path. Read [references/vllm-online-serving.md](references/vllm-online-serving.md).

### Cold-Start-Sensitive vLLM

Use vLLM with memory snapshots and a sleep or wake flow only when cold-start latency is a first-class requirement. Read [references/vllm-cold-starts.md](references/vllm-cold-starts.md).

### Low-Latency Interactive Serving

Use SGLang with `modal.experimental.http_server`, explicit region selection, and sticky routing when the user cares most about latency. Read [references/sglang-low-latency.md](references/sglang-low-latency.md).

### High-Throughput Batch Inference

Use vLLM `LLM` inside `@app.cls` or another batch worker when the task is about tokens per second or tokens per dollar rather than HTTP serving. Read [references/vllm-throughput.md](references/vllm-throughput.md).

## References

- Read [references/performance-playbook.md](references/performance-playbook.md) first for objective-setting, engine selection, and tuning priorities.
- Read [references/vllm-online-serving.md](references/vllm-online-serving.md) for the default HTTP serving path.
- Read [references/vllm-cold-starts.md](references/vllm-cold-starts.md) only when cold-start reduction is worth snapshot complexity.
- Read [references/sglang-low-latency.md](references/sglang-low-latency.md) only when the task explicitly optimizes for low latency.
- Read [references/vllm-throughput.md](references/vllm-throughput.md) only when the workload is throughput or batch oriented.
