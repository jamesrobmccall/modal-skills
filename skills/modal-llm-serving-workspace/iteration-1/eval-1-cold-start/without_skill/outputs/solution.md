# Reducing vLLM Cold-Start Times on Modal

Cold starts of 3+ minutes on Modal with vLLM typically stem from three main bottlenecks:

1. **Container image pull and extraction** — pulling a large image (often 10–20 GB for GPU containers)
2. **Model weight download** — downloading model weights from Hugging Face or S3 on every cold start
3. **vLLM engine initialization** — CUDA kernel compilation and engine warm-up

This guide walks through each lever you have to reduce cold-start latency, with tradeoffs and code examples.

---

## Option 1: Snapshot Model Weights into the Container Image

The single biggest win is baking model weights into the image so they are available immediately when the container starts, rather than being downloaded at runtime.

### How it works

Modal lets you run arbitrary code during `image.run_function()` as part of the image build step. You download the weights once, they get snapshotted into the image layer, and every subsequent container start reads from the local filesystem.

```python
import modal

MODELS_DIR = "/models"
MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.2"

def download_model():
    from huggingface_hub import snapshot_download
    snapshot_download(
        MODEL_NAME,
        local_dir=MODELS_DIR,
        ignore_patterns=["*.pt", "*.bin"],  # prefer safetensors
    )

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.4.2",
        "huggingface_hub",
        "hf_transfer",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})  # faster HF downloads
    .run_function(
        download_model,
        secrets=[modal.Secret.from_name("huggingface-secret")],
        timeout=60 * 20,
    )
)
```

**Tradeoffs:**
- Pro: Eliminates model download time on every cold start (often 1–2 minutes for 7B models)
- Pro: Weights are served from fast local NVMe, not network
- Con: Larger image means longer first image pull on brand-new workers (mitigated by Modal's image caching infrastructure)
- Con: Image must be rebuilt when you want to update model versions

### Enabling fast transfers

Set `HF_HUB_ENABLE_HF_TRANSFER=1` and install `hf_transfer` to use Rust-based parallel downloading during image build. This can reduce the download phase from minutes to tens of seconds.

---

## Option 2: Keep Containers Warm with `keep_warm`

If your traffic is bursty but predictable, you can keep a minimum number of containers running at all times.

```python
app = modal.App("vllm-server")

@app.cls(
    gpu="A100",
    image=image,
    keep_warm=1,  # always keep 1 container hot
    container_idle_timeout=300,  # seconds before idle containers are killed
)
class VLLMServer:
    @modal.enter()
    def load_model(self):
        from vllm import LLM
        self.llm = LLM(model=MODELS_DIR)

    @modal.method()
    def generate(self, prompt: str) -> str:
        outputs = self.llm.generate([prompt])
        return outputs[0].outputs[0].text
```

**Tradeoffs:**
- Pro: Zero cold-start latency for the first `keep_warm` replicas
- Pro: Simplest possible solution — one parameter change
- Con: You pay for idle GPU time (A100 at ~$3–4/hr continuously)
- Con: Does not help when traffic spikes beyond the warm pool size — additional replicas still cold-start

### Tuning `container_idle_timeout`

Increase `container_idle_timeout` to reduce how aggressively Modal tears down containers between bursts. The default is 60 seconds. For bursty traffic with gaps of a few minutes, setting this to 300–600 seconds can eliminate most cold starts.

```python
@app.cls(
    gpu="A100",
    image=image,
    keep_warm=1,
    container_idle_timeout=600,  # 10 minutes
)
```

---

## Option 3: Use Modal's `@modal.enter()` to Initialize Once Per Container

Ensure expensive initialization (model loading, CUDA warmup) happens once per container lifecycle, not on every request. Use `@modal.enter()` for this.

```python
@app.cls(gpu="A100", image=image)
class VLLMServer:
    @modal.enter()
    def load_model(self):
        from vllm import LLM, SamplingParams
        self.llm = LLM(
            model=MODELS_DIR,
            dtype="bfloat16",
            gpu_memory_utilization=0.90,
        )
        # Warm up the model with a dummy request to trigger CUDA compilation
        self.llm.generate(["warmup"], SamplingParams(max_tokens=1))

    @modal.method()
    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        from vllm import SamplingParams
        params = SamplingParams(max_tokens=max_tokens)
        outputs = self.llm.generate([prompt], params)
        return outputs[0].outputs[0].text
```

The explicit warmup call inside `@modal.enter()` forces CUDA kernel compilation before the first real request arrives, ensuring that the first user-facing request is not penalized by JIT compilation overhead.

---

## Option 4: Serve via vLLM's OpenAI-Compatible HTTP Server

Instead of using vLLM's Python API directly, you can run the vLLM OpenAI server as a subprocess. This can reduce Python overhead and gives you an OpenAI-compatible endpoint. Combined with Modal's web endpoint support:

```python
import subprocess
import modal

@app.function(
    gpu="A100",
    image=image,
    keep_warm=1,
    container_idle_timeout=300,
)
@modal.web_server(port=8000, startup_timeout=300)
def serve():
    subprocess.Popen([
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", MODELS_DIR,
        "--dtype", "bfloat16",
        "--port", "8000",
        "--host", "0.0.0.0",
        "--max-model-len", "4096",
    ])
```

**Tradeoffs:**
- Pro: Drop-in replacement for OpenAI API clients
- Pro: vLLM handles batching and streaming natively
- Con: Slightly less control over per-request logic
- Con: `startup_timeout` must be long enough for vLLM to initialize

---

## Option 5: Reduce Model Size / Use Quantization

Smaller models load faster. If your use case tolerates quality tradeoffs, use quantized models:

```python
# Use GPTQ or AWQ quantized model
def download_model():
    from huggingface_hub import snapshot_download
    snapshot_download(
        "TheBloke/Mistral-7B-Instruct-v0.2-AWQ",  # AWQ quantized
        local_dir=MODELS_DIR,
    )
```

Then load with quantization enabled:

```python
self.llm = LLM(
    model=MODELS_DIR,
    quantization="awq",
    dtype="float16",
)
```

AWQ 4-bit quantization reduces a 7B model from ~14 GB to ~4 GB, which roughly halves load time.

**Tradeoffs:**
- Pro: Faster load, lower VRAM usage, can use smaller (cheaper) GPUs
- Con: Small quality degradation; benchmark for your use case
- Con: Not all model families have high-quality quantized checkpoints

---

## Option 6: Use Tensor Parallelism Carefully

If you are using tensor parallelism across multiple GPUs to speed up inference, note that it also increases initialization overhead. For cold-start optimization, prefer a single large GPU (A100 80GB) over multi-GPU tensor parallelism if the model fits.

```python
# Prefer this for cold-start speed (if model fits):
@app.cls(gpu="A100-80GB", image=image)

# Over this (higher init overhead from NCCL setup):
@app.cls(gpu=modal.gpu.A100(count=2), image=image)
```

---

## Recommended Strategy for Bursty Traffic

For bursty API traffic where you need fast response but want to minimize idle cost:

1. **Bake weights into the image** (Option 1) — eliminates the biggest source of cold-start latency
2. **Set `keep_warm=1`** (Option 2) — keeps one container hot for immediate response
3. **Increase `container_idle_timeout`** to 300–600 seconds — prevents premature container teardown between bursts
4. **Add an explicit warmup call** in `@modal.enter()` (Option 3) — ensures CUDA is compiled before first request
5. **Use quantization** (Option 5) — if quality allows, reduces load time further

With weights baked in and one warm container, your effective cold-start for the warm replica drops to near zero. New replicas spun up during a traffic spike will still cold-start, but with weights on disk, that initialization time typically drops from 3+ minutes to 30–60 seconds.

### Complete Example Combining Best Practices

```python
import modal

MODELS_DIR = "/models"
MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.2"

def download_model():
    from huggingface_hub import snapshot_download
    snapshot_download(
        MODEL_NAME,
        local_dir=MODELS_DIR,
        ignore_patterns=["*.pt", "*.bin"],
    )

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm==0.4.2", "huggingface_hub", "hf_transfer")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_function(
        download_model,
        secrets=[modal.Secret.from_name("huggingface-secret")],
        timeout=60 * 20,
    )
)

app = modal.App("vllm-fast-start")

@app.cls(
    gpu="A100",
    image=image,
    keep_warm=1,
    container_idle_timeout=600,
    timeout=300,
)
class VLLMServer:
    @modal.enter()
    def load_model(self):
        from vllm import LLM, SamplingParams
        self.llm = LLM(
            model=MODELS_DIR,
            dtype="bfloat16",
            gpu_memory_utilization=0.90,
        )
        # Force CUDA kernel compilation before first real request
        self.llm.generate(["warmup"], SamplingParams(max_tokens=1))
        print("Model loaded and warmed up.")

    @modal.method()
    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        from vllm import SamplingParams
        params = SamplingParams(max_tokens=max_tokens)
        outputs = self.llm.generate([prompt], params)
        return outputs[0].outputs[0].text

@app.local_entrypoint()
def main():
    server = VLLMServer()
    result = server.generate.remote("What is the capital of France?")
    print(result)
```

---

## Summary Table

| Option | Cold-Start Impact | Cost Impact | Complexity |
|---|---|---|---|
| Bake weights into image | High (removes download) | Low (one-time build) | Low |
| `keep_warm=1` | Eliminates for warm replicas | Medium (idle GPU cost) | Very low |
| Increase `idle_timeout` | Medium (fewer teardowns) | Low-medium | Very low |
| Explicit CUDA warmup | Low-medium (first request) | None | Low |
| Quantization | Medium (smaller model loads faster) | None or negative | Low-medium |
| Avoid multi-GPU for small models | Low-medium (less NCCL init) | None | Low |
