"""
Зураг дээр animated текст давхарлаж MP4 видео үүсгэх.
Pillow + imageio ашиглана (ImageMagick шаардлагагүй).
"""

import os
import logging
import numpy as np
import imageio
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Видео тохиргоо
VIDEO_FPS = 24
VIDEO_DURATION = 10        # секунд
OUTPUT_SIZE = (1080, 1080)  # Instagram/FB квадрат


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Windows системийн фонт ачааллах"""
    font_paths = [
        "C:/Windows/Fonts/arialbd.ttf",    # Arial Bold
        "C:/Windows/Fonts/arial.ttf",       # Arial
        "C:/Windows/Fonts/calibrib.ttf",    # Calibri Bold
        "C:/Windows/Fonts/segoeui.ttf",     # Segoe UI
        "C:/Windows/Fonts/tahoma.ttf",      # Tahoma
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_text_centered(draw: ImageDraw.Draw, text: str, y: int,
                         font: ImageFont.FreeTypeFont, img_width: int,
                         alpha: int):
    """Текстийг дунд нь зурах (сүүдэртэй)"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (img_width - text_w) // 2

    # Сүүдэр
    shadow_color = (0, 0, 0, min(alpha, 200))
    draw.text((x + 3, y + 3), text, font=font, fill=shadow_color)

    # Гол текст
    draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))


def _make_frame(base_rgb: np.ndarray, text_lines: list[str], t: float) -> np.ndarray:
    """
    t = 0.0 ~ 1.0 (нийт хугацааны харьцаа)
    Текст анимэйшн:
      - Доод хагасаас дээш гулсаж гарна
      - Мөр бүр 0.3 секундын зайтай гарна
    """
    h, w = base_rgb.shape[:2]

    # Зурагны суурь (RGBA)
    frame = Image.fromarray(base_rgb).convert("RGBA")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    total_sec = VIDEO_DURATION
    t_sec = t * total_sec

    # Доод хэсэгт хагас тунгалаг хар тал
    bar_h = min(300, h // 3)
    bar_alpha = int(180 * min(1.0, t_sec / 1.0))
    draw.rectangle([(0, h - bar_h), (w, h)], fill=(0, 0, 0, bar_alpha))

    font_sizes = [72, 52, 44, 38]
    line_spacing = 70
    base_y = h - bar_h + 20

    for i, line in enumerate(text_lines[:4]):
        delay = i * 0.5          # мөр бүр 0.5 сек хоцорч гарна
        if t_sec < delay:
            continue

        progress = min(1.0, (t_sec - delay) / 0.4)
        alpha = int(255 * progress)
        slide = int(30 * (1.0 - progress))   # дооноос дээш гулсах

        fsize = font_sizes[min(i, len(font_sizes) - 1)]
        font = _load_font(fsize)

        y = base_y + i * line_spacing - slide
        _draw_text_centered(draw, line, y, font, w, alpha)

    composed = Image.alpha_composite(frame, overlay)
    return np.array(composed.convert("RGB"))


def create_video(image_path: str, text_lines: list[str], output_path: str) -> bool:
    """
    image_path: үүсгэсэн зургийн зам
    text_lines: видео дээр гарах текст мөрүүд (дээд тал 4)
    output_path: гаралт MP4 файлын зам
    Returns True амжилттай бол.
    """
    try:
        # Зурагийг ачааллаж өөрчлөх
        img = Image.open(image_path).convert("RGB").resize(OUTPUT_SIZE, Image.LANCZOS)
        base_rgb = np.array(img)

        logger.info(f"MP4 үүсгэж байна ({VIDEO_DURATION}с, {VIDEO_FPS}fps)...")

        total_frames = VIDEO_DURATION * VIDEO_FPS
        writer = imageio.get_writer(
            output_path,
            fps=VIDEO_FPS,
            codec="libx264",
            quality=8,
            pixelformat="yuv420p",
            output_params=["-preset", "fast"],
        )

        for frame_idx in range(total_frames):
            t = frame_idx / total_frames
            frame = _make_frame(base_rgb, text_lines, t)
            writer.append_data(frame)

        writer.close()
        logger.info(f"MP4 хадгалагдлаа: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Видео үүсгэх алдаа: {e}")
        return False
