# Example Patterns

Use this reference when the task is better served by adapting a known sandbox pattern instead of starting from scratch.

## `run-a-script`

- Look up or create an app with `modal.App.lookup(..., create_if_missing=True)`.
- Start a sandbox with a long-lived command such as `sleep 300`.
- Upload the script with `sandbox.open(...)`, execute it with `sandbox.exec(...)`, then read `stdout` and `stderr`.
- Terminate the sandbox when the task is complete.

## `expose-a-web-service`

- Create the sandbox with the required `encrypted_ports`, `unencrypted_ports`, or `h2_ports`.
- Start the service process inside the sandbox with `exec(...)`.
- Poll `sandbox.tunnels()` until the public URL is available and the service answers readiness checks.
- Return the tunnel URL and keep the sandbox running only as long as the service is needed.

## `snapshot-and-restore`

- Build or mutate the filesystem into the state that should be resumed later.
- Call `snapshot_filesystem()` when the full sandbox state should be carried forward, or `snapshot_directory()` when only one directory matters.
- Store the resulting image reference in durable state outside the sandbox.
- Restore by mounting the saved image into a new sandbox instead of trying to revive the old one.

## `stateful-code-interpreter`

- Use a long-lived controller process inside one sandbox.
- Send newline-delimited JSON over `stdin` and read structured results from `stdout`.
- Set `bufsize=1` for line-oriented interaction.
- Reuse the same process and sandbox to preserve interpreter state across requests.

## `hosted-agent-service`

- Build an image with the agent runtime and any repo content it needs at startup.
- Expose one encrypted service port and fetch the public URL from `sandbox.tunnels()`.
- Print a `modal shell <sandbox_id>` hint so operators can pair-debug the live sandbox.
- Use Secrets for credentials instead of baking them into the image.

## `computer-use-environment`

- Start from a hosted container image when the upstream project already publishes a usable environment.
- Pass API keys through Modal Secrets at runtime.
- Expose multiple encrypted ports when the workload serves more than one interface.
- Poll each tunnel URL for readiness before reporting that the sandbox is ready.
