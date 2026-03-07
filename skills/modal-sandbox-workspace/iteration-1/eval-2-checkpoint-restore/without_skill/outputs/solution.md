# Checkpointing a Modal Sandbox Filesystem Mid-Computation

## Overview

Modal Sandboxes support filesystem snapshots via the `Sandbox.snapshot_filesystem()` method. This lets you capture the state of a running or completed Sandbox's filesystem and later restore it by mounting the resulting `Volume` into a new Sandbox. This is useful for long-running computations where you want fault tolerance or the ability to resume from a known-good state.

## Key Concepts

- `sandbox.snapshot_filesystem()` — captures the current filesystem state of a Sandbox and returns a `modal.Volume`.
- The returned `Volume` can be mounted into a new Sandbox at a chosen path to restore the state.
- Snapshots are point-in-time: they reflect the filesystem at the moment the call is made.
- The Sandbox does not need to be stopped to take a snapshot; you can snapshot mid-computation.

## Step-by-Step Example

### 1. Run a Sandbox and Checkpoint Mid-Computation

```python
import modal

app = modal.App.lookup("sandbox-checkpoint-demo", create_if_missing=True)

# Start a Sandbox
sb = modal.Sandbox.create(
    "bash",
    "-c",
    # Simulate some work: write a file, then pause
    "mkdir -p /workspace && echo 'step 1 complete' > /workspace/progress.txt && sleep 2 && echo 'step 2 complete' >> /workspace/progress.txt",
    image=modal.Image.debian_slim(),
    app=app,
)

# Wait for the Sandbox to finish its work (or take snapshot mid-run if needed)
sb.wait()

# Take a filesystem snapshot — returns a modal.Volume
snapshot_vol = sb.snapshot_filesystem()
print(f"Snapshot volume ID: {snapshot_vol.object_id}")

# Optionally label / persist the volume for later restore
# The volume is already persisted in Modal's cloud storage
```

### 2. Restore from Snapshot in a New Sandbox

```python
import modal

# Look up the previously created snapshot volume by its object ID or name
# If you stored snapshot_vol.object_id, use modal.Volume.from_id(...)
# Or if you labeled the volume, use modal.Volume.lookup(...)

# Here we assume `snapshot_vol` is still in scope (same script run),
# but in a real resume scenario you would look it up:
# snapshot_vol = modal.Volume.from_id("vol_xxxxxxxxxxxx")

restore_sb = modal.Sandbox.create(
    "bash",
    "-c",
    # The restored /workspace will contain files from the checkpoint
    "cat /workspace/progress.txt && echo 'Resuming from checkpoint...' && echo 'step 3 complete' >> /workspace/progress.txt && cat /workspace/progress.txt",
    image=modal.Image.debian_slim(),
    volumes={"/workspace": snapshot_vol},
    app=app,
)

restore_sb.wait()
print(restore_sb.stdout.read())
```

### 3. Full End-to-End Script with Error Handling

```python
import modal
import sys

app = modal.App.lookup("sandbox-checkpoint-demo", create_if_missing=True)

def run_with_checkpoint():
    image = modal.Image.debian_slim()

    # Phase 1: Do initial work and checkpoint
    print("Starting phase 1...")
    sb1 = modal.Sandbox.create(
        "bash",
        "-c",
        """
        mkdir -p /workspace
        echo 'Phase 1: initializing...' > /workspace/log.txt
        # Simulate expensive computation
        for i in $(seq 1 5); do
            echo "Processing item $i" >> /workspace/log.txt
            sleep 0.5
        done
        echo 'Phase 1 complete' >> /workspace/log.txt
        """,
        image=image,
        app=app,
    )
    sb1.wait()

    if sb1.returncode != 0:
        print("Phase 1 failed:", sb1.stderr.read())
        sys.exit(1)

    # Checkpoint the filesystem after phase 1
    print("Checkpointing filesystem...")
    checkpoint_vol = sb1.snapshot_filesystem()
    checkpoint_id = checkpoint_vol.object_id
    print(f"Checkpoint saved: {checkpoint_id}")

    # Phase 2: Continue work, potentially failing
    print("Starting phase 2...")
    sb2 = modal.Sandbox.create(
        "bash",
        "-c",
        """
        echo 'Phase 2: continuing from checkpoint...' >> /workspace/log.txt
        for i in $(seq 6 10); do
            echo "Processing item $i" >> /workspace/log.txt
            sleep 0.5
        done
        echo 'Phase 2 complete' >> /workspace/log.txt
        cat /workspace/log.txt
        """,
        image=image,
        volumes={"/workspace": checkpoint_vol},
        app=app,
    )
    sb2.wait()

    if sb2.returncode != 0:
        print("Phase 2 failed. You can re-run from the checkpoint.")
        print(f"Restore with: modal.Volume.from_id('{checkpoint_id}')")
        sys.exit(1)

    print("Final output:")
    print(sb2.stdout.read())
    return checkpoint_id


if __name__ == "__main__":
    with modal.enable_output():
        run_with_checkpoint()
```

### 4. Restoring from a Saved Checkpoint ID

If a run fails after a checkpoint, you can restore in a separate script invocation:

```python
import modal

app = modal.App.lookup("sandbox-checkpoint-demo", create_if_missing=True)

# Replace with the checkpoint ID printed during your failed run
CHECKPOINT_ID = "vol_xxxxxxxxxxxx"

def resume_from_checkpoint(checkpoint_id: str):
    checkpoint_vol = modal.Volume.from_id(checkpoint_id)

    sb = modal.Sandbox.create(
        "bash",
        "-c",
        """
        echo "Resuming. Current log:"
        cat /workspace/log.txt
        echo "Continuing from where we left off..."
        for i in $(seq 6 10); do
            echo "Processing item $i" >> /workspace/log.txt
        done
        echo "Recovery complete" >> /workspace/log.txt
        cat /workspace/log.txt
        """,
        image=modal.Image.debian_slim(),
        volumes={"/workspace": checkpoint_vol},
        app=app,
    )
    sb.wait()
    print(sb.stdout.read())


if __name__ == "__main__":
    with modal.enable_output():
        resume_from_checkpoint(CHECKPOINT_ID)
```

## Important Notes and Limitations

1. **Snapshot is read-only when used as a restore point** — The Volume returned by `snapshot_filesystem()` reflects the state at snapshot time. If you mount it into a new Sandbox, the Sandbox can write to it (Volumes are read-write by default), but those writes do not affect the original snapshot data unless you snapshot again.

2. **Snapshot timing** — You can call `snapshot_filesystem()` on a running Sandbox (it doesn't need to have exited). This makes true mid-computation checkpointing possible by spawning a separate thread or using subprocess signaling.

3. **Volume persistence** — The snapshot Volume persists in Modal's storage until explicitly deleted. Store the `volume.object_id` or use `modal.Volume.lookup()` with a named volume to retrieve it later.

4. **Named volumes for easier retrieval** — If you want to look up a checkpoint by name rather than ID, persist the volume with a label:

```python
# After snapshot:
snapshot_vol = sb.snapshot_filesystem()

# Persist under a known name for easy lookup:
# (Volumes returned from snapshot_filesystem are already persisted,
#  but you can reference them by ID or use Volume.lookup with the ID)
print("Save this ID:", snapshot_vol.object_id)
```

5. **Mid-run snapshots** — To snapshot while a Sandbox is still running, call `snapshot_filesystem()` before calling `sb.wait()`, or from a separate thread:

```python
import threading, time, modal

app = modal.App.lookup("sandbox-checkpoint-demo", create_if_missing=True)

sb = modal.Sandbox.create(
    "bash", "-c",
    "for i in $(seq 1 20); do echo item$i >> /workspace/out.txt; sleep 1; done",
    image=modal.Image.debian_slim().run_commands("mkdir -p /workspace"),
    app=app,
)

checkpoints = []

def checkpoint_loop():
    time.sleep(5)  # Wait 5 seconds then checkpoint
    vol = sb.snapshot_filesystem()
    checkpoints.append(vol.object_id)
    print(f"Mid-run checkpoint: {vol.object_id}")

t = threading.Thread(target=checkpoint_loop)
t.start()
sb.wait()
t.join()

print("Checkpoints taken:", checkpoints)
```

## Summary

| Step | Action | Modal API |
|------|--------|-----------|
| Create Sandbox | Start computation | `modal.Sandbox.create(...)` |
| Checkpoint | Snapshot filesystem | `sandbox.snapshot_filesystem()` → returns `modal.Volume` |
| Store checkpoint ID | Save for later | `volume.object_id` |
| Restore | Mount snapshot in new Sandbox | `modal.Sandbox.create(..., volumes={"/path": vol})` |
| Retrieve checkpoint | Look up by ID | `modal.Volume.from_id("vol_xxx")` |
