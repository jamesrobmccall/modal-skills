# Modal Skills

A collection of [Claude Skills](https://claude.com/blog/complete-guide-to-building-skills-for-claude) for working with [Modal](https://modal.com) — the cloud platform for running AI workloads, sandboxed code execution, and GPU-accelerated inference.

These skills teach Claude how to create Modal Sandboxes, deploy LLM inference services, and follow Modal best practices, so you can describe what you want and get working Modal code.

## Available Skills

| Skill | Description |
|-------|-------------|
| [modal-sandbox](skills/modal-sandbox/) | Create and control Modal Sandboxes for secure code execution, tunneled services, file exchange, and snapshot-based persistence. |
| [modal-llm-serving](skills/modal-llm-serving/) | Serve open-weight LLMs on Modal with vLLM or SGLang — online APIs, cold-start reduction, low-latency, and batch inference. |

## Installation

### From GitHub

Install a specific skill:

```bash
npx skills add <owner>/<repo> --skill modal-sandbox
```

Or install from the skill subdirectory directly:

```bash
npx skills add https://github.com/<owner>/<repo>/tree/main/skills/modal-sandbox
```

### Local Discovery

Clone the repo and list available skills:

```bash
npx skills add . --list
```

List a specific skill:

```bash
npx skills add ./skills/modal-sandbox --list
```

## Repository Layout

```text
skills/
  <skill-name>/
    SKILL.md          # Core instructions with YAML frontmatter
    agents/           # Agent interface configuration
    references/       # Detailed documentation loaded on-demand
    scripts/          # Executable examples and tests
```

## Contributing

To add a new skill:

1. Create a new directory under `skills/<skill-name>/` using kebab-case naming.
2. Add a `SKILL.md` with valid YAML frontmatter (`name`, `description`, `license`).
3. Put detailed documentation in `references/` to keep `SKILL.md` under 5,000 words.
4. Add runnable examples or tests in `scripts/`.
5. Add an agent interface file in `agents/` (see existing skills for the format).
6. Verify discovery with `npx skills add . --list` before opening a PR.

See the [Anthropic skill creation guide](https://claude.com/blog/complete-guide-to-building-skills-for-claude) for best practices on writing effective skills.

## License

[MIT](LICENSE)
