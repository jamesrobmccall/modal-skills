# Transcript: Detached Modal Job Submission

## Task
Build a solution that lets a web server submit a long-running Modal job in a
detached (fire-and-forget) manner. The caller receives a job ID immediately and
can poll a separate endpoint later to retrieve the result.

---

## Step 1: Understand the core Modal mechanism

Recalled the key APIs from general knowledge of Modal:

- `Function.spawn()` — calls a Modal function asynchronously without blocking.
  Returns a `FunctionCall` object immediately.
- `FunctionCall.object_id` — a stable string identifier for the async call.
  This is the "job ID" we give back to the user.
- `FunctionCall.from_id(job_id)` — reconstructs a FunctionCall handle from
  just the string ID, making it possible to check status from a different
  process or web-server replica.
- `call.get(timeout=0)` — non-blocking poll; raises
  `modal.exception.TimeoutError` when the job has not finished yet.

This combination (spawn → return object_id → from_id → get) is the canonical
Modal pattern for detached long-running jobs.

---

## Step 2: Design the solution structure

Decided to implement:

1. A Modal `App` with:
   - `long_running_job` — the actual workload function (simulates work with
     `time.sleep`, easily replaced with real logic).
   - `web_server` — a FastAPI ASGI app deployed on Modal that exposes two
     HTTP endpoints.

2. Two FastAPI endpoints:
   - `POST /jobs` — calls `long_running_job.spawn(body)`, extracts
     `call.object_id`, returns HTTP 202 with `{"job_id": "..."}`.
   - `GET /jobs/{job_id}` — calls `FunctionCall.from_id(job_id)` then
     `call.get(timeout=0)`. Returns 200 + result when done, or 202 +
     `{"status": "running"}` when still in progress.

3. A `local_entrypoint` for standalone testing without the web layer.

---

## Step 3: Handle edge cases and correctness details

Considered and addressed:

- **Cross-process access**: Used `FunctionCall.from_id()` so the poll endpoint
  works even when served by a different replica than the one that submitted
  the job.
- **Non-blocking poll**: `get(timeout=0)` ensures the web server is never
  blocked waiting; it immediately raises `TimeoutError` if the job is running.
- **HTTP semantics**: Returned 202 Accepted for both "queued" and "running"
  states, and 200 OK only when the job is complete — consistent with
  REST polling conventions.
- **Concurrency**: Added `@modal.concurrent(max_inputs=50)` to the web server
  function so it can handle many simultaneous poll requests without spawning
  a new container per request.
- **Timeout**: Set `timeout=3600` on the long-running function to allow up to
  1 hour of execution.
- **Error handling**: Wrapped the poll logic in a try/except that surfaces
  unexpected errors as HTTP 500.

---

## Step 4: Write solution.py

Wrote the complete, self-contained `solution.py` with:
- Full inline documentation explaining each Modal concept.
- A `Notes` section at the bottom summarising the three key APIs.
- Deployment instructions (`modal deploy solution.py`).

---

## Step 5: Save outputs

- `solution.py` — written.
- `transcript.md` — this file.
- `metrics.json` — to be written last.

---

## Summary

The solution uses three Modal primitives in combination:

| Primitive | Role |
|-----------|------|
| `fn.spawn()` | Submit job without blocking; get FunctionCall handle |
| `call.object_id` | Stable string job ID returned to the caller |
| `FunctionCall.from_id(id)` | Reconstruct handle in any process |
| `call.get(timeout=0)` | Non-blocking poll; raises TimeoutError if pending |

No skill documents were consulted — this solution is based entirely on general
knowledge of the Modal Python SDK.
