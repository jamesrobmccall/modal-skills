#!/usr/bin/env python3
"""
Llama 3.1 8B Instruct — OpenAI-compatible API on Modal with vLLM.

Deploy:
    modal deploy solution.py

Run smoke test:
    modal run solution.py

Point an OpenAI SDK client at the deployed URL:
    from openai import OpenAI
    client = OpenAI(base_url="<MODAL_URL>/v1", api_key="unused")
    response = client.chat.completions.create(
        model="llama-3.1-8b",
        messages=[{"role": "user", "content": "Hello!"}],
    )
"""

from __future__ import annotations

import os
import subprocess
import time

import modal

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

APP_NAME = "llama-3-1-8b-serve"

MODEL_NAME = "meta-llama/Meta-Llama-3.1-8B-Instruct"
# Pinned to a specific commit for reproducibility.
# Update this when you intentionally want a new upstream revision.
MODEL_REVISION = "5206a32e0bd3067aef1ce90f5528ade7d866253f"
SERVED_MODEL_NAME = "llama-3.1-8b"

GPU = "a10g"          # A10G has 24 GB VRAM — sufficient for 8B BF16 + KV cache
GPU_COUNT = 1
TENSOR_PARALLEL_SIZE = GPU_COUNT

PORT = 8000
MINUTES = 60

# Set FAST_BOOT=1 to use --enforce-eager (faster cold starts, slower warm throughput).
# Leave unset or FAST_BOOT=0 for full CUDA-graph capture (better steady-state performance).
FAST_BOOT = bool(int(os.environ.get("FAST_BOOT", "0")))

# ---------------------------------------------------------------------------
# Container image
# ---------------------------------------------------------------------------

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.9.0-devel-ubuntu22.04",
        add_python="3.13",
    )
    .entrypoint([])
    .uv_pip_install("vllm==0.9.2", "huggingface-hub==0.31.4")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

# ---------------------------------------------------------------------------
# Modal app and volumes
# ---------------------------------------------------------------------------

app = modal.App(APP_NAME)

# Separate volumes so the weight cache and compile cache can be managed independently.
hf_cache = modal.Volume.from_name(
    "llama-3-1-8b-huggingface-cache",
    create_if_missing=True,
)
vllm_cache = modal.Volume.from_name(
    "llama-3-1-8b-vllm-cache",
    create_if_missing=True,
)

# ---------------------------------------------------------------------------
# Serving function
# ---------------------------------------------------------------------------


@app.function(
    image=image,
    gpu=f"{GPU}:{GPU_COUNT}",
    timeout=20 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/vllm": vllm_cache,
    },
    # Allow multiple concurrent requests to be handled by the same container.
    # Start conservative and benchmark before increasing this value.
    max_inputs=64,
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=PORT, startup_timeout=10 * MINUTES)
def serve() -> None:
    """Start a vLLM OpenAI-compatible server and wait until it is ready."""
    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--revision", MODEL_REVISION,
        "--served-model-name", SERVED_MODEL_NAME,
        "--host", "0.0.0.0",
        "--port", str(PORT),
        "--tensor-parallel-size", str(TENSOR_PARALLEL_SIZE),
        "--gpu-memory-utilization", "0.90",
        "--max-model-len", "8192",
    ]

    if FAST_BOOT:
        cmd.append("--enforce-eager")

    subprocess.Popen(cmd)

    # Block until the server reports healthy so Modal knows it is ready.
    import urllib.error
    import urllib.request

    health_url = f"http://0.0.0.0:{PORT}/health"
    deadline = time.monotonic() + 9 * MINUTES
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=5) as response:
                if response.status == 200:
                    print("vLLM server is ready.")
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(3)

    raise RuntimeError("vLLM server did not become healthy within the startup window.")


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def main() -> None:
    """
    Run a single chat-completions request against the deployed service to
    verify end-to-end connectivity.

    Usage:
        modal run solution.py
    """
    import json
    import urllib.error
    import urllib.request

    # Resolve the URL of the deployed web server.  `serve.web_url` is set
    # automatically by Modal after deployment.
    base_url = serve.web_url
    if not base_url:
        raise RuntimeError(
            "Could not resolve the service URL. "
            "Make sure the app is deployed with `modal deploy solution.py`."
        )

    print(f"Service URL: {base_url}")

    # 1. Health check
    health_url = f"{base_url}/health"
    print(f"Checking health at {health_url} ...")
    with urllib.request.urlopen(health_url, timeout=30) as resp:
        status = resp.status
    print(f"Health check status: {status}")
    assert status == 200, f"Unexpected health status: {status}"

    # 2. One chat-completions request (streaming disabled for simplicity)
    chat_url = f"{base_url}/v1/chat/completions"
    payload = json.dumps(
        {
            "model": SERVED_MODEL_NAME,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Reply with exactly three words: 'smoke test passed'."},
            ],
            "max_tokens": 16,
            "temperature": 0.0,
            "stream": False,
        }
    ).encode()

    req = urllib.request.Request(
        chat_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    print(f"Sending chat request to {chat_url} ...")
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())

    reply = body["choices"][0]["message"]["content"]
    print(f"Model reply: {reply!r}")
    print("Smoke test passed.")
