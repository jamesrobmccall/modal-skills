"""
Process 5,000 images through a Modal function that resizes them to thumbnails
and collects all results using modal.Function.map for parallel processing.
"""

import modal
import io
import time
from pathlib import Path

# Define the Modal app
app = modal.App("image-thumbnail-processor")

# Define the container image with required dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "Pillow",
    "requests",
)


def generate_synthetic_image(index: int) -> bytes:
    """
    Generate a synthetic image in memory for demonstration purposes.
    In a real workflow, this would load from disk, S3, GCS, etc.
    Returns raw PNG bytes.
    """
    from PIL import Image as PILImage
    import io

    # Create a unique colored image for each index
    width, height = 800, 600
    # Vary colors based on index
    r = (index * 37) % 256
    g = (index * 73) % 256
    b = (index * 113) % 256

    img = PILImage.new("RGB", (width, height), color=(r, g, b))

    # Add some variation - draw a simple pattern
    pixels = img.load()
    for x in range(0, width, 50):
        for y in range(height):
            pixels[x, y] = (255 - r, 255 - g, 255 - b)
    for y in range(0, height, 50):
        for x in range(width):
            pixels[x, y] = (255 - r, 255 - g, 255 - b)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@app.function(image=image, cpu=1, memory=512)
def resize_to_thumbnail(image_data: bytes, thumbnail_size: tuple = (128, 128)) -> dict:
    """
    Modal function that resizes an image to a thumbnail.

    Args:
        image_data: Raw bytes of the input image
        thumbnail_size: Target (width, height) for the thumbnail

    Returns:
        dict with thumbnail bytes, original size, thumbnail size, and processing info
    """
    from PIL import Image as PILImage
    import io
    import time

    start = time.time()

    # Open the image from bytes
    img = PILImage.open(io.BytesIO(image_data))
    original_size = img.size
    original_mode = img.mode

    # Convert to RGB if necessary (handles RGBA, palette mode, etc.)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Use LANCZOS resampling for high-quality downscaling
    img.thumbnail(thumbnail_size, PILImage.LANCZOS)

    # Save thumbnail to bytes
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    thumbnail_bytes = buf.getvalue()

    elapsed = time.time() - start

    return {
        "thumbnail_bytes": thumbnail_bytes,
        "original_size": original_size,
        "thumbnail_size": img.size,
        "original_mode": original_mode,
        "input_bytes": len(image_data),
        "output_bytes": len(thumbnail_bytes),
        "processing_time_ms": round(elapsed * 1000, 2),
    }


@app.function(image=image, timeout=3600)
def generate_image(index: int) -> bytes:
    """
    Generate a synthetic test image. In production, replace this
    with loading from cloud storage (S3, GCS, etc.).
    """
    return generate_synthetic_image(index)


@app.local_entrypoint()
def main():
    """
    Main entrypoint: generate 5,000 synthetic images and process them
    into thumbnails using Modal's .map() for fully parallel execution.
    """
    total_images = 5000
    thumbnail_size = (128, 128)

    print(f"Starting thumbnail processing pipeline for {total_images} images...")
    print(f"Target thumbnail size: {thumbnail_size[0]}x{thumbnail_size[1]}px")
    print()

    # Step 1: Generate all synthetic images in parallel using map
    print("Step 1: Generating synthetic images in parallel...")
    gen_start = time.time()

    image_bytes_list = list(
        generate_image.map(range(total_images), order_outputs=True)
    )

    gen_elapsed = time.time() - gen_start
    print(f"  Generated {len(image_bytes_list)} images in {gen_elapsed:.1f}s")
    total_input_bytes = sum(len(b) for b in image_bytes_list)
    print(f"  Total input data: {total_input_bytes / 1_000_000:.1f} MB")
    print()

    # Step 2: Process all images through thumbnail resizer in parallel
    print("Step 2: Resizing images to thumbnails in parallel via .map()...")
    proc_start = time.time()

    # Use .map() with return_exceptions=True to handle any per-image errors gracefully
    results = list(
        resize_to_thumbnail.map(
            image_bytes_list,
            kwargs={"thumbnail_size": thumbnail_size},
            order_outputs=True,
            return_exceptions=True,
        )
    )

    proc_elapsed = time.time() - proc_start
    print(f"  Processed {len(results)} images in {proc_elapsed:.1f}s")
    print()

    # Step 3: Collect and summarize results
    print("Step 3: Collecting results...")

    successful = []
    errors = []

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors.append({"index": i, "error": str(result)})
        else:
            successful.append(result)

    # Compute aggregate stats
    total_output_bytes = sum(r["output_bytes"] for r in successful)
    avg_processing_ms = (
        sum(r["processing_time_ms"] for r in successful) / len(successful)
        if successful
        else 0
    )
    avg_compression_ratio = (
        sum(r["input_bytes"] / r["output_bytes"] for r in successful) / len(successful)
        if successful
        else 0
    )

    total_elapsed = gen_elapsed + proc_elapsed

    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total images submitted:      {total_images}")
    print(f"Successfully processed:      {len(successful)}")
    print(f"Errors:                      {len(errors)}")
    print(f"Success rate:                {len(successful)/total_images*100:.1f}%")
    print()
    print(f"Total input size:            {total_input_bytes / 1_000_000:.1f} MB")
    print(f"Total output size:           {total_output_bytes / 1_000_000:.1f} MB")
    print(f"Average compression ratio:   {avg_compression_ratio:.1f}x")
    print(f"Avg per-image processing:    {avg_processing_ms:.1f} ms")
    print()
    print(f"Image generation time:       {gen_elapsed:.1f}s")
    print(f"Thumbnail processing time:   {proc_elapsed:.1f}s")
    print(f"Total wall-clock time:       {total_elapsed:.1f}s")
    print(f"Effective throughput:        {total_images / proc_elapsed:.0f} images/sec")
    print("=" * 60)

    if errors:
        print(f"\nFirst few errors:")
        for e in errors[:5]:
            print(f"  Image {e['index']}: {e['error']}")

    # Return results for programmatic use
    return {
        "total": total_images,
        "successful": len(successful),
        "errors": len(errors),
        "results": successful,
        "error_details": errors,
        "stats": {
            "total_input_mb": round(total_input_bytes / 1_000_000, 2),
            "total_output_mb": round(total_output_bytes / 1_000_000, 2),
            "avg_compression_ratio": round(avg_compression_ratio, 2),
            "avg_processing_ms": round(avg_processing_ms, 2),
            "generation_time_s": round(gen_elapsed, 2),
            "processing_time_s": round(proc_elapsed, 2),
            "total_time_s": round(total_elapsed, 2),
            "throughput_images_per_sec": round(total_images / proc_elapsed, 1),
        },
    }


# ---------------------------------------------------------------------------
# Alternative: process images from cloud storage (S3 example)
# Uncomment and adapt for production use.
# ---------------------------------------------------------------------------
#
# import boto3
#
# @app.function(
#     image=image.pip_install("boto3"),
#     secrets=[modal.Secret.from_name("aws-credentials")],
# )
# def resize_from_s3(s3_key: str, bucket: str, thumbnail_size=(128, 128)) -> dict:
#     """Download image from S3, resize, upload thumbnail back to S3."""
#     import boto3, io
#     from PIL import Image as PILImage
#
#     s3 = boto3.client("s3")
#
#     # Download
#     obj = s3.get_object(Bucket=bucket, Key=s3_key)
#     image_data = obj["Body"].read()
#
#     # Resize
#     img = PILImage.open(io.BytesIO(image_data))
#     if img.mode not in ("RGB", "L"):
#         img = img.convert("RGB")
#     img.thumbnail(thumbnail_size, PILImage.LANCZOS)
#
#     # Upload thumbnail
#     thumb_key = s3_key.replace("images/", "thumbnails/", 1)
#     buf = io.BytesIO()
#     img.save(buf, format="JPEG", quality=85)
#     s3.put_object(Bucket=bucket, Key=thumb_key, Body=buf.getvalue())
#
#     return {"source_key": s3_key, "thumbnail_key": thumb_key, "size": img.size}
#
# @app.local_entrypoint()
# def main_s3():
#     bucket = "my-image-bucket"
#     keys = [f"images/photo_{i:05d}.jpg" for i in range(5000)]
#     results = list(resize_from_s3.map(keys, kwargs={"bucket": bucket}))
#     print(f"Processed {len(results)} images")
