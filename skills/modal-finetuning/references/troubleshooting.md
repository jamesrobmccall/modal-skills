# Troubleshooting

## Out Of Memory

- Reduce sequence length, batch size, or generation length before immediately adding GPUs.
- Prefer LoRA or QLoRA over full fine-tuning when the model barely fits.
- For RL workflows, call out vLLM memory pressure separately from trainer memory pressure.

## Bad GPU Sizing

- Re-evaluate model size, quantization mode, and checkpoint format together.
- If the user only says "use a GPU," force a concrete GPU choice into the design.
- Mention multi-node clusters only if the single-node path clearly cannot satisfy the requirement.

## Training Restarts From Scratch

- Check that checkpoints are written to a Modal Volume, not local container disk.
- Check that retry behavior actually points training at the latest checkpoint.
- Check that the checkpoint directory layout is stable across runs.

## Volume Layout Confusion

- Separate base model cache, dataset cache, checkpoints, and exported artifacts into distinct directories.
- Keep names deterministic so multiple experiments can coexist without collisions.
- If later serving is planned, keep exported adapters or merged weights in a clean handoff path.

## Dataset Staging Problems

- Verify the dataset provider and required Secret before debugging the trainer.
- For small custom image sets, confirm the files are actually reachable from the training function.
- For YOLO datasets, verify the YAML or dataset metadata matches the expected format before blaming Modal.

## RL Or vLLM Integration Failures

- Separate trainer failure from rollout or generation failure before changing everything at once.
- Be explicit about whether vLLM runs colocated with the trainer or on separate GPUs.
- If the user asks to expose a trained checkpoint behind an API, stop and switch to `modal-llm-serving` for that phase.
