#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from typing import Any

import modal

MINUTES = 60

APP_NAME = "qwen3-throughput"
GPU = "h100"
MODEL_NAME = "Qwen/Qwen3-1.7B-FP8"
MODEL_REVISION = "1641e6c1b620b7ed7e8711b443990429a23b1b99"
DEFAULT_BATCH_SIZE = 64
DEFAULT_MAX_MODEL_LEN = 4096
DEFAULT_MAX_TOKENS = 128
DEFAULT_NUM_PROMPTS = 256
DEFAULT_PROMPT_CHARS = 1800
SYSTEM_PROMPT = (
    "You are a concise release-ops assistant. Respond in 2-4 sentences and omit "
    "reasoning traces."
)
TOPICS = (
    "queue backpressure",
    "GPU scheduling",
    "token accounting",
    "batch sizing",
    "compile cache reuse",
    "autoscaling policy",
    "warm-start behavior",
    "throughput regression triage",
)

app = modal.App(APP_NAME)

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.9.0-devel-ubuntu22.04",
        add_python="3.13",
    )
    .entrypoint([])
    .uv_pip_install("vllm==0.13.0", "huggingface-hub==0.36.0")
    .env({"HF_XET_HIGH_PERFORMANCE": "1"})
)

hf_cache = modal.Volume.from_name(
    "qwen3-1_7b-fp8-huggingface-cache",
    create_if_missing=True,
)
vllm_cache = modal.Volume.from_name(
    "qwen3-1_7b-fp8-vllm-cache",
    create_if_missing=True,
)

VLLM_KWARGS = {
    "max_model_len": DEFAULT_MAX_MODEL_LEN,
    "attention_backend": "flashinfer",
    "async_scheduling": True,
    "gpu_memory_utilization": 0.95,
    "tensor_parallel_size": 1,
}
CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}
EMPTY_THINK_RE = re.compile(r"^<think>\s*</think>\s*", re.DOTALL)


@dataclass
class BatchMetrics:
    batch_size: int
    duration_s: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_tokens_per_s: float
    completion_tokens_per_s: float
    total_tokens_per_s: float
    samples: list[str]


def build_prompt(index: int, target_chars: int) -> str:
    topic = TOPICS[index % len(TOPICS)]
    intro = (
        f"Request {index}: summarize the operational implications of the following "
        f"throughput tuning notes for {topic}.\n\n"
    )
    filler = (
        "Release note: the batch inference worker now groups prompts by similar "
        "length, warms the engine before timing, caches model weights in a shared "
        "volume, records prompt and completion token counts, and prefers a single "
        "H100 for FP8 workloads to maximize throughput per GPU.\n"
    )
    closing = (
        "\nReturn one short summary and one recommended next step for the team."
    )

    chunks = [intro]
    while len("".join(chunks)) + len(closing) < target_chars:
        chunks.append(filler)
    chunks.append(closing)
    return "".join(chunks)


def build_prompts(count: int, target_chars: int) -> list[str]:
    return [build_prompt(index, target_chars) for index in range(count)]


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def sampling_overrides(max_tokens: int) -> dict[str, Any]:
    return {
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
    }


def strip_empty_think_block(text: str) -> str:
    return EMPTY_THINK_RE.sub("", text).strip()


@app.cls(
    image=image,
    gpu=GPU,
    timeout=20 * MINUTES,
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/vllm": vllm_cache,
    },
)
class Qwen3Throughput:
    @modal.enter()
    def start(self) -> None:
        import vllm

        self.vllm = vllm
        self.llm = vllm.LLM(
            model=MODEL_NAME,
            revision=MODEL_REVISION,
            tokenizer_revision=MODEL_REVISION,
            **VLLM_KWARGS,
        )

        warmup_messages = [
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "/no_think Reply with the single word ready.",
                },
            ]
        ]
        warmup_params = vllm.SamplingParams(**sampling_overrides(max_tokens=16))
        self.llm.chat(
            warmup_messages,
            sampling_params=warmup_params,
            chat_template_kwargs=CHAT_TEMPLATE_KWARGS,
        )

    def _run_batch(
        self,
        prompts: list[str],
        max_tokens: int,
        sample_limit: int = 3,
    ) -> dict[str, Any]:
        sampling_params = self.vllm.SamplingParams(
            **sampling_overrides(max_tokens=max_tokens)
        )
        messages = [
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
            for prompt in prompts
        ]

        started_at = time.perf_counter()
        responses = self.llm.chat(
            messages,
            sampling_params=sampling_params,
            chat_template_kwargs=CHAT_TEMPLATE_KWARGS,
        )
        duration_s = time.perf_counter() - started_at

        prompt_tokens = sum(len(response.prompt_token_ids) for response in responses)
        completion_tokens = sum(
            len(response.outputs[0].token_ids) for response in responses
        )
        total_tokens = prompt_tokens + completion_tokens

        metrics = BatchMetrics(
            batch_size=len(prompts),
            duration_s=round(duration_s, 3),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            prompt_tokens_per_s=round(prompt_tokens / duration_s, 1),
            completion_tokens_per_s=round(completion_tokens / duration_s, 1),
            total_tokens_per_s=round(total_tokens / duration_s, 1),
            samples=[
                strip_empty_think_block(response.outputs[0].text)
                for response in responses[:sample_limit]
            ],
        )
        payload = asdict(metrics)
        print(json.dumps(payload, sort_keys=True))
        return payload

    @modal.method()
    def generate_batch(
        self,
        prompts: list[str],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        return self._run_batch(prompts, max_tokens=max_tokens)

    @modal.method()
    def run_benchmark(
        self,
        prompt_batches: list[list[str]],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        batch_metrics = [
            self._run_batch(batch, max_tokens=max_tokens, sample_limit=1)
            for batch in prompt_batches
        ]
        in_worker_wall_time_s = time.perf_counter() - started_at
        generation_time_s = sum(batch["duration_s"] for batch in batch_metrics)
        prompt_tokens = sum(batch["prompt_tokens"] for batch in batch_metrics)
        completion_tokens = sum(batch["completion_tokens"] for batch in batch_metrics)
        total_tokens = prompt_tokens + completion_tokens

        return {
            "batch_metrics": batch_metrics,
            "num_batches": len(batch_metrics),
            "in_worker_wall_time_s": round(in_worker_wall_time_s, 3),
            "generation_time_s": round(generation_time_s, 3),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "prompt_tokens_per_s_generation_only": round(
                prompt_tokens / generation_time_s, 1
            ),
            "completion_tokens_per_s_generation_only": round(
                completion_tokens / generation_time_s, 1
            ),
            "total_tokens_per_s_generation_only": round(
                total_tokens / generation_time_s, 1
            ),
            "prompt_tokens_per_s_in_worker": round(
                prompt_tokens / in_worker_wall_time_s, 1
            ),
            "completion_tokens_per_s_in_worker": round(
                completion_tokens / in_worker_wall_time_s, 1
            ),
            "total_tokens_per_s_in_worker": round(
                total_tokens / in_worker_wall_time_s, 1
            ),
        }

    @modal.exit()
    def stop(self) -> None:
        del self.llm


def summarize_results(
    benchmark: dict[str, Any],
    wall_time_s: float,
    num_prompts: int,
    batch_size: int,
    prompt_chars: int,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "gpu": GPU,
        "num_prompts": num_prompts,
        "batch_size": batch_size,
        "num_batches": benchmark["num_batches"],
        "prompt_chars": prompt_chars,
        "max_tokens": max_tokens,
        "end_to_end_wall_time_s": round(wall_time_s, 3),
        "in_worker_wall_time_s": benchmark["in_worker_wall_time_s"],
        "generation_time_s": benchmark["generation_time_s"],
        "prompt_tokens": benchmark["prompt_tokens"],
        "completion_tokens": benchmark["completion_tokens"],
        "total_tokens": benchmark["total_tokens"],
        "prompt_tokens_per_s_generation_only": benchmark[
            "prompt_tokens_per_s_generation_only"
        ],
        "completion_tokens_per_s_generation_only": benchmark[
            "completion_tokens_per_s_generation_only"
        ],
        "total_tokens_per_s_generation_only": benchmark[
            "total_tokens_per_s_generation_only"
        ],
        "prompt_tokens_per_s_end_to_end": round(
            benchmark["prompt_tokens"] / wall_time_s, 1
        ),
        "completion_tokens_per_s_end_to_end": round(
            benchmark["completion_tokens"] / wall_time_s, 1
        ),
        "total_tokens_per_s_end_to_end": round(
            benchmark["total_tokens"] / wall_time_s, 1
        ),
    }


@app.local_entrypoint()
def main(
    num_prompts: int = DEFAULT_NUM_PROMPTS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    prompt_chars: int = DEFAULT_PROMPT_CHARS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    wait_for_results: bool = True,
) -> None:
    if num_prompts < 1:
        raise ValueError("num_prompts must be positive")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if prompt_chars < 1:
        raise ValueError("prompt_chars must be positive")
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")

    prompts = build_prompts(num_prompts, prompt_chars)
    prompt_batches = chunked(prompts, batch_size)
    worker = Qwen3Throughput()

    started_at = time.perf_counter()
    job = worker.run_benchmark.spawn(prompt_batches, max_tokens=max_tokens)

    if not wait_for_results:
        print("Collect results later with modal.FunctionCall.from_id")
        print("FunctionCall ID:", job.object_id)
        return

    benchmark = job.get()
    wall_time_s = time.perf_counter() - started_at
    summary = summarize_results(
        benchmark=benchmark,
        wall_time_s=wall_time_s,
        num_prompts=num_prompts,
        batch_size=batch_size,
        prompt_chars=prompt_chars,
        max_tokens=max_tokens,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("Batch metrics:")
    print(json.dumps(benchmark["batch_metrics"], indent=2, sort_keys=True))

    if benchmark["batch_metrics"] and benchmark["batch_metrics"][0]["samples"]:
        print("Sample outputs:")
        for sample in benchmark["batch_metrics"][0]["samples"]:
            print(f"- {sample}")
