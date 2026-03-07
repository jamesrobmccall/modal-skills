# Checkpointing a Modal Sandbox Filesystem Mid-Computation

## Overview

Modal Sandboxes support two stable snapshot mechanisms for checkpointing filesystem state mid-computation:

- `snapshot_filesystem()` — captures the entire sandbox filesystem as a reusable Modal Image
- `snapshot_directory(path)` — captures a single directory as a Modal Image

Both return an Image object (or a reference you can store as an ID) that can be mounted into a fresh sandbox to restore the state. Snapshots persist for **30 days** after last creation or use.

## Key Principles

1. **Snapshots are triggered from outside the sandbox** — you call the method on the `Sandbox` object from your Python controller, not from inside the sandbox.
2. **Persist the snapshot ID in durable external state** — the sandbox itself will eventually terminate; the snapshot ID is what lets you restore.
3. **Restore into a fresh sandbox** — you cannot revive the terminated sandbox; you mount the snapshot image into a new one.
4. **Prefer filesystem snapshots for most restore workflows**; prefer directory snapshots when only one workspace directory carries the relevant state.
5. **Prefer Volumes instead of snapshots** when you want an always-writable shared store rather than point-in-time restore.

---

## Pattern: Checkpoint Mid-Computation and Restore on Failure

The flow has three stages:

1. Start a sandbox and run part of the computation.
2. Checkpoint by calling `snapshot_filesystem()` (or `snapshot_directory()`), storing the returned image reference externally.
3. On failure or restart, create a new sandbox with `mount_image(path, snapshot_image)` to resume from the saved state.

---

## Complete Working Example

```python
"""
checkpoint_restore.py

Demonstrates how to checkpoint a Modal Sandbox filesystem mid-computation
and restore it in a fresh sandbox if the run fails.
"""

import json
import pathlib
import modal

STATE_FILE = pathlib.Path("/tmp/checkpoint_state.json")

# ---------------------------------------------------------------------------
# Stage 1: Run computation and checkpoint mid-way
# ---------------------------------------------------------------------------

def run_with_checkpoint() -> str:
    """
    Runs a multi-stage computation inside a sandbox, takes a filesystem
    snapshot between stages, and persists the snapshot image ID so it
    can be restored later.

    Returns the snapshot image ID string.
    """
    app = modal.App.lookup("checkpoint-demo", create_if_missing=True)

    # Create a sandbox with a base image. Extend it with any dependencies
    # your real computation needs.
    image = modal.Image.debian_slim()

    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            "bash", "-lc", "sleep 3600",
            app=app,
            image=image,
            timeout=3600,
        )

    sandbox_id = sandbox.object_id
    print(f"Sandbox started: {sandbox_id}")

    # --- Stage 1: produce some intermediate results ---
    proc = sandbox.exec("bash", "-c", """
        set -e
        mkdir -p /workspace
        echo "stage1_result=42" > /workspace/stage1.txt
        echo "intermediate data" > /workspace/data.bin
        echo "Stage 1 complete"
    """)
    for line in proc.stdout:
        print("[sandbox]", line, end="")
    proc.wait()

    # --- Checkpoint: snapshot the filesystem after stage 1 ---
    print("Taking filesystem snapshot...")
    snapshot_image = sandbox.snapshot_filesystem()
    snapshot_id = snapshot_image.object_id
    print(f"Snapshot captured: {snapshot_id}")

    # Persist the snapshot ID to durable external state.
    # In production use a database, Modal Dict, or other durable store.
    STATE_FILE.write_text(json.dumps({
        "snapshot_id": snapshot_id,
        "stage_completed": 1,
    }))

    # --- Stage 2: continue computation (may fail) ---
    try:
        proc2 = sandbox.exec("bash", "-c", """
            set -e
            source /workspace/stage1.txt
            echo "stage2 sees stage1_result=$stage1_result"
            echo "stage2_result=100" > /workspace/stage2.txt
            echo "Stage 2 complete"
        """)
        for line in proc2.stdout:
            print("[sandbox]", line, end="")
        proc2.wait()
        print("All stages complete.")
        STATE_FILE.unlink(missing_ok=True)  # clean up checkpoint on success
    except Exception as exc:
        print(f"Stage 2 failed: {exc}")
        print("Checkpoint is available for restore — see STATE_FILE.")
    finally:
        sandbox.terminate()

    return snapshot_id


# ---------------------------------------------------------------------------
# Stage 2: Restore from checkpoint and resume
# ---------------------------------------------------------------------------

def restore_and_resume(snapshot_id: str) -> None:
    """
    Creates a fresh sandbox whose filesystem is initialized from a previous
    snapshot, then resumes computation from stage 2.
    """
    app = modal.App.lookup("checkpoint-demo", create_if_missing=True)

    # Reconstruct the snapshot image from its ID.
    snapshot_image = modal.Image.from_id(snapshot_id)

    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            "bash", "-lc", "sleep 3600",
            app=app,
            # Mount the snapshot as the root image so the entire filesystem
            # is restored to the checkpointed state.
            image=snapshot_image,
            timeout=3600,
        )

    print(f"Restore sandbox started: {sandbox.object_id}")

    # Verify the checkpointed files are present.
    proc = sandbox.exec("bash", "-c", "cat /workspace/stage1.txt")
    for line in proc.stdout:
        print("[restored]", line, end="")
    proc.wait()

    # Resume stage 2.
    proc2 = sandbox.exec("bash", "-c", """
        set -e
        source /workspace/stage1.txt
        echo "Resuming: stage1_result=$stage1_result"
        echo "stage2_result=100" > /workspace/stage2.txt
        echo "Stage 2 complete on restored sandbox"
    """)
    for line in proc2.stdout:
        print("[restored]", line, end="")
    proc2.wait()

    sandbox.terminate()
    STATE_FILE.unlink(missing_ok=True)
    print("Restore and resume complete.")


# ---------------------------------------------------------------------------
# Stage 3: Restore using snapshot_directory (single-directory variant)
# ---------------------------------------------------------------------------

def checkpoint_directory_only() -> str:
    """
    Checkpoints only /workspace instead of the full filesystem.
    Useful when only your working directory holds relevant state.
    """
    app = modal.App.lookup("checkpoint-demo", create_if_missing=True)
    image = modal.Image.debian_slim()

    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            "bash", "-lc", "sleep 3600",
            app=app,
            image=image,
            timeout=3600,
        )

    proc = sandbox.exec("bash", "-c", """
        mkdir -p /workspace
        echo "checkpoint_data=xyz" > /workspace/progress.txt
    """)
    proc.wait()

    # Snapshot only /workspace.
    dir_snapshot = sandbox.snapshot_directory("/workspace")
    dir_snapshot_id = dir_snapshot.object_id
    print(f"Directory snapshot: {dir_snapshot_id}")

    sandbox.terminate()
    return dir_snapshot_id


def restore_from_directory_snapshot(dir_snapshot_id: str) -> None:
    """
    Mounts a directory snapshot back into /workspace of a fresh sandbox.
    """
    app = modal.App.lookup("checkpoint-demo", create_if_missing=True)
    dir_snapshot_image = modal.Image.from_id(dir_snapshot_id)

    with modal.enable_output():
        sandbox = modal.Sandbox.create(
            "bash", "-lc", "sleep 3600",
            app=app,
            image=modal.Image.debian_slim(),
            # Mount the directory snapshot at /workspace.
            mounts=[modal.Image.mount_image("/workspace", dir_snapshot_image)],
            timeout=3600,
        )

    proc = sandbox.exec("bash", "-c", "cat /workspace/progress.txt")
    for line in proc.stdout:
        print("[dir-restore]", line, end="")
    proc.wait()

    sandbox.terminate()
    print("Directory restore complete.")


# ---------------------------------------------------------------------------
# Entry point: demonstrates the full checkpoint-restore cycle
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "full"

    if mode == "full":
        # Run with checkpoint, then simulate a restore.
        snap_id = run_with_checkpoint()
        print(f"\nSimulating restore from snapshot: {snap_id}")
        restore_and_resume(snap_id)

    elif mode == "restore":
        # Resume from a previously saved checkpoint.
        if not STATE_FILE.exists():
            print("No checkpoint state file found.")
            sys.exit(1)
        state = json.loads(STATE_FILE.read_text())
        restore_and_resume(state["snapshot_id"])

    elif mode == "dir":
        # Demonstrate directory-only snapshot.
        snap_id = checkpoint_directory_only()
        restore_from_directory_snapshot(snap_id)
```

---

## Snapshot Limitations

| Constraint | Detail |
|---|---|
| Retention | Snapshots expire 30 days after last creation or use |
| Source sandbox | The sandbox that is snapshotted continues running; you must terminate it explicitly |
| Memory snapshots | Experimental only; expire after 7 days; source sandbox terminates on snapshot; avoid with GPUs or running `exec` processes |
| Restore target | Always a new sandbox — you cannot rehydrate the original sandbox |
| Background processes | No background `exec` processes survive a snapshot/restore cycle |

---

## When to Use Each Approach

| Scenario | Recommended approach |
|---|---|
| Full environment must be restored (deps, config, data) | `snapshot_filesystem()` mounted as the sandbox image |
| Only a workspace directory matters | `snapshot_directory(path)` + `mount_image` |
| Files must persist and be writable across many sandboxes | Modal Volume (not snapshots) |
| Shared object storage already in use | CloudBucketMount |

---

## Running the Example

```bash
# Run the full checkpoint-and-restore demo
python checkpoint_restore.py full

# Restore from a previously saved checkpoint
python checkpoint_restore.py restore

# Run the directory-snapshot variant
python checkpoint_restore.py dir
```

Requires `modal` installed and an authenticated Modal account (`modal token new` or `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET` set).
