# Troubleshooting

Use this reference when the sandbox workflow is failing after the main create and control flow is already chosen.

## `modal` CLI not found or `import modal` fails

- Verify that the `modal` CLI and the Python package come from the same environment.
- Switch to the project virtualenv or the interpreter behind the installed CLI before retrying.

## Sandbox terminates unexpectedly

- Treat 5 minutes as the default maximum lifetime.
- Set `timeout=` explicitly on `Sandbox.create(...)` for longer workloads, up to 24 hours.
- Set `idle_timeout=` when the sandbox should stop only after inactivity.

## `Sandbox.from_name(...)` returns nothing

- `from_name(...)` only finds a currently running named sandbox on a deployed app.
- Recreate the sandbox when the named instance has already terminated.

## Tunnel URL not available

- Poll `sandbox.tunnels()` until the service has finished starting.
- Recheck that the service is bound to the same port exposed in `encrypted_ports`, `unencrypted_ports`, or `h2_ports`.

## File writes not persisted after sandbox termination

- Use Volumes or CloudBucketMounts for data that must outlive a single sandbox.
- Treat direct filesystem operations such as `sandbox.open()` and `sandbox.rm()` as sandbox-scoped runtime IO.
