"""
text_fallback.py - RESPALDO DETERMINISTA DE TEXTO de carousel-gen (2026-09-26).

Cuando un slide agoto sus 2 regeneraciones automaticas y Gemini sigue dibujando el texto
mal (palabras faltantes, duplicadas, inventadas o ilegibles), NO se pregunta ni se detiene
el carrusel: se conserva la ultima imagen visual generada como fondo, se cubre la zona
del texto erroneo con un difuminado oscuro (mismo lenguaje del diseño aprobado: texto
claro sobre zona oscura) y se compone encima el TEXTO EXACTO del slide con Pillow y la
fuente Poppins Bold incluida en la skill (assets/fonts/, licencia SIL OFL 1.1).

El resultado pasa otra vez por el QA estructural y el Text QA. No llama a Gemini ni a
ninguna API: es 100% local y reproducible.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

SKILL_DIR = Path(__file__).resolve().parent.parent
FONT_PATH = SKILL_DIR / "assets" / "fonts" / "Poppins-Bold.ttf"

_SIDE_MARGIN = 0.07        # margen lateral seguro (fraccion del ancho)
_BAND_PAD = 0.045          # aire extra arriba/abajo de la zona de texto detectada
_FADE = 0.05              # degradado suave FUERA de la zona cubierta
_MAX_FONT = 0.060          # tamaño maximo de fuente (fraccion del ancho)
_MIN_FONT = 0.030          # tamaño minimo legible en telefono
_LINE_SPACING = 1.22


class FallbackError(Exception):
    """El respaldo no pudo ejecutarse (fuente o imagen no disponibles)."""


def _placement_region(text_placement: str, width: int, height: int) -> Tuple[int, int]:
    """Zona vertical por defecto segun text_placement del brief (si el OCR no ve texto)."""
    tp = (text_placement or "").lower()
    if any(k in tp for k in ("upper", "superior", "top")):
        return int(height * 0.06), int(height * 0.42)
    if any(k in tp for k in ("lower", "inferior", "bottom")):
        return int(height * 0.55), int(height * 0.94)
    return int(height * 0.30), int(height * 0.70)


def _detect_text_band(img: Image.Image, text_placement: str) -> Optional[Tuple[int, int]]:
    """
    Zona vertical del texto que Gemini dibujo (para taparla), via las cajas de palabras
    de Tesseract (1 hilo, con tiempo maximo). Solo se consideran palabras en la mitad de
    la imagen que indica text_placement, para no tapar la portada del mockup ni la foto.
    Devuelve None si no hay OCR o no se detecta texto.
    """
    try:
        import pytesseract
        import text_qa
    except ImportError:
        return None
    cmd = text_qa._tesseract_cmd()
    if not cmd:
        return None
    pytesseract.pytesseract.tesseract_cmd = cmd
    os.environ["OMP_THREAD_LIMIT"] = "1"
    try:
        with text_qa._OCR_SEMAPHORE:
            data = pytesseract.image_to_data(img.convert("L"), lang="spa+eng",
                                             output_type=pytesseract.Output.DICT,
                                             timeout=text_qa.OCR_TIMEOUT_SECONDS)
    except Exception:  # noqa: BLE001 - sin deteccion: se usa la zona por defecto
        return None
    height = img.height
    tp = (text_placement or "").lower()
    tops: List[int] = []
    bottoms: List[int] = []
    for i, word in enumerate(data.get("text", [])):
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < 20 or len(word.strip()) < 2 or not any(ch.isalnum() for ch in word):
            continue
        top, h = int(data["top"][i]), int(data["height"][i])
        center = top + h / 2
        if any(k in tp for k in ("upper", "superior", "top")) and center > height * 0.55:
            continue
        if any(k in tp for k in ("lower", "inferior", "bottom")) and center < height * 0.45:
            continue
        tops.append(top)
        bottoms.append(top + h)
    if not tops:
        return None
    return min(tops), max(bottoms)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Parte el texto en lineas que caben en max_width. Conserva los saltos de parrafo."""
    lines: List[str] = []
    paragraphs = [p.strip() for p in text.replace("\r\n", "\n").split("\n")]
    for idx, paragraph in enumerate(paragraphs):
        if not paragraph:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def compose_exact_text(src: Path, exact_text: str, text_placement: str, out: Path,
                       font_path: Path = FONT_PATH) -> Dict[str, Any]:
    """
    Compone el TEXTO EXACTO sobre la ultima imagen del slide y guarda el PNG en `out`.
    Devuelve un resumen (zona usada, tamaño de fuente, lineas). Lanza FallbackError si
    falta la fuente o la imagen.
    """
    if not Path(font_path).is_file():
        raise FallbackError(f"fuente no disponible: {font_path}")
    try:
        img = Image.open(src).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise FallbackError(f"imagen no legible: {src} ({exc})")
    width, height = img.size
    detected = _detect_text_band(img, text_placement)
    y0, y1 = detected if detected else _placement_region(text_placement, width, height)
    y0 = max(0, int(y0 - height * _BAND_PAD))
    y1 = min(height, int(y1 + height * _BAND_PAD))
    x0, x1 = int(width * _SIDE_MARGIN), int(width * (1 - _SIDE_MARGIN))
    max_width = x1 - x0

    draw_probe = ImageDraw.Draw(img)
    size = int(width * _MAX_FONT)
    min_size = int(width * _MIN_FONT)
    while True:
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap(draw_probe, exact_text, font, max_width)
        line_h = int(size * _LINE_SPACING)
        text_h = line_h * len(lines)
        if text_h <= (y1 - y0) * 0.92 or size <= min_size:
            break
        size -= 2
    # Si ni con la fuente minima cabe, se agranda la zona (nunca se encoge mas el texto).
    if text_h > (y1 - y0) * 0.92:
        target = min(height, int(text_h / 0.92))
        center = (y0 + y1) // 2
        y0 = max(0, center - target // 2)
        y1 = min(height, y0 + target)
        y0 = max(0, y1 - target)

    # Tapar el texto erroneo: la zona [y0, y1] queda TOTALMENTE cubierta (difuminado +
    # oscurecido) y el degradado suave queda FUERA de ella, para que no asomen restos del
    # texto de Gemini por los bordes.
    fade = max(1, int(height * _FADE))
    by0, by1 = max(0, y0 - fade), min(height, y1 + fade)
    band = img.crop((0, by0, width, by1)).filter(ImageFilter.GaussianBlur(radius=max(12, width // 40)))
    band = ImageEnhance.Brightness(band).enhance(0.30)
    mask = Image.new("L", band.size, 255)
    mdraw = ImageDraw.Draw(mask)
    top_fade, bottom_fade = y0 - by0, by1 - y1
    for i in range(top_fade):
        mdraw.line([(0, i), (band.width, i)], fill=int(255 * (i + 1) / top_fade))
    for i in range(bottom_fade):
        mdraw.line([(0, band.height - 1 - i), (band.width, band.height - 1 - i)],
                   fill=int(255 * (i + 1) / bottom_fade))
    img.paste(band, (0, by0), mask)

    # Texto exacto centrado, blanco con sombra suave (legibilidad en telefono).
    draw = ImageDraw.Draw(img)
    top = y0 + ((y1 - y0) - text_h) // 2
    shadow = max(1, size // 18)
    for n, line in enumerate(lines):
        if not line:
            continue
        w = draw.textlength(line, font=font)
        x = (width - w) / 2
        y = top + n * line_h
        draw.text((x + shadow, y + shadow), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
    return {"band": [y0, y1], "detected_band": bool(detected), "font_size": size, "lines": len(lines)}
