# Lifecycle And Exec

Use this reference when the task is about creating, reattaching to, or driving a sandbox with commands.

## Creation Rules

- Create sandboxes from local code with `modal.App.lookup(..., create_if_missing=True)` and `modal.Sandbox.create(...)`.
- Treat the Python SDK as the source of truth for create and control flows.
- Avoid inventing a `modal sandbox` CLI workflow. As of Modal CLI 1.3.4, use `modal shell <sandbox_id>` to attach to a running sandbox instead.

## Lifecycle Controls

- Treat the default maximum lifetime as 5 minutes.
- Set `timeout` when the sandbox must live longer, up to 24 hours.
- Set `idle_timeout` when the sandbox should terminate after inactivity.
- Use `Sandbox.from_id(...)` when a sandbox ID already exists.
- Use `Sandbox.from_name(app_name, name, ...)` only for a currently running named sandbox on a deployed app.
- Use `detach()` when the client should disconnect but the sandbox should keep running.
- Use `terminate()` when the sandbox should stop now.

## Exec Pattern

- Use `Sandbox.exec(...)` for most command execution.
- Expect a `ContainerProcess` back with `stdin`, `stdout`, `stderr`, `wait()`, and `returncode`.
- Use `stdout.read()` and `stderr.read()` after `wait()` when full buffered output is enough.
- Iterate over `stdout` or `stderr` when the user needs live streaming output.
- Set `bufsize=1` for line-oriented controller loops.
- Set `pty=True` only for commands that genuinely require a TTY.
- Set `timeout=` on `exec(...)` separately from sandbox lifetime when a single command should be bounded.

## Stateful Controller Loop

- Start one long-lived process inside the sandbox when the task needs conversational state or a REPL.
- Exchange JSON or newline-delimited messages over `stdin` and `stdout`.
- Reuse the same sandbox and process instead of creating a new sandbox per turn.
- Prefer this pattern for code interpreters, agent drivers, and REPL-like tooling.
