---
name: modal-finetuning
description: Design and debug Modal GPU fine-tuning workflows for LLM SFT/LoRA/QLoRA, diffusion LoRA, YOLO-style vision training, and GRPO post-training. Use whenever the user wants to fine-tune, post-train, adapt, resume, checkpoint, or tune a model on Modal GPUs, even if they only mention Unsloth, PEFT, LoRA, QLoRA, YOLO, Diffusers, GRPO, TRL, or verl. Do not use for from-scratch pretraining, inference serving, sandbox lifecycle, or generic batch orchestration.
license: MIT
---

# Modal Fine-Tuning

## Quick Start

1. Verify the actual local Modal environment before writing code.

```bash
modal --version
python -c "import modal,sys; print(modal.__version__); print(sys.executable)"
modal profile current
```

- Do not assume the default `python` interpreter matches the environment behind the `modal` CLI.
- Read [references/training-playbook.md](references/training-playbook.md) first.
- Confirm the training goal before writing code: LLM supervised fine-tuning, diffusion LoRA, YOLO-style vision fine-tuning, or GRPO post-training.
- Ground every implementation in the actual task: base model, dataset location and format, GPU type and count, checkpoint destination, secrets, and what should happen after training finishes.

## Choose the Workflow

- Use Unsloth or another PEFT-style path for LLM SFT, LoRA, or QLoRA on a single node. Read [references/llm-sft-and-lora.md](references/llm-sft-and-lora.md).
- Use the combined vision and diffusion path for YOLO dataset training or Diffusers LoRA image fine-tuning. Read [references/vision-and-diffusion-finetuning.md](references/vision-and-diffusion-finetuning.md).
- Use GRPO only for reinforcement-learning-style post-training. Prefer TRL for the simpler single-node path, and use verl when the task needs a more explicit rollout or trainer split, or more advanced vLLM-backed RL plumbing. Read [references/rl-post-training.md](references/rl-post-training.md).

## Default Rules

- Prefer PEFT methods such as LoRA or QLoRA before full fine-tuning unless the user explicitly needs weight updates across the whole model.
- Start with a cheap smoke test on a tiny ungated model and tiny dataset before a long or expensive run. Use it to validate image builds, trainer API compatibility, dataset formatting, checkpoint paths, and one saved sample artifact.
- Persist datasets, pretrained weights, checkpoints, merged adapters, and sample outputs in Modal Volumes. Do not rely on ephemeral container disk for anything that must survive retries or later inspection.
- Keep Hugging Face, Weights & Biases, Roboflow, and similar credentials in Modal Secrets.
- Design long runs so they can resume from checkpoints. Add retries only when resume behavior is correct.
- Set `timeout=` intentionally for long training jobs and keep one stateful container per training run by default. Prefer `single_use_containers=True` when retries should start from a fresh container.
- Use `@app.local_entrypoint` or a plain local launcher to expose hyperparameters and dataset switches as CLI arguments instead of hard-coding every experiment.
- Keep the first version single-node unless the user explicitly asks for clusters. Modal multi-node training is a separate advanced path and is currently a beta workflow.
- Store final artifacts in a layout that makes handoff obvious: base model cache, dataset cache, checkpoint tree, and final exported weights or adapters.
- If the task is really about serving the tuned model behind HTTP, OpenAI-compatible APIs, vLLM, or SGLang, stop and use `modal-llm-serving`.
- If the task is really about detached job orchestration, queueing, `.map`, `.spawn`, or `@modal.batched`, stop and use `modal-batch-processing`.
- If the task is really about sandbox lifecycle, tunnels, `Sandbox.exec(...)`, or secure runtime code execution infrastructure, stop and use `modal-sandbox`.

## Validate

- Run `npx skills add . --list` after editing the package metadata or skill descriptions.
- Keep `evals/evals.json` aligned with the actual workflow boundaries of the skill.

## References

- Read [references/training-playbook.md](references/training-playbook.md) first for shared storage, GPU, secret, and resume rules.
- Read [references/llm-sft-and-lora.md](references/llm-sft-and-lora.md) for single-node LLM SFT, LoRA, and QLoRA guidance grounded in the Unsloth example.
- Read [references/vision-and-diffusion-finetuning.md](references/vision-and-diffusion-finetuning.md) for YOLO and Diffusers LoRA training flows.
- Read [references/rl-post-training.md](references/rl-post-training.md) for GRPO with TRL or verl.
- Read [references/example-patterns.md](references/example-patterns.md) for compact adaptation templates.
- Read [references/troubleshooting.md](references/troubleshooting.md) for common training failures and recovery paths.
