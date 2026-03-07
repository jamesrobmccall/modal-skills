# Execution Transcript — Batch Inference on 50k Documents with Qwen3

## Step 1: Read SKILL.md

Read `/skills/modal-llm-serving/SKILL.md`. Key guidance extracted:

- Workload is "high-throughput batch inference" -> read `vllm-throughput.md` and `performance-playbook.md`
- Use vLLM Python `LLM` interface (not HTTP) for offline batch
- Pin model revisions with `revision=` and `tokenizer_revision=` in `vllm.LLM(...)`
- Cache weights in a Modal Volume; cache compilation artifacts in a second Volume
- Set `HF_XET_HIGH_PERFORMANCE=1` for faster HF Hub downloads
- Include a `local_entrypoint` as the smoke-test / orchestration entry
- Adapt `scripts/qwen3_throughput.py` as the reference artifact

## Step 2: Read the reference script

Read `scripts/qwen3_throughput.py`. Identified the canonical pattern:

- `modal.Image` based on `nvidia/cuda:12.9.0-devel-ubuntu22.04` + `add_python="3.13"`
- `vllm==0.13.0` installed via `uv_pip_install`
- Two Volumes: `hf_cache` (model weights) and `vllm_cache` (engine artifacts)
- `@app.cls` with `@modal.enter` / `@modal.exit` lifecycle methods
- `vllm.LLM(model=..., revision=..., tokenizer_revision=..., **VLLM_KWARGS)`
- VLLM_KWARGS: `flashinfer`, `async_scheduling=True`, `gpu_memory_utilization=0.95`
- Warmup: small `.chat()` call in `@modal.enter` before timing real batches
- `chat_template_kwargs={"enable_thinking": False}` to suppress Qwen3 reasoning traces
- `sampling_params` with temperature, top_p, top_k
- `.spawn()` + `.get()` for detached execution from `local_entrypoint`

## Step 3: Read vllm-throughput.md

Key rules for the batch pattern:

- One GPU per replica is the right default for throughput-per-dollar
- `attention_backend="flashinfer"` and `async_scheduling=True` for offline serving
- Set `max_model_len` from actual prompt distribution (not the model maximum)
- Warm the engine with a dummy request before timing production batches
- Fan work into batches large enough for parallelism but fitting in memory
- Use `.spawn` and `modal.FunctionCall.gather` (or `.map`) for detached batch processing
- Log prompt-token and output-token counts with wall-clock duration for tuning
- For a single-GPU throughput run, process multiple sub-batches sequentially in one warm worker (spawning a fresh worker per sub-batch mostly measures cold starts)

## Step 4: Read performance-playbook.md

Confirmed:

- Engine selection: vLLM Python LLM interface for offline/batch
- Caching: two Volumes (weights + compilation artifacts)
- Model pinning for reproducibility
- `HF_XET_HIGH_PERFORMANCE=1` for faster Hub transfers
- Prefer smaller/lower-precision models before scaling GPU count when cost matters
- Benchmark with representative prompts before tuning knobs

## Step 5: Design decisions for 50k documents

### Model choice: Qwen3-8B-FP8 (not 1.7B)

The reference script uses `Qwen3-1.7B-FP8` as a quick benchmark target. For a
production 50k document job, 8B gives substantially better summarization quality.
8B FP8 still fits on a single H100 (80 GB) with room for a healthy KV cache.
Revision pinned to `35af3b1c0ad30c8285fa8be5a5eb53e7d9e2ab7a` (user should
verify/update against HF hub: `huggingface-cli api Qwen/Qwen3-8B-FP8 --field sha`).

### Fan-out strategy: .map across worker replicas

The reference script uses a single worker processing all batches sequentially.
For 50k documents at scale, multiple concurrent replicas reduce wall-clock time.

Design:
- `DOCS_PER_SHARD = 2_000` -> 25 shards for 50k docs
- `worker.process_shard.map(shard_ids, doc_starts, doc_counts, kwargs=...)` launches
  all 25 containers in parallel; each gets its own H100 and warm vLLM engine
- Results returned in input order once all shards finish
- `.map` chosen over manual `.spawn` + `modal.FunctionCall.gather` as it is
  idiomatic Modal and handles ordering automatically

### Per-worker sub-batching

Each shard of 2,000 docs is processed in sub-batches of 512 prompts per
`.chat()` call. This:
- Keeps individual vLLM calls a manageable size for the KV cache
- Allows per-batch progress logging visible in Modal container logs
- Matches the pattern from the reference script's `_run_batch` helper

### Throughput knobs

| Knob | Value | Rationale |
|---|---|---|
| `max_model_len` | 4096 | Conservative for summarization; increase if corpus has longer docs |
| `gpu_memory_utilization` | 0.93 | Slightly below reference's 0.95 for stable headroom on 8B model |
| `attention_backend` | flashinfer | Best throughput for offline batches per vllm-throughput.md |
| `async_scheduling` | True | Overlaps scheduling with execution |
| `tensor_parallel_size` | 1 | One H100 per replica — efficient for 8B FP8, optimal tokens/dollar |
| `temperature` | 0.3 | Lower than reference's 0.7 — appropriate for deterministic summarization |
| `enable_thinking` | False | Suppresses Qwen3 CoT, reduces output tokens and latency |

### Volume naming

`qwen3-8b-fp8-huggingface-cache` and `qwen3-8b-fp8-vllm-cache` — model-specific
names prevent cache conflicts if multiple models are deployed to the same account.

### Document loader

`load_documents(start, count)` is a documented placeholder generating synthetic docs.
Comments explain how to replace it with S3, a Modal Volume, or a database.
This is the only part of the code users need to modify for their real corpus.

### local_entrypoint parameters

All parameters are overridable via CLI flags:
```
modal run solution.py
modal run solution.py --total-docs 50000 --docs-per-shard 2000
modal run solution.py --docs-per-shard 5000  # fewer, larger shards
```

Printed summary includes end-to-end throughput, tokens/sec, docs/sec, and
per-shard breakdown for tuning.

## Step 6: Verified the solution covers all requirements

- [x] vLLM Python LLM interface (not HTTP) — `vllm.LLM` inside `@app.cls`
- [x] Fan out across Modal workers — `worker.process_shard.map(...)`
- [x] local_entrypoint — `@app.local_entrypoint() def main(...)`
- [x] Pinned Qwen3 revision — `MODEL_REVISION` constant passed to `vllm.LLM` as `revision=` and `tokenizer_revision=`
- [x] Volume-cached weights — two `modal.Volume.from_name(...)` mounts
- [x] Optimized for throughput — flashinfer, async_scheduling, warmup, sub-batching, FP8 on H100
- [x] 50k document scale — sharding with configurable `docs_per_shard`

## Key files read

1. `/skills/modal-llm-serving/SKILL.md`
2. `/skills/modal-llm-serving/scripts/qwen3_throughput.py`
3. `/skills/modal-llm-serving/references/vllm-throughput.md`
4. `/skills/modal-llm-serving/references/performance-playbook.md`
