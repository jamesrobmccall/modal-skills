# Transcript: Expose HTTP Service in Modal Sandbox via Public URL

## Task
Expose an HTTP service running inside a Modal Sandbox via a public URL, then shut it down when done.

## Approach

### Step 1: Understand the Modal Sandbox API
From general knowledge of Modal:
- `modal.Sandbox.create(...)` creates an ephemeral sandbox environment that can run arbitrary commands
- Sandboxes support tunneling via `sandbox.tunnels()`, which returns a dict mapping port numbers to tunnel objects
- Each tunnel object has a `.url` attribute containing the public HTTPS URL
- `sandbox.terminate()` shuts down the sandbox and closes associated tunnels

### Step 2: Design the solution
The solution needs to:
1. Create a sandbox running a simple HTTP server (Python's built-in `http.server` module on port 8000)
2. Wait briefly for the server to start
3. Call `sandbox.tunnels()[8000]` to get the public tunnel URL
4. Optionally verify the URL is reachable with an HTTP request
5. Call `sandbox.terminate()` to shut everything down

### Step 3: Key API details used
- `modal.Sandbox.create("python", "-m", "http.server", "8000", image=..., timeout=...)` — creates sandbox running an HTTP server
- `sandbox.tunnels()` — returns a mapping of `{port: Tunnel}` for the sandbox
- `tunnel.url` — the public HTTPS URL for the tunneled port
- `sandbox.terminate()` — terminates the sandbox and all its resources
- `modal.enable_output()` — context manager for local script execution to show Modal output

### Step 4: Write and save solution
Wrote `solution.py` with complete imports and runnable code. The script:
- Uses `modal.App` and `modal.Image.debian_slim()` for the environment
- Starts the sandbox with Python's built-in HTTP server on port 8000
- Waits 3 seconds for server startup
- Retrieves the public URL via `sandbox.tunnels()[8000].url`
- Makes an HTTP request to verify accessibility
- Calls `sandbox.terminate()` to clean up

## Notes
- No skill documents were available; solution based entirely on Modal API knowledge
- The `sandbox.tunnels()` call is synchronous and returns immediately once the tunnel is established
- Terminating the sandbox automatically closes any open tunnels
- The `timeout=300` parameter gives the sandbox up to 5 minutes to run before auto-termination

## Files Created
- `solution.py` — complete runnable solution
- `transcript.md` — this file
- `metrics.json` — tool call and step counts
