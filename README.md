# Modal Skills

Anthropic-first [Claude Skills](https://claude.com/blog/complete-guide-to-building-skills-for-claude) for working with [Modal](https://modal.com/docs/). The repo packages reusable skills for Modal Sandboxes, GPU fine-tuning, self-hosted LLM inference services, and batch-processing workflows so agents can pick the right Modal pattern without re-deriving it from scratch.

## Skills

| Skill | Use when | Do not use when | Example prompt |
| --- | --- | --- | --- |
| [`modal-sandbox`](skills/modal-sandbox/) | You need isolated code execution, a long-lived controller loop, a tunneled service, runtime file exchange, or snapshot-based restore flows on Modal. | The real task is a regular `@app.function` deployment, LLM serving, or batch job orchestration rather than sandbox lifecycle and control. | "Create a Modal Sandbox that runs a FastAPI app and give me the public URL." |
| [`modal-finetuning`](skills/modal-finetuning/) | You need to fine-tune or post-train a model on Modal GPUs, including LLM SFT/LoRA/QLoRA, diffusion LoRA, YOLO-style vision training, or GRPO workflows. | The real task is from-scratch pretraining, inference serving, sandbox lifecycle, or generic batch orchestration rather than training. | "Fine-tune Qwen on my dataset with LoRA on Modal and make the checkpoints resumable." |
| [`modal-llm-serving`](skills/modal-llm-serving/) | You need a self-hosted vLLM or SGLang text-generation service on Modal, an OpenAI-compatible endpoint for an open-weight model, cold-start tuning, low-latency routing, or throughput benchmarking. | The task is embeddings, generic Hugging Face pipeline serving, diffusion inference, fine-tuning, RAG, or an app that only calls OpenAI's hosted API. | "Deploy Qwen on Modal behind an OpenAI-compatible endpoint and tune cold starts." |
| [`modal-batch-processing`](skills/modal-batch-processing/) | You need `.map`, `.starmap`, `.spawn`, `.spawn_map`, or `@modal.batched` to run CPU or GPU jobs on Modal. | The primary problem is self-hosted LLM serving, model training, or sandbox lifecycle rather than detached jobs, result collection, or dynamic batching. | "Design a Modal batch workflow that fans out OCR jobs and lets me poll results later." |

## Which Skill Should I Use?

- Choose `modal-sandbox` when the core problem is interactive execution, stateful sandbox control, tunnels, or filesystem and snapshot handling.
- Choose `modal-finetuning` when the core problem is training or adapting model weights on Modal GPUs, including LLM LoRA or QLoRA, diffusion LoRA, YOLO fine-tuning, or GRPO post-training.
- Choose `modal-llm-serving` when the core problem is self-hosted open-weight text generation with vLLM or SGLang, including API shape, GPU sizing, latency, cold starts, or throughput.
- Choose `modal-batch-processing` when the core problem is job orchestration, fan-out, detached runs, result gathering, retries, or dynamic batching.

## Install From GitHub

List the published skills before installing anything:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --list
```

Install one skill:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-sandbox
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-finetuning
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-llm-serving
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-batch-processing
```

Install one skill for Claude Code explicitly:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-finetuning --agent claude-code
```

Install all skills:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --skill '*'
```

Install all skills globally without prompts:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --skill '*' --agent claude-code -g -y
```

## Develop Locally

List the skills in the checked-out repo:

```bash
npx skills add . --list
```

Install a local copy of one skill into Claude Code while iterating:

```bash
npx skills add . --skill modal-finetuning --agent claude-code
```

## Public Repo Surface

Only `skills/<published-skill>/` is part of the public package.

- `.agents/skills/` and `.claude/skills/` are local helper install locations and are not published.
- `skills/*-workspace/` contains generated eval runs, benchmarks, and transcripts and is kept local.
- `skills-lock.json` is local tooling state and is not published.

Keep those paths out of commits so a clean checkout exposes only the four published Modal skills.

## Repository Layout

```text
skills/
  <skill-name>/
    SKILL.md
    agents/openai.yaml
    evals/
    references/
    scripts/        # optional
```

## Contributing

Keep skill folders machine-facing and the root README human-facing.

- Use Anthropic-style frontmatter in `SKILL.md`: `name`, `description`, `license`.
- Keep `SKILL.md` short and procedural. Put variant-specific detail, examples, and troubleshooting in `references/`.
- Keep `evals/evals.json` and `evals/trigger-evals.json` aligned with the current skill boundary.
- Add `scripts/` only when runnable artifacts or deterministic helpers make repeated use materially better.
- Keep `agents/openai.yaml` aligned with the skill: `display_name`, `short_description`, `default_prompt`, and concise tags.
- Validate public discovery with `npx skills add . --list` from a clean checkout or tracked-only copy before opening a PR.
- Re-run the relevant script in `scripts/` when you change an executable example or workflow artifact.

## License

[MIT](LICENSE)
