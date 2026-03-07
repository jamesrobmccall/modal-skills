"""
Expose an HTTP service running inside a Modal Sandbox via a public tunnel URL,
then shut the sandbox down when done.

Pattern: expose-a-web-service (from example-patterns.md)

Steps:
  1. Look up (or create) a Modal App.
  2. Create a Sandbox with encrypted_ports=[8000] so Modal provisions a tunnel.
  3. Start a simple HTTP server inside the sandbox with exec(...).
  4. Poll sandbox.tunnels() until the tunnel URL is available.
  5. Poll the public tunnel URL until the service answers HTTP 200.
  6. Print the URL, do work, then terminate() the sandbox.
"""

import time
import urllib.request
import urllib.error

import modal

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_NAME = "sandbox-http-tunnel-demo"
CONTAINER_PORT = 8000
POLL_INTERVAL_S = 2
READINESS_TIMEOUT_S = 120  # seconds to wait for HTTP readiness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_tunnel(sandbox: modal.Sandbox, port: int, timeout: float = 60.0) -> str:
    """Poll sandbox.tunnels() until the tunnel for *port* is available.

    Returns the public HTTPS URL string.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        tunnels = sandbox.tunnels()
        if port in tunnels:
            return tunnels[port].url
        print(f"  [tunnel] waiting for port {port} tunnel to appear...")
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(
        f"Tunnel for port {port} did not appear within {timeout}s"
    )


def wait_for_http(url: str, timeout: float = READINESS_TIMEOUT_S) -> None:
    """Poll *url* with HTTP GET until a 2xx response is received."""
    deadline = time.time() + timeout
    last_exc = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if 200 <= resp.status < 300:
                    print(f"  [readiness] service answered {resp.status} at {url}")
                    return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            print(f"  [readiness] not ready yet ({exc}), retrying in {POLL_INTERVAL_S}s...")
        time.sleep(POLL_INTERVAL_S)
    raise TimeoutError(
        f"Service at {url} did not become ready within {timeout}s. "
        f"Last error: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Step 1: Look up (or create) the Modal App.
    app = modal.App.lookup(APP_NAME, create_if_missing=True)

    # Step 2: Create the sandbox.
    #   - encrypted_ports=[CONTAINER_PORT] tells Modal to provision a TLS
    #     tunnel endpoint for that port.
    #   - timeout=300 gives us 5 minutes — plenty for a demo.
    #   - The entrypoint is a quiet sleep so the container stays alive while
    #     we drive it via exec().
    print(f"[sandbox] creating sandbox with encrypted_ports=[{CONTAINER_PORT}]...")
    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            "sleep",
            "300",
            app=app,
            encrypted_ports=[CONTAINER_PORT],
            timeout=300,
        )
    print(f"[sandbox] created: {sandbox.object_id}")

    try:
        # Step 3: Start the HTTP server inside the sandbox.
        #   Python's built-in http.server is available in the default image.
        #   We run it in the background by launching exec() without waiting.
        print(f"[exec] starting HTTP server on container port {CONTAINER_PORT}...")
        _server_proc = sandbox.exec(
            "python",
            "-m",
            "http.server",
            str(CONTAINER_PORT),
            "--directory",
            "/tmp",
        )
        # We deliberately do NOT call _server_proc.wait() here; the server
        # runs in the background while we do the readiness dance below.

        # Step 4: Wait for the tunnel URL to appear.
        print("[tunnel] polling for tunnel URL...")
        tunnel_url = wait_for_tunnel(sandbox, CONTAINER_PORT, timeout=60.0)
        print(f"[tunnel] public URL: {tunnel_url}")

        # Step 5: Poll the public URL until the service is ready.
        print("[readiness] waiting for HTTP service to respond...")
        wait_for_http(tunnel_url, timeout=READINESS_TIMEOUT_S)

        # --- Service is live ---
        print("\n=== Service is live ===")
        print(f"  Sandbox ID : {sandbox.object_id}")
        print(f"  Public URL : {tunnel_url}")
        print("  (Keeping sandbox alive for 10 seconds to demonstrate uptime...)")

        # In a real application you would do your work here — send requests,
        # serve traffic, run tasks, etc.
        time.sleep(10)

    finally:
        # Step 6: Terminate the sandbox unconditionally.
        print("\n[sandbox] terminating sandbox...")
        sandbox.terminate()
        print("[sandbox] terminated. Done.")


if __name__ == "__main__":
    main()
