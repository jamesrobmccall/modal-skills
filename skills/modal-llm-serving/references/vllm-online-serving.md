# vLLM Online Serving

Use this reference for the default Modal LLM serving path: an OpenAI-compatible HTTP API backed by vLLM.

## Container and Model Setup

- Start from a CUDA base image with `entrypoint([])` so the container does not inherit a noisy default process.
- Install `vllm` and `huggingface-hub` in the image.
- Set `HF_XET_HIGH_PERFORMANCE=1` for faster model downloads.
- Pin the model revision when serving from Hugging Face.

## Cache Layout

- Mount one Volume for Hugging Face weights, usually at `/root/.cache/huggingface`.
- Mount a second Volume for vLLM compilation artifacts, usually at `/root/.cache/vllm`.
- Keep the weight cache and compile cache separate so they can be reasoned about independently.

## Serving Pattern

- Use a Modal Function decorated with `@modal.web_server`.
- Add `@modal.concurrent(max_inputs=...)` only after choosing a target based on the workload.
- Start `vllm serve` in a subprocess that listens on `0.0.0.0` and the port exposed by `@modal.web_server`.
- Pass `--revision`, `--served-model-name`, `--host`, `--port`, and `--tensor-parallel-size` explicitly.

## Fast Boot vs Warm Performance

- Add a `FAST_BOOT` switch or equivalent deployment choice.
- Use `--enforce-eager` when the service often scales from zero and startup time matters most.
- Use `--no-enforce-eager` when warm performance matters more than boot speed.
- Treat this choice as workload-specific; do not hard-code it without a reason.

## Verification

- Include a readiness check against `/health` before declaring the service ready.
- Include a `local_entrypoint` or a small client that sends one OpenAI-compatible chat request after the health check passes.
- Prefer streaming chat-completions testing when the user cares about incremental output behavior.

## When Not to Use This Path

- Switch to the low-latency SGLang path when latency is the primary service objective.
- Switch to the throughput path when the workload is offline or batch oriented and does not need HTTP semantics.
