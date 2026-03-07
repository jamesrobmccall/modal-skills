"""
Detached job submission pattern using Modal.

Architecture:
  - `worker_app` defines and deploys the long-running Modal function.
  - `web_app` (FastAPI) is a separate service that submits jobs via `.spawn()`
    and exposes a polling endpoint.  The web server never blocks on the job.

Deploy the worker first:
    modal deploy solution.py

Then run the web server locally (or also deploy it):
    uvicorn solution:web_app --reload
"""

from __future__ import annotations

import modal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# 1.  Modal worker app — deploy with `modal deploy solution.py`
# ---------------------------------------------------------------------------

worker_app = modal.App("detached-job-worker")


@worker_app.function(
    timeout=3600,          # allow up to 1 hour; set deliberately
    retries=0,             # not idempotent by default — enable only if safe
)
def process_job(payload: dict) -> dict:
    """Long-running unit of work.  Runs entirely on Modal infrastructure."""
    import time

    # Simulate expensive processing (replace with real logic).
    duration = int(payload.get("duration_seconds", 10))
    time.sleep(duration)

    return {
        "status": "done",
        "input": payload,
        "result": f"processed after {duration}s",
    }


# ---------------------------------------------------------------------------
# 2.  FastAPI web server — submits jobs and exposes a polling endpoint
# ---------------------------------------------------------------------------

web_app = FastAPI(title="Job Queue API")


class JobRequest(BaseModel):
    duration_seconds: int = 5
    data: dict = {}


class JobSubmitResponse(BaseModel):
    job_id: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str          # "pending" | "done" | "error"
    result: dict | None = None
    error: str | None = None


def _get_remote_function() -> modal.Function:
    """Look up the deployed Modal function by name.

    Uses Function.from_name so the web server never imports or re-deploys
    the worker; it only needs the app and function name strings.
    """
    return modal.Function.from_name("detached-job-worker", "process_job")


@web_app.post("/jobs", response_model=JobSubmitResponse)
def submit_job(request: JobRequest) -> JobSubmitResponse:
    """Submit a long-running job and return immediately with a job ID.

    The job runs detached on Modal.  The web server does NOT block.
    """
    remote_fn = _get_remote_function()

    payload = {"duration_seconds": request.duration_seconds, **request.data}

    # .spawn() submits the job and returns a FunctionCall immediately.
    # The web server is free the moment spawn() returns.
    call: modal.FunctionCall = remote_fn.spawn(payload)

    # object_id is a stable string that can be stored in any durable store
    # (database, cache, etc.) and later used to rehydrate the FunctionCall.
    job_id: str = call.object_id

    return JobSubmitResponse(
        job_id=job_id,
        message="Job submitted. Poll /jobs/{job_id} for status.",
    )


@web_app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def poll_job(job_id: str) -> JobStatusResponse:
    """Poll the status of a previously submitted job.

    Returns immediately if the job is still running (status="pending").
    Returns the result when the job is done (status="done").
    Results remain accessible for up to 7 days after completion.
    """
    # Rehydrate the FunctionCall from just the string ID.
    call = modal.FunctionCall.from_id(job_id)

    try:
        # timeout=0 makes get() non-blocking: raises TimeoutError if not done.
        result = call.get(timeout=0)
        return JobStatusResponse(job_id=job_id, status="done", result=result)
    except TimeoutError:
        return JobStatusResponse(job_id=job_id, status="pending")
    except modal.exception.FunctionTimeoutError as exc:
        return JobStatusResponse(job_id=job_id, status="error", error=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# 3.  Optional: local entrypoint for quick testing without a web server
# ---------------------------------------------------------------------------

@worker_app.local_entrypoint()
def local_test():
    """Run a quick local test of the spawn + poll pattern."""
    import time

    print("Spawning a short job...")
    call = process_job.spawn({"duration_seconds": 2})
    job_id = call.object_id
    print(f"Job ID: {job_id}")

    print("Polling until done...")
    for _ in range(30):
        restored = modal.FunctionCall.from_id(job_id)
        try:
            result = restored.get(timeout=0)
            print(f"Done: {result}")
            return
        except TimeoutError:
            print("  still running, waiting 1s...")
            time.sleep(1)

    print("Timed out waiting for local test job.")
