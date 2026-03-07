# RL Post-Training

Use this reference for GRPO-style reinforcement-learning post-training on Modal.

## Choose TRL Or verl

- Prefer TRL for the simpler single-node path. Start from Modal's [GRPO with TRL example](https://modal.com/docs/examples/grpo_trl) when the user wants a more direct trainer flow.
- Use verl when the task needs a more explicit rollout or trainer split, or a more advanced RL stack grounded in Modal's [GRPO with verl example](https://modal.com/docs/examples/grpo_verl).
- Treat GRPO as a different workflow from supervised fine-tuning. Do not collapse RL design into ordinary SFT guidance.

## What To Confirm

- The reward function shape and whether it depends on secure code execution, external APIs, or offline scoring.
- The dataset schema expected by the trainer.
- Whether vLLM is only used for generation inside the RL loop or whether the user is also asking for a later serving deployment.
- The checkpoint cadence, logging requirements, and GPU budget.

## Implementation Rules

- Persist checkpoints in a Modal Volume and make the latest usable checkpoint easy to identify.
- Use Secrets for Hugging Face, Weights & Biases, and any external reward dependencies.
- Treat sandbox-backed execution as a reward-evaluation detail, not the main platform choice. If the user needs help designing Sandboxes themselves, hand off that part to `modal-sandbox`.
- Keep serving concerns separate. If the user wants to expose the trained checkpoint behind HTTP afterward, hand off that phase to `modal-llm-serving`.
- Stay single-node by default in this skill. Mention clusters only as an advanced future path.

## Practical Defaults

- Start with TRL unless the user describes requirements that clearly need verl's more explicit pipeline structure.
- Keep the reward function deterministic enough to debug. If reward noise is high, say so.
- Use resumeable checkpoints and detached runs for long training jobs, but do not drift into generic job-orchestration advice unless the user's actual problem is orchestration.
- Be explicit about the memory tradeoff when vLLM shares or competes for GPU memory with the trainer.

## When Not To Use This

- Do not use this reference for plain SFT, LoRA, or QLoRA.
- Do not use this reference for diffusion or YOLO training.
- Do not use this reference for standalone inference serving architecture.
