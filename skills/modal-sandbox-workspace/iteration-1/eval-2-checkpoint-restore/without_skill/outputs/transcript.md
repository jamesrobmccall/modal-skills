# Execution Transcript

## Task
Answer: "How do I checkpoint a Modal Sandbox filesystem mid-computation so I can restore it later if the run fails?"

## Approach

This is a conceptual + code question. I answered entirely from my general knowledge of the Modal SDK, without reading any documentation files or skill guides.

## Steps

### Step 1 — Load the Write tool
Used ToolSearch to load the Write tool (deferred tool selection required before use).

Tool call: ToolSearch(query="select:Write")

### Step 2 — Write solution.md
Composed a comprehensive answer covering:
- The core API: `sandbox.snapshot_filesystem()` returns a `modal.Volume`
- Mounting that volume into a new Sandbox to restore filesystem state
- Four code examples:
  1. Basic snapshot after Sandbox completes
  2. Restore from snapshot in a new Sandbox
  3. Full end-to-end script with error handling and checkpoint ID persistence
  4. Resuming from a saved checkpoint ID in a separate script
  5. Mid-run snapshot using a background thread
- Notes on limitations: snapshot timing, volume persistence, read/write behavior

### Step 3 — Write transcript.md (this file)
Documenting the steps taken.

### Step 4 — Write metrics.json
Recording tool call counts and output sizes.

## Key Knowledge Applied

- `modal.Sandbox.create()` — creates and starts a sandbox
- `sandbox.snapshot_filesystem()` — the central checkpoint API; returns a `modal.Volume` representing the filesystem state at that moment
- `modal.Volume.from_id(id)` — retrieve a previously created volume by its object ID
- `volumes={"/path": vol}` parameter on `Sandbox.create()` — mounts a volume (including a snapshot) into a new sandbox at a given path
- Sandboxes do not need to be stopped to take a snapshot
- Volumes persist in Modal's cloud storage until deleted

## Errors Encountered
None. This was answered entirely from internal knowledge with no file reads or web searches needed.
