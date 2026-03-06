# vLLM Cold Starts

Use this reference only when reducing vLLM startup latency matters enough to justify extra operational complexity.

## Preferred Escalation Order

- First try the standard vLLM path with fast-boot settings.
- Next consider keeping a warm container with `min_containers` if the workload is latency-sensitive.
- Reach for memory snapshots only when those simpler options are still too slow.

## Snapshot-Oriented Serving Pattern

- Use a class-based service with `@app.cls(...)` so startup and shutdown behavior are explicit.
- Enable memory snapshots with `enable_memory_snapshot=True`.
- Enable GPU snapshots with `experimental_options={"enable_gpu_snapshot": True}` when the workload and account support it.
- Keep the public serving path on `@modal.web_server`.

## vLLM Configuration for Snapshots

- Set `VLLM_SERVER_DEV_MODE=1` so the server can use the sleep and wake endpoints.
- Set `TORCHINDUCTOR_COMPILE_THREADS=1` to improve compatibility with snapshot flows.
- Start `vllm serve` in `@modal.enter(snap=True)`.
- Wait for the server to be healthy, then warm it up with a few real requests before taking the snapshot.
- Put the server into sleep mode after warmup so the snapshot captures a predictable state.

## Make the Snapshot Predictable

- Enable sleep mode in the vLLM command line.
- Bound `--max-num-seqs`, `--max-model-len`, and `--max-num-batched-tokens` so the snapshot does not capture an oversized runtime shape.
- Keep the warmup request small and deterministic.
- Add a second `@modal.enter(snap=False)` hook to wake the server and wait for readiness after restore.

## Caveats

- Treat this as an advanced-only path.
- Expect more model-specific and kernel-specific edge cases than with standard vLLM serving.
- Prefer the standard vLLM path if the user only needs a simple deployable server.
- Refer to Modal's snapshot-based serving examples for the concrete snapshot flow pattern.
