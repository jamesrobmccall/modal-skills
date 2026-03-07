# Execution Transcript

## Task
Run a Python script securely in a Modal Sandbox and stream back stdout line by line.

## Steps

### Step 1 — Read the skill
Read `/skills/modal-sandbox/SKILL.md`.

Key findings:
- Must call `modal.App.lookup(..., create_if_missing=True)` before `Sandbox.create(...)` when running from local code.
- Use `Sandbox.exec(...)` as the default execution primitive.
- Iterate over `stdout` (rather than calling `.read()` after `.wait()`) when live streaming output is needed.
- Set `bufsize=1` for line-oriented streaming.
- The skill pointed to `references/lifecycle-and-exec.md` and `references/example-patterns.md` as most relevant to this task.

### Step 2 — Read lifecycle-and-exec.md
Read `/skills/modal-sandbox/references/lifecycle-and-exec.md`.

Key findings:
- `Sandbox.exec(...)` returns a `ContainerProcess` with `.stdin`, `.stdout`, `.stderr`, `.wait()`, `.returncode`.
- Iterate over `stdout` or `stderr` for live streaming; use `.read()` only when full buffered output is acceptable.
- `bufsize=1` is explicitly required for line-oriented loops.
- `pty=True` only for commands that genuinely need a TTY — not needed here.
- Wrap `Sandbox.create(...)` in `with modal.enable_output():` to see build/provisioning logs locally.

### Step 3 — Read example-patterns.md
Read `/skills/modal-sandbox/references/example-patterns.md`.

Key findings:
- The `run-a-script` pattern is exactly the right match:
  1. Look up / create the app.
  2. Start sandbox with a long-lived idle command (`sleep 300`).
  3. Upload script with `sandbox.open(...)`.
  4. Execute with `sandbox.exec(...)`.
  5. Read stdout / stderr.
  6. Terminate when done.

### Step 4 — Read scripts/smoke_test.py
Read the smoke test to see the real API surface in action.

Key findings:
- `sandbox.open(path, "w")` / `.write(...)` / `.close()` for file upload.
- `process = sandbox.exec("sh", "-lc", cmd)` for command execution.
- `process.wait()` then `process.stdout.read()` for buffered reads.
- Confirmed `sandbox.terminate()` in a `finally` block for cleanup.

### Step 5 — Design the solution

Workflow chosen: `run-a-script` pattern.

Design decisions:
- Use `modal.Image.debian_slim()` as the base image — lightweight and has Python 3.
- Start sandbox with `sleep 300` so it remains alive during upload + exec.
- Upload the script to `/tmp/user_script.py` via `sandbox.open(...)`.
- Execute with `sandbox.exec("python3", remote_path, bufsize=1)`.
- **Stream stdout line by line** by iterating over `process.stdout` in a `for` loop — this is the correct streaming API per the skill.
- After the loop, call `process.wait()` to collect the return code.
- Read stderr after wait for any error output.
- Always call `sandbox.terminate()` in a `finally` block.

The demo script (`SCRIPT_CONTENT`) prints 5 lines with 0.3s delays between them to demonstrate real streaming behavior.

### Step 6 — Write outputs
Wrote `solution.py`, `transcript.md`, and `metrics.json` to the output directory.

## Key API Facts (for reference)
- `modal.App.lookup(name, create_if_missing=True)` — required before Sandbox.create from local code.
- `modal.Sandbox.create(*cmd, app=app, image=..., timeout=...)` — creates and starts the sandbox.
- `sandbox.open(path, "w")` — opens a remote file for writing (used to upload scripts).
- `sandbox.exec(*cmd, bufsize=1)` — runs a command; returns a `ContainerProcess`.
- `for line in process.stdout:` — streams output line by line in real time.
- `process.wait()` — blocks until the process exits; sets `process.returncode`.
- `process.stderr.read()` — reads all stderr after process exits.
- `sandbox.terminate()` — stops the sandbox immediately.
