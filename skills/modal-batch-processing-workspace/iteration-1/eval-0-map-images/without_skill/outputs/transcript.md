# Transcript: Processing 5,000 Images with Modal

## Task
Process 5,000 images through a Modal function that resizes them to thumbnails and collect all results.

## Approach

### Step 1: Planning the solution

The core requirement is:
- A Modal function that resizes images to thumbnails
- Process 5,000 images
- Collect all results

The natural Modal primitive for this is `Function.map()`, which fans out work across many parallel containers and collects results in order. Key design decisions:

1. **Image generation**: For a standalone demo, generate synthetic images programmatically using Pillow. In production, images would be loaded from cloud storage (S3, GCS, etc.).
2. **Parallelism**: Use `.map()` on both the image generation step and the resize step so all 5,000 units run in parallel.
3. **Error handling**: Use `return_exceptions=True` so a single failed image doesn't abort the entire batch.
4. **Result collection**: Wrap `.map()` in `list()` to materialize all results locally.

### Step 2: Container image

Used `modal.Image.debian_slim(python_version="3.11").pip_install("Pillow", "requests")`.

Pillow is the standard Python image processing library, providing `Image.thumbnail()` with LANCZOS resampling for high-quality downscaling.

### Step 3: Modal function — `resize_to_thumbnail`

- Accepts raw image bytes and a target thumbnail size (default 128x128).
- Opens image with Pillow, converts non-RGB modes to RGB.
- Calls `img.thumbnail()` which resizes in-place preserving aspect ratio.
- Saves the result as JPEG (quality=85) into a BytesIO buffer.
- Returns a dict with thumbnail bytes, size metadata, compression info, and processing time.

### Step 4: Parallel orchestration with `.map()`

Two-stage pipeline in `main()`:

1. **Generate images**: `generate_image.map(range(5000))` — runs 5,000 image generation calls in parallel, returns list of bytes.
2. **Resize thumbnails**: `resize_to_thumbnail.map(image_bytes_list, ...)` — fans out all 5,000 resize operations in parallel across Modal containers.

Both calls use `order_outputs=True` to maintain index correspondence, and `list()` to collect results.

### Step 5: Result aggregation

After `.map()` completes:
- Separate successful results from exceptions
- Compute aggregate stats: success rate, total MB in/out, compression ratio, throughput
- Print a summary table
- Return a structured dict for programmatic use

### Step 6: Production notes

Added commented S3 example showing how to adapt the pattern for real cloud storage: download from S3, resize, upload thumbnail back to S3, all within a single Modal function called via `.map()`.

## Key Modal patterns used

- `modal.App` — defines the application
- `modal.Image` — custom container with Pillow installed
- `@app.function` — decorates Python functions to run remotely
- `@app.local_entrypoint` — marks the local driver script
- `Function.map()` — parallel fan-out over an iterable, returns results in order
- `return_exceptions=True` — graceful per-item error handling

## Solution file
`solution.py` — complete, runnable with `modal run solution.py`
