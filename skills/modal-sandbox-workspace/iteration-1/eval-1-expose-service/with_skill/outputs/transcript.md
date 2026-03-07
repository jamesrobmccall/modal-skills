# Execution Transcript

## Step 1: Read the skill

Read `/skills/modal-sandbox/SKILL.md`. Key guidance extracted:
- Use `modal.App.lookup(..., create_if_missing=True)` before `modal.Sandbox.create(...)`.
- Use `encrypted_ports=[...]` for HTTPS public endpoints.
- Poll `sandbox.tunnels()` for readiness.
- Use `terminate()` to shut the sandbox down immediately when done.
- The skill pointed to `references/networking-and-tunnels.md` and `references/example-patterns.md` as the most relevant references for this task.

## Step 2: Read networking-and-tunnels.md

Key points:
- `encrypted_ports=[...]` for HTTPS-style public endpoints.
- `sandbox.tunnels()` returns a mapping from container port to tunnel metadata with a `.url` attribute.
- Poll the tunnel URL from outside the sandbox until the expected HTTP status appears.
- Only expose the ports the task actually needs.

## Step 3: Read example-patterns.md

The `expose-a-web-service` pattern matches this task exactly:
1. Create the sandbox with the required `encrypted_ports`.
2. Start the service inside with `exec(...)`.
3. Poll `sandbox.tunnels()` until the public URL is available and the service answers readiness checks.
4. Return the tunnel URL and keep the sandbox running only as long as needed.

## Step 4: Read lifecycle-and-exec.md

Confirmed:
- Default sandbox lifetime is 5 minutes; set `timeout` explicitly.
- Use `exec(...)` to run commands; do not call `wait()` on background server processes.
- Use `terminate()` for immediate shutdown.
- Wrap `Sandbox.create(...)` in `with modal.enable_output():` for provisioning logs.

## Step 5: Design decisions

| Decision | Rationale |
|---|---|
| `encrypted_ports=[8000]` | HTTPS tunnel is preferred over unencrypted; port 8000 is conventional for HTTP dev servers |
| Entrypoint `sleep 300` | Keeps the container alive independently of the exec'd server; matches the skill's recommended long-lived pattern |
| `python -m http.server 8000` | Available in every Python image, no dependencies, produces a valid HTTP 200 on directory listing |
| Two-phase polling | First poll `tunnels()` (tunnel infrastructure may lag sandbox boot), then poll the HTTP URL (service may lag tunnel) |
| `try/finally` with `terminate()` | Guarantees cleanup even if polling raises `TimeoutError` or any other exception |
| `urllib.request` only | No third-party dependencies required; keeps the solution self-contained |

## Step 6: Write solution.py

Wrote a fully self-contained script that:
1. Looks up or creates the Modal App.
2. Creates a sandbox with `encrypted_ports=[8000]` and `timeout=300`.
3. Starts `python -m http.server 8000` via `sandbox.exec(...)` without waiting.
4. Polls `sandbox.tunnels()` with a 60-second timeout until the port-8000 tunnel URL appears.
5. Polls the public HTTPS URL with `urllib.request.urlopen` until HTTP 200 is received.
6. Prints the live URL and simulates 10 seconds of uptime.
7. Calls `sandbox.terminate()` in a `finally` block for guaranteed cleanup.

## Errors encountered

None.
