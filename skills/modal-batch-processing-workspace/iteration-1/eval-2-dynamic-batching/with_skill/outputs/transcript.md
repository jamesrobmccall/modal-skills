# Execution Transcript

## Task
Produce a Modal solution for batching Whisper transcription requests per GPU call using `@modal.batched`.

## Steps

### Step 1 — Read SKILL.md
Read `/Users/jmccall/Documents/Coding/modal_skills/modal_skills/skills/modal-batch-processing/SKILL.md`.

Key takeaways:
- The skill directs: use `@modal.batched` when many small, homogeneous requests should be coalesced into fewer executions.
- The matching reference to read is `references/dynamic-batching.md`.
- Use `@app.cls` when batching benefits from expensive state kept warm in memory (model weights).

### Step 2 — Read dynamic-batching.md
Read `/Users/jmccall/Documents/Coding/modal_skills/modal_skills/skills/modal-batch-processing/references/dynamic-batching.md`.

Key contracts extracted:
- Decorate with `@modal.batched(max_batch_size=..., wait_ms=...)`.
- Implementation accepts lists as inputs and returns a list of the same length.
- Callers submit individual inputs; batching is transparent to the caller.
- `.map()` is the clearest way to submit a stream of inputs.
- Use `@app.cls` so the model is loaded once per warm container via `@modal.enter()`.
- Class rule: do not add other `@modal.method` or `@modal.batched` methods to the same class as the batched method.
- The Whisper example is called out explicitly as the reference anchor pattern.

### Step 3 — Design decisions

**GPU**: Chose `T4` — cost-effective for Whisper inference, well-supported by Modal, compatible with the `base` model at batch size 16.

**max_batch_size=16**: The Whisper `base` model on a T4 (16 GB VRAM) can comfortably process 16 audio clips simultaneously. Larger models (e.g. `large`) would require reducing this.

**wait_ms=200**: 200 ms provides a reasonable queue window to accumulate concurrent requests without making latency-sensitive callers wait too long. This is tunable — lower for interactive use, higher for bulk offline jobs.

**Model loading**: Used `@modal.enter()` to load the model once per container. This keeps the model in GPU memory across batched calls, amortizing the load cost.

**Volume for model cache**: Added a `modal.Volume` mounted at `/model-cache` so Whisper weights are downloaded once and reused across cold starts, rather than re-downloading on each new container.

**Audio handling**: Each audio item in the batch is processed sequentially within the batched call using `whisper.load_audio` (which expects a file path), written to a tempfile. This correctly handles the list-in/list-out contract while using Whisper's native audio loading.

**Caller patterns shown**:
1. `.remote()` — single item call, blocks until the batch fires.
2. `.map()` — stream of items, most natural for bulk workloads.
3. `modal.Cls.from_name()` — for callers in other services after `modal deploy`.

### Step 4 — Wrote solution.py

Complete solution written to the output directory. The file includes:
- `WhisperBatchTranscriber` class with `@app.cls(gpu="T4", ...)`
- `@modal.enter()` method loading the Whisper model
- `@modal.batched(max_batch_size=16, wait_ms=200)` method accepting `list[bytes]`, returning `list[str]`
- Length assertion to enforce the contract
- `@app.local_entrypoint()` showing both `.remote()` and `.map()` caller patterns
- Standalone `call_from_another_service()` function showing `modal.Cls.from_name()` usage

### Step 5 — Wrote transcript.md and metrics.json
