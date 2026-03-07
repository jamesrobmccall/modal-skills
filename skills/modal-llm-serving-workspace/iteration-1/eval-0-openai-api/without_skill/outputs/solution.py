# Deploy Llama 3.1 8B on Modal with an OpenAI-compatible API
#
# This script deploys Meta's Llama 3.1 8B Instruct model on Modal using vLLM,
# exposing an OpenAI-compatible REST API endpoint.
#
# Usage:
#   modal deploy solution.py
#
# Then point your OpenAI SDK client at the deployed URL:
#   from openai import OpenAI
#   client = OpenAI(base_url="https://<your-modal-workspace>--llama-31-8b-serve.modal.run/v1", api_key="token")
#   response = client.chat.completions.create(model="meta-llama/Meta-Llama-3.1-8B-Instruct", messages=[...])

import modal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"
MODEL_DIR = "/model"
GPU_CONFIG = "A10G"
VLLM_PORT = 8000

APP_NAME = "llama-31-8b-serve"

# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------

# Build a container image that has vLLM installed and the model weights
# cached so cold-starts are fast.

vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.6.3.post1",
        "huggingface_hub[hf_transfer]==0.26.2",
        "hf-transfer==0.1.8",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# Download model weights into the image at build time so they are baked in
# and available immediately on cold start without an extra network fetch.
def download_model():
    from huggingface_hub import snapshot_download

    snapshot_download(
        MODEL_ID,
        local_dir=MODEL_DIR,
        ignore_patterns=["*.pt", "*.bin"],  # prefer safetensors
    )


vllm_image = vllm_image.run_function(
    download_model,
    secrets=[modal.Secret.from_name("huggingface-secret")],
    timeout=60 * 20,  # allow up to 20 minutes for the initial download
)

# ---------------------------------------------------------------------------
# Modal App
# ---------------------------------------------------------------------------

app = modal.App(APP_NAME)

# ---------------------------------------------------------------------------
# vLLM Server
# ---------------------------------------------------------------------------


@app.cls(
    image=vllm_image,
    gpu=GPU_CONFIG,
    # Keep one container warm to reduce cold-start latency.
    min_containers=1,
    # Each container serves many concurrent requests via vLLM's async engine.
    max_containers=5,
    # Allow up to 10 minutes for model loading on a fresh container.
    timeout=600,
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
@modal.concurrent(max_inputs=50)
class LlamaServer:
    @modal.enter()
    def start_server(self):
        """Start the vLLM OpenAI-compatible server in a background thread."""
        import subprocess
        import time

        import requests

        self.proc = subprocess.Popen(
            [
                "python",
                "-m",
                "vllm.entrypoints.openai.api_server",
                "--model",
                MODEL_DIR,
                "--served-model-name",
                MODEL_ID,
                "--host",
                "0.0.0.0",
                "--port",
                str(VLLM_PORT),
                "--trust-remote-code",
                "--max-model-len",
                "8192",
                "--dtype",
                "bfloat16",
            ],
        )

        # Wait until the server is healthy before accepting traffic.
        health_url = f"http://localhost:{VLLM_PORT}/health"
        for _ in range(120):  # up to 2 minutes
            try:
                resp = requests.get(health_url, timeout=2)
                if resp.status_code == 200:
                    print("vLLM server is ready.")
                    return
            except Exception:
                pass
            time.sleep(1)

        raise RuntimeError("vLLM server failed to become healthy in time.")

    @modal.exit()
    def stop_server(self):
        self.proc.terminate()
        self.proc.wait(timeout=30)

    @modal.web_server(port=VLLM_PORT, startup_timeout=300)
    def serve(self):
        """Expose the vLLM OpenAI-compatible HTTP server as a Modal web endpoint."""
        # The server is already running from @modal.enter(); this method simply
        # tells Modal which port to route external HTTPS traffic to.
        pass


# ---------------------------------------------------------------------------
# Example local usage (run with: modal run solution.py)
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def main():
    """Quick smoke-test: send a chat completion request to the deployed server."""
    import urllib.request, json

    # Retrieve the web endpoint URL from the deployed app.
    # In practice, copy the URL printed by `modal deploy` and paste it below.
    base_url = "https://<YOUR-MODAL-WORKSPACE>--llama-31-8b-serve.modal.run"

    payload = json.dumps(
        {
            "model": MODEL_ID,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"},
            ],
            "max_tokens": 128,
            "temperature": 0.7,
        }
    ).encode()

    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer token"},
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        print(result["choices"][0]["message"]["content"])


# ---------------------------------------------------------------------------
# Client example (not executed here — shown for reference)
# ---------------------------------------------------------------------------
#
# from openai import OpenAI
#
# client = OpenAI(
#     base_url="https://<YOUR-MODAL-WORKSPACE>--llama-31-8b-serve.modal.run/v1",
#     api_key="token",  # any non-empty string; vLLM does not verify the key by default
# )
#
# response = client.chat.completions.create(
#     model="meta-llama/Meta-Llama-3.1-8B-Instruct",
#     messages=[
#         {"role": "system", "content": "You are a helpful assistant."},
#         {"role": "user", "content": "Explain quantum entanglement in simple terms."},
#     ],
#     max_tokens=512,
#     temperature=0.7,
#     stream=False,
# )
# print(response.choices[0].message.content)
#
# # Streaming example:
# stream = client.chat.completions.create(
#     model="meta-llama/Meta-Llama-3.1-8B-Instruct",
#     messages=[{"role": "user", "content": "Tell me a joke."}],
#     max_tokens=256,
#     stream=True,
# )
# for chunk in stream:
#     if chunk.choices[0].delta.content:
#         print(chunk.choices[0].delta.content, end="", flush=True)
