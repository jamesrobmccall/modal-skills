# Reducing vLLM Cold Starts on Modal

Cold starts of 3+ minutes are common when a vLLM container must download model weights, compile CUDA kernels, and initialize GPU memory before serving the first request. Modal provides several tools to address this. The skill guidance prescribes a clear escalation order: reach for the simplest fix first and stop when you hit your latency target.

---

## What Causes a 3-Minute Cold Start

- Model weights re-downloaded from Hugging Face on every container start (10–30 GB for typical LLMs)
- CUDA graph compilation / torch.compile warmup at vLLM startup (60–120 seconds)
- KV cache allocation and engine initialization

All three problems have direct solutions in Modal.

---

## Escalation Order

1. Fast-boot settings — persistent volumes + `--enforce-eager` (zero extra infrastructure)
2. `min_containers=1` warm replica (eliminates cold starts; costs idle GPU time)
3. Memory snapshots — sleep/wake flow (sub-15s restores; highest operational complexity)

Apply them in order and stop when you reach your latency target.

---

## Option 1 — Fast-Boot Settings (Start Here)

### 1a. Cache Weights and Compilation Artifacts in Modal Volumes

The single biggest win is eliminating the weight download. Create one volume for model weights and a separate volume for vLLM compilation artifacts. Download weights once; every subsequent container start reads from the volume instead of the network.

Set `HF_XET_HIGH_PERFORMANCE=1` during the download step to use Hugging Face's XET transfer protocol, which is significantly faster than the default HTTP download.

Pin the model revision so the cached weights remain stable across deploys.

```python
import subprocess
import time
import socket
import modal

app = modal.App("vllm-fast-boot")

# Separate volumes — weights and compile cache are independent concerns
hf_cache_vol = modal.Volume.from_name("hf-model-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-compile-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim()
    .pip_install("vllm", "huggingface-hub[hf_transfer]")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"
MODEL_REVISION = "a1234abc..."  # pin a commit SHA — never leave as None in production
PORT = 8000


@app.function(
    image=image,
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,  # weights live here
        "/root/.cache/vllm": vllm_cache_vol,       # compile artifacts live here
    },
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=3600,
)
def download_model():
    """Run once: modal run script.py::download_model"""
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL_ID, revision=MODEL_REVISION)
    hf_cache_vol.commit()
```

### 1b. Disable CUDA Graph Compilation with `--enforce-eager`

By default vLLM compiles CUDA graphs at startup, adding 60–90 seconds. `--enforce-eager` disables this for faster starts at a ~10–20% throughput cost. For bursty APIs where latency at scale-up matters more than peak tokens/second, this is almost always the right trade.

Also bound `--max-model-len`, `--max-num-seqs`, and `--max-num-batched-tokens` to reduce KV cache allocation time and make startup more predictable.

```python
@app.function(
    image=image,
    gpu="A100",
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    timeout=600,
)
@modal.web_server(port=PORT, startup_timeout=300)
def serve():
    cmd = [
        "vllm", "serve", MODEL_ID,
        "--revision", MODEL_REVISION,
        "--served-model-name", "llama3",
        "--host", "0.0.0.0",
        "--port", str(PORT),
        "--enforce-eager",            # saves ~60-90s; slight throughput reduction
        "--max-model-len", "4096",    # reduces KV cache allocation time
        "--max-num-seqs", "32",
        "--max-num-batched-tokens", "4096",
    ]
    subprocess.Popen(cmd)

    deadline = time.time() + 270
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return
        except OSError:
            time.sleep(2)
    raise RuntimeError("vLLM did not become healthy in time")
```

**Expected savings with Option 1:**

| Intervention | Typical Saving |
|---|---|
| Persistent HF volume | 1–3 minutes (model-size dependent) |
| `HF_XET_HIGH_PERFORMANCE=1` | 20–50% faster when weights must be downloaded |
| `--enforce-eager` | 60–90 seconds |
| Bounded `--max-model-len` | 10–30 seconds |

For most 7B–13B model deployments, Option 1 alone brings a 3-minute cold start under 60 seconds.

---

## Option 2 — Keep a Warm Container with `min_containers`

If Option 1 is still too slow, or your bursty traffic pattern means you scale from zero frequently, keep one replica always warm. This completely eliminates cold starts for traffic up to the pre-warmed pool size.

```python
@app.function(
    image=image,
    gpu="A100",
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    timeout=600,
    min_containers=1,       # keep one warm replica at all times
    max_containers=10,      # cap scale-out for cost control
)
@modal.concurrent(max_inputs=32)
@modal.web_server(port=PORT, startup_timeout=300)
def serve():
    # same startup code as Option 1
    ...
```

**Tradeoffs:**
- You pay for idle GPU time continuously: ~$1.10/hr for A10G, ~$3.70/hr for A100-80GB.
- For bursty-but-not-always-idle APIs, this is often cheaper than the SLA cost of cold starts.
- Complexity is minimal — one additional parameter.
- Does not eliminate cold starts for scale-out beyond `min_containers`; combine with Option 1 so those additional containers start fast.

---

## Option 3 — Memory Snapshots (Advanced — Last Resort)

When Option 1 + 2 is either too expensive (idle GPU cost) or still too slow, Modal's memory snapshot feature restores a fully-initialized vLLM process from a saved state. New containers skip model loading, weight sharding, and kernel compilation entirely and wake in seconds.

This is the correct answer for zero-to-peak bursty traffic where you cannot afford a warm container but also cannot accept multi-minute cold starts.

### How the Sleep/Wake Flow Works

1. A container starts and runs `@modal.enter(snap=True)` (executed once, before the snapshot is taken).
2. In that hook: `vllm serve` launches with dev-mode and sleep-mode flags.
3. The code waits for the server to report healthy, then sends a small warmup request to trigger kernel compilation.
4. The server enters sleep mode — it pauses its event loop at a known, quiescent state.
5. Modal snapshots the container's memory at this exact point.
6. On subsequent cold starts, Modal restores from the snapshot and runs `@modal.enter(snap=False)` instead.
7. The `snap=False` hook wakes the server and waits for it to report healthy. This takes seconds, not minutes.

### Required Flags and Environment Variables

| Setting | Why |
|---|---|
| `VLLM_SERVER_DEV_MODE=1` | Enables `/sleep` and `/wake` HTTP endpoints |
| `TORCHINDUCTOR_COMPILE_THREADS=1` | Improves snapshot/restore compatibility |
| `--enable-sleep-mode` | Allows the server to enter a quiescent state |
| `--max-num-seqs N` | Bounds runtime shape; keeps snapshot size predictable |
| `--max-model-len N` | Bounds sequence length for same reason |
| `--max-num-batched-tokens N` | Further bounds batch shape |

Bounding the shape parameters is important: an unbounded snapshot captures whatever memory was allocated during warmup, which can be large and variable across runs.

### Full Implementation

```python
import subprocess
import time
import requests
import modal

app = modal.App("vllm-snapshot-serving")

hf_cache_vol = modal.Volume.from_name("hf-model-cache", create_if_missing=True)
vllm_cache_vol = modal.Volume.from_name("vllm-compile-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim()
    .pip_install("vllm", "huggingface-hub[hf_transfer]")
    .env({
        "HF_XET_HIGH_PERFORMANCE": "1",
        "VLLM_SERVER_DEV_MODE": "1",          # enables /sleep and /wake endpoints
        "TORCHINDUCTOR_COMPILE_THREADS": "1", # improves snapshot compatibility
    })
)

MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"
MODEL_REVISION = "a1234abc..."
PORT = 8000


def wait_for_health(port: int, timeout: int = 300) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError(f"vLLM did not become healthy within {timeout}s")


@app.cls(
    image=image,
    gpu="A100",
    volumes={
        "/root/.cache/huggingface": hf_cache_vol,
        "/root/.cache/vllm": vllm_cache_vol,
    },
    timeout=600,
    enable_memory_snapshot=True,
    # Uncomment if your account has GPU snapshot access — reduces restore to ~5s:
    # experimental_options={"enable_gpu_snapshot": True},
)
class VLLMServer:

    @modal.enter(snap=True)
    def start_and_snapshot(self):
        """
        Runs ONCE before the snapshot is taken.
        Starts vLLM, warms it up, then puts it into sleep mode so the
        snapshot captures a clean, predictable in-memory state.
        """
        cmd = [
            "vllm", "serve", MODEL_ID,
            "--revision", MODEL_REVISION,
            "--served-model-name", "llama3",
            "--host", "0.0.0.0",
            "--port", str(PORT),
            "--enable-sleep-mode",          # required for snapshot sleep/wake cycle
            "--enforce-eager",              # more stable snapshot behavior
            "--max-model-len", "4096",      # bound shape for predictable snapshot size
            "--max-num-seqs", "32",
            "--max-num-batched-tokens", "4096",
        ]
        self.proc = subprocess.Popen(cmd)
        wait_for_health(PORT)

        # One small warmup request — triggers kernel compilation before snapshot
        requests.post(
            f"http://127.0.0.1:{PORT}/v1/chat/completions",
            json={
                "model": "llama3",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 1,
            },
            timeout=30,
        )

        # Put server into sleep mode; snapshot is taken at this quiescent state
        requests.post(f"http://127.0.0.1:{PORT}/sleep", timeout=10)

    @modal.enter(snap=False)
    def wake_after_restore(self):
        """
        Runs after EVERY snapshot restore (i.e., every subsequent cold start).
        Wakes the vLLM server and blocks until it is ready to serve traffic.
        """
        requests.post(f"http://127.0.0.1:{PORT}/wake", timeout=30)
        wait_for_health(PORT)

    @modal.web_server(port=PORT, startup_timeout=60)
    def serve(self):
        # The web server is already running; this method exposes the port.
        pass
```

### GPU Snapshots

When `experimental_options={"enable_gpu_snapshot": True}` is set and your account has GPU snapshot access enabled, Modal also captures GPU memory (KV cache allocations, compiled kernels). This reduces restore time from ~20–30 seconds (CPU-only snapshot) to ~5 seconds. GPU snapshot availability depends on GPU type and account tier.

### Caveats for Memory Snapshots

- Not all models and CUDA kernels support snapshot/restore cleanly. Some kernel versions produce non-deterministic memory addresses that break restore. Test on your specific model before relying on this in production.
- The snapshot must be retaken whenever you update the model, vLLM version, or CUDA environment.
- Operational complexity is significantly higher: snapshot lifecycle management on top of serving lifecycle.
- If `min_containers=1` fits your budget, use that instead — it is far simpler and equally effective.
- Refer to Modal's official snapshot-based serving examples for the authoritative flow pattern.

---

## Decision Tree

```
Cold start > 3 minutes?
│
├── Are weights being re-downloaded every start?
│     YES → Add Modal Volumes for HF cache and vLLM compile cache
│           Add HF_XET_HIGH_PERFORMANCE=1; pin --revision
│           Expected saving: 1–3 minutes
│
├── Is CUDA graph compilation running at startup?
│     YES → Add --enforce-eager
│           Expected saving: 60–90 seconds
│
├── Still too slow OR cannot tolerate any cold start on burst?
│     → Set min_containers=1
│       Eliminates cold starts; costs one idle GPU continuously
│
└── min_containers too expensive AND need sub-15s restores?
      → Implement memory snapshots (advanced; see Option 3 above)
```

---

## Quick-Start Priority Checklist

1. Add `modal.Volume` for `/root/.cache/huggingface` and `/root/.cache/vllm`
2. Set `HF_XET_HIGH_PERFORMANCE=1` in the image environment
3. Pin `--revision` on the model in all serve commands
4. Add `--enforce-eager` to vLLM args
5. Bound `--max-model-len`, `--max-num-seqs`, `--max-num-batched-tokens`
6. If bursts cannot tolerate cold starts: set `min_containers=1`
7. If idle GPU cost is prohibitive and latency target is <15s: implement memory snapshots

---

## Summary of Expected Improvements

| Intervention | Typical Saving | Complexity |
|---|---|---|
| Persistent weight Volume | 1–3 minutes | Low |
| `HF_XET_HIGH_PERFORMANCE=1` | 20–50% of download time | Trivial |
| `--enforce-eager` | 60–90 seconds | Low |
| Bounded `--max-model-len` | 10–30 seconds | Low |
| `min_containers=1` | Eliminates cold starts | Low |
| Memory snapshots (CPU) | Reduces restore to <30s | High |
| Memory snapshots + GPU | Reduces restore to <10s | Very high |

With volumes and `--enforce-eager` combined, most 7B–13B model deployments go from 3+ minutes to under 60 seconds. Add `min_containers=1` if that is still not acceptable. Reach for memory snapshots only when the idle GPU cost is prohibitive and you need sub-15-second restores.
