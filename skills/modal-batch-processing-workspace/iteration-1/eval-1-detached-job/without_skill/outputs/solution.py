"""
Detached Modal Job Submission with Polling

This solution demonstrates how to submit a long-running Modal job from a web
server in a "fire and forget" fashion. The client receives a job ID immediately
and can poll a status endpoint to check progress.

Key Modal concepts used:
- modal.Function.spawn()  — launches a function call asynchronously; returns a
  FunctionCall handle whose .object_id is the stable job ID.
- modal.functions.FunctionCall.from_id()  — reconstructs the handle from the
  job ID so any process (including a different web-server worker) can query it.
- FunctionCall.get(timeout=0)  — non-blocking poll; raises TimeoutError when
  the job is still running.

The web layer is FastAPI, but the Modal pieces work identically with Flask,
Django, or any other framework.
"""

from __future__ import annotations

import time
from typing import Any

import modal

# ---------------------------------------------------------------------------
# Modal app definition
# ---------------------------------------------------------------------------

app = modal.App("detached-job-demo")

# A simple image — add your own dependencies here.
image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi[standard]")


# ---------------------------------------------------------------------------
# The long-running Modal function
# ---------------------------------------------------------------------------

@app.function(image=image, timeout=3600)  # allow up to 1 hour
def long_running_job(payload: dict) -> dict:
    """
    Simulate a long-running computation.

    Replace the body with your actual workload (ML training, data pipeline,
    video transcoding, etc.).
    """
    import time as _time

    duration = payload.get("duration_seconds", 30)
    print(f"[job] starting — will run for {duration}s")
    _time.sleep(duration)

    result = {
        "status": "complete",
        "input": payload,
        "output": f"Processed after {duration}s",
    }
    print(f"[job] done — {result}")
    return result


# ---------------------------------------------------------------------------
# FastAPI web server (also deployed on Modal)
# ---------------------------------------------------------------------------

@app.function(image=image)
@modal.concurrent(max_inputs=50)          # handle many simultaneous HTTP requests
@modal.asgi_app()
def web_server():
    """
    ASGI app that exposes two endpoints:

    POST /jobs          — submit a new job, returns {"job_id": "..."}
    GET  /jobs/{job_id} — poll job status, returns status + result when done
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    import modal.functions  # needed for FunctionCall.from_id

    api = FastAPI(title="Detached Job API")

    @api.post("/jobs")
    async def submit_job(body: dict) -> JSONResponse:
        """
        Fire-and-forget job submission.

        The call to .spawn() returns immediately with a FunctionCall handle.
        We surface its .object_id as the job_id the client should store.
        """
        # .spawn() does NOT block — it schedules the function and returns a handle.
        call: modal.functions.FunctionCall = long_running_job.spawn(body)

        job_id: str = call.object_id   # stable identifier, safe to store in DB/cache

        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": "queued",
                "message": "Job submitted. Poll /jobs/{job_id} for status.",
            },
        )

    @api.get("/jobs/{job_id}")
    async def poll_job(job_id: str) -> JSONResponse:
        """
        Non-blocking poll.  Returns the job result when available, or a
        'running' status while the job is still in progress.
        """
        try:
            # Reconstruct the FunctionCall from the opaque job_id string.
            call = modal.functions.FunctionCall.from_id(job_id)

            # get(timeout=0) raises modal.exception.TimeoutError if still running.
            result: Any = call.get(timeout=0)

            return JSONResponse(
                status_code=200,
                content={"job_id": job_id, "status": "complete", "result": result},
            )

        except modal.exception.TimeoutError:
            # Job is still running — tell the client to try again later.
            return JSONResponse(
                status_code=202,
                content={"job_id": job_id, "status": "running"},
            )

        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return api


# ---------------------------------------------------------------------------
# Standalone usage (outside the web server)
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main():
    """
    Demonstrates the same spawn / poll pattern from a plain Python script.
    Useful for testing or for non-HTTP callers (CLI tools, other services, etc.)
    """
    payload = {"duration_seconds": 5, "task": "demo"}

    print("Submitting job (non-blocking)…")
    call = long_running_job.spawn(payload)
    job_id = call.object_id
    print(f"Job submitted. job_id = {job_id!r}")

    # Poll until done.
    while True:
        try:
            result = call.get(timeout=0)          # non-blocking
            print(f"Job complete! result = {result}")
            break
        except modal.exception.TimeoutError:
            print("Job still running — sleeping 3s before next poll…")
            time.sleep(3)


# ---------------------------------------------------------------------------
# Notes on the key Modal APIs
# ---------------------------------------------------------------------------
#
# 1. fn.spawn(*args, **kwargs) -> FunctionCall
#    • Schedules the function for execution and returns immediately.
#    • The returned FunctionCall object has an .object_id string that is
#      stable, serialisable, and can be passed across process boundaries.
#
# 2. FunctionCall.from_id(job_id) -> FunctionCall
#    • Reconstructs the handle from the string ID.
#    • Any authenticated Modal client can call this — including a different
#      web-server replica or a background cron job.
#
# 3. call.get(timeout=N) -> result
#    • Blocks for up to N seconds waiting for the result.
#    • timeout=0  → non-blocking poll; raises modal.exception.TimeoutError
#      immediately if the job has not finished.
#    • timeout=None → blocks indefinitely until done (useful in batch scripts).
#
# 4. Deployment
#    modal deploy solution.py
#
#    After deploying, the web server URL is printed to stdout.
#    The local_entrypoint can be run with:
#    modal run solution.py
