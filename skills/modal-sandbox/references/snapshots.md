# Snapshots

Use this reference when the task needs a restorable sandbox state.

## Stable Snapshot Path

- Use `snapshot_filesystem()` when the whole sandbox filesystem should become a reusable image.
- Use `snapshot_directory(path)` when only one directory should be carried forward.
- Use `mount_image(path, image)` to mount a previous snapshot into a new sandbox.

## Snapshot Selection

- Prefer filesystem snapshots for most restore workflows.
- Prefer directory snapshots when the state is isolated to one workspace directory.
- Prefer Volumes instead of snapshots when the task wants an always-writable shared store rather than point-in-time restore.

## Retention

- Expect directory snapshots to persist for 30 days after last creation or use.
- Handle missing or expired snapshots gracefully when the task restores by ID or stored metadata.

## Memory Snapshots

- Treat memory snapshots as advanced-only and experimental.
- Expect them to expire after 7 days.
- Expect the source sandbox to terminate when the snapshot is taken.
- Avoid them with GPUs.
- Avoid them while any `Sandbox.exec` command is still running.
- Avoid relying on background `exec` processes to survive restore.

## Restore Pattern

- Trigger the snapshot from outside the sandbox.
- Persist the returned snapshot ID in the caller's state store.
- Restore into a fresh sandbox on the next session instead of trying to reuse the terminated source sandbox.
