---
name: modal-llm-serving
description: Serve open-weight LLMs on Modal with vLLM or SGLang, including OpenAI-compatible HTTP APIs, low-latency regional deployments, cold-start reduction, and throughput-oriented batch inference. Use when the user wants to deploy or serve an open-weight model (Llama, Mistral, Gemma, Qwen, Phi, Falcon, etc.) on Modal, needs an OpenAI-compatible API endpoint backed by a self-hosted model they can point their OpenAI SDK client at, is troubleshooting vLLM cold starts or OOM errors on Modal GPUs, wants to reduce cold-start time with memory snapshots or keep-warm containers, needs to optimize throughput or tokens-per-dollar for batch LLM inference on Modal, wants low-latency serving with SGLang and regional routing, or is tuning knobs like concurrent inputs, tensor parallelism, Volume caching, or GPU memory utilization for a Modal LLM service. Do not use for fine-tuning, RAG, training, or general ML pipelines.
license: MIT
---

# Modal LLM Serving

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

## Choose the Workflow

- Use vLLM with `@modal.web_server` for the default OpenAI-compatible serving path. Read [references/vllm-online-serving.md](references/vllm-online-serving.md).
- Use vLLM with memory snapshots and a sleep or wake flow only when cold-start latency is a first-class requirement. Read [references/vllm-cold-starts.md](references/vllm-cold-starts.md).
- Use SGLang with `modal.experimental.http_server`, explicit region selection, and sticky routing when the user cares most about latency. Read [references/sglang-low-latency.md](references/sglang-low-latency.md).
- Use the vLLM Python `LLM` interface inside `@app.cls` or another batch worker when the task is about tokens per second or tokens per dollar rather than HTTP serving. Read [references/vllm-throughput.md](references/vllm-throughput.md).

## Default Rules

- Pin model revisions when pulling from Hugging Face or another mutable registry.
- Cache model weights in one Modal Volume and engine compilation artifacts in another when the runtime produces them.
- Set `HF_XET_HIGH_PERFORMANCE=1` for Hub downloads unless the environment has a specific reason not to.
- Include a readiness check before reporting success. Add a smoke-test path such as a `local_entrypoint` or a small client that hits `/health` and one OpenAI-compatible request.
- Treat `max_inputs`, `target_inputs`, tensor parallelism, and related knobs as workload-specific. Start conservative and benchmark before increasing them.
- Expose only the ports and endpoints the task actually needs.
- Keep one serving pattern per file unless the user explicitly asks for a comparison artifact or benchmark harness.
- Use SGLang only when lowest latency is the explicit objective and the extra setup is justified.
- Use the vLLM Python `LLM` interface only for offline or batch inference that does not need per-request HTTP behavior.
- Use snapshot-based cold-start reduction only when startup latency matters enough to justify extra operational complexity.

## Validate

- Run `npx skills add . --list` after editing the package metadata or skill descriptions.
- Run `python3 -m py_compile skills/modal-llm-serving/scripts/qwen3_throughput.py` when changing the throughput artifact.

## References

- Read [references/performance-playbook.md](references/performance-playbook.md) first for objective-setting, engine selection, and tuning priorities.
- Read [references/vllm-online-serving.md](references/vllm-online-serving.md) for the default HTTP serving path.
- Read [references/vllm-cold-starts.md](references/vllm-cold-starts.md) only when cold-start reduction is worth snapshot complexity.
- Read [references/sglang-low-latency.md](references/sglang-low-latency.md) only when the task explicitly optimizes for low latency.
- Read [references/vllm-throughput.md](references/vllm-throughput.md) only when the workload is throughput or batch oriented.
- Read [references/example-patterns.md](references/example-patterns.md) for compact serving templates and adaptation paths.
- Read [references/troubleshooting.md](references/troubleshooting.md) for common serving failures and recovery steps.
- Adapt [scripts/qwen3_throughput.py](scripts/qwen3_throughput.py) for throughput-oriented batch workloads with a pinned model and local benchmark entrypoint.
