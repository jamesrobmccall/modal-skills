---
name: modal-llm-serving
description: Serve open-weight LLMs on Modal with vLLM or SGLang, including OpenAI-compatible HTTP APIs, low-latency regional deployments, cold-start reduction, and throughput-oriented batch inference. Use when deploying, tuning, benchmarking, or debugging Modal-based LLM inference services. Do not use for fine-tuning, RAG, training, or broader ML pipelines.
license: MIT
metadata:
  version: "0.1.0"
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

## Examples

### Deploy an OpenAI-Compatible vLLM Endpoint

User says: "Deploy Llama 3 on Modal with an OpenAI-compatible API."

1. Confirm the workload is a standard online API.
2. Read [references/vllm-online-serving.md](references/vllm-online-serving.md).
3. Build a container image with vLLM and the model weights cached in a Volume.
4. Serve with `@modal.web_server` exposing the OpenAI-compatible endpoint.
5. Verify with a health check and a test chat completion request.

Result: A deployed Modal app serving `/v1/chat/completions` with the chosen model.

### Reduce Cold-Start Latency With Snapshots

User says: "My vLLM deployment takes too long to start up."

1. Confirm cold-start reduction is the priority.
2. Read [references/vllm-cold-starts.md](references/vllm-cold-starts.md).
3. Add memory-snapshot support with `@modal.enter(snap=True)` hooks.
4. Configure sleep/wake endpoints for idle-period hibernation.
5. Benchmark cold-start time before and after.

Result: Dramatically faster cold starts by restoring from a memory snapshot instead of re-initializing the engine.

### Run a Throughput Benchmark

User says: "I want to benchmark tokens-per-second for Qwen3 on Modal."

1. Confirm the workload is throughput or batch oriented.
2. Read [references/vllm-throughput.md](references/vllm-throughput.md).
3. Adapt [scripts/qwen3_throughput.py](scripts/qwen3_throughput.py) for the target model.
4. Run the benchmark via `modal run` and collect metrics.

Result: Tokens-per-second metrics for the model on the chosen GPU.

## Troubleshooting

### Model download fails or hangs
Ensure `HF_XET_HIGH_PERFORMANCE=1` is set. Verify the Hugging Face token has access to gated models. Check that the model weights Volume is correctly mounted.

### GPU out-of-memory errors
Reduce `gpu_memory_utilization` (default 0.90 is a safe starting point). Consider a smaller `max_model_len`, a quantized model variant, or a larger GPU.

### Cold starts still slow after adding snapshots
Verify the snapshot was actually created — check Modal dashboard for snapshot artifacts. Ensure `@modal.enter(snap=True)` and `@modal.enter(snap=False)` hooks are correctly sequenced.

### `503 Service Unavailable` from the endpoint
No replicas are live. This is expected when all containers have scaled to zero. The first request triggers a cold start; subsequent requests will be faster.

### Inconsistent or incorrect model output
Ensure the model revision is pinned. Check that chat template kwargs are set correctly (e.g., `enable_thinking` for Qwen3). Verify the prompt format matches what the model expects.

## References

- Read [references/performance-playbook.md](references/performance-playbook.md) first for objective-setting, engine selection, and tuning priorities.
- Read [references/vllm-online-serving.md](references/vllm-online-serving.md) for the default HTTP serving path.
- Read [references/vllm-cold-starts.md](references/vllm-cold-starts.md) only when cold-start reduction is worth snapshot complexity.
- Read [references/sglang-low-latency.md](references/sglang-low-latency.md) only when the task explicitly optimizes for low latency.
- Read [references/vllm-throughput.md](references/vllm-throughput.md) only when the workload is throughput or batch oriented.
- Adapt [scripts/qwen3_throughput.py](scripts/qwen3_throughput.py) for throughput-oriented batch workloads with a pinned model and local benchmark entrypoint.
