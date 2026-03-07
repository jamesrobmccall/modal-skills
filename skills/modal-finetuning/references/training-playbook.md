# Training Playbook

Read this first. Use it to classify the fine-tuning job before choosing a specific framework.

## Start With the Objective

- Confirm whether the job is LLM supervised fine-tuning, diffusion LoRA, YOLO-style vision training, or GRPO post-training.
- Confirm the base model family, dataset location and format, GPU budget, checkpoint destination, and what happens after training finishes.
- Ask whether the output should be adapters only, merged weights, evaluation samples, or a handoff to a later serving workflow.
- For long or expensive jobs, plan a cheap smoke test first with a tiny public model, a tiny dataset, and very few steps so you can verify the end-to-end training loop before scaling up.

## Choose the Smallest Effective Adaptation

- Default to LoRA, QLoRA, or another PEFT path before full fine-tuning.
- Use full fine-tuning only when the user explicitly needs broad weight updates and can justify the extra GPU memory, runtime, and checkpoint size.
- For LLMs, prefer single-node Unsloth or PEFT-style flows for v1 work.
- For image generation, prefer Diffusers LoRA unless the user has a clear reason to retrain much more of the model.

## Persist State Intentionally

- Store base model caches, dataset caches, checkpoints, merged outputs, and representative samples in Modal Volumes.
- Design a stable directory layout so retries and later inspection find the same artifacts.
- Do not rely on ephemeral container disk for any artifact that matters after one container exits.
- Ground storage patterns in Modal's [Volumes guide](https://modal.com/docs/guide/volumes).

## Keep Secrets Out of Code

- Use `modal.Secret.from_name(...)` for Hugging Face, Weights & Biases, Roboflow, and similar credentials.
- Call out gated model access early. Some upstream models require license acceptance before the training run can start.
- If the user needs access into private data systems, describe the Secret requirement explicitly instead of embedding credentials in scripts.

## Size the GPU to the Workload

- Treat GPU choice as part of the design, not a postscript.
- Favor single-node runs first. Use 1 to 8 GPUs on one host when the workload or framework supports it.
- Prefer quantized or PEFT-based methods before scaling GPU count purely to make the model fit.
- Mention multi-node clusters only as an advanced path. Modal multi-node training is currently a beta workflow and is out of scope for this skill unless the user explicitly asks for it.

## Design for Resume, Not Hope

- Add `timeout=` intentionally for long runs.
- Add retries only when checkpoint resume is correct.
- Keep one stateful training container per run by default, and prefer `single_use_containers=True` on retry-sensitive jobs instead of relying on stale `max_inputs` guidance.
- Make resume points obvious and durable so a retried run can continue instead of silently starting over.
- Save at least one small post-training artifact, such as a sample generation or validation output, so the smoke test proves more than just "the process exited."

## Keep Boundaries Clear

- If the real problem is serving the trained model behind HTTP, OpenAI-compatible APIs, vLLM, or SGLang, use `modal-llm-serving`.
- If the real problem is detached orchestration, `.map`, `.spawn`, or result collection across many jobs, use `modal-batch-processing`.
- If the real problem is sandbox lifecycle, secure code execution infrastructure, tunnels, or snapshotting, use `modal-sandbox`.

## Primary Source Examples

- [Efficient LLM Finetuning with Unsloth](https://modal.com/docs/examples/unsloth_finetune)
- [Fine-tune Flux on your pet using LoRA](https://modal.com/docs/examples/diffusers_lora_finetune)
- [Fine-tune open source YOLO models for object detection](https://modal.com/docs/examples/finetune_yolo)
- [Train a model to solve math problems using GRPO and verl](https://modal.com/docs/examples/grpo_verl)
- [Train a model to solve coding problems using GRPO and TRL](https://modal.com/docs/examples/grpo_trl)
