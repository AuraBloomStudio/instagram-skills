#!/usr/bin/env python3
"""Generate a flat numbered-steps diagram image for the 10% "diagrama" leg of
the 60/30/10 mixed visual style (see scripts/references/mixed_visual_style.md).

Unlike generate_post_image.py's photo/illustration styles, this script never
calls Gemini. Image generation models -- Gemini included -- are unreliable at
rendering legible embedded text (labels, numbers, arrows), which is exactly
what a diagram needs. Instead this draws a simple vertical numbered-steps
diagram directly with Pillow: a numbered circle per item, a connecting line,
and word-wrapped label text, over a solid/gradient BRAND_COLORS background
(same palette and parsing as --flat-color in generate_post_image.py, reused
directly from that module rather than duplicated here).

No people, no photorealism, no Gemini call, no API key needed -- diagrams are
deterministic and free to generate, same as --flat-color quote cards.

The top ~22% of the canvas is left empty on purpose, matching the negative-
space convention the photo/illustration styles use for their Canva title
overlay (see canva_title_style.md) -- a short headline can still be added by
hand on top of a diagram slide without colliding with the diagram itself.

Usage:
  python scripts/generate_diagram_image.py "scripts/output_clips/mi_reel/03_senales_a.png" \\
      --items-json '["Primera senal", "Segunda senal", "Tercera senal"]' \\
      --flat-color 3 --aspect 9:16
"""
from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# Reuse BRAND_COLORS parsing and the solid/gradient background renderer
# instead of duplicating that regex/logic -- both scripts live in the same
# directory, so a plain import works when run as `python
# scripts/generate_diagram_image.py` from the repo root.
from generate_post_image import (
    ASPECT_RATIO_SPECS,
    DEFAULT_ASPECT_RATIO,
    GenerationError,
    load_style_guide,
    render_flat_color_image,
    select_brand_color,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FONT_CACHE_DIR = REPO_ROOT / "testing" / "fonts"

# Same google/fonts raw-GitHub hosting pattern already used for
# HOOK_ACCENT_FONT_URL in render_reel_json2video.py (there it's handed to
# JSON2Video as a URL; here it's downloaded once and cached locally so Pillow
# can render with it offline afterward).
POPPINS_BOLD_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Bold.ttf"
)
POPPINS_SEMIBOLD_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-SemiBold.ttf"
)

TOP_MARGIN_FRACTION = 0.22  # kept empty for a Canva title overlay, see docstring
SIDE_MARGIN_FRACTION = 0.10
CIRCLE_DIAMETER = 90
CIRCLE_TEXT_GAP = 32
ITEM_MIN_GAP = 36  # extra vertical space between items beyond text height

ACCENT_RGB = (184, 152, 94)  # "Dorado" from BRAND_COLORS -- fixed diagram accent
ACCENT_NUMBER_RGB = (75, 58, 48)  # dark chocolate, readable on the gold accent
LIGHT_TEXT_RGB = (243, 233, 216)
DARK_TEXT_RGB = (75, 58, 48)


def _download_font(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=30)
    if resp.status_code >= 400:
        raise GenerationError(f"No se pudo descargar la fuente {url}: HTTP {resp.status_code}")
    dest.write_bytes(resp.content)
    return dest


def load_fonts(number_size: int, text_size: int) -> dict:
    bold_path = _download_font(POPPINS_BOLD_URL, FONT_CACHE_DIR / "Poppins-Bold.ttf")
    semibold_path = _download_font(POPPINS_SEMIBOLD_URL, FONT_CACHE_DIR / "Poppins-SemiBold.ttf")
    return {
        "number": ImageFont.truetype(str(bold_path), number_size),
        "text": ImageFont.truetype(str(semibold_path), text_size),
    }


def _relative_luminance(rgb: tuple) -> float:
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _text_color_for_background(color: dict) -> tuple:
    top_rgb = color["colors"][0]
    return DARK_TEXT_RGB if _relative_luminance(top_rgb) > 0.5 else LIGHT_TEXT_RGB


def _wrap_text(draw: "ImageDraw.ImageDraw", text: str, font: "ImageFont.FreeTypeFont", max_width: int) -> list:
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_diagram(items: list, color: dict, size: tuple) -> "Image.Image":
    width, height = size
    image = render_flat_color_image(color, size)
    draw = ImageDraw.Draw(image)

    text_color = _text_color_for_background(color)
    number_size = max(round(CIRCLE_DIAMETER * 0.5), 24)
    text_size = max(round(width * 0.042), 26)
    fonts = load_fonts(number_size, text_size)

    left_margin = round(width * SIDE_MARGIN_FRACTION)
    circle_center_x = left_margin + CIRCLE_DIAMETER // 2
    text_left = left_margin + CIRCLE_DIAMETER + CIRCLE_TEXT_GAP
    text_max_width = width - text_left - round(width * SIDE_MARGIN_FRACTION)

    top_bound = round(height * TOP_MARGIN_FRACTION)
    bottom_bound = height - round(height * SIDE_MARGIN_FRACTION)
    available_height = bottom_bound - top_bound

    # Two-pass layout: first wrap every item's text to know its block height,
    # then distribute the fixed available_height evenly (extra whitespace
    # between items) instead of guessing a per-item height up front.
    wrapped_items = []
    line_height = round(text_size * 1.25)
    for item in items:
        lines = _wrap_text(draw, item, fonts["text"], text_max_width)
        block_height = max(len(lines) * line_height, CIRCLE_DIAMETER)
        wrapped_items.append((lines, block_height))

    total_block_height = sum(h for _, h in wrapped_items)
    gap_count = max(len(wrapped_items) - 1, 1)
    max_gap = round(height * 0.09)
    gap = min(max((available_height - total_block_height) / gap_count, ITEM_MIN_GAP), max_gap)

    total_content_height = total_block_height + gap * gap_count
    y = top_bound + max((available_height - total_content_height) / 2, 0)
    circle_centers = []
    for index, (lines, block_height) in enumerate(wrapped_items):
        circle_center_y = y + CIRCLE_DIAMETER // 2
        circle_centers.append((circle_center_x, circle_center_y))

        draw.ellipse(
            [
                circle_center_x - CIRCLE_DIAMETER // 2,
                circle_center_y - CIRCLE_DIAMETER // 2,
                circle_center_x + CIRCLE_DIAMETER // 2,
                circle_center_y + CIRCLE_DIAMETER // 2,
            ],
            fill=ACCENT_RGB,
        )
        number_text = str(index + 1)
        number_bbox = draw.textbbox((0, 0), number_text, font=fonts["number"])
        draw.text(
            (
                circle_center_x - (number_bbox[2] - number_bbox[0]) / 2,
                circle_center_y - (number_bbox[3] - number_bbox[1]) / 2 - number_bbox[1],
            ),
            number_text,
            font=fonts["number"],
            fill=ACCENT_NUMBER_RGB,
        )

        text_y = circle_center_y - (len(lines) * line_height) / 2
        for line in lines:
            draw.text((text_left, text_y), line, font=fonts["text"], fill=text_color)
            text_y += line_height

        y += block_height + gap

    for i in range(len(circle_centers) - 1):
        x1, y1 = circle_centers[i]
        x2, y2 = circle_centers[i + 1]
        draw.line(
            [(x1, y1 + CIRCLE_DIAMETER // 2), (x2, y2 - CIRCLE_DIAMETER // 2)],
            fill=ACCENT_RGB,
            width=4,
        )

    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_file", help="Ruta de salida del PNG (carpeta y nombre exactos)")
    parser.add_argument(
        "--items-json",
        required=True,
        help='Lista JSON de 2-6 strings, un item por paso/senal, ej. \'["Primera", "Segunda"]\'',
    )
    parser.add_argument(
        "--flat-color",
        required=True,
        metavar="INDICE_O_NOMBRE",
        help="Color de fondo de BRAND_COLORS (image_prompt_style.md) -- indice numerico o texto "
        "parcial del nombre. Distinto del elegido para el hook/CTA del mismo carrusel/reel.",
    )
    parser.add_argument(
        "--aspect",
        default=DEFAULT_ASPECT_RATIO,
        choices=sorted(ASPECT_RATIO_SPECS),
        help=f"Aspect ratio de salida (default: {DEFAULT_ASPECT_RATIO}). 9:16 para momentos de reel.",
    )
    args = parser.parse_args()

    try:
        items = json.loads(args.items_json)
    except json.JSONDecodeError as e:
        print(f"--items-json invalido: {e}", file=sys.stderr)
        return 1
    if not isinstance(items, list) or not (2 <= len(items) <= 6) or not all(isinstance(i, str) and i.strip() for i in items):
        print("--items-json debe ser una lista JSON de 2 a 6 strings no vacios.", file=sys.stderr)
        return 1

    out_path = Path(args.out_file)
    output_size = ASPECT_RATIO_SPECS[args.aspect]["size"]

    try:
        style = load_style_guide()
        color = select_brand_color(args.flat_color, style["brand_colors"])
        print(f"Generando diagrama ({len(items)} items, color: {color['label']})...")
        image = render_diagram(items, color, output_size)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_path, "PNG")
        print(f"Imagen guardada en: {out_path} ({output_size[0]}x{output_size[1]})")
    except GenerationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
