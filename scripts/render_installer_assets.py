from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "installer" / "assets"
LOGO = ROOT / "assets" / "bonusdesk.png"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    family = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(family, size)


def gradient(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    pixels = image.load()
    for y in range(height):
        progress = y / max(1, height - 1)
        start = (12, 35, 63)
        end = (18, 64, 104)
        color = tuple(int(a + (b - a) * progress) for a, b in zip(start, end))
        for x in range(width):
            pixels[x, y] = color
    return image


def render_large() -> None:
    image = gradient((164, 314))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((80, -30, 215, 105), fill=(37, 99, 235, 90))
    draw.ellipse((-80, 210, 110, 400), fill=(66, 170, 255, 45))

    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((78, 78), Image.Resampling.LANCZOS)
    image.paste(logo, ((164 - logo.width) // 2, 60), logo)

    title_font = font(20, bold=True)
    subtitle_font = font(10)
    title = "BonusDesk"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((164 - (title_box[2] - title_box[0])) / 2, 157), title, font=title_font, fill="white")
    subtitle = "BONUS REVIEW"
    subtitle_box = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    draw.text(
        ((164 - (subtitle_box[2] - subtitle_box[0])) / 2, 187),
        subtitle,
        font=subtitle_font,
        fill=(177, 211, 246),
    )
    draw.rounded_rectangle((37, 222, 127, 225), radius=2, fill=(72, 160, 255))
    draw.text((33, 252), "Локально. Быстро. Чисто.", font=font(9), fill=(210, 228, 247))
    image.save(OUTPUT / "wizard-large.bmp")


def render_small() -> None:
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 62, 62), radius=14, fill=(241, 246, 253), outline=(207, 222, 239), width=1)
    logo = Image.open(LOGO).convert("RGBA")
    logo.thumbnail((48, 48), Image.Resampling.LANCZOS)
    image.paste(logo, ((64 - logo.width) // 2, (64 - logo.height) // 2), logo)
    image.save(OUTPUT / "wizard-small.bmp")


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    render_large()
    render_small()
