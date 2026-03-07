"""
Modal offline batch inference for 50,000 documents using Qwen3.
Optimized for throughput, not latency.

Key design decisions:
- Use vLLM's offline LLM engine (not the async server) for maximum throughput
- Process documents in large batches per GPU worker
- Use Modal's map() with order_outputs=False for parallel processing
- Enable chunked prefill and prefix caching for throughput gains
- Use tensor parallelism for larger Qwen3 variants
- Cache model weights on a Modal Volume to avoid re-downloading

Usage:
    # Generate synthetic test data first:
    python solution.py  # calls generate_test_documents() if __name__ == "__main__"

    # Run batch inference:
    modal run solution.py
    modal run solution.py --input-file my_docs.jsonl --output-file my_results.jsonl
"""

import json
import modal
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_ID = "Qwen/Qwen3-8B"   # swap to Qwen3-14B / 32B / 72B as needed
MODEL_REVISION = "main"

# Number of documents to feed each GPU worker in a single call.
# Larger = higher GPU utilization = better throughput.
# Reduce if you hit OOM (especially for larger model variants).
DOCS_PER_BATCH = 500

# vLLM generation parameters — tuned for throughput
MAX_NEW_TOKENS = 512
TEMPERATURE = 0.0     # greedy decoding: fastest, deterministic
TOP_P = 1.0
TOP_K = -1

# GPU: A100-80GB gives excellent throughput/cost for Qwen3-8B.
# For Qwen3-72B: switch to H100 and set TENSOR_PARALLEL_SIZE=4, GPU_COUNT=4.
GPU_CONFIG = modal.gpu.A100(size="80GB", count=1)
TENSOR_PARALLEL_SIZE = 1          # set >1 and match GPU_COUNT for larger models
GPU_MEMORY_UTILIZATION = 0.93     # leave ~5 GB headroom for CUDA overhead

# How many concurrent GPU containers Modal will run simultaneously.
# 50,000 docs / 500 per batch = 100 batches; 20 workers = ~5 parallel waves.
MAX_CONTAINERS = 20

# ---------------------------------------------------------------------------
# Modal image — install vLLM and dependencies
# ---------------------------------------------------------------------------

vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm>=0.6.0",
        "huggingface_hub[hf_transfer]>=0.22.0",
        "transformers>=4.45.0",
        "torch>=2.4.0",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})  # faster model downloads via hf_transfer
)

# ---------------------------------------------------------------------------
# Modal volumes
# ---------------------------------------------------------------------------

# Cache model weights so they are only downloaded once across all containers.
model_volume = modal.Volume.from_name("qwen3-model-weights", create_if_missing=True)
MODEL_CACHE_DIR = "/model-cache"

# Store inference results so they survive container teardown.
results_volume = modal.Volume.from_name("qwen3-batch-results", create_if_missing=True)
RESULTS_DIR = "/results"

# ---------------------------------------------------------------------------
# Modal app
# ---------------------------------------------------------------------------

app = modal.App("qwen3-batch-inference")

# ---------------------------------------------------------------------------
# Helper: download model weights once, cache to Volume
# ---------------------------------------------------------------------------


@app.function(
    image=vllm_image,
    volumes={MODEL_CACHE_DIR: model_volume},
    gpu=GPU_CONFIG,
    timeout=3600,
    # Uncomment if the model is gated on HuggingFace:
    # secrets=[modal.Secret.from_name("huggingface-secret")],
)
def download_model():
    """Download Qwen3 model weights to the Modal Volume (idempotent)."""
    from huggingface_hub import snapshot_download

    local_dir = Path(MODEL_CACHE_DIR) / MODEL_ID.replace("/", "--")
    if (local_dir / "config.json").exists():
        print(f"Model already cached at {local_dir}")
        return str(local_dir)

    print(f"Downloading {MODEL_ID} ...")
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=str(local_dir),
        ignore_patterns=["*.pt", "*.bin"],  # prefer safetensors
    )
    model_volume.commit()
    print("Download complete.")
    return str(local_dir)


# ---------------------------------------------------------------------------
# Core inference function — one Modal call per batch of documents
# ---------------------------------------------------------------------------


@app.function(
    image=vllm_image,
    volumes={MODEL_CACHE_DIR: model_volume},
    gpu=GPU_CONFIG,
    timeout=3600,
    # Allow up to MAX_CONTAINERS simultaneous GPU workers
    concurrency_limit=MAX_CONTAINERS,
    # Keep containers warm between batch assignments to avoid cold-start penalty
    scaledown_window=120,
)
def infer_batch(
    batch: list[dict],
    system_prompt: str = "You are a helpful assistant.",
) -> list[dict]:
    """
    Run vLLM offline inference on a batch of documents.

    Input:
        batch: list of dicts, each with at least {"id": <str|int>, "text": <str>}
        system_prompt: instruction prepended to every document

    Returns:
        list of dicts: {"id": ..., "response": ..., "tokens_generated": ...}
    """
    from vllm import LLM, SamplingParams

    model_path = str(Path(MODEL_CACHE_DIR) / MODEL_ID.replace("/", "--"))

    # Instantiate the vLLM offline engine.
    # These settings are tuned for maximum throughput:
    llm = LLM(
        model=model_path,
        tensor_parallel_size=TENSOR_PARALLEL_SIZE,
        gpu_memory_utilization=GPU_MEMORY_UTILIZATION,
        max_model_len=8192,
        # Prefix caching: reuses KV cache for the shared system prompt across all
        # requests, saving compute proportional to system_prompt length.
        enable_prefix_caching=True,
        # Chunked prefill: splits long prefills into chunks so decode steps are
        # not starved, keeping GPU utilization high across heterogeneous doc lengths.
        enable_chunked_prefill=True,
        max_num_batched_tokens=8192,
        max_num_seqs=DOCS_PER_BATCH,
        # CPU swap space lets vLLM handle more concurrent sequences than fit in VRAM.
        swap_space=4,  # GB
        dtype="bfloat16",
        trust_remote_code=True,  # required for Qwen models
    )

    sampling_params = SamplingParams(
        temperature=TEMPERATURE,
        top_p=TOP_P,
        top_k=TOP_K,
        max_tokens=MAX_NEW_TOKENS,
        skip_special_tokens=True,
    )

    # Build chat-formatted prompts for the full batch at once.
    # Using the tokenizer's apply_chat_template ensures correct Qwen3 formatting.
    tokenizer = llm.get_tokenizer()
    prompts = []
    for item in batch:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": item["text"]},
        ]
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        prompts.append(prompt)

    # Single vLLM call processes the entire batch — vLLM's continuous batching
    # scheduler packs requests together to maximize GPU utilization.
    outputs = llm.generate(prompts, sampling_params)

    results = []
    for item, output in zip(batch, outputs):
        generated_text = output.outputs[0].text
        results.append(
            {
                "id": item["id"],
                "response": generated_text,
                "tokens_generated": len(output.outputs[0].token_ids),
            }
        )

    return results


# ---------------------------------------------------------------------------
# Orchestrator — splits 50k docs into batches and fans out across workers
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def main(
    input_file: str = "documents.jsonl",
    output_file: str = "results.jsonl",
    system_prompt: str = "Summarise the following document concisely.",
    limit: Optional[int] = None,
):
    """
    Orchestrate batch inference across 50,000 documents.

    Args:
        input_file:    Path to a JSONL file. Each line: {"id": ..., "text": ...}
        output_file:   Where to write results JSONL.
        system_prompt: System instruction sent to every document.
        limit:         If set, only process the first N documents (for testing).

    The pipeline:
        1. Ensure model weights are cached on the Modal Volume.
        2. Load documents from the JSONL input file.
        3. Split into batches of DOCS_PER_BATCH.
        4. Fan out to up to MAX_CONTAINERS GPU workers via infer_batch.map().
        5. Stream results back and write to output_file.
    """
    import time

    # --- 1. Ensure model weights are cached ---------------------------------
    print("Ensuring model weights are cached on Modal Volume ...")
    download_model.remote()

    # --- 2. Load documents --------------------------------------------------
    print(f"Loading documents from {input_file} ...")
    documents = []
    with open(input_file, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            documents.append(json.loads(line))

    if limit:
        documents = documents[:limit]

    total = len(documents)
    print(f"Loaded {total:,} documents.")

    # --- 3. Split into batches ----------------------------------------------
    batches = [
        documents[i : i + DOCS_PER_BATCH]
        for i in range(0, total, DOCS_PER_BATCH)
    ]
    print(
        f"Split into {len(batches)} batches of up to {DOCS_PER_BATCH} docs each."
    )

    # --- 4. Fan out with Modal map() — fully parallel across containers -----
    print(
        f"Dispatching {len(batches)} batches to up to {MAX_CONTAINERS} GPU workers ..."
    )
    all_results: list[dict] = []
    completed = 0
    t0 = time.time()

    # map() streams results back as each batch finishes.
    # order_outputs=False returns results as-ready rather than in submission order,
    # which prevents a slow batch from blocking faster ones from being written.
    for batch_results in infer_batch.map(
        batches,
        kwargs={"system_prompt": system_prompt},
        order_outputs=False,
    ):
        all_results.extend(batch_results)
        completed += len(batch_results)
        elapsed = time.time() - t0
        rate = completed / elapsed if elapsed > 0 else 0
        print(
            f"  Progress: {completed:,}/{total:,} docs "
            f"({100 * completed / total:.1f}%) | "
            f"{rate:.0f} docs/s",
            end="\r",
        )

    elapsed = time.time() - t0
    throughput = total / elapsed if elapsed > 0 else 0
    print(f"\nAll {completed:,} documents processed in {elapsed:.1f}s "
          f"({throughput:.1f} docs/s).")

    # --- 5. Write results ---------------------------------------------------
    print(f"Writing results to {output_file} ...")
    with open(output_file, "w", encoding="utf-8") as fh:
        for result in all_results:
            fh.write(json.dumps(result, ensure_ascii=False) + "\n")

    total_tokens = sum(r.get("tokens_generated", 0) for r in all_results)
    avg_tokens = total_tokens / total if total else 0
    print(f"Done.")
    print(f"  Total tokens generated : {total_tokens:,}")
    print(f"  Avg tokens per doc     : {avg_tokens:.1f}")
    print(f"  Wall-clock time        : {elapsed:.1f}s")
    print(f"  Throughput             : {throughput:.1f} docs/s")
    print(f"  Results written to     : {output_file}")


# ---------------------------------------------------------------------------
# Helper: generate synthetic test documents
# ---------------------------------------------------------------------------


def generate_test_documents(
    n: int = 50_000,
    output_path: str = "documents.jsonl",
) -> None:
    """Write N synthetic documents to a JSONL file for testing."""
    import random

    random.seed(42)
    topics = [
        "climate change and renewable energy policy",
        "advances in large language model training",
        "supply chain disruption in global markets",
        "the future of autonomous vehicle regulation",
        "cybersecurity threats in critical infrastructure",
        "the impact of AI on healthcare diagnostics",
        "global economic inequality and redistribution policies",
        "deep sea exploration and marine biodiversity",
    ]
    with open(output_path, "w", encoding="utf-8") as fh:
        for i in range(n):
            topic = topics[i % len(topics)]
            doc = {
                "id": i,
                "text": (
                    f"Document {i}: Provide a concise analysis of {topic}. "
                    "Cover key challenges, recent developments, and future outlook. "
                    "Include economic, social, and technological dimensions."
                ),
            }
            fh.write(json.dumps(doc) + "\n")
    print(f"Generated {n:,} test documents at {output_path}")


if __name__ == "__main__":
    # Generate synthetic test data before running:
    #   python solution.py
    # Then run inference:
    #   modal run solution.py
    generate_test_documents(50_000, "documents.jsonl")
