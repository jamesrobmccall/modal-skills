# LLM SFT And LoRA

Use this reference for single-node LLM supervised fine-tuning on Modal.

## Default Path

- Start from the Modal [Unsloth fine-tuning example](https://modal.com/docs/examples/unsloth_finetune).
- Prefer Unsloth or a PEFT-based workflow for SFT, LoRA, and QLoRA on a single node.
- Default to LoRA or QLoRA for cost-sensitive work unless the user explicitly requires full fine-tuning.

## What To Confirm

- Base model name and whether it can fit with the intended quantization mode.
- Dataset source, format, and whether it should be cached locally in a Volume.
- Whether the output should be an adapter, merged model, tokenizer, or all three.
- Logging requirements such as Weights & Biases.

## Implementation Rules

- Cache the pretrained model in a Modal Volume to avoid redownloading it on every run.
- Keep checkpoints in a separate Volume path from the base model cache.
- Use Secrets for Hugging Face and Weights & Biases when relevant.
- Expose major hyperparameters through `@app.local_entrypoint` or CLI flags instead of rewriting source for every experiment.
- Prefer structured config objects so dataset, optimizer, LoRA, and checkpoint settings stay grouped and easy to review.
- Resume from checkpoints on retries rather than starting over.

## Practical Defaults

- Use LoRA target modules that match the model family rather than assuming one universal list.
- Keep batch size, gradient accumulation, sequence length, and quantization choices tied to the chosen GPU memory budget.
- Save often enough to resume usefully, but not so often that checkpointing dominates runtime.
- Keep training and later inference separate. If the user wants to serve the result, hand off to `modal-llm-serving` after the training artifact exists.

## When Not To Use This

- Do not use this path for GRPO or other RL-style post-training.
- Do not use this path for diffusion or YOLO image tasks.
- Do not use this path to design a vLLM or SGLang endpoint.
