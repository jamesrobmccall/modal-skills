"""
Run a Python script securely in a Modal Sandbox and stream stdout line by line.

Pattern: run-a-script
- Look up or create a Modal App
- Start a sandbox with a long-lived idle command (sleep)
- Upload the user script via sandbox.open(...)
- Execute the script with sandbox.exec(...)
- Iterate over stdout line by line as they arrive (streaming)
- Terminate the sandbox when done
"""

from __future__ import annotations

import modal

# ---------------------------------------------------------------------------
# The Python script to run securely inside the sandbox.
# Replace this with any script you want to execute.
# ---------------------------------------------------------------------------
SCRIPT_CONTENT = """\
import time

print("Starting secure script execution...")
for i in range(1, 6):
    print(f"Line {i}: processing step {i}")
    time.sleep(0.3)
print("Script complete.")
"""

SCRIPT_REMOTE_PATH = "/tmp/user_script.py"
APP_NAME = "modal-sandbox-run-script"


def run_script_in_sandbox(script: str, remote_path: str = SCRIPT_REMOTE_PATH) -> int:
    """
    Upload `script` into a fresh Modal Sandbox and stream its stdout line by line.

    Returns the script's exit code.
    """
    # 1. Look up (or create) a Modal App. Required when provisioning from
    #    local / non-Modal code.
    app = modal.App.lookup(APP_NAME, create_if_missing=True)

    # 2. Create the sandbox.
    #    - Use debian_slim with Python pre-installed.
    #    - Start a long-lived idle process so the container stays alive while
    #      we upload and exec the script.
    #    - timeout=300 gives a 5-minute window; increase as needed.
    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            "sleep",
            "300",
            app=app,
            image=modal.Image.debian_slim().pip_install("python3"),
            timeout=300,
        )

    print(f"Sandbox created: {sandbox.object_id}")
    print(f"Attach with: modal shell {sandbox.object_id}\n")

    try:
        # 3. Upload the script into the sandbox filesystem.
        writer = sandbox.open(remote_path, "w")
        writer.write(script)
        writer.close()

        # 4. Execute the script.
        #    - bufsize=1 enables line-buffered reads for real-time streaming.
        #    - pty=False (default) is correct here; no TTY needed.
        process = sandbox.exec("python3", remote_path, bufsize=1)

        # 5. Stream stdout line by line as each line arrives.
        print("--- script output (streaming) ---")
        for line in process.stdout:
            # Each yielded value is already a decoded string line.
            print(line, end="")
        print("--- end of output ---\n")

        # 6. Wait for the process to finish and collect the return code.
        process.wait()

        # 7. Capture and print any stderr.
        stderr_output = process.stderr.read()
        if stderr_output:
            print("--- stderr ---")
            print(stderr_output)
            print("--- end stderr ---\n")

        if process.returncode != 0:
            print(f"Script exited with code {process.returncode}")
        else:
            print("Script finished successfully (exit code 0).")

        return process.returncode

    finally:
        # 8. Always terminate the sandbox to release resources.
        sandbox.terminate()
        print(f"Sandbox terminated: {sandbox.object_id}")


if __name__ == "__main__":
    exit_code = run_script_in_sandbox(SCRIPT_CONTENT)
    raise SystemExit(exit_code)
