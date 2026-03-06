# Modal Skills

Modal-focused skills for coding agents.

## Repository Layout

This repo is organized for the `skills` CLI and `skills.sh` discovery flow:

```text
skills/
  modal-sandbox/
    SKILL.md
    agents/
    references/
    scripts/
```

Add future skills under `skills/<skill-name>/`.

## Local Discovery

List skills in this repo:

```bash
npx skills add . --list
```

List a specific skill path directly:

```bash
npx skills add ./skills/modal-sandbox --list
```

## GitHub Install

Once this repo is pushed to GitHub, install from the repo root:

```bash
npx skills add <owner>/<repo> --skill modal-sandbox
```

Or install from the skill subdirectory directly:

```bash
npx skills add https://github.com/<owner>/<repo>/tree/main/skills/modal-sandbox
```

## Publish Notes

- Keep each skill self-contained under `skills/<skill-name>/`.
- Keep `SKILL.md` frontmatter valid and descriptive so discovery works well.
- Avoid extra docs inside skill folders; put repo-level guidance here instead.
- Verify discovery with `npx skills add . --list` before pushing.
