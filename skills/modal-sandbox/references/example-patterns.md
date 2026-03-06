# Example Patterns

Use this reference when the task is better served by adapting a known sandbox pattern instead of starting from scratch.

## `simple_code_interpreter`

- Use a long-lived controller process inside one sandbox.
- Send newline-delimited JSON over `stdin` and read structured results from `stdout`.
- Set `bufsize=1` for line-oriented interaction.
- Reuse the same process and sandbox to preserve interpreter state across requests.

## `opencode_server`

- Build an image with the agent runtime and any repo content it needs at startup.
- Expose one encrypted service port and fetch the public URL from `sandbox.tunnels()`.
- Print a `modal shell <sandbox_id>` hint so operators can pair-debug the live sandbox.
- Use Secrets for credentials instead of baking them into the image.

## `agent`

- Reuse one sandbox for repeated `exec(...)` calls instead of paying setup cost for every command.
- Add dependencies to the image up front and attach GPU resources only when the workload needs them.
- Keep sandbox execution separate from the outer orchestrator so the caller can inspect outputs and decide the next action.

## `anthropic_computer_use`

- Start from a hosted container image when the upstream project already publishes a usable environment.
- Pass API keys through Modal Secrets at runtime.
- Expose multiple encrypted ports when the workload serves more than one interface.
- Poll each tunnel URL for readiness before reporting that the sandbox is ready.
