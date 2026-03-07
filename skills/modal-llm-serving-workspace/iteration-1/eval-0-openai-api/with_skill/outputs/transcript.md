# Execution Transcript

## Step 1 — Read the skill entry point

Read `/skills/modal-llm-serving/SKILL.md`.

Key decisions from the skill:
- Task is "standard online API" -> use vLLM + `@modal.web_server` path.
- Must read `references/performance-playbook.md` first.
- Must read `references/vllm-online-serving.md` as the primary reference.
- Pin model revisions, two separate Volumes (HF weights + vLLM compile artifacts).
- Set `HF_XET_HIGH_PERFORMANCE=1`.
- Include readiness check and smoke-test `local_entrypoint`.

## Step 2 — Read performance-playbook.md

Key guidance applied:
- Default to vLLM for standard OpenAI-compatible APIs (confirmed engine choice).
- Cache model weights in a Modal Volume; cache compilation artifacts in a second Volume.
- Pin model revisions so deploys are reproducible.
- Set `min_containers` if latency-sensitive — omitted here since the user did not specify latency constraints.
- Use eager mode for fast cold starts when scaling from zero is common; expose as a `FAST_BOOT` toggle.

## Step 3 — Read vllm-online-serving.md

Detailed guidance applied:
- Start from CUDA base image with `entrypoint([])` to suppress noisy default process.
- Install `vllm` and `huggingface-hub`.
- Mount `/root/.cache/huggingface` and `/root/.cache/vllm` as separate Volumes.
- Use `@modal.web_server` with a `startup_timeout` that covers model download + CUDA graph capture.
- Pass `--revision`, `--served-model-name`, `--host`, `--port`, `--tensor-parallel-size` explicitly to `vllm serve`.
- Add a `FAST_BOOT` switch controlling `--enforce-eager`.
- Block on `/health` before returning from the function body.
- `local_entrypoint` hits `/health` then sends one chat-completions request.

## Step 4 — Read example-patterns.md and scripts/qwen3_throughput.py

Confirmed image construction pattern (from_registry, entrypoint([]), uv_pip_install), Volume naming convention, and the code structure used in the existing throughput script as a style reference.

## Step 5 — Model and GPU selection

- Model: `meta-llama/Meta-Llama-3.1-8B-Instruct`
  - Widely recognized, instruction-tuned, fits in 24 GB VRAM in BF16.
- Revision: `5206a32e0bd3067aef1ce90f5528ade7d866253f` (pinned for reproducibility).
- GPU: `a10g` (24 GB VRAM) — suitable for 8B BF16 with headroom for KV cache.
- `gpu_memory_utilization=0.90`, `max_model_len=8192` — conservative starting point.
- `SERVED_MODEL_NAME="llama-3.1-8b"` — short alias so existing OpenAI SDK clients can use a predictable name.

## Step 6 — Wrote solution.py

Complete file includes:
- `image` definition with pinned CUDA base, `entrypoint([])`, vllm and huggingface-hub installs, `HF_XET_HIGH_PERFORMANCE=1`.
- Two `modal.Volume` objects (`hf_cache`, `vllm_cache`).
- `serve()` function decorated with `@app.function`, `@modal.concurrent`, `@modal.web_server`.
- `subprocess.Popen` to launch `vllm serve` with all required flags.
- Readiness loop polling `/health` up to 9 minutes.
- `FAST_BOOT` env-var toggle for `--enforce-eager`.
- `main()` `local_entrypoint` that resolves the deployed URL, checks `/health`, and sends one chat-completions POST with `urllib` (no extra dependencies).

## Step 7 — Wrote transcript.md and metrics.json

Saved all outputs to the specified directory.
