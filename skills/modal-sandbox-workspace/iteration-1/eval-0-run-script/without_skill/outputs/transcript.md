# Transcript: Run Python Script in Modal Sandbox with Stdout Streaming

## Task
Run a Python script securely in a Modal Sandbox and stream back stdout line by line.

## Steps

### Step 1 — Understand the goal
The user wants to:
1. Execute an arbitrary Python script inside a Modal Sandbox (isolated, secure container).
2. Stream the sandbox's stdout back to the caller line by line (rather than waiting for the process to complete before reading all output at once).

### Step 2 — Recall Modal Sandbox API
Modal Sandboxes (`modal.Sandbox`) are ephemeral, isolated containers suitable for running untrusted code. Key facts:

- Created with `modal.Sandbox.create(command, *args, image=..., **kwargs)`.
- The sandbox's stdout is exposed as `sb.stdout`, an iterable of lines.
- `sb.stderr` is similarly readable.
- `sb.wait()` blocks until the sandbox process exits and populates `sb.returncode`.
- Resource limits (cpu, memory, timeout) can be set at creation time for additional security.

### Step 3 — Design the solution
The solution consists of:
1. A helper function `run_script_in_sandbox(script)` that:
   - Builds a minimal Debian Slim image with Python 3.12.
   - Creates a sandbox running `python -c <script>`.
   - Iterates over `sb.stdout` to print each line as it arrives.
   - Calls `sb.wait()` to surface the exit code.
   - Prints stderr if the exit code is non-zero.
2. A `@app.local_entrypoint()` main function with an example script that prints 5 lines with a 0.5-second delay between each, demonstrating true streaming behavior.

### Step 4 — Write solution.py
Wrote `solution.py` with complete, runnable code including proper imports, docstrings, resource limits (timeout=60, cpu=1.0, memory=512 MiB), and an example entrypoint.

### Step 5 — Write output files
- `solution.py` — complete solution
- `transcript.md` — this file
- `metrics.json` — tool-call counts

## Key Design Decisions

| Decision | Rationale |
|---|---|
| `python -c script` invocation | Avoids writing a temp file; the script is passed inline. |
| `for line in sb.stdout` | Modal's stdout iterator yields lines as they are produced, enabling true streaming. |
| `sb.wait()` after streaming | Ensures we capture the exit code and don't leave zombie sandboxes. |
| Resource limits (cpu, memory, timeout) | Hardens the sandbox against runaway or malicious scripts. |
| `debian_slim` base image | Minimal attack surface; no unnecessary packages. |

## How to Run

```bash
modal run solution.py
```

The output will stream line by line:

```
=== Sandbox stdout ===
Line 1: hello from the sandbox!
Line 2: hello from the sandbox!
Line 3: hello from the sandbox!
Line 4: hello from the sandbox!
Line 5: hello from the sandbox!
Script finished successfully.

=== Sandbox exited with code 0 ===
```
