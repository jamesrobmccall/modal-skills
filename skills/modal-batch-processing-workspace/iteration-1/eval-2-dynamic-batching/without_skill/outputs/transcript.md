# Transcript: Batched Whisper Transcription on Modal (Without Skill Guidance)

## Task

Build a Modal solution that batches multiple audio inputs per GPU call to maximize
GPU utilization when running Whisper transcription, using `@modal.batched`.

---

## Step 1: Problem Analysis

Whisper inference is GPU-bound. Sending one audio file per Modal call wastes GPU
capacity because:

- Model loading (cold start) costs ~5–15 s for large-v3 on first container start.
- A single short audio clip does not saturate an A10G (24 GB VRAM).
- Each call incurs Modal scheduling and network round-trip overhead.

Goal: group multiple concurrent audio inputs into a single GPU invocation so the
model-load cost is amortized and the GPU runs at higher utilization.

---

## Step 2: Architecture Decisions

### Core batching mechanism — `@modal.batched`

Modal's `@modal.batched` decorator intercepts concurrent `.remote()` / `.spawn()`
calls to the same method and groups them into a single list before invoking the
underlying GPU function. The two key parameters are:

- `max_batch_size=16` — dispatch immediately once 16 requests accumulate.
- `wait_ms=500` — dispatch a partial batch after 500 ms even if fewer than 16
  requests have arrived, keeping latency bounded.

The decorated method must accept `list[T]` and return `list[U]` where the output
length equals the input length. Modal enforces this contract and routes each
output back to the correct caller.

### Class-based design with `@modal.enter()`

Using `@app.cls` + `@modal.enter()` loads the Whisper model once when the
container starts and keeps it in memory for the container's lifetime. All batched
calls within that container reuse the warm model — no repeated disk I/O or
CUDA initialization overhead.

### GPU choice

`A10G` — 24 GB VRAM, good balance of cost and capacity for faster-whisper
`large-v3`. Can upgrade to `A100-40GB` or `A100-80GB` for larger throughput or
batching more concurrent long-form transcriptions.

### Model backend

`faster-whisper` (CTranslate2) was chosen over `openai-whisper` because:
- ~4x faster than stock Whisper at equivalent accuracy.
- Native fp16 compute type on CUDA with no extra configuration.
- Built-in VAD filtering to skip silence, reducing wasted GPU cycles.

### Audio input format

Each caller passes raw bytes of one audio file (mp3, wav, m4a, ogg, flac, …).
The method writes bytes to a `tempfile` so ffmpeg/faster-whisper can decode any
container format. Magic-byte sniffing provides the correct file extension hint.

---

## Step 3: Implementation Details

### `@modal.batched` parameters

```python
@modal.batched(max_batch_size=16, wait_ms=500)
def transcribe(self, audio_bytes_batch: list[bytes]) -> list[str]:
    ...
```

- `max_batch_size=16` — chosen to fit 16 simultaneous transcription tasks within
  typical A10G memory; adjust down if very long audio files cause OOM.
- `wait_ms=500` — 500 ms keeps batch utilization high without adding more than
  half a second of queuing latency per request.

### Volume for model caching

```python
model_volume = modal.Volume.from_name("whisper-model-cache", create_if_missing=True)
```

The first run downloads `large-v3` weights (~3 GB) into the persistent volume.
Subsequent container starts load from volume rather than re-downloading, saving
~30–60 s per cold start.

### VAD filtering

```python
vad_filter=True,
vad_parameters=dict(min_silence_duration_ms=500),
```

Skips non-speech regions before transcription, reducing GPU work on podcasts or
interviews with long pauses.

### Caller patterns

Two patterns are shown:

**Pattern 1 — `.map()`** (preferred for batch jobs):

```python
results = list(transcriber.transcribe.map(audio_bytes_list))
```

Modal fans out all inputs concurrently and the scheduler groups them into batches
server-side. Results are returned in input order.

**Pattern 2 — `.spawn()` + `.get()`** (for async / interleaved workflows):

```python
futures = [transcriber.transcribe.spawn(audio) for audio in audio_bytes_list]
texts = [f.get() for f in futures]
```

Each `.spawn()` returns immediately; `.get()` blocks until that result is ready.
Useful when inputs arrive asynchronously or you want to pipeline other work.

---

## Step 4: Testing Approach

The `main()` local entrypoint generates synthetic silent WAV files when no audio
paths are provided, allowing smoke-testing of the Modal plumbing without real
audio. Silent WAVs will produce empty transcriptions (no speech), which validates:

1. The app deploys without errors.
2. Batch calls round-trip correctly and return a list of the same length.
3. Result ordering is preserved.

For real validation, pass actual audio files:

```bash
modal run solution.py -- interview.mp3 lecture.m4a
```

---

## Step 5: Key Modal APIs Used

| API | Purpose |
|-----|---------|
| `@app.cls(gpu="A10G")` | GPU-backed class container |
| `@modal.enter()` | Run once on container start — model loading |
| `@modal.batched(max_batch_size, wait_ms)` | Dynamic batching decorator |
| `modal.parameter()` | Configurable model size at deploy time |
| `modal.Volume.from_name(...)` | Persistent model weight cache |
| `.map()` | Fan-out caller pattern for batch jobs |
| `.spawn()` / `.get()` | Async caller pattern |
| `container_idle_timeout` | Keep container warm between request bursts |

---

## Step 6: Potential Pitfalls (Without Skill Guidance)

Without authoritative skill documentation, the following uncertainties arose:

1. **`@modal.batched` placement** — the decorator must go on a `@app.cls` method,
   not on a standalone `@app.function` with multiple list arguments. The correct
   signature is `method(self, items: list[T]) -> list[U]`.

2. **`keep_warm` vs `container_idle_timeout`** — the current Modal SDK uses
   `container_idle_timeout` on `@app.cls` to keep containers warm; `keep_warm`
   is a separate parameter available on some function types.

3. **`modal.parameter()`** — used for class-level configuration (e.g., model
   size) that can be set at deploy time; not all Modal versions support this.

4. **Output ordering guarantee** — Modal guarantees that `@modal.batched` returns
   outputs in the same order as inputs, so callers do not need to track request
   IDs manually.

---

## Step 7: Files Written

1. `solution.py` — complete, runnable Modal application
2. `transcript.md` — this file (step-by-step execution notes)
3. `metrics.json` — tool call counts

---

## Summary

The solution uses `@modal.batched(max_batch_size=16, wait_ms=500)` on a
`@app.cls` method backed by an A10G GPU. The faster-whisper `large-v3` model is
loaded once per container via `@modal.enter()` and weights are cached in a
persistent `modal.Volume`. Callers pass raw audio bytes per item and receive
transcription strings back, with batching fully transparent. Two caller patterns
(`.map()` and `.spawn()`) are demonstrated.
