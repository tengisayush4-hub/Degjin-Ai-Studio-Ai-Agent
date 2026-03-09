"""
Image generation - Gemini эсвэл DALL-E 3 model сонголттой
"""

import os
import base64
import logging
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def generate_image(prompt: str, output_path: str, reference_images: list[bytes] = None,
                   model_provider: str = "gemini") -> bool:
    if model_provider == "dalle":
        return _generate_dalle(prompt, output_path)
    return _generate_gemini(prompt, output_path, reference_images)


def _generate_gemini(prompt: str, output_path: str, reference_images: list[bytes] = None) -> bool:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    logger.info(f"[Gemini] Зураг үүсгэж байна: {prompt[:80]}...")

    try:
        parts = []
        if reference_images:
            for img_bytes in reference_images:
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
        parts.append(types.Part.from_text(text=prompt))

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=parts,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(output_path)
                logger.info(f"[Gemini] Зураг хадгалагдлаа: {output_path}")
                return True

        logger.error("[Gemini] Response-д зураг олдсонгүй")
        return False

    except Exception as e:
        logger.error(f"[Gemini] Зураг үүсгэх алдаа: {e}")
        return False


def _generate_dalle(prompt: str, output_path: str) -> bool:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        logger.info(f"[DALL-E 3] Зураг үүсгэж байна: {prompt[:80]}...")

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="hd",
            response_format="b64_json",
        )

        img_data = base64.b64decode(response.data[0].b64_json)
        image = Image.open(BytesIO(img_data))
        image.save(output_path)
        logger.info(f"[DALL-E 3] Зураг хадгалагдлаа: {output_path}")
        return True

    except Exception as e:
        logger.error(f"[DALL-E 3] Зураг үүсгэх алдаа: {e}")
        return False
