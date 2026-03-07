# Example Patterns

Use these as compact adaptation templates. Pick one and specialize it to the user's model, dataset, and artifact requirements.

## Pattern 1: Single-GPU LLM QLoRA

- Base the workflow on the Unsloth example.
- Mount one Volume for model cache and one for checkpoints.
- Use Secrets for Hugging Face and optional Weights & Biases logging.
- Expose model name, dataset name, sequence length, LoRA settings, and max steps via `@app.local_entrypoint`.
- Resume from the latest checkpoint on retry.

## Pattern 2: Diffusion LoRA With Inspectable Outputs

- Base the workflow on the Diffusers LoRA example.
- Store source images, checkpoints, and generated sample images in a Volume.
- Call out any gated base-model license acceptance before the run starts.
- Save representative prompts and outputs so the user can compare training runs later.

## Pattern 3: YOLO Dataset Plus Training Artifacts

- Base the workflow on the YOLO example.
- Download or mount the dataset into a Volume-backed path.
- Run a short debug pass before a long training job.
- Persist weights, logs, and validation artifacts for later evaluation.

## Pattern 4: GRPO With TRL First

- Start with the TRL GRPO example unless the user clearly needs verl.
- Keep checkpoints in a Volume and make the latest checkpoint discoverable.
- Use Sandboxes only when the reward function must execute generated code or another risky program.
- Keep any later inference endpoint out of scope for this phase and hand that step to `modal-llm-serving`.
