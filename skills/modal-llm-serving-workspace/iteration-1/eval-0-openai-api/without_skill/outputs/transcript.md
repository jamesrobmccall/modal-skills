# Transcript: Deploy Llama 3.1 8B on Modal with OpenAI-compatible API

## Task
Deploy Meta Llama 3.1 8B Instruct on Modal using vLLM, exposing an OpenAI-compatible REST API that any existing OpenAI SDK client can target by changing only `base_url`.

## Steps

### Step 1 — Design the architecture
No existing files to read; this is a greenfield solution. I drew on general knowledge of:
- Modal's Python SDK (`modal.App`, `@app.cls`, `@modal.web_server`, `@modal.enter`, `@modal.exit`, `@modal.concurrent`)
- vLLM's built-in OpenAI-compatible server (`vllm.entrypoints.openai.api_server`)
- HuggingFace Hub model download patterns

Key design decisions:
1. **Image baking**: Download model weights at image build time (`run_function`) so they are cached in the container image and cold starts only need to load weights from disk, not fetch from HuggingFace.
2. **`@modal.web_server`**: Exposes the vLLM HTTP server on a stable HTTPS URL that Modal manages (TLS termination, routing).
3. **`@modal.concurrent(max_inputs=50)`**: vLLM's async engine handles many parallel requests internally; Modal should route up to 50 simultaneous inputs to a single container rather than spawning new ones needlessly.
4. **`min_containers=1`**: Keep one container warm so the first request after a quiet period doesn't incur a full cold start (model load takes ~60–90 s on an A10G).
5. **GPU**: A10G (24 GB VRAM) is sufficient for 8B in bfloat16 (model fits in ~16 GB).
6. **`max-model-len=8192`**: Caps KV-cache size to prevent OOM while still supporting long contexts.
7. **HuggingFace secret**: Llama 3.1 is a gated model; the deploy needs a HF token stored as `modal.Secret.from_name("huggingface-secret")`.

### Step 2 — Write `solution.py`
Wrote the complete Modal deployment file covering:
- Image construction with vLLM + hf-transfer
- Model download baked into the image
- `LlamaServer` class with `@modal.enter` to launch the vLLM subprocess and health-check it
- `@modal.web_server` to expose the vLLM port
- `@modal.exit` for clean shutdown
- A `local_entrypoint` smoke-test
- Inline comments showing how to use the standard `openai` Python SDK against the deployed endpoint

### Step 3 — Validate mentally
Walked through the deployment flow:
1. `modal deploy solution.py` builds the image (downloads model once), creates the app.
2. Modal prints a URL like `https://<workspace>--llama-31-8b-serve.modal.run`.
3. First request spins up a container, loads the model, health-check passes, request is served.
4. Subsequent requests hit the warm container instantly.
5. OpenAI SDK: set `base_url` to `<modal-url>/v1`, any non-empty `api_key`.

### Step 4 — Write output files
- `solution.py` — complete deployment code
- `transcript.md` — this file
- `metrics.json` — tool call counts

## Key design notes / gotchas

- **Gated model**: You must accept Meta's license on HuggingFace and create a HF token with read access. Store it as a Modal secret named `huggingface-secret` with key `HF_TOKEN`.
- **Model name in API calls**: Use `"meta-llama/Meta-Llama-3.1-8B-Instruct"` as the `model` parameter, matching `--served-model-name`.
- **API key**: vLLM does not validate the API key by default; pass any non-empty string.
- **Streaming**: The vLLM OpenAI server supports `stream=True` natively.
- **Scaling**: Increase `max_containers` for higher throughput; vLLM batches requests automatically.
- **Cost**: An A10G on Modal costs ~$1.10/hr. With `min_containers=1` you pay continuously; set to 0 for pay-per-use (slower cold starts).
