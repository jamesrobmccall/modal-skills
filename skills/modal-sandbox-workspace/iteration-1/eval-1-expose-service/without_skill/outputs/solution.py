"""
Expose an HTTP service running inside a Modal Sandbox via a public URL,
then shut it down when done.

This script:
1. Creates a Modal Sandbox running a simple HTTP server
2. Tunnels the server port to a public URL using sandbox.tunnels()
3. Makes a request to verify the service is accessible
4. Terminates the sandbox when done
"""

import time
import urllib.request

import modal

app = modal.App("sandbox-http-service")


def main():
    # Define the image with Python available (default)
    image = modal.Image.debian_slim()

    print("Creating Modal Sandbox with an HTTP server...")

    # Create a sandbox that runs a simple Python HTTP server on port 8000
    sandbox = modal.Sandbox.create(
        "python",
        "-m",
        "http.server",
        "8000",
        image=image,
        # Give the sandbox time to start up
        timeout=300,
    )

    print(f"Sandbox created: {sandbox.sandbox_id}")

    # Wait a moment for the HTTP server to start inside the sandbox
    time.sleep(3)

    # Create a tunnel to expose port 8000 publicly
    print("Creating tunnel to expose port 8000...")
    tunnel = sandbox.tunnels()[8000]

    public_url = tunnel.url
    print(f"Service is publicly accessible at: {public_url}")

    # Verify the service is reachable
    print("Verifying service is reachable...")
    try:
        with urllib.request.urlopen(public_url, timeout=15) as response:
            status = response.status
            print(f"HTTP response status: {status}")
            # Read a snippet of the response body
            body_snippet = response.read(200).decode("utf-8", errors="replace")
            print(f"Response body snippet: {body_snippet[:100]}")
    except Exception as e:
        print(f"Request error (may still be starting): {e}")

    print(f"\nPublic URL is active: {public_url}")
    print("Service is running. Shutting down sandbox...")

    # Terminate the sandbox — this also closes the tunnel
    sandbox.terminate()
    print("Sandbox terminated. Service is no longer accessible.")


if __name__ == "__main__":
    # Run directly with modal.enable_output() for local execution
    with modal.enable_output():
        main()
