#!/usr/bin/env python3
"""
Offline batch inference on 50,000 documents using Qwen3 on Modal.
Optimized for throughput (tokens/sec, tokens/dollar) — not latency.

Architecture:
- vLLM Python LLM interface (not HTTP) inside @app.cls
- Multiple Modal worker replicas process document shards in parallel via .map
- Weights and vLLM compilation artifacts cached in Modal Volumes
- Pinned Qwen3 model revision for reproducible deploys
- local_entrypoint fans out to workers, gathers and prints aggregate metrics
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

import modal

MINUTES = 60

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_NAME = "qwen3-batch-50k"
GPU = "h100"

# Qwen3-8B-FP8: fits on one H100, FP8-native, strong quality for doc processing.
MODEL_NAME = "Qwen/Qwen3-8B-FP8"
# Pin the revision — HF repos are mutable; this keeps deploys reproducible.
# Verify / update via: huggingface-cli api Qwen/Qwen3-8B-FP8 --field sha
MODEL_REVISION = "35af3b1c0ad30c8285fa8be5a5eb53e7d9e2ab7a"

# Throughput knobs — tune to your actual document distribution.
WORKER_BATCH_SIZE = 512    # prompts per vLLM .chat() call inside each worker
DOCS_PER_SHARD = 2_000     # documents handled by each Modal container (shard)
TOTAL_DOCS = 50_000        # total corpus size
MAX_MODEL_LEN = 4096       # set from prompt distribution; increase for longer docs
MAX_TOKENS = 256           # max output tokens per document

SYSTEM_PROMPT = (
    "You are a concise analytical assistant. Summarize the key points of the "
    "provided document in 3-5 sentences. Be precise and factual."
)

# ---------------------------------------------------------------------------
# Modal image: CUDA 12.9 + vLLM 0.13.0 + fast HF transfers
# ---------------------------------------------------------------------------

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.9.0-devel-ubuntu22.04",
        add_python="3.13",
    )
    .entrypoint([])
    .uv_pip_install("vllm==0.13.0", "huggingface-hub==0.36.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

app = modal.App(APP_NAME)

# ---------------------------------------------------------------------------
# Modal Volumes: cache weights and vLLM compilation artifacts across restarts
# ---------------------------------------------------------------------------

hf_cache = modal.Volume.from_name(
    "qwen3-8b-fp8-huggingface-cache",
    create_if_missing=True,
)
vllm_cache = modal.Volume.from_name(
    "qwen3-8b-fp8-vllm-cache",
    create_if_missing=True,
)

# ---------------------------------------------------------------------------
# vLLM engine settings (throughput-oriented)
# ---------------------------------------------------------------------------

VLLM_KWARGS: dict[str, Any] = {
    "max_model_len": MAX_MODEL_LEN,
    "attention_backend": "flashinfer",   # best throughput for offline batches
    "async_scheduling": True,            # overlaps scheduling with execution
    "gpu_memory_utilization": 0.93,      # leave headroom; increase once workload is stable
    "tensor_parallel_size": 1,           # one H100 per replica — efficient for 8B FP8
}

CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}  # suppress reasoning traces
EMPTY_THINK_RE = re.compile(r"^<think>\s*</think>\s*", re.DOTALL)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ShardMetrics:
    shard_id: int
    num_docs: int
    num_batches: int
    duration_s: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_tokens_per_s: float


def sampling_params_kwargs(max_tokens: int) -> dict[str, Any]:
    return {
        "max_tokens": max_tokens,
        "temperature": 0.3,   # lower temp for summarization — more deterministic
        "top_p": 0.9,
        "top_k": 50,
    }


def strip_empty_think_block(text: str) -> str:
    return EMPTY_THINK_RE.sub("", text).strip()


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


# ---------------------------------------------------------------------------
# Document loader (replace with your real corpus source)
# ---------------------------------------------------------------------------

def load_documents(start: int, count: int) -> list[str]:
    """
    Return `count` document strings starting at offset `start`.

    Replace this function with your real data source:
      - Read from a Modal Volume containing your corpus files
      - Pull from S3 / GCS via boto3 or google-cloud-storage
      - Query a database or object store
    The function must return plain text strings, one per document.
    """
    filler = (
        "The quarterly earnings report shows a 12% revenue increase driven by "
        "strong product adoption in the enterprise segment. Operating margins "
        "improved to 28% despite increased R&D spend. The board approved a share "
        "buyback program valued at $500 million. Customer churn declined to 3.2% "
        "year-over-year.\n"
    )
    docs = []
    for i in range(count):
        idx = start + i
        intro = f"Document {idx}: Financial Summary Q3-2025 — Entity #{idx % 5000}\n\n"
        body = filler * 6  # ~600 chars, representative length
        docs.append(intro + body)
    return docs


# ---------------------------------------------------------------------------
# Modal worker: one vLLM engine per replica, processes a shard of documents
# ---------------------------------------------------------------------------

@app.cls(
    image=image,
    gpu=GPU,
    timeout=60 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/vllm": vllm_cache,
    },
)
class BatchWorker:
    """
    One replica = one H100 + one vLLM LLM engine.
    The local_entrypoint fans out shards across replicas with .map.
    """

    @modal.enter()
    def start(self) -> None:
        import vllm

        self.vllm = vllm
        self.llm = vllm.LLM(
            model=MODEL_NAME,
            revision=MODEL_REVISION,
            tokenizer_revision=MODEL_REVISION,
            **VLLM_KWARGS,
        )

        # Warm the engine before timing: fires prefill + decode path once so
        # KV-cache allocation and any JIT compilation finish before real work.
        warmup_params = vllm.SamplingParams(max_tokens=8, temperature=0.0)
        self.llm.chat(
            [[{"role": "user", "content": "ready"}]],
            sampling_params=warmup_params,
            chat_template_kwargs=CHAT_TEMPLATE_KWARGS,
        )

    @modal.exit()
    def stop(self) -> None:
        del self.llm

    def _run_batch(
        self, docs: list[str], max_tokens: int
    ) -> tuple[int, int, float]:
        """Process one vLLM batch; return (prompt_tokens, completion_tokens, duration_s)."""
        sampling_params = self.vllm.SamplingParams(**sampling_params_kwargs(max_tokens))
        messages = [
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": doc},
            ]
            for doc in docs
        ]

        t0 = time.perf_counter()
        responses = self.llm.chat(
            messages,
            sampling_params=sampling_params,
            chat_template_kwargs=CHAT_TEMPLATE_KWARGS,
        )
        elapsed = time.perf_counter() - t0

        prompt_tok = sum(len(r.prompt_token_ids) for r in responses)
        completion_tok = sum(len(r.outputs[0].token_ids) for r in responses)
        return prompt_tok, completion_tok, elapsed

    @modal.method()
    def process_shard(
        self,
        shard_id: int,
        doc_start: int,
        doc_count: int,
        batch_size: int = WORKER_BATCH_SIZE,
        max_tokens: int = MAX_TOKENS,
    ) -> dict[str, Any]:
        """
        Load `doc_count` documents starting at `doc_start`, process them in
        sub-batches of `batch_size` through the vLLM engine, and return
        aggregated metrics.

        Called via .map from the local_entrypoint — each invocation runs in
        its own Modal container with a freshly warmed vLLM engine.
        """
        docs = load_documents(doc_start, doc_count)
        batches = chunked(docs, batch_size)

        shard_start = time.perf_counter()
        total_prompt = 0
        total_completion = 0

        for batch_idx, batch in enumerate(batches):
            p_tok, c_tok, dur = self._run_batch(batch, max_tokens)
            total_prompt += p_tok
            total_completion += c_tok

            batch_total = p_tok + c_tok
            print(
                json.dumps({
                    "shard_id": shard_id,
                    "batch": batch_idx,
                    "docs_in_batch": len(batch),
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok,
                    "batch_tok_per_s": round(batch_total / dur, 1),
                })
            )

        shard_wall_time = time.perf_counter() - shard_start
        total_tokens = total_prompt + total_completion
        metrics = ShardMetrics(
            shard_id=shard_id,
            num_docs=doc_count,
            num_batches=len(batches),
            duration_s=round(shard_wall_time, 3),
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_tokens,
            total_tokens_per_s=round(total_tokens / shard_wall_time, 1),
        )
        payload = asdict(metrics)
        print(json.dumps({"shard_summary": payload}))
        return payload


# ---------------------------------------------------------------------------
# Local entrypoint: fan out with .map, gather results, print summary
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main(
    total_docs: int = TOTAL_DOCS,
    docs_per_shard: int = DOCS_PER_SHARD,
    batch_size: int = WORKER_BATCH_SIZE,
    max_tokens: int = MAX_TOKENS,
) -> None:
    """
    Orchestrate offline batch inference over `total_docs` documents.

    Fans out ceil(total_docs / docs_per_shard) Modal workers concurrently via
    .map — each worker handles its own shard on a dedicated H100.

    Usage:
        modal run solution.py
        modal run solution.py --total-docs 50000 --docs-per-shard 2000
        modal run solution.py --docs-per-shard 5000  # fewer, larger shards

    Adjust docs_per_shard to trade off wall-clock time vs. cost:
        - Smaller shards -> more parallelism -> faster, higher cost
        - Larger shards  -> fewer replicas   -> slower, lower cost
    """
    if total_docs < 1:
        raise ValueError("total_docs must be positive")
    if docs_per_shard < 1:
        raise ValueError("docs_per_shard must be positive")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")

    # Build shard assignments
    shard_ids: list[int] = []
    doc_starts: list[int] = []
    doc_counts: list[int] = []
    shard_id = 0
    offset = 0
    while offset < total_docs:
        count = min(docs_per_shard, total_docs - offset)
        shard_ids.append(shard_id)
        doc_starts.append(offset)
        doc_counts.append(count)
        offset += count
        shard_id += 1

    num_shards = len(shard_ids)
    print(f"Model         : {MODEL_NAME} @ {MODEL_REVISION}")
    print(f"GPU           : {GPU}")
    print(f"Documents     : {total_docs:,}")
    print(f"Shards        : {num_shards} x {docs_per_shard:,} docs")
    print(f"Batch size    : {batch_size} (prompts per vLLM call)")
    print(f"Max tokens    : {max_tokens}")
    print()

    worker = BatchWorker()
    t_global_start = time.perf_counter()

    # Fan out: .map launches one container per shard, all running in parallel.
    # Results are returned in input order once all shards complete.
    shard_results: list[dict[str, Any]] = list(
        worker.process_shard.map(
            shard_ids,
            doc_starts,
            doc_counts,
            kwargs={"batch_size": batch_size, "max_tokens": max_tokens},
        )
    )

    wall_time_s = time.perf_counter() - t_global_start

    # Aggregate metrics across all shards
    total_prompt_tokens = sum(s["prompt_tokens"] for s in shard_results)
    total_completion_tokens = sum(s["completion_tokens"] for s in shard_results)
    total_tokens = total_prompt_tokens + total_completion_tokens
    docs_processed = sum(s["num_docs"] for s in shard_results)

    summary = {
        "model": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "gpu": GPU,
        "total_docs_requested": total_docs,
        "total_docs_processed": docs_processed,
        "num_shards": num_shards,
        "docs_per_shard": docs_per_shard,
        "batch_size": batch_size,
        "max_tokens": max_tokens,
        "end_to_end_wall_time_s": round(wall_time_s, 3),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "throughput_total_tok_per_s_e2e": round(total_tokens / wall_time_s, 1),
        "throughput_completion_tok_per_s_e2e": round(
            total_completion_tokens / wall_time_s, 1
        ),
        "docs_per_second_e2e": round(docs_processed / wall_time_s, 2),
        "shard_results": shard_results,
    }

    print("\n=== Batch Job Summary ===")
    print(json.dumps(summary, indent=2, sort_keys=True))
