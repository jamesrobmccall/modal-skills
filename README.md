# Modal Skills

Anthropic-first [Claude Skills](https://claude.com/blog/complete-guide-to-building-skills-for-claude) for working with [Modal](https://modal.com/docs/). The repo packages reusable skills for Modal Sandboxes, LLM inference services, and batch-processing workflows so agents can pick the right Modal pattern without re-deriving it from scratch.

## Skills

| Skill | Use when | Do not use when | Example prompt |
| --- | --- | --- | --- |
| [`modal-sandbox`](skills/modal-sandbox/) | You need secure code execution, a long-lived controller loop, a tunneled service, runtime file exchange, or snapshot-based restore flows on Modal. | The real task is LLM serving or batch job orchestration rather than sandbox lifecycle and control. | "Create a Modal Sandbox that runs a FastAPI app and give me the public URL." |
| [`modal-llm-serving`](skills/modal-llm-serving/) | You need a Modal-hosted vLLM or SGLang inference service, an OpenAI-compatible API, cold-start tuning, low-latency routing, or throughput benchmarking. | The task is fine-tuning, RAG, training, or a broader ML pipeline outside inference serving. | "Deploy Qwen on Modal behind an OpenAI-compatible endpoint and tune cold starts." |
| [`modal-batch-processing`](skills/modal-batch-processing/) | You need `.map`, `.starmap`, `.spawn`, `.spawn_map`, or `@modal.batched` to run CPU or GPU jobs on Modal. | The primary problem is HTTP LLM serving architecture rather than detached jobs, result collection, or dynamic batching. | "Design a Modal batch workflow that fans out OCR jobs and lets me poll results later." |

## Which Skill Should I Use?

- Choose `modal-sandbox` when the core problem is interactive execution, stateful sandbox control, tunnels, or filesystem and snapshot handling.
- Choose `modal-llm-serving` when the core problem is inference serving with vLLM or SGLang, including API shape, GPU sizing, latency, or cold starts.
- Choose `modal-batch-processing` when the core problem is job orchestration, fan-out, detached runs, result gathering, retries, or dynamic batching.

## Install From GitHub

List the published skills before installing anything:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --list
```

Install one skill:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-sandbox
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-llm-serving
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-batch-processing
```

Install one skill for Claude Code explicitly:

```bash
npx skills add https://github.com/jamesrobmccall/modal_skills --skill modal-sandbox --agent claude-code
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
npx skills add . --skill modal-sandbox --agent claude-code
```

## Repository Layout

```text
skills/
  <skill-name>/
    SKILL.md
    agents/openai.yaml
    references/
    scripts/
```

## Contributing

Keep skill folders machine-facing and the root README human-facing.

- Use Anthropic-style frontmatter in `SKILL.md`: `name`, `description`, `license`.
- Keep `SKILL.md` short and procedural. Put variant-specific detail, examples, and troubleshooting in `references/`.
- Add `scripts/` only when runnable artifacts or deterministic helpers make repeated use materially better.
- Keep `agents/openai.yaml` aligned with the skill: `display_name`, `short_description`, `default_prompt`, and concise tags.
- Validate discovery with `npx skills add . --list` before opening a PR.
- Re-run the relevant script in `scripts/` when you change an executable example or workflow artifact.

## License

[MIT](LICENSE)
