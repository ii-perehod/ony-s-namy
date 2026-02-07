"""Photo restoration and colorization pipeline using Replicate API.

Full pipeline:
  1. Preprocess — crop, straighten, remove glare/scratches, enhance
  2. CodeFormer — restore faces, remove remaining noise
  3. DeOldify — colorize the restored image

All steps preserve original features: faces, buildings, nature, layout.
"""

import asyncio
import base64
import io
import urllib.request
import replicate
from PIL import Image

from preprocess import (
    merge_two_angles,
    auto_crop,
    remove_scratches,
    enhance_for_restoration,
)


async def restore_and_colorize(image_bytes: bytes, filename: str) -> bytes:
    """Full pipeline: preprocess → restore → colorize."""

    # Preprocessing
    processed = auto_crop(image_bytes)
    processed = remove_scratches(processed)
    processed = enhance_for_restoration(processed)

    # Convert to data URI for Replicate
    data_uri = _to_data_uri(processed)

    # AI restoration + colorization
    restored_url = await _run_codeformer(data_uri)
    colorized_url = await _run_deoldify(restored_url)

    return await _download_result(colorized_url)


async def restore_from_two_photos(img_bytes_1: bytes, img_bytes_2: bytes) -> bytes:
    """Pipeline for 2 photos of the same print (glare removal)."""

    # Merge two angles to remove glare
    merged = merge_two_angles(img_bytes_1, img_bytes_2)

    # Then standard pipeline
    processed = auto_crop(merged)
    processed = remove_scratches(processed)
    processed = enhance_for_restoration(processed)

    data_uri = _to_data_uri(processed)

    restored_url = await _run_codeformer(data_uri)
    colorized_url = await _run_deoldify(restored_url)

    return await _download_result(colorized_url)


def _to_data_uri(image_bytes: bytes) -> str:
    """Convert image bytes to a JPEG data URI for Replicate."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


async def _run_codeformer(image_input: str) -> str:
    """Restore faces and remove damage using CodeFormer."""
    output = await asyncio.to_thread(
        replicate.run,
        "sczhou/codeformer:7bc05e82f4b10e96c383a5755a3ce4a091b9e251e3b94f152e9acba7b4a4a647",
        input={
            "image": image_input,
            "codeformer_fidelity": 0.7,
            "upscale": 2,
            "background_enhance": True,
            "face_upsample": True,
        },
    )
    return output


async def _run_deoldify(image_url: str) -> str:
    """Colorize a grayscale/sepia image using DeOldify."""
    output = await asyncio.to_thread(
        replicate.run,
        "arielreplicate/deoldify_image:0da600fab0c45a66211339f1c16b71345d22f26ef5fea3dca1bb90bb5711e950",
        input={
            "input_image": image_url,
            "model_name": "Artistic",
            "render_factor": 35,
        },
    )
    return output


async def _download_result(url: str) -> bytes:
    """Download result image without blocking the event loop."""
    def _fetch(u):
        with urllib.request.urlopen(u) as resp:
            return resp.read()
    return await asyncio.to_thread(_fetch, url)
