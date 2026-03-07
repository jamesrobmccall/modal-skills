# Transcript: Qwen3 Modal Batch Inference (without skill guidance)

## Task

Produce complete Modal + vLLM code to run offline batch inference on 50,000 documents using Qwen3, optimized for throughput rather than latency.

---

## Step 1 — Clarify requirements

The task specifies:
- **Scale**: 50,000 documents
- **Model**: Qwen3 (family); default chosen is `Qwen/Qwen3-8B` with notes for larger variants
- **Optimization goal**: throughput (tokens/second across the whole job), not per-request latency

Throughput optimization implies:
1. Large per-worker batch sizes — vLLM processes all prompts in a single `generate()` call, filling the GPU
2. Many parallel GPU workers — Modal `map()` with a high `concurrency_limit`
3. Model weight caching on a Modal Volume to avoid redundant downloads across containers
4. vLLM features that improve throughput: prefix caching, chunked prefill, bfloat16, high `gpu_memory_utilization`
5. Greedy decoding (`temperature=0.0`) — fastest generation, no sampling overhead

---

## Step 2 — Design the architecture

### Components chosen

| Component | Choice | Reason |
|---|---|---|
| Inference engine | vLLM offline (`LLM.generate`) | Best OSS throughput for transformer LLMs; continuous batching built in |
| GPU | A100-80GB | Good VRAM/throughput; lower cost than H100 for Qwen3-8B |
| Parallelism | Modal `map()` + `concurrency_limit=20` | Fan out batches across 20 simultaneous GPU containers |
| Batch size | 500 docs/worker call | Fills vLLM's request queue without OOM risk |
| Weight storage | `modal.Volume` | Download once, reuse across all containers |
| Output streaming | `order_outputs=False` | Results returned as-ready; no blocking on slowest batch |
| Decoding | Greedy (`temperature=0.0`) | Fastest; eliminates sampling overhead |

### Data flow

```
local JSONL file (50k docs)
       |
       v
   main() local_entrypoint
       |
       | split into 100 batches of 500 docs
       |
       v
  infer_batch.map()  --> up to 20 parallel GPU containers
       |                 each runs vLLM.generate() on 500 prompts at once
       |                 results streamed back as containers finish
       v
   write results.jsonl (local)
```

---

## Step 3 — Key throughput decisions

### 3a. Large batch size per worker (500 docs)

vLLM's continuous batching scheduler fills the GPU with as many sequences as VRAM allows. Giving it 500 prompts at once lets it pack the GPU far more efficiently than single-request serving. At 512 max output tokens and ~256 average input tokens for typical documents, 500 sequences fit comfortably within 80 GB.

### 3b. High gpu_memory_utilization (0.93)

vLLM pre-allocates KV cache from available GPU memory. A higher value gives more KV cache slots, enabling larger effective batch sizes and higher throughput. 0.93 leaves ~5 GB headroom for CUDA/PyTorch overhead.

### 3c. enable_prefix_caching=True

All documents share the same system prompt. Prefix caching reuses the KV cache for that common prefix, saving compute and memory on every request after the first within a container.

### 3d. enable_chunked_prefill=True + max_num_batched_tokens=8192

Chunked prefill prevents long prefill phases from starving decode steps, keeping GPU utilization smooth across heterogeneous document lengths.

### 3e. dtype="bfloat16"

Native precision for Qwen3; avoids fp16 overflow issues while delivering the same throughput as fp16 on A100/H100.

### 3f. Modal concurrency_limit=20 + map(order_outputs=False)

Twenty simultaneous A100s process 100 batches in roughly 5 parallel waves. `order_outputs=False` means results stream back as each container finishes, rather than waiting for all containers to finish before returning anything — useful for large jobs where early results can be written immediately.

### 3g. scaledown_window=120

Keeps containers alive for 2 minutes between batch assignments. For 100 batches across 20 workers, each worker gets ~5 batches; reusing a warm container avoids the ~30-60 s cold-start penalty on subsequent batches.

### 3h. Greedy decoding (temperature=0.0, top_k=-1)

Setting temperature to 0 disables sampling entirely, using argmax selection at each step. This is the fastest generation mode and produces deterministic outputs suitable for document processing tasks.

---

## Step 4 — Code structure

The solution is structured as a single `solution.py` with:

1. **`download_model()`** — Modal function that downloads weights to a shared Volume. Idempotent (checks if already cached). Called once before the batch job starts.

2. **`infer_batch(batch, system_prompt)`** — Modal function decorated with GPU, volume, and concurrency settings. Instantiates `LLM` with throughput-optimized settings, builds chat-templated prompts using the tokenizer's `apply_chat_template`, calls `llm.generate()` on the full batch, returns results.

3. **`main()`** — `@app.local_entrypoint()` that loads the JSONL, chunks it into batches, dispatches via `infer_batch.map()`, streams results back, and writes to the output file with real-time progress reporting.

4. **`generate_test_documents()`** — local helper to produce synthetic test data (50k JSONL records).

---

## Step 5 — Scaling notes

| Model | GPU | TP Size | Batch Size | Notes |
|---|---|---|---|---|
| Qwen3-8B | A100-80GB | 1 | 500 | Default config |
| Qwen3-14B | A100-80GB | 1 | 300 | Reduce batch slightly |
| Qwen3-32B | A100-80GB | 2 | 150 | 2x GPU, TP=2 |
| Qwen3-72B | H100-80GB | 4 | 100 | 4x H100, TP=4 |

Increase `MAX_CONTAINERS` up to your Modal account limit for even higher aggregate throughput.

---

## Step 6 — Estimated throughput (Qwen3-8B, A100-80GB)

| Metric | Estimate |
|---|---|
| Tokens/second per GPU (offline batch) | ~3,000-4,000 |
| 50k docs x avg 512 output tokens | ~25.6M output tokens total |
| Time per single GPU | ~6,400-8,500 s |
| Time with 20 GPUs in parallel | ~320-425 s (~5-7 minutes) |

These are rough estimates; actual throughput depends heavily on prompt/completion length distribution.

---

## Errors encountered

None. Solution written from general knowledge of Modal and vLLM APIs.

---

## Files created

- `solution.py` — complete Modal batch inference code
- `transcript.md` — this file
- `metrics.json` — tool call metrics
