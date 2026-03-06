---
name: modal-sandbox
description: Python-first Modal Sandbox creation and control for secure code execution, long-lived controller processes, tunneled services, file exchange, and snapshot-based persistence. Use when Codex needs to create, attach to, debug, or restore a Modal Sandbox, or wire one into an agent or code interpreter workflow.
---

# Modal Sandbox

## Overview

Use this skill to create and operate Modal Sandboxes from Python. Prefer the Python SDK for provisioning and control, and use the CLI only to inspect or attach to an existing sandbox.

## Quick Start

1. Verify prerequisites before doing any work.

```bash
modal --version
<chosen-python> -c "import modal; print(modal.__version__)"
```

- Do not assume `python3` can import `modal` just because the `modal` CLI exists.
- Use the interpreter from the active Modal environment, project venv, or the environment behind the installed CLI.
- As of Modal CLI 1.3.4, do not look for a `modal sandbox` subcommand. Use `modal shell <sandbox_id>` for direct access and `modal container ...` only for generic container inspection.

2. Create an App before creating a sandbox from outside Modal.

```python
import modal

app = modal.App.lookup("my-sandbox-app", create_if_missing=True)
sandbox = modal.Sandbox.create("sh", "-lc", "sleep 300", app=app)
```

3. Choose the workflow that matches the task before writing code.

## Choose the Workflow

- Use one-shot `Sandbox.exec(...)` for isolated commands and output capture.
- Use a long-lived controller loop when the sandbox must keep state across requests; read [references/example-patterns.md](references/example-patterns.md).
- Use tunnels when the sandbox must expose HTTP or TCP services; read [references/networking-and-tunnels.md](references/networking-and-tunnels.md).
- Use Volumes or CloudBucketMounts for persisted or shared files, and snapshots for restore flows; read [references/files-and-persistence.md](references/files-and-persistence.md) and [references/snapshots.md](references/snapshots.md).
- Reattach to a live sandbox with `Sandbox.from_id(...)` or `Sandbox.from_name(...)` instead of creating duplicates.

## Create or Reattach

- Use the Python SDK as the authoritative create/control surface.
- Use `modal.App.lookup(..., create_if_missing=True)` before `modal.Sandbox.create(...)` when creating from local code.
- Set lifecycle limits deliberately:
  - Treat the default sandbox lifetime as 5 minutes.
  - Set `timeout` up to 24 hours when the workload needs more time.
  - Set `idle_timeout` when the sandbox should terminate after inactivity.
- Name a sandbox only when you need a singleton per project or session. `Sandbox.from_name(...)` only works for a currently running named sandbox on a deployed app.
- Use `Sandbox.from_id(...)` when the object ID is already known.
- Use `detach()` after finishing interaction with a sandbox that should keep running.
- Use `terminate()` when the sandbox should stop now.
- Use CLI interop only for debugging or direct access:

```bash
modal shell sb-abc123
```

## Run Commands

- Treat `Sandbox.exec(...)` as the default execution primitive.
- Expect `Sandbox.exec(...)` to return a `ContainerProcess` with `stdin`, `stdout`, `stderr`, `wait()`, and `returncode`.
- Use `stdout.read()` and `stderr.read()` after completion when you want the full output.
- Iterate over `stdout` or `stderr` for streaming output.
- Use `bufsize=1` for line-oriented controller loops that exchange JSON or REPL-style messages.
- Use `timeout=` on `exec(...)` to bound command runtime separately from sandbox lifetime.
- Pass `pty=True` only when a command genuinely requires a TTY.
- Keep one controller process running inside the sandbox when the task needs stateful back-and-forth over `stdin` and `stdout`.

## Expose Services

- Open only the required ports with `encrypted_ports`, `unencrypted_ports`, or `h2_ports`.
- Retrieve public URLs with `sandbox.tunnels()`.
- Poll for readiness from outside the sandbox before declaring the service healthy.
- Use `block_network=True` to disable outbound network access completely.
- Use `cidr_allowlist=[...]` when the sandbox needs restricted outbound egress instead of unrestricted Internet access.
- Use `create_connect_token()` only when the service needs authenticated HTTP connections routed through Modal's proxy.

## Work With Files

- Use `Image.add_local_file(...)` or `Image.add_local_dir(...)` when local inputs should be baked into the image at build time.
- Use Volumes or CloudBucketMounts when files must outlive one sandbox or be shared across sandboxes.
- Use `open()`, `ls()`, `mkdir()`, and `rm()` on the `Sandbox` object for runtime file access.
- Prefer Volumes for controller loops that must preserve user work across sandbox restarts.
- Remember that the direct filesystem API is alpha and best suited to lightweight runtime reads and writes.
- Remember that Volume writes generally sync back on termination unless you explicitly use the relevant sync mechanism; CloudBucketMounts sync automatically.

## Persist State

- Prefer `snapshot_filesystem()` when the whole filesystem should be cloned or restored.
- Use `snapshot_directory()` plus `mount_image()` when only one directory needs to be carried forward.
- Treat directory snapshots as durable but not permanent; current docs say they persist for 30 days after last use.
- Treat memory snapshots as advanced-only:
  - Treat them as alpha.
  - Expect 7-day expiration.
  - Expect the source sandbox to terminate when the snapshot is taken.
  - Avoid them with GPUs.
  - Avoid them while any `Sandbox.exec` process is still running.
  - Avoid relying on background processes launched via `exec` to restore cleanly.
- Prefer filesystem snapshots unless the task explicitly requires in-memory process state.

## References

- Read [references/lifecycle-and-exec.md](references/lifecycle-and-exec.md) for lifecycle, reattachment, and command-execution details.
- Read [references/networking-and-tunnels.md](references/networking-and-tunnels.md) for tunnels, network controls, and service exposure.
- Read [references/files-and-persistence.md](references/files-and-persistence.md) for build-time uploads, runtime file IO, Volumes, and persistence tradeoffs.
- Read [references/snapshots.md](references/snapshots.md) for snapshot selection, limitations, and restore patterns.
- Read [references/example-patterns.md](references/example-patterns.md) for distilled example workflows.
