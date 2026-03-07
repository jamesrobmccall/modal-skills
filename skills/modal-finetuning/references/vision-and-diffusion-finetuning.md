# Vision And Diffusion Fine-Tuning

Use this reference for image-model adaptation on Modal: YOLO-style object detection training and Diffusers LoRA training.

## Diffusion LoRA

- Start from Modal's [Diffusers LoRA example](https://modal.com/docs/examples/diffusers_lora_finetune).
- Prefer LoRA-style adaptation for small custom image sets and style or subject transfer.
- Store training outputs, checkpoints, and sample generations in a Modal Volume so the user can inspect results after the run.
- Call out gated model access and Hugging Face Secret requirements early.
- Keep training separate from any later Gradio or HTTP serving; if the user wants to deploy the model afterward, hand off that step to `modal-llm-serving`.

## YOLO Fine-Tuning

- Start from Modal's [YOLO fine-tuning example](https://modal.com/docs/examples/finetune_yolo).
- Confirm whether the dataset comes from Roboflow or another source. Use a Secret for Roboflow API access when needed.
- Persist the downloaded dataset and training artifacts in a Modal Volume so later evaluation and inference can reuse them.
- Keep the first implementation single-node and GPU-aware.
- Focus the guidance on training, validation artifacts, and dataset layout rather than interactive streaming inference.

## Shared Rules

- Keep the dataset path, checkpoints, and exported artifacts in stable directories inside mounted Volumes.
- Use small debug or quick-check runs first when the user is still validating dataset wiring.
- Treat sample outputs and validation metrics as first-class artifacts, not temporary byproducts.
- Separate training concerns from post-training serving or web UX.

## When Not To Use This

- Do not use this reference for LLM SFT, LoRA, or QLoRA.
- Do not use this reference for GRPO or other RL post-training.
- Do not use this reference when the main task is building a streaming or HTTP inference service.
