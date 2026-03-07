"""
Whisper transcription on Modal using @modal.batched for GPU utilization.

This solution coalesces many individual audio transcription requests into
fewer GPU kernel launches, amortizing model load and kernel overhead.

Pattern: @app.cls with a single @modal.batched method.
"""

import modal

app = modal.App("whisper-batched-transcription")

# Modal image with whisper and its ffmpeg dependency
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install("openai-whisper", "torch")
)

# A Modal Volume used to cache the downloaded Whisper model weights so that
# warm containers reuse the weights without re-downloading them.
model_cache = modal.Volume.from_name("whisper-model-cache", create_if_missing=True)
MODEL_CACHE_PATH = "/model-cache"


@app.cls(
    image=image,
    gpu="T4",                      # T4 is cost-effective for Whisper inference
    volumes={MODEL_CACHE_PATH: model_cache},
    timeout=300,
)
class WhisperBatchTranscriber:
    """
    Loads the Whisper model once per warm container, then serves batched
    transcription requests using @modal.batched.

    Invocation model (from the skill reference):
      - Callers submit *individual* audio byte payloads.
      - @modal.batched accumulates up to max_batch_size inputs or waits
        wait_ms milliseconds before dispatching a single GPU call.
      - The implementation receives and returns lists; list lengths always match.
    """

    @modal.enter()
    def load_model(self):
        import whisper

        # Load model into GPU memory once; subsequent batched calls reuse it.
        self.model = whisper.load_model("base", download_root=MODEL_CACHE_PATH)

    @modal.batched(max_batch_size=16, wait_ms=200)
    def transcribe(self, audio_bytes_list: list[bytes]) -> list[str]:
        """
        Accept a batch of raw audio byte strings and return a matching list of
        transcription strings.

        max_batch_size=16  – largest batch the model can handle reliably on a T4
                             before running into GPU memory limits with 'base'.
                             Increase to 32 for the 'tiny' model; decrease for
                             'large' variants.
        wait_ms=200        – queue inputs for up to 200 ms to build a larger
                             batch. Tune lower (e.g. 50 ms) for latency-sensitive
                             workloads; higher (e.g. 500 ms) for pure throughput.
        """
        import io
        import tempfile
        import os
        import numpy as np
        import torch
        import whisper

        results: list[str] = []

        for audio_bytes in audio_bytes_list:
            # Write bytes to a temp file; whisper.load_audio expects a path.
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                # load_audio resamples to 16 kHz mono numpy array
                audio = whisper.load_audio(tmp_path)
                audio = whisper.pad_or_trim(audio)

                # log-Mel spectrogram on GPU
                mel = whisper.log_mel_spectrogram(audio).to(self.model.device)

                options = whisper.DecodingOptions(fp16=torch.cuda.is_available())
                result = whisper.decode(self.model, mel, options)
                results.append(result.text)
            finally:
                os.unlink(tmp_path)

        # The returned list must be the same length as the input list.
        assert len(results) == len(audio_bytes_list), (
            f"Length mismatch: {len(results)} results for "
            f"{len(audio_bytes_list)} inputs"
        )
        return results


# ---------------------------------------------------------------------------
# Caller example – local entrypoint
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main():
    """
    Demonstrates how callers submit individual inputs to a batched function.

    Two patterns shown:
      1. .remote() – submit one item, block until the batch fires and returns.
      2. .map()    – stream many items; clearest way to observe outputs in order.
    """
    import pathlib

    transcriber = WhisperBatchTranscriber()

    # --- Pattern 1: single remote call (blocks until batch window closes) ---
    sample_path = pathlib.Path("sample.wav")
    if sample_path.exists():
        audio_bytes = sample_path.read_bytes()
        transcript = transcriber.transcribe.remote(audio_bytes)
        print(f"Single call result: {transcript!r}")

    # --- Pattern 2: .map() over a list of audio files ---
    audio_dir = pathlib.Path("audio_samples")
    if audio_dir.is_dir():
        audio_files = sorted(audio_dir.glob("*.wav"))
        audio_payloads = [f.read_bytes() for f in audio_files]

        # .map() submits each item individually; @modal.batched coalesces them
        # server-side into GPU batches automatically.
        for audio_path, transcript in zip(
            audio_files,
            transcriber.transcribe.map(audio_payloads),
        ):
            print(f"{audio_path.name}: {transcript!r}")


# ---------------------------------------------------------------------------
# Programmatic caller (outside a local_entrypoint, e.g. from a web service)
# ---------------------------------------------------------------------------

def call_from_another_service(audio_bytes: bytes) -> str:
    """
    Example of looking up a deployed function by name and calling it.

    Deploy first:   modal deploy solution.py
    Then call from any Python process:
    """
    # Retrieve the deployed class without importing the module directly.
    WhisperRemote = modal.Cls.from_name("whisper-batched-transcription", "WhisperBatchTranscriber")
    transcriber = WhisperRemote()
    return transcriber.transcribe.remote(audio_bytes)
