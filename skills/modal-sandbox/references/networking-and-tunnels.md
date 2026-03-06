# Networking And Tunnels

Use this reference when the sandbox must expose a service or run with explicit network restrictions.

## Expose Services

- Use `encrypted_ports=[...]` for HTTPS-style public endpoints.
- Use `unencrypted_ports=[...]` only when plaintext traffic is acceptable.
- Use `h2_ports=[...]` when the service needs HTTP/2 instead of HTTP/1.1.
- Retrieve public tunnel metadata with `sandbox.tunnels()`.
- Expect `sandbox.tunnels()` to return a mapping from container port to tunnel metadata.

## Readiness Checks

- Wait for the service to boot before reporting success.
- Poll the tunnel URL from outside the sandbox until the expected HTTP status or TCP readiness appears.
- Ignore service logs that mention `localhost`; use the returned tunnel URLs instead.

## Security Controls

- Use `block_network=True` to disable outbound network access entirely.
- Use `cidr_allowlist=[...]` when the sandbox should only reach specific outbound ranges.
- Expose only the ports the task requires.
- Use `create_connect_token()` only when the application needs authenticated HTTP connections forwarded through Modal's proxy.

## CLI Interop

- Use `modal shell <sandbox_id>` for direct debugging access to a running sandbox.
- Use `modal container list`, `modal container logs`, or `modal container exec` only as generic inspection tools, not as the primary sandbox-creation API.
