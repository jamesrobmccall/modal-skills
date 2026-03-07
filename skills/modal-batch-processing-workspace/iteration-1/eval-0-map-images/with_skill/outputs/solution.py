"""
Process 5,000 images through a Modal function that resizes them to thumbnails,
collecting all results in-process using .map().

Pattern: map-and-gather (synchronous fan-out, in-process result collection)
Reference: modal-batch-processing/references/map-and-gather.md
"""

import io
import modal

# ---------------------------------------------------------------------------
# App and image definition
# ---------------------------------------------------------------------------

app = modal.App("image-thumbnail-batch")

# Remote image includes Pillow for image processing
remote_image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "Pillow==10.3.0"
)

# ---------------------------------------------------------------------------
# Thumbnail size
# ---------------------------------------------------------------------------

THUMBNAIL_SIZE = (128, 128)

# ---------------------------------------------------------------------------
# Remote function: resize a single image to a thumbnail
#
# Input:  image_bytes (bytes)  — raw bytes of any Pillow-readable image format
# Output: dict with:
#           "thumbnail_bytes": bytes  — PNG-encoded thumbnail
#           "original_size":   tuple  — (width, height) of the source image
#           "thumbnail_size":  tuple  — actual size after thumbnail()
# ---------------------------------------------------------------------------


@app.function(
    image=remote_image,
    # Allow up to 100 containers to run concurrently so 5,000 images are
    # processed quickly without overwhelming downstream resources.
    max_containers=100,
    # Each resize is fast; 60 s is generous but prevents stalls on corrupt
    # inputs that Pillow may spend time trying to decode.
    timeout=60,
    # Retry once on transient container failure (idempotent work).
    retries=1,
)
def resize_to_thumbnail(image_bytes: bytes) -> dict:
    """Resize image_bytes to a thumbnail and return metadata + encoded result."""
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes)) as img:
        original_size = img.size
        # thumbnail() modifies in-place and preserves aspect ratio within the
        # bounding box defined by THUMBNAIL_SIZE.
        img.thumbnail(THUMBNAIL_SIZE)
        thumbnail_size = img.size

        # Encode result as PNG bytes so the caller receives a self-contained
        # image without needing to know the original format.
        out_buf = io.BytesIO()
        img.save(out_buf, format="PNG")
        thumbnail_bytes = out_buf.getvalue()

    return {
        "thumbnail_bytes": thumbnail_bytes,
        "original_size": original_size,
        "thumbnail_size": thumbnail_size,
    }


# ---------------------------------------------------------------------------
# Helper: generate synthetic image bytes for demonstration
#
# In production, replace this with real image loading logic (e.g., read from
# a Modal Volume, S3 bucket mount, or a local directory).
# ---------------------------------------------------------------------------


def _generate_synthetic_images(n: int):
    """
    Yield n synthetic JPEG image bytes for testing purposes.

    Each image is a unique solid-color 640x480 JPEG so that the batch is
    representative of varied inputs without requiring an external dataset.
    """
    from PIL import Image

    for i in range(n):
        # Vary the color across the batch to produce non-identical images.
        r = (i * 37) % 256
        g = (i * 71) % 256
        b = (i * 113) % 256
        img = Image.new("RGB", (640, 480), color=(r, g, b))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        yield buf.getvalue()


# ---------------------------------------------------------------------------
# Local entrypoint
# ---------------------------------------------------------------------------


@app.local_entrypoint()
def main():
    """
    Fan out 5,000 image resize operations across Modal containers using .map(),
    wait for all results, and report summary statistics locally.
    """
    NUM_IMAGES = 5_000

    print(f"Generating {NUM_IMAGES} synthetic images locally...")
    # Build a list so we can pass the iterable to .map() and also report
    # total byte count.
    image_payloads = list(_generate_synthetic_images(NUM_IMAGES))
    total_input_bytes = sum(len(b) for b in image_payloads)
    print(
        f"Total input size: {total_input_bytes / 1_048_576:.1f} MB across"
        f" {NUM_IMAGES} images"
    )

    print(f"Submitting batch to Modal via .map() with max_containers=100 ...")

    # .map() fans out over the iterable and returns results in input order
    # (order_outputs=True is the default).
    #
    # return_exceptions=True keeps partial progress if individual images are
    # corrupt or unreadable, rather than aborting the entire batch.
    results = list(
        resize_to_thumbnail.map(
            image_payloads,
            order_outputs=True,
            return_exceptions=True,
        )
    )

    # ---------------------------------------------------------------------------
    # Post-process results locally
    # ---------------------------------------------------------------------------
    successes = []
    failures = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            failures.append((idx, result))
        else:
            successes.append(result)

    total_output_bytes = sum(len(r["thumbnail_bytes"]) for r in successes)

    print(f"\n--- Batch complete ---")
    print(f"Total images submitted : {NUM_IMAGES}")
    print(f"Successful             : {len(successes)}")
    print(f"Failed                 : {len(failures)}")
    print(
        f"Total thumbnail bytes  : {total_output_bytes / 1_048_576:.1f} MB"
    )

    if successes:
        sample = successes[0]
        print(
            f"Sample [0]: original={sample['original_size']},"
            f" thumbnail={sample['thumbnail_size']},"
            f" bytes={len(sample['thumbnail_bytes'])}"
        )

    if failures:
        print(f"\nFirst failure: index={failures[0][0]}, error={failures[0][1]}")

    # In production you would write `results` to a Modal Volume, S3 bucket,
    # or a database here.  For demonstration we just return the count.
    return len(successes)
