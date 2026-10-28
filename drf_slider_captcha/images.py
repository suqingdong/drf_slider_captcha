"""Server-only image generation; no coordinates are sent to the browser."""
import base64
from io import BytesIO
from pathlib import Path
import secrets
import random

from django.core.exceptions import ImproperlyConfigured
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


def _background(config):
    if config.BACKGROUND_DIR:
        paths = [p for p in Path(config.BACKGROUND_DIR).iterdir()
                 if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
        if not paths:
            raise ImproperlyConfigured("BACKGROUND_DIR contains no PNG/JPEG/WebP images.")
        with Image.open(secrets.choice(paths)) as source:
            if source.width * source.height > 25_000_000:
                raise ImproperlyConfigured("CAPTCHA backgrounds must not exceed 25 million pixels.")
            source = ImageOps.exif_transpose(source).convert("RGB")
            return ImageOps.fit(source, (config.WIDTH, config.HEIGHT), method=Image.Resampling.LANCZOS)
    # Bundled zero-download demo art. Supply your own photographs in production.
    width, height = config.WIDTH, config.HEIGHT
    palette = secrets.choice([((239, 223, 198), (189, 153, 112)),
                              ((223, 235, 230), (124, 165, 152)),
                              ((231, 228, 241), (157, 150, 181))])
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    art_rng = random.Random(secrets.randbits(128))
    for y in range(height):
        for x in range(width):
            ratio = (x / width + y / height) / 2
            grain = art_rng.randrange(9) - 4
            pixels[x, y] = tuple(max(0, min(255, int(a * (1 - ratio) + b * ratio) + grain))
                                 for a, b in zip(*palette))
    scale = 3
    large = image.resize((width * scale, height * scale))
    draw = ImageDraw.Draw(large)
    def coords(values):
        return tuple(round(v * scale) for v in values)
    # An illustrated coffee / notebook scene reminiscent of the supplied reference.
    draw.polygon(coords((width * .54, -10, width + 30, 0, width + 30, height + 20, width * .3, height + 20)), fill="#f8f3e8")
    for i in range(11):
        y = height * .40 + i * 6
        draw.line(coords((width * .68 - i * 1.8, y, width * .94, y + 18)), fill="#d9d0be", width=scale)
    cx, cy, r = width * .20, height * .41, height * .32
    draw.ellipse(coords((cx-r-8, cy-r+9, cx+r+12, cy+r+21)), fill="#a99177")
    draw.ellipse(coords((cx-r-12, cy-r+3, cx+r+9, cy+r+16)), fill="#fff8ed")
    draw.ellipse(coords((cx+r-7, cy-16, cx+r+27, cy+15)), fill="#fcf5e8")
    draw.ellipse(coords((cx+r+2, cy-9, cx+r+20, cy+8)), fill=palette[1])
    draw.ellipse(coords((cx-r, cy-r, cx+r, cy+r)), fill="#fffcf6")
    draw.ellipse(coords((cx-r+6, cy-r+6, cx+r-6, cy+r-6)), fill="#8c5533")
    draw.ellipse(coords((cx-r+10, cy-r+10, cx+r-10, cy+r-10)), fill="#b87947")
    draw.arc(coords((cx-r+15, cy-r+14, cx+r-14, cy+r-14)), 205, 315, fill="#f4d6ae", width=3*scale)
    draw.line(coords((width * .44, height * .86, width * .7, height * .96)), fill="#466a65", width=6*scale)
    return large.resize((width, height), Image.Resampling.LANCZOS)


def _mask(width):
    scale = 3
    mask = Image.new("L", (width * scale, width * scale))
    draw = ImageDraw.Draw(mask)
    r = width // 7
    left, right, mid = r, width-r-1, width//2
    draw.rectangle(tuple(v*scale for v in (left, left, right, right)), fill=255)
    # Random orientations alter the puzzle profile, not merely its position.
    sides = [(mid, left), (right, mid), (mid, right), (left, mid)]
    outward = secrets.choice([(0, 1), (1, 2), (2, 3), (0, 3)])
    for i, (cx, cy) in enumerate(sides):
        draw.ellipse(tuple(v*scale for v in (cx-r, cy-r, cx+r, cy+r)),
                     fill=255 if i in outward else 0)
    return mask.resize((width, width), Image.Resampling.LANCZOS)


def _data_url(image, format):
    output = BytesIO()
    image.save(output, format=format, **({"quality": 88} if format == "JPEG" else {}))
    mime = "image/jpeg" if format == "JPEG" else "image/png"
    return f"data:{mime};base64," + base64.b64encode(output.getvalue()).decode("ascii")


def generate_puzzle(config):
    original = _background(config)
    pw = config.PIECE_WIDTH
    x = pw + 12 + secrets.randbelow(config.WIDTH - 2*pw - 24)
    y = 8 + secrets.randbelow(config.HEIGHT - pw - 15)
    mask = _mask(pw)
    full_mask = Image.new("L", original.size)
    full_mask.paste(mask, (x, y))
    dimmed = Image.blend(original, Image.new("RGB", original.size, "#253333"), .48)
    background = Image.composite(dimmed, original, full_mask)
    outline = ImageChops.subtract(full_mask.filter(ImageFilter.MaxFilter(3)),
                                 full_mask.filter(ImageFilter.MinFilter(3)))
    background = Image.composite(Image.new("RGB", original.size, "#e4e9dc"), background, outline)
    # Full-height transparent strip preserves hidden y and needs no puzzleSize.top updates.
    puzzle = Image.new("RGBA", (pw, config.HEIGHT))
    cutout = original.crop((x, y, x+pw, y+pw)).convert("RGBA")
    cutout.putalpha(mask)
    puzzle.paste(cutout, (0, y))
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
    border = Image.new("RGBA", (pw, pw), "#ffffff")
    border.putalpha(edge)
    puzzle.alpha_composite(border, (0, y))
    return {"bgUrl": _data_url(background, "JPEG"), "puzzleUrl": _data_url(puzzle, "PNG")}, x
