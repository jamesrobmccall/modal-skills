# Small LLM PEFT Smoke Test

## Outcome

- Status: passed
- Modal app: `ap-Y6t2k0Jp3nsF33KWayXF3k`
- GPU: `T4`
- Model: `HuggingFaceTB/SmolLM2-135M-Instruct`
- Training steps: `6`
- Train examples: `6`

## Artifacts

- Remote summary: [summary.json](/Users/jmccall/Documents/Coding/modal_skills/modal_skills/skills/modal-finetuning-workspace/iteration-1/eval-0-small-llm/with_skill/outputs/remote_artifacts/summary.json)
- Remote sample: [sample.txt](/Users/jmccall/Documents/Coding/modal_skills/modal_skills/skills/modal-finetuning-workspace/iteration-1/eval-0-small-llm/with_skill/outputs/remote_artifacts/sample.txt)
- Remote adapter directory: `modal-finetuning-smoke-checkpoints:/runs/smoke-20260307-210910/final_adapter`

## What Worked

- Modal ran a real single-GPU fine-tuning loop and completed successfully.
- The job wrote checkpoints, a final adapter, and a sample output into a Modal Volume.
- A cheap PEFT smoke test on a tiny public instruct model was enough to validate storage, training, and artifact handoff.

## Issues Found

- The first draft used an outdated TRL SFTTrainer signature. `tokenizer=` failed; the current path needed `SFTConfig` plus `processing_class=`.
- The first draft used Modal `max_inputs`, which now emits a deprecation warning in favor of `single_use_containers=True`.
- The sample output remained mostly base-model behavior, which is acceptable for a 6-step smoke test and confirms this run is a harness check, not a quality benchmark.

## Skill Updates Made

- Added an explicit "cheap smoke test first" rule to the core skill and training playbook.
- Clarified that plain PEFT is the right fallback for tiny public models or when Unsloth support is uncertain.
- Added a troubleshooting note about training-library API drift.
