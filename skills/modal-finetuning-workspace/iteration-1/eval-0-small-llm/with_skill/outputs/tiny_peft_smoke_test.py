import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import modal

app = modal.App("modal-finetuning-smoke-test")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "accelerate==1.9.0",
        "datasets==3.6.0",
        "hf-transfer==0.1.9",
        "peft==0.16.0",
        "sentencepiece==0.2.0",
        "torch==2.7.0",
        "transformers==4.54.0",
        "trl==0.19.1",
    )
    .env(
        {
            "HF_HOME": "/model_cache/hf",
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
        }
    )
)

with image.imports():
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

MODEL_CACHE_VOLUME = modal.Volume.from_name(
    "modal-finetuning-smoke-model-cache", create_if_missing=True
)
CHECKPOINT_VOLUME = modal.Volume.from_name(
    "modal-finetuning-smoke-checkpoints", create_if_missing=True
)

MODEL_NAME = "HuggingFaceTB/SmolLM2-135M-Instruct"
GPU_TYPE = "T4"


@dataclass
class SmokeTestConfig:
    model_name: str = MODEL_NAME
    max_steps: int = 6
    save_steps: int = 3
    max_seq_length: int = 512
    learning_rate: float = 2e-4
    batch_size: int = 1
    gradient_accumulation_steps: int = 1
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()


def build_messages():
    return [
        {
            "messages": [
                {"role": "system", "content": "You answer briefly and concretely."},
                {
                    "role": "user",
                    "content": "What is Modal used for?",
                },
                {
                    "role": "assistant",
                    "content": "Modal is used to run Python workloads, GPUs, batch jobs, and web endpoints in the cloud.",
                },
            ]
        },
        {
            "messages": [
                {"role": "system", "content": "You answer briefly and concretely."},
                {
                    "role": "user",
                    "content": "Why would I use LoRA for fine-tuning?",
                },
                {
                    "role": "assistant",
                    "content": "LoRA updates a small adapter instead of the full model, which reduces memory use, checkpoint size, and cost.",
                },
            ]
        },
        {
            "messages": [
                {"role": "system", "content": "You answer briefly and concretely."},
                {
                    "role": "user",
                    "content": "Where should checkpoints go during a Modal training run?",
                },
                {
                    "role": "assistant",
                    "content": "Checkpoints should be written to a Modal Volume so they survive container restarts and can be reused later.",
                },
            ]
        },
        {
            "messages": [
                {"role": "system", "content": "You answer briefly and concretely."},
                {
                    "role": "user",
                    "content": "How do Secrets fit into a training workflow?",
                },
                {
                    "role": "assistant",
                    "content": "Use Modal Secrets for tokens such as Hugging Face or Weights and Biases credentials instead of hard-coding them in source files.",
                },
            ]
        },
        {
            "messages": [
                {"role": "system", "content": "You answer briefly and concretely."},
                {
                    "role": "user",
                    "content": "What should I test before a long fine-tune?",
                },
                {
                    "role": "assistant",
                    "content": "Run a tiny smoke test first to verify dataset formatting, model loading, checkpoint paths, and the training loop before spending on a large job.",
                },
            ]
        },
        {
            "messages": [
                {"role": "system", "content": "You answer briefly and concretely."},
                {
                    "role": "user",
                    "content": "When should I switch from training guidance to serving guidance?",
                },
                {
                    "role": "assistant",
                    "content": "Once the model artifact exists and the task becomes exposing an inference API, switch to the serving workflow instead of extending the training job.",
                },
            ]
        },
    ]


def render_messages(tokenizer, messages, add_generation_prompt: bool) -> str:
    if getattr(tokenizer, "chat_template", None):
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=add_generation_prompt,
        )

    rendered = []
    for message in messages:
        rendered.append(f"{message['role']}: {message['content']}")
    if add_generation_prompt:
        rendered.append("assistant:")
    return "\n".join(rendered)


def build_dataset(tokenizer):
    rows = []
    for example in build_messages():
        rows.append(
            {
                "text": render_messages(
                    tokenizer,
                    example["messages"],
                    add_generation_prompt=False,
                )
            }
        )
    return Dataset.from_list(rows)


@app.function(
    image=image,
    gpu=GPU_TYPE,
    timeout=30 * 60,
    volumes={
        "/model_cache": MODEL_CACHE_VOLUME,
        "/checkpoints": CHECKPOINT_VOLUME,
    },
    single_use_containers=True,
)
def run_smoke_test(config: SmokeTestConfig) -> dict:
    run_name = datetime.utcnow().strftime("smoke-%Y%m%d-%H%M%S")
    run_dir = Path("/checkpoints") / "runs" / run_name
    adapter_dir = run_dir / "final_adapter"
    run_dir.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        config.model_name,
        cache_dir="/model_cache/base-models",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config.model_name,
        cache_dir="/model_cache/base-models",
        torch_dtype=torch.float16,
    )
    model.config.use_cache = False

    train_dataset = build_dataset(tokenizer)

    peft_config = LoraConfig(
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules="all-linear",
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=train_dataset,
        peft_config=peft_config,
        args=SFTConfig(
            output_dir=str(run_dir / "checkpoints"),
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=config.gradient_accumulation_steps,
            learning_rate=config.learning_rate,
            max_steps=config.max_steps,
            save_steps=config.save_steps,
            save_strategy="steps",
            logging_steps=1,
            eval_strategy="no",
            dataset_text_field="text",
            max_length=config.max_seq_length,
            packing=False,
            fp16=True,
            report_to="none",
            seed=42,
        ),
    )

    trainer.train()
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    prompt_messages = [
        {"role": "system", "content": "You answer briefly and concretely."},
        {
            "role": "user",
            "content": "What should I test before a long fine-tune on Modal?",
        },
    ]
    prompt = render_messages(tokenizer, prompt_messages, add_generation_prompt=True)
    encoded = tokenizer(prompt, return_tensors="pt").to(trainer.model.device)

    with torch.no_grad():
        output = trainer.model.generate(
            **encoded,
            max_new_tokens=48,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    sample_text = tokenizer.decode(output[0], skip_special_tokens=True)
    sample_path = run_dir / "sample.txt"
    sample_path.write_text(sample_text)

    summary = {
        "run_name": run_name,
        "model_name": config.model_name,
        "gpu": GPU_TYPE,
        "train_examples": len(train_dataset),
        "max_steps": config.max_steps,
        "adapter_dir": str(adapter_dir),
        "sample_path": str(sample_path),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    CHECKPOINT_VOLUME.commit()
    MODEL_CACHE_VOLUME.commit()
    return summary


@app.local_entrypoint()
def main():
    summary = run_smoke_test.remote(SmokeTestConfig())
    print(json.dumps(summary, indent=2))
