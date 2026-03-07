"""
Run a Python script securely in a Modal Sandbox and stream stdout line by line.

Modal Sandboxes provide an isolated execution environment for running untrusted
or arbitrary code securely. This solution demonstrates how to:
1. Create a Modal Sandbox with a specified image
2. Execute a Python script inside the sandbox
3. Stream stdout line by line back to the caller
"""

import modal

app = modal.App("sandbox-stream-stdout")


def run_script_in_sandbox(script: str) -> None:
    """
    Run an arbitrary Python script inside a Modal Sandbox and stream
    its stdout line by line.

    Args:
        script: The Python source code to execute inside the sandbox.
    """
    # Define the image the sandbox will use.
    # python:3.12-slim is a minimal, secure base image.
    image = modal.Image.debian_slim(python_version="3.12")

    # Create the sandbox. The sandbox is an isolated container that
    # runs the given command. We pass the script via stdin so we don't
    # need to write it to a file first.
    sb = modal.Sandbox.create(
        "python",
        "-c",
        script,
        image=image,
        # Optional security / resource controls:
        timeout=60,          # kill the sandbox after 60 seconds
        cpu=1.0,             # limit to 1 vCPU
        memory=512,          # limit to 512 MiB of RAM
    )

    # Stream stdout line by line as the process runs.
    print("=== Sandbox stdout ===")
    for line in sb.stdout:
        print(line, end="")  # lines already include the trailing newline

    # Wait for the process to finish and surface any errors.
    sb.wait()

    return_code = sb.returncode
    print(f"\n=== Sandbox exited with code {return_code} ===")

    if return_code != 0:
        # Also surface stderr so the caller knows what went wrong.
        print("=== Sandbox stderr ===")
        stderr_output = sb.stderr.read()
        print(stderr_output)


# ---------------------------------------------------------------------------
# Example usage — run this file directly with `modal run solution.py`
# ---------------------------------------------------------------------------

# A sample script that prints lines with a short delay to demonstrate streaming.
EXAMPLE_SCRIPT = """
import time

for i in range(1, 6):
    print(f"Line {i}: hello from the sandbox!")
    time.sleep(0.5)

print("Script finished successfully.")
"""


@app.local_entrypoint()
def main():
    run_script_in_sandbox(EXAMPLE_SCRIPT)
