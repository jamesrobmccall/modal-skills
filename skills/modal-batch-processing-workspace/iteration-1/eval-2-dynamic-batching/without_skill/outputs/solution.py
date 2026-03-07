"""
Batched Whisper Transcription on Modal using @modal.batched.

This solution demonstrates how to batch multiple audio inputs per GPU call to
maximize GPU utilization when running Whisper transcription on Modal.

Key design decisions:
- @modal.batched collects concurrent .remote() / .spawn() calls and groups them
  into a single list invocation on the GPU container.
- max_batch_size=16: dispatch immediately when 16 requests have accumulated.
- wait_ms=500: wait at most 500 ms before dispatching a partial batch.
- Inputs and outputs follow the list contract: the decorated method receives
  list[bytes] and must return list[str] of the same length.
- The model is loaded once per container via @modal.enter() — not per call.
- Callers use .map() or .spawn() exactly as with any other Modal function;
  batching is transparent to the caller.
"""

import modal

# ---------------------------------------------------------------------------
# Container image — faster-whisper uses CTranslate2 for GPU inference
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "faster-whisper==1.0.3",
        "numpy",
    )
    .apt_install("ffmpeg")
)

app = modal.App("batched-whisper-transcription", image=image)

# ---------------------------------------------------------------------------
# Persistent volume — cache downloaded model weights across container restarts
# ---------------------------------------------------------------------------
MODEL_DIR = "/model-cache"
model_volume = modal.Volume.from_name("whisper-model-cache", create_if_missing=True)


# ---------------------------------------------------------------------------
# Batched transcription class
# ---------------------------------------------------------------------------

@app.cls(
    gpu="A10G",                      # 24 GB VRAM — handles large-v3 comfortably
    volumes={MODEL_DIR: model_volume},
    container_idle_timeout=300,      # keep container warm 5 min between requests
    image=image,
)
class WhisperBatchTranscriber:
    """
    GPU-accelerated Whisper transcription with Modal dynamic batching.

    The @modal.batched decorator causes Modal to accumulate concurrent caller
    requests and dispatch them together as a list to the transcribe() method.
    This maximizes GPU utilization: the container handles many audio files per
    invocation rather than one at a time.

    Input contract  (per caller element): bytes — raw audio file bytes in any
                                                   format supported by ffmpeg
                                                   (mp3, wav, m4a, ogg, flac …)
    Output contract (per caller element): str  — full transcription text

    Batching parameters:
        max_batch_size=16  dispatch immediately once 16 requests accumulate
        wait_ms=500        wait at most 500 ms before dispatching partial batch
    """

    # Expose model size as a Modal parameter so it can be changed at deploy time
    # e.g.  modal deploy solution.py --env MODEL_SIZE=medium
    model_size: str = modal.parameter(default="large-v3")

    @modal.enter()
    def load_model(self):
        """Load Whisper model once when the container starts (warm start)."""
        from faster_whisper import WhisperModel

        print(f"Loading faster-whisper '{self.model_size}' on GPU …")
        self.model = WhisperModel(
            self.model_size,
            device="cuda",
            compute_type="float16",   # fp16 for best GPU throughput
            download_root=MODEL_DIR,
        )
        print("Model ready.")

    @modal.batched(max_batch_size=16, wait_ms=500)
    def transcribe(self, audio_bytes_batch: list[bytes]) -> list[str]:
        """
        Transcribe a batch of audio files on the GPU.

        Modal calls this method with a list assembled from concurrent callers.
        Each element in audio_bytes_batch is one caller's single audio input.

        Parameters
        ----------
        audio_bytes_batch : list[bytes]
            Each element is the raw bytes of one audio file. Modal populates
            this list automatically by grouping concurrent .remote() calls up
            to max_batch_size=16, or after wait_ms=500 ms have elapsed.

        Returns
        -------
        list[str]
            Transcription text for each corresponding input, in the same order.
            len(result) == len(audio_bytes_batch) is always guaranteed by Modal.

        Notes
        -----
        faster-whisper processes each file sequentially on the GPU within the
        batch. The GPU utilization benefit comes from:
          1. Amortized model loading — loaded once, shared across all items.
          2. Reduced Modal scheduling overhead — one container activation serves
             up to 16 concurrent callers.
          3. VAD filtering skips silence, reducing wasted compute.
        For true tensor-level batching (fused forward pass across many utterance
        segments), pre-chunk audio into equal-length windows and process with a
        custom CTranslate2 batched_generate() call.
        """
        import os
        import tempfile

        results: list[str] = []

        for i, audio_bytes in enumerate(audio_bytes_batch):
            suffix = _detect_audio_suffix(audio_bytes)
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                segments, info = self.model.transcribe(
                    tmp_path,
                    beam_size=5,
                    language=None,      # auto-detect language per file
                    vad_filter=True,    # skip non-speech regions
                    vad_parameters=dict(min_silence_duration_ms=500),
                )
                text = " ".join(seg.text.strip() for seg in segments)
                print(
                    f"  [{i + 1}/{len(audio_bytes_batch)}] "
                    f"lang={info.language} dur={info.duration:.1f}s "
                    f"-> {len(text)} chars"
                )
                results.append(text)
            finally:
                os.unlink(tmp_path)

        return results


# ---------------------------------------------------------------------------
# Helper — sniff audio container format from magic bytes
# ---------------------------------------------------------------------------

def _detect_audio_suffix(data: bytes) -> str:
    """Return a file-extension hint based on the first few magic bytes."""
    if data[:4] == b"fLaC":
        return ".flac"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    if data[:4] == b"OggS":
        return ".ogg"
    if data[:4] == b"RIFF":
        return ".wav"
    return ".audio"   # ffmpeg handles most unknown containers gracefully


# ---------------------------------------------------------------------------
# Synthetic WAV generator — smoke-test without real audio files
# ---------------------------------------------------------------------------

def _make_silent_wav(duration_s: float = 2.0, sample_rate: int = 16_000) -> bytes:
    """Return bytes of a silent mono 16-bit PCM WAV at the given duration."""
    import struct

    num_samples = int(sample_rate * duration_s)
    data_size = num_samples * 2   # 16-bit = 2 bytes per sample
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b"data", data_size,
    )
    return header + b"\x00" * data_size


# ---------------------------------------------------------------------------
# Local entrypoint — run with:  modal run solution.py [audio1.mp3 audio2.wav …]
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main():
    """
    Submit multiple audio files to the batched transcriber and print results.

    Two caller patterns are demonstrated:
      Pattern 1 — .map()   : fan out a list; Modal batches server-side
      Pattern 2 — .spawn() : fire-and-forget with manual future collection

    Usage
    -----
    Smoke test (synthetic silent WAVs, no audio files needed):
        modal run solution.py

    Real audio files:
        modal run solution.py -- interview.mp3 lecture.m4a podcast.wav

    The transcriber accumulates concurrent .remote() calls up to
    max_batch_size=16, or dispatches after wait_ms=500 ms either way.
    """
    import pathlib
    import sys

    args = sys.argv[1:]
    if args:
        print(f"Reading {len(args)} audio file(s) from disk …")
        audio_bytes_list = [pathlib.Path(f).read_bytes() for f in args]
    else:
        print("No audio files supplied — generating 6 synthetic silent WAV blobs.")
        audio_bytes_list = [_make_silent_wav(d) for d in (2.0, 3.0, 4.0, 2.0, 3.0, 5.0)]

    transcriber = WhisperBatchTranscriber()

    # ------------------------------------------------------------------
    # Pattern 1: .map() — preferred for fan-out batch workloads.
    # Modal groups all concurrent requests into batches of up to 16.
    # ------------------------------------------------------------------
    print(f"\nSubmitting {len(audio_bytes_list)} file(s) via .map() …")
    results = list(transcriber.transcribe.map(audio_bytes_list))

    print("\n=== Transcription Results ===")
    for idx, text in enumerate(results, start=1):
        preview = (text[:120] + "…") if len(text) > 120 else text
        print(f"[{idx}] {preview!r}")

    return results


# ---------------------------------------------------------------------------
# Pattern 2: spawn + gather — import and call from any Modal function or script
# ---------------------------------------------------------------------------

def spawn_and_gather(audio_bytes_list: list[bytes]) -> list[str]:
    """
    Alternative caller pattern: fire all requests concurrently, collect later.

    Each .spawn() call returns a modal.FunctionCall future immediately.
    Modal batches the concurrent spawns server-side (up to max_batch_size=16
    or wait_ms=500 ms), then resolves all futures.

    This pattern is useful when you want to interleave other work between
    submission and result collection, or when inputs arrive asynchronously.

    Example
    -------
    from solution import WhisperBatchTranscriber, spawn_and_gather

    texts = spawn_and_gather([
        open("a.mp3", "rb").read(),
        open("b.wav", "rb").read(),
    ])
    print(texts)
    """
    transcriber = WhisperBatchTranscriber()
    futures = [transcriber.transcribe.spawn(audio) for audio in audio_bytes_list]
    return [f.get() for f in futures]
