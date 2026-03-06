# Files And Persistence

Use this reference when the task moves files into or out of a sandbox, or when sandbox data must survive restarts.

## Build-Time Inputs

- Use `Image.add_local_file(...)` when one local file should be present when the sandbox starts.
- Use `Image.add_local_dir(...)` when a local directory should be baked into the image.
- Use build-time image inputs when the files are static and known before sandbox creation.

## Runtime File Access

- Use `sandbox.open(path, mode)` for direct reads and writes inside the sandbox.
- Use `sandbox.mkdir(...)`, `sandbox.ls(...)`, and `sandbox.rm(...)` for basic filesystem operations.
- Treat the direct filesystem API as alpha and keep usage lightweight.

## Persistent Storage

- Use a Volume when files must persist across sandbox restarts or be shared with later sandboxes.
- Use a CloudBucketMount when the workload is already organized around object storage.
- Prefer Volumes for agent workspaces, code interpreter state, and user project files.

## Sync Tradeoffs

- Expect Volume writes to sync back on termination unless the task explicitly uses the relevant sync path.
- Expect CloudBucketMount updates to sync automatically.
- Use snapshots when the task wants a restorable filesystem image rather than a shared writable store.
