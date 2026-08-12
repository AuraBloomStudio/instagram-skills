#!/usr/bin/env python3
"""Generate a cover image for an approved Constelaciones Familiares post.

Flow:
  1. Read the approved copy from a .docx or .txt file.
  2. Ask Gemini to identify the copy's central emotion and theme, and to write
     a people-centered visual concept (never a literal metaphor object) using
     the rules and a randomly chosen composition archetype from
     scripts/references/image_prompt_style.md.
  3. Build the final English image prompt for Gemini Flash Image by appending
     the BRAND_STYLE block from that same reference file: warm cinematic
     color photography, generic/anonymous people, no overlaid text. Title and
     signature are added later by hand in Canva, so the image itself carries
     no text at all.
  4. Call Gemini Flash Image with that prompt, requesting the aspect ratio
     given by --aspect (default 4:5; also supports 9:16 for Stories and 1:1).
  5. Resize to the exact matching pixel size and save the PNG to
     Desktop/Imagenes Posts/<nombre-del-copy>.png (or wherever --out-dir points)

--protagonist "<description>" carries a fixed protagonist description (e.g.
"a woman in her 30s") into step 2, so multiple slides of one carousel depict
the same person instead of a different generic figure each call.

--flat-color <index-or-name> skips Gemini entirely (no API key needed) and
instead renders a solid or gradient background from BRAND_COLORS in
image_prompt_style.md -- used for "quote card" carousel slides that carry no
photo, just text added later in Canva.

--visual-style <photo|minimal|book|cartoon|storytelling|mezcla-ilustracion>
switches the whole prompt pipeline. "photo" (the default) is completely
unchanged: warm cinematic photography per image_prompt_style.md. minimal/
book/cartoon/storytelling read scripts/references/illustration_style.md
instead -- a separate, simpler rule set for line-art, storybook, cartoon, or
sequential-panel illustration, since the photographic file's anonymity/
composition/setting rotation is specific to photorealism and doesn't map
cleanly onto illustrated characters. "mezcla-ilustracion" also reads
illustration_style.md but is a deliberately different, faceless leg used by
the 60/30/10 mixed visual style (see references/mixed_visual_style.md): flat
conceptual/iconographic illustration with NO people, so it never needs
--protagonist.

--setting <index-or-name> pins one specific SETTINGS entry (image_prompt_style.md)
instead of letting the script rotate one automatically -- used to keep the
same room/light source across every photo slide of one carousel (composition
archetype and camera angle keep rotating freely per slide either way). Only
applies to --visual-style photo; ignored otherwise.

--headline-main "<phrase>" (optional --headline-accent "<shorter phrase>" too)
bakes a short title directly onto the generated image with Pillow, instead of
leaving it for a later manual Canva step -- same two-tier typography as
canva_title_style.md (bold poster headline + optional pale-gold script accent
line). For --visual-style photo and the 4 character-illustration styles, the
headline is placed in whichever third of the frame (top or bottom) doesn't
show a face: a fixed camera-angle -> safe-zone table skips the check
entirely when the requested angle already guarantees no face in a zone
(CAMERA_ANGLE_SAFE_ZONES) AND the composition depicts only one person, and an
OpenCV Haar-cascade veto (needs opencv-python) verifies every other case --
ambiguous angles, illustrated styles with no angle system, and any
multi-person composition (MULTI_PERSON_ARCHETYPE_INDICES), since a
deterministic angle only ever describes where the PROTAGONIST's face can be,
not a companion's.
Flat-color and mezcla-ilustracion slides have no protagonist at all, so the
headline is centered with no face check. Omitting --headline-main leaves the
image exactly as before this option existed -- no text, no opencv import.

The visual style (lighting, composition options, how metaphors get reinterpreted)
for photography lives entirely in scripts/references/image_prompt_style.md,
and for illustration in scripts/references/illustration_style.md -- edit
those references to tune the output without touching code.

GEMINI_API_KEY is never hardcoded. If it is not already set as an
environment variable, this script prompts for it (input is masked) and
offers to save it to the local .env file, which is already gitignored.

Usage:
  python scripts/generate_post_image.py "C:\\path\\to\\Posts Constelaciones\\archivo.docx"
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import random
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv, set_key
from PIL import Image, ImageDraw, ImageFont

try:
    import docx  # python-docx
except ImportError:
    docx = None

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-flash-latest")
IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")

DEFAULT_OUTPUT_DIR = Path(os.path.expanduser("~")) / "Desktop" / "Imagenes Posts"

# Aspect ratios this script knows how to produce. "size" is the exact pixel
# output after resize; "prompt_text" is appended to the image prompt in place
# of whatever aspect-ratio line lives in BRAND_STYLE, so the written prompt
# always matches the aspectRatio actually sent to the Gemini API -- keeping
# these in sync in one place avoids asking for 9:16 while telling Gemini "4:5"
# in the prompt text.
ASPECT_RATIO_SPECS = {
    "4:5": {
        "size": (1080, 1350),
        "prompt_text": "Vertical 4:5 composition, high resolution.",
    },
    "9:16": {
        "size": (1080, 1920),
        "prompt_text": "Vertical 9:16 composition (Instagram/Facebook Stories format), high resolution.",
    },
    "1:1": {
        "size": (1080, 1080),
        "prompt_text": "Square 1:1 composition, high resolution.",
    },
}
DEFAULT_ASPECT_RATIO = "4:5"

STYLE_GUIDE_PATH = Path(__file__).resolve().parent / "references" / "image_prompt_style.md"
ILLUSTRATION_STYLE_PATH = Path(__file__).resolve().parent / "references" / "illustration_style.md"
VISUAL_STYLES = {
    "photo": None,
    "minimal": "STYLE_MINIMAL",
    "book": "STYLE_BOOK",
    "cartoon": "STYLE_CARTOON",
    "storytelling": "STYLE_STORYTELLING",
    "mezcla-ilustracion": "STYLE_MEZCLA_ILUSTRACION",
}
# Which ILLUSTRATION_ANALYSIS_RULES-style block in illustration_style.md
# supplies the analysis-step instructions for each non-photo style. The
# original 4 character styles all share ILLUSTRATION_ANALYSIS_RULES (forces a
# human figure, needs __PROTAGONIST__); mezcla-ilustracion is the opposite
# contract (no people, no __PROTAGONIST__ token at all) and gets its own block
# -- see illustration_style.md for why.
ILLUSTRATION_ANALYSIS_BLOCKS = {
    "minimal": "ILLUSTRATION_ANALYSIS_RULES",
    "book": "ILLUSTRATION_ANALYSIS_RULES",
    "cartoon": "ILLUSTRATION_ANALYSIS_RULES",
    "storytelling": "ILLUSTRATION_ANALYSIS_RULES",
    "mezcla-ilustracion": "MEZCLA_ILUSTRACION_ANALYSIS_RULES",
}
DEFAULT_VISUAL_STYLE = "photo"
STATE_PATH = REPO_ROOT / "testing" / "image_gen_state.json"
ROTATION_HISTORY = 2  # avoid repeating any of the last N picks per category

# --- Baked-in headline text (--headline-main / --headline-accent / ---------
# --headline-extra / --body-text) --------------------------------------
# Shared font cache -- generate_diagram_image.py imports FONT_CACHE_DIR and
# _download_font from here instead of keeping its own copy, so there is one
# cache directory and one download helper for every script that bakes text.
FONT_CACHE_DIR = REPO_ROOT / "testing" / "fonts"

# Poppins Bold for the main headline -- matches render_reel_json2video.py's
# HOOK_MAIN_FONT exactly (reels and carousels read as one brand system, not
# two different typography systems). Anton was tried first as a stand-in for
# canva_title_style.md's old "Anton or Oswald Bold" spec, but that spec is
# now Poppins Bold too, see canva_title_style.md.
HEADLINE_MAIN_FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Bold.ttf"
)
HEADLINE_ACCENT_FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/"
    "PlayfairDisplay-Italic%5Bwght%5D.ttf"
)
# --headline-extra (hook only, a short third line under main+accent) --
# Poppins SemiBold, same pale gold as the accent line so it doesn't compete
# in hierarchy with the main headline.
HEADLINE_EXTRA_FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-SemiBold.ttf"
)
HEADLINE_MAIN_COLOR = (242, 169, 0)  # #F2A900
HEADLINE_ACCENT_COLOR = (250, 232, 168)  # #FAE8A8
HEADLINE_EXTRA_COLOR = HEADLINE_ACCENT_COLOR  # same pale gold
# --body-text (content slides 2-5 only): the longer 2-4 sentence microdolor
# copy, baked separately from the gold title/subtitle -- same cyan as the
# reel subtitles (SUBTITLE_WORD_COLOR in render_reel_json2video.py), same
# Poppins Bold weight too. Never combined with --headline-extra on the same
# slide (hook vs. content slides are mutually exclusive callers).
BODY_TEXT_COLOR = (34, 211, 238)  # #22D3EE
# Solid outline behind the headline, same rationale as HOOK_MAIN_STROKE_* in
# render_reel_json2video.py: keeps contrast when the zone lands on a bright
# patch of the photo (a window, a light wall) -- applied to every block here
# since static photos vary more than reel B-roll, unlike the reel hook which
# only stroked the main phrase.
HEADLINE_STROKE_COLOR = (28, 18, 8)  # #1C1208

# Default text band is the top/bottom 30% of the frame (a short 1-2 line
# headline). A body-text paragraph (2-4 sentences) needs more room to sit
# next to the title/subtitle without crowding, so it gets a wider band --
# both the OpenCV face check and the text layout use the same band size, so
# the check always covers exactly the area the text will actually occupy.
DEFAULT_BAND_FRACTION = 0.30
BODY_BAND_FRACTION = 0.55

# Index into CAMERA_ANGLES (image_prompt_style.md) -> deterministic
# text-safe zone. The script already knows exactly which angle it asked for
# per call, so most of the time no pixel analysis is needed at all: "Shot
# from directly behind" and "framed from shoulders/collarbone down" and the
# hands-only close-up all guarantee (by construction) where the face can or
# can't be. "auto" marks the 2 angles that don't guarantee anything on their
# own (profile/three-quarter turned away, softly backlit) -- those fall back
# to the OpenCV veto check on both thirds before trusting either one. Only
# meaningful for Gemini-generated photos (the script requested that angle);
# --source-image (Pexels or any externally supplied photo) always uses
# "auto" since nothing was requested about its composition.
CAMERA_ANGLE_SAFE_ZONES = ["bottom", "auto", "auto", "top", "top"]

# Index into COMPOSITION_ARCHETYPES (image_prompt_style.md) for the 2 that
# depict more than one person. CAMERA_ANGLE_SAFE_ZONES' deterministic zones
# only describe where the PROTAGONIST's head/face can be -- confirmed in a
# real test that "framed from shoulders down" (a deterministic "top" zone)
# left a second figure's face partially inside the top third anyway, since
# that instruction only binds "the figure" (singular). For these 2
# archetypes, never trust the deterministic zone -- always run the OpenCV
# veto regardless of which camera angle was picked.
MULTI_PERSON_ARCHETYPE_INDICES = {2, 3}


def _download_font(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=30)
    if resp.status_code >= 400:
        raise GenerationError(f"No se pudo descargar la fuente {url}: HTTP {resp.status_code}")
    dest.write_bytes(resp.content)
    return dest


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


def _zone_pixel_bounds(
    zone: str, width: int, height: int, band_fraction: float = DEFAULT_BAND_FRACTION
) -> tuple:
    band_height = round(height * band_fraction)
    if zone == "top":
        return (0, 0, width, band_height)
    return (0, height - band_height, width, height)


def _zone_has_face(
    image: "Image.Image", zone: str, band_fraction: float = DEFAULT_BAND_FRACTION
) -> bool:
    """OpenCV Haar-cascade check on the given band of the frame -- offline,
    free, no extra Gemini call. Reached for the 2 ambiguous Gemini camera
    angles, the 4 character-illustration styles (no angle system at all),
    and always for --source-image (Pexels or any externally supplied photo,
    no composition info at all) -- never for flat-color/mezcla-ilustracion
    (no protagonist, no face possible) or the 3 deterministic photo angles.

    This is a best-effort pre-filter, not a guarantee: a real carousel test
    found this exact cascade (even after tuning below) can flip between
    detecting and missing the same real, visibly uncovered face depending on
    a 1px difference in the crop height it's given (itself a function of how
    much text the caller is baking) -- an inherent instability of Haar
    cascades on marginal (tilted, partially hand-occluded) faces, not
    something scaleFactor/minNeighbors alone can fully close. The mandatory
    visual review step in carrusel-constelaciones/SKILL.md (checking every
    generated image by eye before shipping) is the real backstop; this
    function only reduces how often that manual check finds something."""
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        raise GenerationError(
            "Quemar texto con proteccion de rostro requiere opencv-python. "
            "Instala con: pip install opencv-python"
        ) from e

    box = _zone_pixel_bounds(zone, image.width, image.height, band_fraction)
    crop = image.crop(box).convert("L")
    array = np.array(crop)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    # scaleFactor=1.1/minNeighbors=5 (OpenCV's own defaults) missed a real,
    # visibly uncovered face in a real carousel test -- tilted down, one hand
    # partially raised near it. minNeighbors=5 requires 5 overlapping
    # detection windows to agree before counting a hit; the real face only
    # ever produced 3. A missed face means baked text silently covers it,
    # which the mandatory rule forbids outright; a false positive here only
    # costs a zone swap or a manual-review warning. Biasing hard toward
    # over-detection is the correct tradeoff for a safety veto.
    faces = cascade.detectMultiScale(array, scaleFactor=1.05, minNeighbors=3)
    return len(faces) > 0


def resolve_headline_zone(
    preferred_zone: str, image: "Image.Image", band_fraction: float = DEFAULT_BAND_FRACTION
) -> str:
    """preferred_zone is "top"/"bottom" (deterministic, no check needed) or
    "auto" (ambiguous angle, illustrated style, or --source-image -- verify
    with OpenCV before trusting a zone). band_fraction must match whatever
    render_headline will actually use for this call (see BODY_BAND_FRACTION),
    so the face check covers the real footprint of the text, not just a
    generic third. Always returns a usable zone: if both bands show a face,
    defaults to "top" anyway with a warning rather than skipping the
    headline entirely -- every generated image gets baked text, never a
    silent gap."""
    if preferred_zone in ("top", "bottom"):
        return preferred_zone
    if not _zone_has_face(image, "top", band_fraction):
        return "top"
    if not _zone_has_face(image, "bottom", band_fraction):
        return "bottom"
    print(
        "  Aviso: se detecto un rostro en ambas zonas candidatas para el "
        "texto; se usa la zona superior de todos modos (revisar el "
        "resultado a mano)."
    )
    return "top"


# Same alpha stops as render_reel_json2video.py's GRADIENT_HTML_TEMPLATE
# (approved there after 2 rounds of adjustment against real renders,
# confirmed visible even against the brightest frame of a real render) --
# darkest at the very top and very bottom, lightest in the middle. Reused
# verbatim rather than re-derived, so a cyan body-text block over an
# uncontrolled Pexels photo gets the same proven contrast treatment reels
# already rely on.
GRADIENT_STOPS = [
    (0.00, 0.75),
    (0.12, 0.45),
    (0.25, 0.18),
    (0.55, 0.18),
    (0.75, 0.45),
    (0.88, 0.75),
    (1.00, 0.95),
]


def _gradient_alpha_at(t: float) -> float:
    for (t0, a0), (t1, a1) in zip(GRADIENT_STOPS, GRADIENT_STOPS[1:]):
        if t0 <= t <= t1:
            frac = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return a0 + (a1 - a0) * frac
    return GRADIENT_STOPS[-1][1]


def apply_gradient_scrim(image: "Image.Image") -> "Image.Image":
    """Full-frame top-to-bottom dark scrim, only applied when baking
    --body-text (a full paragraph, unlike the short headline, needs
    guaranteed contrast regardless of where it lands on real footage)."""
    width, height = image.size
    overlay = Image.new("RGBA", (width, height))
    for y in range(height):
        alpha = _gradient_alpha_at(y / max(height - 1, 1))
        overlay.paste((0, 0, 0, round(alpha * 255)), (0, y, width, y + 1))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _build_text_blocks(
    draw: "ImageDraw.ImageDraw",
    width: int,
    headline_main: str,
    headline_accent: Optional[str] = None,
    headline_extra: Optional[str] = None,
    body_text: Optional[str] = None,
) -> tuple:
    """Wrap headline_main (+ optional accent/extra/body_text) into the same
    line/font/color blocks render_headline draws, and return (blocks,
    total_block_height). Split out from render_headline so the real pixel
    height this specific text needs can be measured BEFORE picking a zone --
    a long body_text paragraph can need more room than the fixed
    BODY_BAND_FRACTION reserves, see compute_band_fraction."""
    max_text_width = round(width * 0.86)

    main_path = _download_font(HEADLINE_MAIN_FONT_URL, FONT_CACHE_DIR / "Poppins-Bold.ttf")
    main_size = max(round(width * 0.075), 40)
    main_font = ImageFont.truetype(str(main_path), main_size)
    main_lines = _wrap_text(draw, headline_main.upper(), main_font, max_text_width)
    blocks = [
        {
            "lines": main_lines, "font": main_font,
            "line_height": round(main_size * 1.15), "color": HEADLINE_MAIN_COLOR,
            "stroke_width": max(round(main_size * 0.035), 2),
        }
    ]

    if headline_accent:
        accent_path = _download_font(
            HEADLINE_ACCENT_FONT_URL, FONT_CACHE_DIR / "PlayfairDisplay-Italic.ttf"
        )
        accent_size = max(round(width * 0.06), 32)
        accent_font = ImageFont.truetype(str(accent_path), accent_size)
        blocks.append(
            {
                "lines": _wrap_text(draw, headline_accent, accent_font, max_text_width),
                "font": accent_font, "line_height": round(accent_size * 1.2),
                "color": HEADLINE_ACCENT_COLOR, "stroke_width": max(round(accent_size * 0.02), 1),
            }
        )

    if headline_extra:
        extra_path = _download_font(
            HEADLINE_EXTRA_FONT_URL, FONT_CACHE_DIR / "Poppins-SemiBold.ttf"
        )
        extra_size = max(round(width * 0.045), 26)
        extra_font = ImageFont.truetype(str(extra_path), extra_size)
        blocks.append(
            {
                "lines": _wrap_text(draw, headline_extra, extra_font, max_text_width),
                "font": extra_font, "line_height": round(extra_size * 1.3),
                "color": HEADLINE_EXTRA_COLOR, "stroke_width": max(round(extra_size * 0.025), 1),
            }
        )

    if body_text:
        body_size = max(round(width * 0.042), 28)
        body_font = ImageFont.truetype(str(main_path), body_size)  # same Poppins Bold file
        blocks.append(
            {
                "lines": _wrap_text(draw, body_text, body_font, max_text_width),
                "font": body_font, "line_height": round(body_size * 1.35),
                "color": BODY_TEXT_COLOR, "stroke_width": max(round(body_size * 0.025), 1),
            }
        )

    block_height = sum(len(b["lines"]) * b["line_height"] for b in blocks)
    return blocks, block_height


def compute_band_fraction(
    width: int,
    height: int,
    headline_main: str,
    headline_accent: Optional[str] = None,
    headline_extra: Optional[str] = None,
    body_text: Optional[str] = None,
) -> float:
    """The band_fraction resolve_headline_zone's OpenCV check and
    render_headline's placement must BOTH use for this exact text, instead of
    the fixed DEFAULT_BAND_FRACTION/BODY_BAND_FRACTION constants. A carousel
    content slide's body_text paragraph can run long enough that its block
    (title + subtitle + paragraph) genuinely exceeds the fixed 55% band --
    when that happened with a fixed fraction, render_headline centered the
    overflow past the pixel range the veto had actually checked, silently
    baking text over a real face the check never looked at (found via visual
    review, never caught by the veto itself). Adding an 8% safety margin over
    the measured block height and re-checking the constants as a floor keeps
    short text at the original comfortable minimum; 0.85 caps it so a
    pathologically long paragraph can't demand the whole frame."""
    dummy = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(dummy)
    _, block_height = _build_text_blocks(
        draw, width, headline_main, headline_accent, headline_extra, body_text
    )
    minimum = BODY_BAND_FRACTION if body_text else DEFAULT_BAND_FRACTION
    return min(max(minimum, (block_height / height) * 1.08), 0.85)


def render_headline(
    image: "Image.Image",
    zone: str,
    headline_main: str,
    headline_accent: Optional[str] = None,
    headline_extra: Optional[str] = None,
    body_text: Optional[str] = None,
    band_fraction: Optional[float] = None,
) -> "Image.Image":
    """Bake headline_main (+ optional headline_accent, and EITHER
    headline_extra OR body_text, never both) onto image, centered within the
    given zone ("top"/"bottom" = that band of the frame, sized by
    band_fraction -- "center" = the whole canvas, used for flat-color quote
    cards where the text IS the entire design). body_text also gets a
    full-frame gradient scrim behind every block (see apply_gradient_scrim).
    band_fraction should be whatever compute_band_fraction returned for this
    same text -- callers that skip it (band_fraction=None) get it computed
    here as a fallback, but then resolve_headline_zone's earlier face check
    may have used a different, unmatched fraction."""
    image = image.copy()
    if body_text:
        image = apply_gradient_scrim(image)
    draw = ImageDraw.Draw(image)
    width, height = image.size
    blocks, block_height = _build_text_blocks(
        draw, width, headline_main, headline_accent, headline_extra, body_text
    )

    if band_fraction is None:
        band_fraction = compute_band_fraction(
            width, height, headline_main, headline_accent, headline_extra, body_text
        )
    if zone == "top":
        band_top, band_bottom = 0, round(height * band_fraction)
    elif zone == "bottom":
        band_top, band_bottom = height - round(height * band_fraction), height
    else:  # "center" -- flat-color quote cards, text is the whole design
        band_top, band_bottom = 0, height
    y = (band_top + band_bottom) / 2 - block_height / 2

    for b in blocks:
        for line in b["lines"]:
            bbox = draw.textbbox((0, 0), line, font=b["font"])
            x = (width - (bbox[2] - bbox[0])) / 2
            draw.text(
                (x, y), line, font=b["font"], fill=b["color"],
                stroke_width=b["stroke_width"], stroke_fill=HEADLINE_STROKE_COLOR,
            )
            y += b["line_height"]

    return image


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _pick_avoiding_recent(pool: list, key: str, state: dict) -> str:
    """Random-pick from `pool`, excluding whatever was picked for `key` in the
    last ROTATION_HISTORY runs (tracked in `state`), so the same composition or
    setting can't repeat back-to-back across separate script invocations."""
    recent = state.get(key, [])
    candidates = [item for item in pool if item not in recent] or pool
    choice = random.choice(candidates)
    state[key] = ([choice] + recent)[:ROTATION_HISTORY]
    return choice


def _extract_marked_block(text: str, name: str, source_path: Path = STYLE_GUIDE_PATH) -> str:
    match = re.search(
        rf"<!--\s*BEGIN:{name}\s*-->(.*?)<!--\s*END:{name}\s*-->",
        text,
        re.DOTALL,
    )
    if not match:
        raise GenerationError(
            f"No se encontró el bloque {name} en {source_path}. "
            "Revisa que los marcadores <!-- BEGIN/END --> sigan intactos."
        )
    return match.group(1).strip()


def load_style_guide() -> dict:
    if not STYLE_GUIDE_PATH.exists():
        raise GenerationError(f"No existe el archivo de estilo: {STYLE_GUIDE_PATH}")
    text = STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    brand_style = _extract_marked_block(text, "BRAND_STYLE")
    analysis_rules = _extract_marked_block(text, "ANALYSIS_RULES")

    def _numbered_list(block_name: str) -> list:
        block = _extract_marked_block(text, block_name)
        items = [
            re.sub(r"^\d+\.\s*", "", line).strip()
            for line in block.splitlines()
            if line.strip()
        ]
        if not items:
            raise GenerationError(f"{block_name} está vacío en {STYLE_GUIDE_PATH}")
        return items

    return {
        "brand_style": brand_style,
        "analysis_rules": analysis_rules,
        "archetypes": _numbered_list("COMPOSITION_ARCHETYPES"),
        "camera_angles": _numbered_list("CAMERA_ANGLES"),
        "settings": _numbered_list("SETTINGS"),
        "brand_colors": _numbered_list("BRAND_COLORS"),
    }


def load_illustration_style(visual_style: str) -> dict:
    """Load the analysis rules + style suffix for a non-photo --visual-style.
    Only BRAND_COLORS (for --flat-color) comes from image_prompt_style.md;
    everything else here is illustration-specific."""
    if visual_style not in VISUAL_STYLES or VISUAL_STYLES[visual_style] is None:
        raise GenerationError(f"'{visual_style}' no es un estilo de ilustración válido.")
    if not ILLUSTRATION_STYLE_PATH.exists():
        raise GenerationError(f"No existe el archivo de estilo: {ILLUSTRATION_STYLE_PATH}")
    text = ILLUSTRATION_STYLE_PATH.read_text(encoding="utf-8")
    analysis_block_name = ILLUSTRATION_ANALYSIS_BLOCKS[visual_style]
    analysis_rules = _extract_marked_block(text, analysis_block_name, ILLUSTRATION_STYLE_PATH)
    style_block_name = VISUAL_STYLES[visual_style]
    style_suffix = _extract_marked_block(text, style_block_name, ILLUSTRATION_STYLE_PATH)
    return {"analysis_rules": analysis_rules, "style_suffix": style_suffix}


ANALYSIS_SYSTEM_PROMPT = """Eres un director de arte para una marca de sanación \
familiar y constelaciones sistémicas en Instagram. Vas a leer el copy de un post \
ya aprobado, escrito en español, y vas a devolver EXCLUSIVAMENTE un objeto JSON \
(sin markdown, sin explicación) con esta forma exacta:

{
  "emotion_es": "<la emoción central del copy, en español, 1-3 palabras>",
  "emotion_en": "<esa misma emoción, en inglés, 1-2 palabras>",
  "theme_en": "<el tema/situación del copy en una frase breve, en inglés>",
  "visual_concept_en": "<una escena fotográfica concreta que represente esa \
emoción y ese tema, en inglés, 2-3 frases, SIN personas con rostro reconocible \
y SIN texto en la imagen>"
}

__ANALYSIS_RULES__

Copy del post:
---
__COPY_TEXT__
---
"""


class GenerationError(RuntimeError):
    pass


RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _post_with_retry(url: str, api_key: str, payload: dict, timeout: float, attempts: int = 4) -> requests.Response:
    """POST to a Gemini endpoint, retrying transient failures (503 high-demand,
    429 rate limit, network hiccups) with exponential backoff. A 429 caused by
    an exhausted daily/free-tier quota also carries a short `retryDelay` in the
    error body, so it is retried too rather than treated as permanent."""
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            resp = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            resp = None
        if resp is not None and resp.status_code not in RETRYABLE_STATUSES:
            return resp
        if attempt == attempts - 1:
            if resp is not None:
                return resp
            raise last_exc
        delay = 2 * (2 ** attempt)
        print(f"  (intento {attempt + 1}/{attempts} falló, reintentando en {delay}s...)")
        time.sleep(delay)
    raise AssertionError("unreachable")


def read_copy_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        if docx is None:
            raise GenerationError(
                "python-docx no está instalado. Instala con: pip install python-docx"
            )
        document = docx.Document(str(path))
        paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
    elif path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8-sig")
    else:
        raise GenerationError(
            f"Formato no soportado: {path.suffix}. Usa un archivo .docx o .txt"
        )
    text = text.strip()
    if not text:
        raise GenerationError(f"El archivo {path} está vacío o no se pudo leer texto.")
    return text


def ensure_gemini_api_key() -> str:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key

    print("No se encontró GEMINI_API_KEY en el entorno ni en .env.")
    api_key = getpass.getpass(
        "Pega tu API key de Gemini (no se mostrará en pantalla): "
    ).strip()
    if not api_key:
        raise GenerationError("No se ingresó ninguna API key. Abortando.")

    save = input(
        f"¿Guardarla en {ENV_PATH.name} para no volver a pedirla? [S/n]: "
    ).strip().lower()
    if save in ("", "s", "si", "sí", "y", "yes"):
        set_key(str(ENV_PATH), "GEMINI_API_KEY", api_key)
        print(f"Guardada en {ENV_PATH} (este archivo está en .gitignore).")
    os.environ["GEMINI_API_KEY"] = api_key
    return api_key


DEFAULT_PROTAGONIST_TEXT = (
    "No specific protagonist identity is required; choose whatever generic "
    "figure(s) best fit the composition and setting."
)


def _protagonist_instruction(protagonist: Optional[str]) -> str:
    if not protagonist:
        return DEFAULT_PROTAGONIST_TEXT
    return (
        f"All figures depicting the protagonist across this carousel must "
        f"consistently read as: {protagonist}. Do not switch gender or "
        f"general appearance between slides."
    )


def _hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))


_SOLID_COLOR_RE = re.compile(
    r"^Solido\s*--\s*(?P<name>.+?)\s*\(#(?P<hex>[0-9A-Fa-f]{6})\)$"
)
_GRADIENT_COLOR_RE = re.compile(
    r"^Degradado\s*--\s*(?P<name1>.+?)\s*\(#(?P<hex1>[0-9A-Fa-f]{6})\)\s+a\s+"
    r"(?P<name2>.+?)\s*\(#(?P<hex2>[0-9A-Fa-f]{6})\)$"
)


def _parse_brand_color(entry: str) -> dict:
    match = _SOLID_COLOR_RE.match(entry)
    if match:
        return {"kind": "solid", "colors": [_hex_to_rgb(match.group("hex"))], "label": entry}
    match = _GRADIENT_COLOR_RE.match(entry)
    if match:
        return {
            "kind": "gradient",
            "colors": [_hex_to_rgb(match.group("hex1")), _hex_to_rgb(match.group("hex2"))],
            "label": entry,
        }
    raise GenerationError(
        f"No se pudo interpretar la entrada de BRAND_COLORS: {entry!r}. Formato "
        "esperado: 'Solido -- Nombre (#RRGGBB)' o "
        "'Degradado -- Nombre1 (#RRGGBB) a Nombre2 (#RRGGBB)'."
    )


def _resolve_indexed_entry(spec: str, items: list, arg_label: str) -> str:
    """Resolve a CLI value (a 1-based index or a case-insensitive substring)
    to one entry of a numbered reference list -- shared by --flat-color
    (BRAND_COLORS) and --setting (SETTINGS)."""
    spec = spec.strip()
    if spec.isdigit():
        idx = int(spec) - 1
        if not (0 <= idx < len(items)):
            raise GenerationError(
                f"{arg_label} {spec} fuera de rango ({len(items)} entradas disponibles)."
            )
        return items[idx]
    matches = [c for c in items if spec.lower() in c.lower()]
    if not matches:
        raise GenerationError(f"{arg_label} {spec!r} no coincide con ninguna entrada.")
    if len(matches) > 1:
        raise GenerationError(
            f"{arg_label} {spec!r} coincide con varias entradas: {matches}. "
            "Sé más específico o usa el número de índice."
        )
    return matches[0]


def select_brand_color(spec: str, brand_colors: list) -> dict:
    """Resolve --flat-color's value (a 1-based index or a case-insensitive
    substring of the entry name) to a parsed BRAND_COLORS entry."""
    return _parse_brand_color(_resolve_indexed_entry(spec, brand_colors, "--flat-color"))


def select_setting(spec: str, settings: list) -> str:
    """Resolve --setting's value to one exact SETTINGS entry -- pins the same
    room/light source across every photo slide of a carousel instead of
    letting the script rotate one automatically."""
    return _resolve_indexed_entry(spec, settings, "--setting")


def cover_resize(image: "Image.Image", target_size: tuple) -> "Image.Image":
    """Scale image to fully cover target_size (never letterboxed), then
    center-crop the overflow -- used for --source-image, since a real Pexels
    photo's native dimensions rarely match the exact carousel aspect ratio."""
    target_w, target_h = target_size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = round(src_w * scale), round(src_h * scale)
    resized = image.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def render_flat_color_image(color: dict, size: tuple) -> "Image.Image":
    width, height = size
    if color["kind"] == "solid":
        return Image.new("RGB", size, color["colors"][0])
    top, bottom = color["colors"]
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        r = round(top[0] + (bottom[0] - top[0]) * t)
        g = round(top[1] + (bottom[1] - top[1]) * t)
        b = round(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return image


def _extract_json_object(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        raise GenerationError(f"No se pudo interpretar la respuesta de Gemini: {text[:300]}")
    return json.loads(match.group(0))


def _run_emotion_analysis(rules: str, copy_text: str, api_key: str) -> dict:
    prompt = (
        ANALYSIS_SYSTEM_PROMPT.replace("__ANALYSIS_RULES__", rules)
        .replace("__COPY_TEXT__", copy_text)
    )
    url = f"{GEMINI_API_BASE}/{TEXT_MODEL}:generateContent"
    resp = _post_with_retry(
        url, api_key, {"contents": [{"parts": [{"text": prompt}]}]}, timeout=60
    )
    if resp.status_code >= 400:
        raise GenerationError(f"Gemini (análisis) HTTP {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise GenerationError(f"Respuesta de análisis inesperada: {data}") from e

    analysis = _extract_json_object(raw_text)
    required = {"emotion_es", "emotion_en", "theme_en", "visual_concept_en"}
    missing = required - analysis.keys()
    if missing:
        raise GenerationError(f"Faltan campos en el análisis de Gemini: {missing}")
    return analysis


def analyze_copy(
    copy_text: str,
    api_key: str,
    style: dict,
    archetype: str,
    camera_angle: str,
    setting: str,
    protagonist: Optional[str] = None,
) -> dict:
    rules = (
        style["analysis_rules"]
        .replace("__COMPOSITION_ARCHETYPE__", archetype)
        .replace("__CAMERA_ANGLE__", camera_angle)
        .replace("__SETTING__", setting)
        .replace("__PROTAGONIST__", _protagonist_instruction(protagonist))
    )
    analysis = _run_emotion_analysis(rules, copy_text, api_key)
    analysis["composition_archetype"] = archetype
    analysis["camera_angle"] = camera_angle
    analysis["setting"] = setting
    return analysis


def analyze_copy_illustration(
    copy_text: str,
    api_key: str,
    illustration_style: dict,
    protagonist: Optional[str] = None,
) -> dict:
    rules = illustration_style["analysis_rules"].replace(
        "__PROTAGONIST__", _protagonist_instruction(protagonist)
    )
    return _run_emotion_analysis(rules, copy_text, api_key)


def build_image_prompt(analysis: dict, style: dict, aspect_ratio: str) -> str:
    return (
        f"{analysis['visual_concept_en']} "
        f"Central emotional tone: {analysis['emotion_en']} "
        f"({analysis['theme_en']}). "
        f"{style['brand_style']} "
        f"{ASPECT_RATIO_SPECS[aspect_ratio]['prompt_text']}"
    )


def build_image_prompt_illustration(analysis: dict, illustration_style: dict, aspect_ratio: str) -> str:
    return (
        f"{analysis['visual_concept_en']} "
        f"Central emotional tone: {analysis['emotion_en']} "
        f"({analysis['theme_en']}). "
        f"{illustration_style['style_suffix']} "
        f"{ASPECT_RATIO_SPECS[aspect_ratio]['prompt_text']}"
    )


def generate_image(prompt: str, api_key: str, aspect_ratio: str) -> bytes:
    url = f"{GEMINI_API_BASE}/{IMAGE_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"imageConfig": {"aspectRatio": aspect_ratio}},
    }
    resp = _post_with_retry(url, api_key, payload, timeout=180)
    if resp.status_code >= 400:
        raise GenerationError(
            f"Gemini (imagen, modelo={IMAGE_MODEL}) HTTP {resp.status_code}: "
            f"{resp.text[:500]}\nSi el modelo no existe, prueba fijando la "
            "variable de entorno GEMINI_IMAGE_MODEL a un modelo de imagen "
            "vigente en tu cuenta."
        )
    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as e:
        raise GenerationError(f"Respuesta de imagen inesperada: {data}") from e

    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    raise GenerationError(f"Gemini no devolvió datos de imagen: {data}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("copy_file", help="Ruta al archivo .docx o .txt con el copy aprobado")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f'Carpeta de salida (default: "{DEFAULT_OUTPUT_DIR}")',
    )
    parser.add_argument(
        "--aspect",
        default=DEFAULT_ASPECT_RATIO,
        choices=sorted(ASPECT_RATIO_SPECS),
        help=f"Aspect ratio de salida (default: {DEFAULT_ASPECT_RATIO}). "
        "9:16 para Stories, 1:1 para cuadrado.",
    )
    parser.add_argument(
        "--protagonist",
        default=None,
        help="Descripción fija del protagonista (ej. 'a woman in her 30s'), "
        "para mantener a la misma persona consistente entre varias slides de "
        "un mismo carrusel. Sin esta opción, cada llamada elige libremente.",
    )
    parser.add_argument(
        "--flat-color",
        default=None,
        metavar="INDICE_O_NOMBRE",
        help="Salta Gemini por completo (gratis, instantáneo) y genera un "
        "fondo sólido o degradado a partir de BRAND_COLORS en "
        "image_prompt_style.md -- índice numérico (1, 2, ...) o texto "
        "parcial del nombre. Para slides tipo 'quote card' sin foto.",
    )
    parser.add_argument(
        "--visual-style",
        default=DEFAULT_VISUAL_STYLE,
        choices=sorted(VISUAL_STYLES),
        help=f"Estilo visual (default: {DEFAULT_VISUAL_STYLE}, sin cambios de "
        "comportamiento). minimal/book/cartoon/storytelling usan "
        "illustration_style.md en vez de image_prompt_style.md.",
    )
    parser.add_argument(
        "--setting",
        default=None,
        metavar="INDICE_O_NOMBRE",
        help="Solo con --visual-style photo: fija un SETTINGS de "
        "image_prompt_style.md en vez de rotarlo, para mantener el mismo "
        "ambiente/luz en todas las slides de foto de un carrusel. "
        "Composición y ángulo de cámara siguen rotando libres.",
    )
    parser.add_argument(
        "--source-image",
        default=None,
        metavar="RUTA",
        help="Salta Gemini por completo: abre esta imagen ya existente (ej. "
        "descargada de Pexels), la ajusta al --aspect pedido (cover + recorte "
        "centrado) y le quema el titular encima. La zona del titular siempre "
        "se resuelve con el veto de OpenCV (no hay composición pedida que "
        "garantice nada de antemano). Incompatible con --flat-color y con "
        "cualquier llamada a Gemini.",
    )
    parser.add_argument(
        "--headline-main",
        default=None,
        help="Titular corto a quemar sobre la imagen con Pillow (Poppins "
        "Bold, mismo estilo que canva_title_style.md y que los reels). Sin "
        "esta opción, comportamiento idéntico al de antes: ninguna imagen "
        "lleva texto.",
    )
    parser.add_argument(
        "--headline-accent",
        default=None,
        help="Línea de cierre opcional, más corta, debajo de --headline-main "
        "(Playfair Display italic dorado pálido). Requiere --headline-main.",
    )
    parser.add_argument(
        "--headline-extra",
        default=None,
        help="Tercer bloque opcional, más corto todavía, debajo de "
        "--headline-accent (Poppins SemiBold dorado pálido). Solo para el "
        "hook de carrusel-constelaciones. Requiere --headline-main. "
        "Incompatible con --body-text.",
    )
    parser.add_argument(
        "--body-text",
        default=None,
        help="Párrafo largo (2-4 oraciones) a quemar en cian #22D3EE Poppins "
        "Bold, con un degradado oscuro de fondo para legibilidad (mismos "
        "stops que el degradado de reels). Solo para slides de contenido de "
        "carrusel-constelaciones. Requiere --headline-main. Incompatible con "
        "--headline-extra.",
    )
    args = parser.parse_args()
    if args.headline_accent and not args.headline_main:
        print("--headline-accent requiere --headline-main.", file=sys.stderr)
        return 1
    if args.headline_extra and not args.headline_main:
        print("--headline-extra requiere --headline-main.", file=sys.stderr)
        return 1
    if args.body_text and not args.headline_main:
        print("--body-text requiere --headline-main.", file=sys.stderr)
        return 1
    if args.headline_extra and args.body_text:
        print("--headline-extra y --body-text son incompatibles entre si.", file=sys.stderr)
        return 1
    if args.source_image and args.flat_color:
        print("--source-image y --flat-color son incompatibles entre si.", file=sys.stderr)
        return 1

    copy_path = Path(args.copy_file)
    if not copy_path.exists():
        print(f"No existe el archivo: {copy_path}", file=sys.stderr)
        return 1

    aspect_ratio = args.aspect
    output_size = ASPECT_RATIO_SPECS[aspect_ratio]["size"]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{copy_path.stem}.png"

    try:
        style = load_style_guide()

        if args.flat_color:
            color = select_brand_color(args.flat_color, style["brand_colors"])
            print(f"Generando fondo de color (sin Gemini, sin API key): {color['label']}")
            image = render_flat_color_image(color, output_size)
            if args.headline_main:
                image = render_headline(
                    image, "center", args.headline_main, args.headline_accent,
                    args.headline_extra, args.body_text,
                )
            image.save(out_path, "PNG")
            print(f"Imagen guardada en: {out_path} ({output_size[0]}x{output_size[1]})")
            return 0

        if args.source_image:
            src_path = Path(args.source_image)
            if not src_path.exists():
                raise GenerationError(f"No existe --source-image: {src_path}")
            print(f"Usando imagen existente (sin Gemini, sin API key): {src_path.name}")
            image = Image.open(src_path).convert("RGB")
            image = cover_resize(image, output_size)
            if args.headline_main:
                band_fraction = compute_band_fraction(
                    output_size[0], output_size[1], args.headline_main,
                    args.headline_accent, args.headline_extra, args.body_text,
                )
                zone = resolve_headline_zone("auto", image, band_fraction)
                print(f"  Zona del titular: {zone}")
                image = render_headline(
                    image, zone, args.headline_main, args.headline_accent,
                    args.headline_extra, args.body_text, band_fraction,
                )
            image.save(out_path, "PNG")
            print(f"Imagen guardada en: {out_path} ({output_size[0]}x{output_size[1]})")
            return 0

        api_key = ensure_gemini_api_key()

        print(f"Leyendo copy: {copy_path.name}")
        copy_text = read_copy_text(copy_path)

        headline_zone = "top"  # default for illustration/mezcla-ilustracion (no protagonist)
        if args.visual_style == "photo":
            state = _load_state()
            archetype = _pick_avoiding_recent(style["archetypes"], "composition", state)
            if args.setting:
                setting = select_setting(args.setting, style["settings"])
                state["setting"] = ([setting] + state.get("setting", []))[:ROTATION_HISTORY]
            else:
                setting = _pick_avoiding_recent(style["settings"], "setting", state)
            camera_angle = _pick_avoiding_recent(style["camera_angles"], "camera_angle", state)
            archetype_index = style["archetypes"].index(archetype)
            if archetype_index in MULTI_PERSON_ARCHETYPE_INDICES:
                headline_zone = "auto"
            else:
                headline_zone = CAMERA_ANGLE_SAFE_ZONES[style["camera_angles"].index(camera_angle)]

            print("Analizando emoción central y tema con Gemini...")
            analysis = analyze_copy(
                copy_text, api_key, style, archetype, camera_angle, setting, args.protagonist
            )
            print(f"  Emoción central: {analysis['emotion_es']} ({analysis['emotion_en']})")
            print(f"  Tema: {analysis['theme_en']}")
            print(f"  Ubicación elegida: {analysis['setting']}")
            print(f"  Composición elegida: {analysis['composition_archetype']}")
            print(f"  Ángulo de cámara elegido: {analysis['camera_angle']}")

            image_prompt = build_image_prompt(analysis, style, aspect_ratio)
        else:
            illustration_style = load_illustration_style(args.visual_style)
            if args.visual_style != "mezcla-ilustracion":
                headline_zone = "auto"  # no archetype/angle system for the 4 character styles
            print(f"Analizando emoción central y tema con Gemini (estilo: {args.visual_style})...")
            analysis = analyze_copy_illustration(
                copy_text, api_key, illustration_style, args.protagonist
            )
            print(f"  Emoción central: {analysis['emotion_es']} ({analysis['emotion_en']})")
            print(f"  Tema: {analysis['theme_en']}")

            image_prompt = build_image_prompt_illustration(analysis, illustration_style, aspect_ratio)
            state = None

        print(f"Prompt de imagen:\n  {image_prompt}\n")

        print(f"Generando imagen con {IMAGE_MODEL} (aspect {aspect_ratio})...")
        image_bytes = generate_image(image_prompt, api_key, aspect_ratio)

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        if image.size != output_size:
            image = image.resize(output_size, Image.LANCZOS)

        if args.headline_main:
            band_fraction = compute_band_fraction(
                output_size[0], output_size[1], args.headline_main,
                args.headline_accent, args.headline_extra, args.body_text,
            )
            zone = resolve_headline_zone(headline_zone, image, band_fraction)
            print(f"  Zona del titular: {zone}")
            image = render_headline(
                image, zone, args.headline_main, args.headline_accent,
                args.headline_extra, args.body_text, band_fraction,
            )

        image.save(out_path, "PNG")
        print(f"Imagen guardada en: {out_path} ({output_size[0]}x{output_size[1]})")

        if state is not None:
            _save_state(state)
    except GenerationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
