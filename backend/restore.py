"""Photo restoration and colorization pipeline using Replicate API.

Pipeline:
  1. GFP-GAN / CodeFormer — restore faces, remove scratches and noise
  2. DeOldify — colorize the restored image

Both models preserve original features: faces, buildings, nature, layout.
"""

import base64
import io
import replicate
from PIL import Image


async def restore_and_colorize(image_bytes: bytes, filename: str) -> bytes:
    """Full pipeline: restore → colorize. Returns processed image bytes."""

    # Convert image to data URI for Replicate
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    b64 = base64.b64encode(buf.getvalue()).decode()
    data_uri = f"data:image/jpeg;base64,{b64}"

    # Step 1: Face restoration + scratch/noise removal (CodeFormer)
    restored_url = await _run_codeformer(data_uri)

    # Step 2: Colorization (DeOldify)
    colorized_url = await _run_deoldify(restored_url)

    # Download final result
    import urllib.request
    with urllib.request.urlopen(colorized_url) as resp:
        result_bytes = resp.read()

    return result_bytes


async def _run_codeformer(image_input: str) -> str:
    """Restore faces and remove damage using CodeFormer."""
    output = replicate.run(
        "sczhou/codeformer:7bc05e82f4b10e96c383a5755a3ce4a091b9e251e3b94f152e9acba7b4a4a647",
        input={
            "image": image_input,
            "codeformer_fidelity": 0.7,  # Balance quality vs fidelity (higher = more faithful)
            "upscale": 2,
            "background_enhance": True,
            "face_upsample": True,
        },
    )
    return output


async def _run_deoldify(image_url: str) -> str:
    """Colorize a grayscale/sepia image using DeOldify."""
    output = replicate.run(
        "arielreplicate/deoldify_image:0da600fab0c45a66211339f1c16b71345d22f26ef5fea3dca1bb90bb5711e950",
        input={
            "input_image": image_url,
            "model_name": "Artistic",
            "render_factor": 35,
        },
    )
    return output
