# Execution Transcript

## Task
Answer the question: "My vLLM deployment on Modal is cold-starting in 3+ minutes, which is too slow for my bursty API traffic — what are my options?"

## Approach

Since this is an eval run without skill guidance, I drew entirely on my knowledge of Modal's platform features and vLLM internals to construct a comprehensive answer.

## Step 1: Identify the root causes of cold-start latency

Before listing solutions, I reasoned about what actually causes 3+ minute cold starts in a typical vLLM-on-Modal deployment:

1. **Container image pull** — Modal workers may need to pull the container image. For GPU containers with CUDA and vLLM installed, images are commonly 10–20 GB.
2. **Model weight download** — If weights are fetched at runtime from Hugging Face or S3, a 7B model in bfloat16 is ~14 GB. At typical network speeds, this takes 1–2+ minutes.
3. **vLLM engine init** — vLLM compiles CUDA kernels on first use (via Triton JIT), initializes the KV cache, and allocates GPU memory. This can take 30–90 seconds.

Understanding these three phases determined the structure of my solution.

## Step 2: Enumerate Modal-specific knobs

I enumerated Modal platform features relevant to cold start:

- `image.run_function()` — can bake model weights into the image layer at build time
- `keep_warm` parameter on `@app.cls` — maintains a minimum pool of hot containers
- `container_idle_timeout` — controls how aggressively idle containers are reclaimed
- `@modal.enter()` — runs initialization code once per container lifecycle, not per request
- `hf_transfer` + `HF_HUB_ENABLE_HF_TRANSFER` — Rust-based parallel downloader for HuggingFace
- `@modal.web_server()` — for serving the vLLM OpenAI-compatible HTTP server

## Step 3: Enumerate vLLM-specific knobs

- Quantization (AWQ, GPTQ) — reduces model size and therefore load time
- `gpu_memory_utilization` — controls KV cache allocation aggressiveness
- Single large GPU vs. multi-GPU tensor parallelism — NCCL initialization adds overhead
- Explicit warmup request — forces CUDA kernel compilation before first user request

## Step 4: Rank options by impact and simplicity

I ranked the options:

1. **Bake weights into image** — highest impact, relatively simple, addresses the #1 bottleneck
2. **`keep_warm=1`** — eliminates cold start entirely for the steady-state warm replica, trivial to implement
3. **Increase `container_idle_timeout`** — prevents premature teardown between bursts, zero code complexity
4. **Explicit CUDA warmup in `@modal.enter()`** — improves first-request latency, low complexity
5. **Quantization** — medium impact, requires model selection
6. **Avoid unnecessary tensor parallelism** — situational, low complexity

## Step 5: Write solution.md

Wrote a comprehensive markdown document covering:
- Root cause explanation
- All six options with code examples
- Tradeoff analysis for each
- A recommended combined strategy for bursty traffic
- A complete working code example combining best practices
- A summary comparison table

## Step 6: Write transcript.md and metrics.json

Documented execution steps and computed metrics.

## Notes on confidence

- Modal's `keep_warm`, `container_idle_timeout`, `@modal.enter()`, and `image.run_function()` APIs are stable and well-documented features I am confident in.
- vLLM's `LLM` class constructor arguments (`dtype`, `gpu_memory_utilization`, `quantization`) reflect the vLLM 0.4.x API.
- `hf_transfer` and `HF_HUB_ENABLE_HF_TRANSFER` are standard HuggingFace tooling.
- The exact cold-start time estimates (30–60 seconds with weights baked in) are approximations based on typical A100 initialization benchmarks.
