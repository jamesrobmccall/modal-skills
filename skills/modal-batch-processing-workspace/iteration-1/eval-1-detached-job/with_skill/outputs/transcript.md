# Execution Transcript

## Step 1 — Read the skill

Read `/skills/modal-batch-processing/SKILL.md`.

Key takeaways:
- The skill tells me to pick a workflow before writing code.
- The task (submit a long-running job from a web server, return a job ID, poll later) maps directly to `.spawn`.
- The skill directs me to read `references/job-queues-and-detached-runs.md`.

## Step 2 — Read the reference document

Read `references/job-queues-and-detached-runs.md`.

Key facts extracted:
- Deploy the app with `modal deploy`; look up the function via `modal.Function.from_name(app_name, function_name)`.
- `.spawn(...)` returns a `modal.FunctionCall` immediately — the caller is not blocked.
- `FunctionCall.object_id` is the stable job ID string to store and share with clients.
- Rehydrate with `modal.FunctionCall.from_id(call_id)`.
- `.get(timeout=0)` raises `TimeoutError` if the job is still running (non-blocking poll).
- Results remain accessible for up to 7 days after completion.

## Step 3 — Read the smoke test for API patterns

Read `scripts/smoke_test.py` to see actual working Modal API usage:
- Confirmed `modal.FunctionCall.from_id(retrieved_call.object_id)` pattern.
- Confirmed `.get(timeout=30)` usage.
- Confirmed `modal.FunctionCall.gather(*calls)` for multi-job collection.

## Step 4 — Design decisions

**Single-file design**: Both the Modal worker app and the FastAPI web server live in `solution.py`. This keeps the example self-contained and easy to follow.

**Two separate Modal apps avoided**: The worker app (`worker_app`) is deployed with `modal deploy`. The FastAPI app (`web_app`) runs wherever the web server runs (locally or on another platform). `Function.from_name` bridges them.

**Non-blocking poll**: `call.get(timeout=0)` makes the poll endpoint return immediately with `status="pending"` instead of blocking the web server thread.

**No `.spawn_map`**: The task is single-job submission with a returned job ID — `.spawn_map` is for fire-and-forget fan-out with external result sinks, which does not match.

**No `.map`**: `.map` blocks the caller until all results are collected — the opposite of what is needed here.

**`Function.from_name` on every request**: The web server looks up the deployed function on each request. In production this could be cached at module level or in a startup event, but the per-request pattern is simple and correct.

**Timeout set deliberately**: `timeout=3600` on the worker function ensures stuck jobs do not linger indefinitely.

**`retries=0`** (explicit): The task does not specify idempotency, so retries are off by default.

## Step 5 — Write solution.py

Wrote the complete solution covering:
1. `worker_app` with `@worker_app.function` defining `process_job`.
2. FastAPI `web_app` with `POST /jobs` (submit via `.spawn()`, return `job_id`) and `GET /jobs/{job_id}` (poll via `FunctionCall.from_id` + `.get(timeout=0)`).
3. `_get_remote_function()` helper using `modal.Function.from_name`.
4. Local test entrypoint with the spawn + poll loop pattern.

## Step 6 — Write output files

Wrote `solution.py`, `transcript.md`, and `metrics.json` to the output directory.
