# Execution Transcript

## Step 1: Load tools and read the skill file

Loaded `Read` and `Glob` tools via ToolSearch. Read `SKILL.md` to understand the skill structure and which reference files are relevant.

The skill pointed to four references for this task:
- `references/snapshots.md` (primary — directly about snapshot/restore flows)
- `references/files-and-persistence.md` (secondary — persistence tradeoffs and Volume vs snapshot)
- `references/example-patterns.md` (secondary — the `snapshot-and-restore` pattern template)

Also ran Glob to confirm the full directory layout so no references were missed.

## Step 2: Read all three relevant reference files in parallel

Read `snapshots.md`, `files-and-persistence.md`, and `example-patterns.md` simultaneously.

### Key findings from snapshots.md

- Two stable snapshot APIs: `snapshot_filesystem()` (full sandbox) and `snapshot_directory(path)` (single directory).
- `mount_image(path, image)` is used to mount a snapshot into a new sandbox.
- Directory snapshots persist 30 days after last creation or use.
- Memory snapshots are experimental-only, expire after 7 days, terminate the source sandbox, and should be avoided with GPUs or running exec processes.
- The restore pattern: trigger from outside the sandbox, persist the returned snapshot ID externally, restore into a fresh sandbox.

### Key findings from files-and-persistence.md

- Volumes are preferred when files must be shared and always writable across sandboxes; snapshots are for point-in-time restore.
- CloudBucketMounts sync automatically and suit object-storage-organized workloads.
- The direct filesystem API (`sandbox.open`, `sandbox.mkdir`, etc.) is alpha-quality.

### Key findings from example-patterns.md

- The `snapshot-and-restore` template: build/mutate filesystem, call `snapshot_filesystem()` or `snapshot_directory()`, store image reference in durable state, restore by mounting into a new sandbox.

## Step 3: Decide on solution structure

The task asked for:
1. Explanation of the checkpoint mechanism
2. Complete code showing snapshot creation, limitations, and restore pattern

Decided to write a single `solution.md` containing:
- A concise conceptual overview
- Key principles drawn from the references
- A three-function complete Python script covering: full-filesystem checkpoint/restore, directory-only checkpoint/restore, and the external state persistence pattern
- A limitations table
- A when-to-use-each-approach table
- Run instructions

The code uses `snapshot_filesystem()` as the primary example (most common restore workflow per the skill guidance), and `snapshot_directory()` as a secondary example. Memory snapshots are mentioned in the limitations table but not given code examples, consistent with the skill's guidance to treat them as advanced/experimental-only.

## Step 4: Write output files

Wrote `solution.md` with full explanation and working code.
Wrote `transcript.md` (this file).
Wrote `metrics.json`.

## Decisions made

- Did not include memory snapshot code examples — the skill explicitly says to treat them as advanced-only and avoid relying on them for standard workflows.
- Used `modal.Image.from_id(snapshot_id)` to reconstruct the image from a stored ID, which is the correct pattern for restoring from external durable state.
- Used `json` + a local file to simulate durable state storage in the example, with a comment directing users to use a real durable store (database, Modal Dict) in production.
- Preferred `snapshot_filesystem()` over `snapshot_directory()` as the primary example since the skill says to prefer filesystem snapshots for most restore workflows.
- Included both patterns in the code so users can choose the lighter-weight directory snapshot when only one workspace directory matters.
