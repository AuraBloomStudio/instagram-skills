#!/usr/bin/env python3
"""Render the final Instagram Reel for a Constelaciones Familiares reel using
the JSON2Video API (https://json2video.com).

Flow:
  1. Locate scripts/output_clips/<slug>/orden_edicion.txt (written by
     seleccion-clips-pexels) and scripts/output_audio/<slug>/narracion.mp3
     (written by narracion-voz-gemini). The two skills sometimes save under a
     slightly different slug spelling (hyphens vs underscores) for the same
     reel, so both folders are resolved independently with a fallback.
  2. Parse orden_edicion.txt into ordered moments, each with its guion line
     and 1-3 candidate clip files. Per moment, pick the first video candidate
     (falling back to the first photo candidate if the moment has no video).
  3. Split the narration's total duration across moments proportionally to
     each moment's word count (a reasonable proxy for how long that beat
     takes to narrate at a roughly constant speaking pace).
  4. Upload the narration, the selected clips, and (optionally) a background
     music file to JSON2Video's media library (every asset referenced in a
     JSON2Video movie must be a public URL, never a local path).
  5. Submit the movie JSON (one scene per moment, narration + optional music
     + native auto-generated subtitles as movie-level elements, vertical
     "instagram-story" resolution) and poll until it renders. Each scene
     carries a full-frame dark gradient scrim (readable text top and
     bottom) and a 0.4s crossfade into the next. If --hook-main/--hook-accent
     are given, a leading hook scene (big two-font headline over the first
     clip) plays before the narration audio starts.
  6. Download the final MP4 to scripts/output_reels/<slug>/reel_final.mp4 and
     delete the uploaded source assets from JSON2Video's media library (its
     free tier only grants ~50MB of storage, so cleaning up after every
     render matters).

JSON2VIDEO_API_KEY is never hardcoded. If it is not already set as an
environment variable, this script prompts for it (input is masked) and
offers to save it to the local .env file, which is already gitignored --
same pattern as generate_post_image.py and generate_reel_narration.py.

Usage:
  python scripts/render_reel_json2video.py <reel_slug> [--music PATH] [--quality high|medium|low] [--hook-main "TEXTO"] [--hook-accent "texto"]
"""
from __future__ import annotations

import argparse
import getpass
import html
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv, set_key

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

J2V_API_BASE = "https://api.json2video.com/v2"

DEFAULT_CLIPS_DIR = REPO_ROOT / "scripts" / "output_clips"
DEFAULT_AUDIO_DIR = REPO_ROOT / "scripts" / "output_audio"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "scripts" / "output_reels"

# Vertical 9:16 preset -> 1080x1920, confirmed against a real render.
RESOLUTION = "instagram-story"
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

# "Dorado" from the brand's BRAND_COLORS palette (scripts/references/
# image_prompt_style.md). Both word-color (the currently-spoken word) and
# line-color (the rest of the line) are set to the SAME gold on purpose --
# an earlier version used white for the line and gold only for the active
# word, but the user wanted one solid color throughout, not a white/gold
# contrast. "classic-progressive" still reveals word by word, it just no
# longer changes color when it does.
SUBTITLE_WORD_COLOR = "#B8985E"
SUBTITLE_LINE_COLOR = SUBTITLE_WORD_COLOR
# Custom pixel position instead of a preset. The "mid-bottom-center" preset
# (ASS \pos landed at y=1440, 25% up from the bottom) cleared Instagram's UI
# but still read as "stuck to the bottom" -- confirmed too low by the user
# after watching the render. y=1150 (~60% down the 1920 canvas) sits clearly
# in the lower-middle zone: below the top third (640px) but well above both
# the old 1440 position and Instagram's bottom UI band. x is the canvas
# horizontal center; subtitles use the same custom x/y anchor semantics as
# the html/image/video elements (center-anchored, confirmed via the ASS
# \pos() override on a real render).
SUBTITLE_X = CANVAS_WIDTH // 2
SUBTITLE_Y = 1150

# Dark gradient covering the FULL frame top-to-bottom (not just the subtitle
# band) so both the hook text (near the top) and the narration subtitles
# (lower-middle) stay readable over any footage. Darkest at the very top and
# very bottom, lightest in the middle so the footage itself still reads
# clearly where there's no text. Confirmed by a real render that this MUST
# be a per-scene element (not a movie-level element with duration -2, which
# silently failed to render at all) with an explicit numeric duration
# matching that scene's own duration.
#
# Alpha values raised a second time -- a first "full coverage" version (0.5
# top / 0.9 bottom, tapering to ~0.1 by 15%/30%) still read as basically
# unfiltered at the very top against a bright window in a real hook frame:
# the darkening ramped down to near-zero too fast to register visually.
# Confirmed the CURRENT stronger formula (0.75 top / 0.95 bottom, still
# tapering to ~0.18 mid-frame) visibly darkens even a light-gray test
# background at both edges via a real render before shipping it -- always
# re-check with an extracted frame against a BRIGHT scene when touching
# these numbers, pixel-sampling alone caught a false negative here.
GRADIENT_HTML_TEMPLATE = (
    "<div style='width:{width}px;height:{height}px;"
    "background:linear-gradient(to bottom, "
    "rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.45) 12%, rgba(0,0,0,0.18) 25%, "
    "rgba(0,0,0,0.18) 55%, rgba(0,0,0,0.45) 75%, rgba(0,0,0,0.75) 88%, "
    "rgba(0,0,0,0.95) 100%)'></div>"
)

# --- Hook text (shown before the narration starts) -------------------------
# Two font families mixed in one overlay: a bold sans headline word/phrase
# (brand-neutral, high-impact) plus an italic serif accent phrase in the
# brand gold, confirmed rendering correctly together via a real render
# (Poppins + Playfair Display, both resolved as real Google Fonts by
# JSON2Video's html element with no extra @import needed).
# Main phrase in the brand's cream/beige (from BRAND_COLORS in
# image_prompt_style.md: "Degradado -- Crema/beige (#E3D5BF) a Dorado
# (#B8985E)") instead of pure white -- flat white read too plain/generic
# against the warm footage.
HOOK_DURATION_S = 2.0
HOOK_MAIN_FONT = "Poppins"
HOOK_MAIN_WEIGHT = 800
HOOK_MAIN_COLOR = "#E3D5BF"
HOOK_MAIN_SIZE = 88
HOOK_ACCENT_FONT = "Playfair Display"
HOOK_ACCENT_COLOR = SUBTITLE_WORD_COLOR
HOOK_ACCENT_SIZE = 100
HOOK_Y = 650  # upper-middle zone: clear of the top edge, far above SUBTITLE_Y
HOOK_BOX_HEIGHT = 500
HOOK_HTML_TEMPLATE = (
    "<div style='width:{width}px;text-align:center;line-height:1.15;"
    "font-family:sans-serif;'>"
    "<span style='font-family:\"{main_font}\";font-weight:{main_weight};"
    "color:{main_color};font-size:{main_size}px;'>{main_text}</span><br/>"
    "<span style='font-family:\"{accent_font}\";font-style:italic;"
    "font-weight:600;color:{accent_color};font-size:{accent_size}px;'>"
    "{accent_text}</span>"
    "</div>"
)

# "Fundido cruzado" between every pair of adjacent scenes (hook->moment 1,
# and moment N -> moment N+1). Confirmed by a real render that a scene's
# `transition` overlaps with the PREVIOUS scene and shortens the movie's
# total duration by the transition's own duration (2 scenes of 2.2s each +
# one 0.4s transition rendered as 4.0s, not 4.4s) -- compensated in
# compute_target_durations's caller so the final render still matches the
# narration length.
#
# TRANSITION_DURATION_S IS CAPPED AT ITS CURRENT VALUE ON PURPOSE. Exhaustive
# testing (9+ real test renders) found that whenever the movie has
# movie-level audio + subtitles elements (i.e. always, in this script), the
# duration-shortening overlap ONLY happens reliably at exactly 0.4s with
# style "fade": every other combination tried -- 0.5s, 0.6s, 0.7s (all
# styles), style "circleopen" at the same safe 0.4s, an explicit scene-level
# `duration` key, a full-height gradient instead of a partial one, a custom
# vs. preset subtitle position, "quality": "high" instead of "low", 8 short
# scenes instead of 2, and a 26s real-audio/real-clip render instead of a
# 6s snippet -- all silently reverted to a hard cut (0 transition) instead
# of erroring, confirmed via exact duration mismatches every time. Only the
# full real production render (8 scenes, full ~67s narration, 0.4s/fade, no
# explicit scene duration) has ever shown the expected overlap. Raise this
# constant only after a real test render confirms the resulting duration
# via the aggregate-duration-match technique above -- do not trust a
# "successful" JSON submission alone, JSON2Video accepts and silently
# no-ops an unsupported duration/style combination here.
TRANSITION_STYLE = "fade"
TRANSITION_DURATION_S = 0.4
# A transition never eats more than this fraction of the shorter of its two
# adjacent scenes, so a very short moment never gets swallowed by its own
# crossfade.
MAX_TRANSITION_FRACTION_OF_SCENE = 0.4

# "Volumen bajo" background music under a voice track. JSON2Video's own docs
# suggest ~0.2 as a usual value for background music under narration; this
# stays a notch under that.
BACKGROUND_MUSIC_VOLUME = 0.15
BACKGROUND_MUSIC_FADE_OUT_S = 2.0

# Every moment gets at least this many seconds on screen, even if its guion
# line is very short -- keeps a single-word beat from flashing by unusably
# fast before the proportional split kicks in.
MIN_MOMENT_DURATION_S = 1.2

POLL_INTERVAL_S = 7
POLL_TIMEOUT_S = 30 * 60

CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}

VIDEO_EXTENSIONS = {".mp4", ".mov"}
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class RenderError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# API key handling (same pattern as generate_reel_narration.py)
# ---------------------------------------------------------------------------


def ensure_api_key() -> str:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("JSON2VIDEO_API_KEY")
    if api_key:
        return api_key

    print("No se encontro JSON2VIDEO_API_KEY en el entorno ni en .env.")
    api_key = getpass.getpass(
        "Pega tu API key de JSON2Video (no se mostrara en pantalla): "
    ).strip()
    if not api_key:
        raise RenderError("No se ingreso ninguna API key. Abortando.")

    save = input(
        f"¿Guardarla en {ENV_PATH.name} para no volver a pedirla? [S/n]: "
    ).strip().lower()
    if save in ("", "s", "si", "sí", "y", "yes"):
        set_key(str(ENV_PATH), "JSON2VIDEO_API_KEY", api_key)
        print(f"Guardada en {ENV_PATH} (este archivo esta en .gitignore).")
    os.environ["JSON2VIDEO_API_KEY"] = api_key
    return api_key


# ---------------------------------------------------------------------------
# Slug resolution -- seleccion-clips-pexels and narracion-voz-gemini have
# been observed to save the same reel under different separator styles
# (crei_que_solo_tenia_mal_caracter vs crei-que-solo-tenia-mal-caracter).
# ---------------------------------------------------------------------------


def resolve_slug_dir(base_dir: Path, slug: str, what: str) -> Path:
    candidates = [slug, slug.replace("-", "_"), slug.replace("_", "-")]
    seen = []
    for c in candidates:
        if c in seen:
            continue
        seen.append(c)
        p = base_dir / c
        if p.is_dir():
            return p

    available = sorted(p.name for p in base_dir.glob("*") if p.is_dir())
    hint = f" Carpetas disponibles en {base_dir}: {', '.join(available)}" if available else ""
    raise RenderError(
        f"No se encontro carpeta de {what} para '{slug}' (probado: {', '.join(seen)})."
        f"{hint}"
    )


# ---------------------------------------------------------------------------
# orden_edicion.txt parsing
# ---------------------------------------------------------------------------


@dataclass
class Moment:
    order: int
    label: str
    guion_line: str
    candidate_files: list = field(default_factory=list)
    notes: list = field(default_factory=list)


_MOMENT_HEADER_RE = re.compile(r"^Momento\s+(\d+)\s*--\s*(.+)$", re.MULTILINE)
_GUION_LINE_RE = re.compile(r"Línea del guion:\s*(.+)")
_CANDIDATE_RE = re.compile(
    r"^\s*(\S+\.(?:mp4|mov|jpg|jpeg|png))\s+--\s+autor:", re.MULTILINE
)
_NOTE_RE = re.compile(r"^\s*[⚠ℹ]\s*(.+)$", re.MULTILINE)


def parse_orden_edicion(path: Path) -> list:
    text = path.read_text(encoding="utf-8-sig")
    headers = list(_MOMENT_HEADER_RE.finditer(text))
    if not headers:
        raise RenderError(f"No se encontro ningun 'Momento N -- label' en {path}")

    moments = []
    for i, m in enumerate(headers):
        order = int(m.group(1))
        label = m.group(2).strip()
        block_start = m.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[block_start:block_end]

        guion_match = _GUION_LINE_RE.search(block)
        guion_line = guion_match.group(1).strip() if guion_match else ""

        candidate_files = [cm.group(1) for cm in _CANDIDATE_RE.finditer(block)]
        notes = [nm.group(1).strip() for nm in _NOTE_RE.finditer(block)]

        moments.append(
            Moment(order=order, label=label, guion_line=guion_line,
                   candidate_files=candidate_files, notes=notes)
        )

    moments.sort(key=lambda mm: mm.order)
    return moments


def select_clip_for_moment(moment: Moment, clips_dir: Path) -> tuple:
    """Return (path, is_photo) for the first video candidate, falling back to
    the first photo candidate if the moment has no video."""
    if not moment.candidate_files:
        raise RenderError(f"Momento {moment.order:02d} ({moment.label}) no tiene candidatos en orden_edicion.txt")

    video_candidates = [f for f in moment.candidate_files if Path(f).suffix.lower() in VIDEO_EXTENSIONS]
    chosen_name = video_candidates[0] if video_candidates else moment.candidate_files[0]
    path = clips_dir / chosen_name
    if not path.exists():
        raise RenderError(f"El clip elegido para el momento {moment.order:02d} no existe: {path}")
    is_photo = path.suffix.lower() in PHOTO_EXTENSIONS
    return path, is_photo


# ---------------------------------------------------------------------------
# Duration helpers
# ---------------------------------------------------------------------------


def ffprobe_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RenderError(f"ffprobe fallo en {path}:\n{result.stderr[-500:]}")
    return float(result.stdout.strip())


def compute_target_durations(moments: list, total_duration: float) -> list:
    """Split total_duration across moments proportionally to each moment's
    guion_line word count, with a floor of MIN_MOMENT_DURATION_S per moment.
    The last moment absorbs rounding so the sum matches total_duration
    exactly (JSON2Video scenes are placed back to back on the timeline)."""
    word_counts = [max(len(m.guion_line.split()), 1) for m in moments]
    total_words = sum(word_counts)

    raw = [total_duration * wc / total_words for wc in word_counts]
    floored = [max(d, MIN_MOMENT_DURATION_S) for d in raw]

    # Floors can push the sum above total_duration when moments are many and
    # short; rescale the non-floored (still proportional) durations down to
    # compensate, floors themselves are left alone as a hard minimum.
    floor_hit = [d <= MIN_MOMENT_DURATION_S for d in raw]
    floor_sum = sum(d for d, hit in zip(floored, floor_hit) if hit)
    remaining_budget = max(total_duration - floor_sum, 0.0)
    remaining_raw_sum = sum(d for d, hit in zip(raw, floor_hit) if not hit) or 1.0

    scaled = []
    for d, hit in zip(raw, floor_hit):
        if hit:
            scaled.append(MIN_MOMENT_DURATION_S)
        else:
            scaled.append(d / remaining_raw_sum * remaining_budget)

    # Fix rounding drift on the last moment so scenes sum exactly to the
    # narration length.
    drift = total_duration - sum(scaled)
    scaled[-1] = max(scaled[-1] + drift, MIN_MOMENT_DURATION_S)

    return [round(d, 2) for d in scaled]


def compute_transition_durations(targets: list) -> list:
    """One entry per scene boundary (len(targets) - 1). Each transition is
    clamped to MAX_TRANSITION_FRACTION_OF_SCENE of the shorter of its two
    adjacent scenes, so a short moment's crossfade never eats more than a
    sane slice of its own screen time."""
    durations = []
    for i in range(1, len(targets)):
        cap = MAX_TRANSITION_FRACTION_OF_SCENE * min(targets[i - 1], targets[i])
        durations.append(round(min(TRANSITION_DURATION_S, cap), 2))
    return durations


def compensate_for_transitions(targets: list, transition_durations: list) -> list:
    """A JSON2Video crossfade overlaps two adjacent scenes and shortens the
    movie's total rendered duration by the transition's own length (confirmed
    against a real render: two 2.2s scenes + one 0.4s transition rendered as
    4.0s, not 4.4s). Scale every target up so the final render still lands on
    the narration's actual length despite that overlap."""
    total = sum(targets)
    overlap_total = sum(transition_durations)
    if total <= 0 or overlap_total <= 0:
        return targets
    scale = (total + overlap_total) / total
    scaled = [t * scale for t in targets]
    drift = (total + overlap_total) - sum(scaled)
    scaled[-1] += drift
    return [round(d, 2) for d in scaled]


# ---------------------------------------------------------------------------
# JSON2Video media upload (POST /media/file -> presigned S3 URL -> PUT bytes)
# ---------------------------------------------------------------------------


def guess_content_type(path: Path) -> str:
    ctype = CONTENT_TYPES.get(path.suffix.lower())
    if not ctype:
        raise RenderError(f"Extension no soportada para subir a JSON2Video: {path}")
    return ctype


def upload_asset(path: Path, dest_name: str, api_key: str) -> str:
    """Upload one local file to JSON2Video's media library and return its
    public URL. Raises on any failure (name collision, expired presigned
    URL, non-2xx S3 response)."""
    content_type = guess_content_type(path)
    size = path.stat().st_size
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    resp = requests.post(
        f"{J2V_API_BASE}/media/file", headers=headers,
        json={"name": dest_name, "contentType": content_type, "size": size},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RenderError(f"JSON2Video media/file (POST) fallo para {dest_name}: HTTP {resp.status_code}: {resp.text[:300]}")
    upload_url = resp.json()["uploadUrl"]

    with open(path, "rb") as f:
        put = requests.put(upload_url, data=f.read(), headers={"Content-Type": content_type}, timeout=120)
    if put.status_code >= 300:
        raise RenderError(f"Subida a S3 fallo para {dest_name}: HTTP {put.status_code}: {put.text[:300]}")

    return upload_url.split("?")[0]


def delete_asset(dest_name: str, api_key: str) -> None:
    """Best-effort cleanup -- never raises, just warns, since a failed
    cleanup should not fail an otherwise-successful render."""
    try:
        r = requests.delete(
            f"{J2V_API_BASE}/media/file",
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            json={"name": dest_name}, timeout=30,
        )
        if r.status_code >= 400:
            print(f"  (aviso: no se pudo borrar '{dest_name}' de JSON2Video: HTTP {r.status_code})")
    except requests.RequestException as e:
        print(f"  (aviso: no se pudo borrar '{dest_name}' de JSON2Video: {e})")


# ---------------------------------------------------------------------------
# Movie JSON assembly
# ---------------------------------------------------------------------------


def build_gradient_element(target_duration: float) -> dict:
    """Full-frame top-to-bottom scrim -- see GRADIENT_HTML_TEMPLATE for why
    this has to be a per-scene element with an explicit numeric duration
    (a movie-level element with duration -2 silently failed to render at
    all, confirmed against a real render)."""
    return {
        "type": "html",
        "html": GRADIENT_HTML_TEMPLATE.format(width=CANVAS_WIDTH, height=CANVAS_HEIGHT),
        "position": "custom",
        "x": 0,
        "y": 0,
        "width": CANVAS_WIDTH,
        "height": CANVAS_HEIGHT,
        "z-index": 5,
        "duration": target_duration,
        "wait": 0.2,
    }


def build_hook_html(main_text: str, accent_text: str) -> dict:
    markup = HOOK_HTML_TEMPLATE.format(
        width=CANVAS_WIDTH,
        main_font=HOOK_MAIN_FONT, main_weight=HOOK_MAIN_WEIGHT,
        main_color=HOOK_MAIN_COLOR, main_size=HOOK_MAIN_SIZE,
        main_text=html.escape(main_text),
        accent_font=HOOK_ACCENT_FONT, accent_color=HOOK_ACCENT_COLOR,
        accent_size=HOOK_ACCENT_SIZE, accent_text=html.escape(accent_text),
    )
    return {
        "type": "html",
        "html": markup,
        "position": "custom",
        "x": 0,
        "y": HOOK_Y,
        "width": CANVAS_WIDTH,
        "height": HOOK_BOX_HEIGHT,
        "z-index": 10,
        "duration": HOOK_DURATION_S,
        "wait": 0.3,
    }


def build_hook_scene(clip_url: str, clip_duration: Optional[float],
                      main_text: str, accent_text: str) -> dict:
    """Leading scene shown before the narration starts: the reel's first
    clip (muted, reused -- already being uploaded for moment 1 anyway) with
    the gradient scrim and the big two-font hook headline on top. No
    transition in (it's the first scene in the movie)."""
    loop = 1
    if clip_duration and clip_duration > 0 and clip_duration < HOOK_DURATION_S:
        loop = math.ceil(HOOK_DURATION_S / clip_duration)
    video_element = {
        "type": "video",
        "src": clip_url,
        "duration": HOOK_DURATION_S,
        "loop": loop,
        "resize": "cover",
        "muted": True,
    }
    return {
        "elements": [
            video_element,
            build_gradient_element(HOOK_DURATION_S),
            build_hook_html(main_text, accent_text),
        ]
    }


def build_scene(moment: Moment, clip_url: str, is_photo: bool, target_duration: float,
                 clip_duration: Optional[float], pan_index: int,
                 transition_duration: Optional[float]) -> dict:
    if is_photo:
        pan = "right" if pan_index % 2 == 0 else "left"
        element = {
            "type": "image",
            "src": clip_url,
            "duration": target_duration,
            "resize": "cover",
            "zoom": 2,
            "pan": pan,
        }
    else:
        loop = 1
        if clip_duration and clip_duration > 0 and clip_duration < target_duration:
            loop = math.ceil(target_duration / clip_duration)
        element = {
            "type": "video",
            "src": clip_url,
            "duration": target_duration,
            "loop": loop,
            "resize": "cover",
            "muted": True,
        }
    scene = {"elements": [element, build_gradient_element(target_duration)]}
    # A transition sits on the INCOMING scene and overlaps with the tail of
    # the previous one -- confirmed against a real render. The caller never
    # passes a duration for the very first scene in the movie (hook, if any,
    # otherwise moment 1) since there is no previous scene to blend from.
    if transition_duration:
        scene["transition"] = {
            "type": "xfade",
            "style": TRANSITION_STYLE,
            "duration": transition_duration,
        }
    return scene


def build_movie(scenes: list, narration_url: str, narration_start: float,
                 music_url: Optional[str], quality: str) -> dict:
    elements = [
        {"type": "audio", "src": narration_url, "volume": 1, "start": narration_start},
    ]
    if music_url:
        elements.append({
            "type": "audio",
            "src": music_url,
            "volume": BACKGROUND_MUSIC_VOLUME,
            "loop": -1,
            "duration": -2,
            "fade-out": BACKGROUND_MUSIC_FADE_OUT_S,
        })
    elements.append({
        "type": "subtitles",
        "language": "es",
        "model": "whisper",
        "settings": {
            "style": "classic-progressive",
            "word-color": SUBTITLE_WORD_COLOR,
            "line-color": SUBTITLE_LINE_COLOR,
            "all-caps": False,
            "position": "custom",
            "x": SUBTITLE_X,
            "y": SUBTITLE_Y,
        },
    })
    return {
        "resolution": RESOLUTION,
        "quality": quality,
        "scenes": scenes,
        "elements": elements,
    }


# ---------------------------------------------------------------------------
# Render submission + polling
# ---------------------------------------------------------------------------


def submit_movie(movie: dict, api_key: str) -> str:
    resp = requests.post(
        f"{J2V_API_BASE}/movies",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json=movie, timeout=60,
    )
    if resp.status_code >= 400:
        raise RenderError(f"JSON2Video rechazo el movie JSON: HTTP {resp.status_code}: {resp.text[:1000]}")
    data = resp.json()
    project = data.get("project")
    if not project:
        raise RenderError(f"Respuesta inesperada de POST /movies: {data}")
    return project


def poll_movie(project: str, api_key: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        resp = requests.get(
            f"{J2V_API_BASE}/movies", headers={"x-api-key": api_key},
            params={"project": project}, timeout=30,
        )
        if resp.status_code >= 400:
            raise RenderError(f"JSON2Video status check fallo: HTTP {resp.status_code}: {resp.text[:500]}")
        movie = resp.json().get("movie", {})
        status = movie.get("status")
        print(f"  estado: {status}")
        if status == "done":
            return movie
        if status in ("error", "timeout"):
            raise RenderError(f"El render fallo (status={status}): {movie.get('message')}")
        time.sleep(POLL_INTERVAL_S)
    raise RenderError(f"Se agoto el tiempo de espera ({POLL_TIMEOUT_S}s) esperando el render.")


def download_final(url: str, out_path: Path) -> None:
    r = requests.get(url, timeout=120, stream=True)
    if r.status_code >= 400:
        raise RenderError(f"No se pudo descargar el video final: HTTP {r.status_code}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 256):
            f.write(chunk)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reel_slug", help="Nombre/slug del reel (define que carpetas de origen y de salida usar)")
    parser.add_argument("--music", default=None, help="Ruta a un archivo local de musica de fondo (opcional)")
    parser.add_argument("--quality", default="high", choices=["low", "medium", "high"], help="Calidad de render (default: high)")
    parser.add_argument("--hook-main", default=None, help="Frase principal del gancho (blanco, Poppins bold). Requiere --hook-accent.")
    parser.add_argument("--hook-accent", default=None, help="Frase de acento del gancho (dorado, Playfair Display italic). Requiere --hook-main.")
    parser.add_argument("--clips-dir", default=str(DEFAULT_CLIPS_DIR), help="Carpeta base de clips (default: scripts/output_clips)")
    parser.add_argument("--audio-dir", default=str(DEFAULT_AUDIO_DIR), help="Carpeta base de audio (default: scripts/output_audio)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR), help="Carpeta base de salida (default: scripts/output_reels)")
    args = parser.parse_args()

    if bool(args.hook_main) != bool(args.hook_accent):
        print("Error: --hook-main y --hook-accent van juntos (o ninguno, o los dos).", file=sys.stderr)
        return 1
    has_hook = bool(args.hook_main and args.hook_accent)

    uploaded_names: list = []
    api_key = None

    try:
        api_key = ensure_api_key()

        clips_dir = resolve_slug_dir(Path(args.clips_dir), args.reel_slug, "clips (seleccion-clips-pexels)")
        audio_dir = resolve_slug_dir(Path(args.audio_dir), args.reel_slug, "narracion (narracion-voz-gemini)")

        orden_path = clips_dir / "orden_edicion.txt"
        if not orden_path.exists():
            raise RenderError(f"No existe {orden_path}")
        narration_path = audio_dir / "narracion.mp3"
        if not narration_path.exists():
            raise RenderError(f"No existe {narration_path}")

        print(f"Clips: {clips_dir}")
        print(f"Narracion: {narration_path}")

        moments = parse_orden_edicion(orden_path)
        print(f"{len(moments)} momentos encontrados en orden_edicion.txt")

        selected = []
        for m in moments:
            path, is_photo = select_clip_for_moment(m, clips_dir)
            duration = None if is_photo else ffprobe_duration_seconds(path)
            selected.append((m, path, is_photo, duration))
            flag = " ".join(f"[{n}]" for n in m.notes)
            kind = "foto" if is_photo else "video"
            print(f"  {m.order:02d} {m.label}: {path.name} ({kind}) {flag}")

        narration_duration = ffprobe_duration_seconds(narration_path)
        print(f"Duracion de la narracion: {narration_duration:.1f}s")

        targets = compute_target_durations(moments, narration_duration)
        # Transition caps/compensation need to see the hook's fixed duration
        # too (it's the first scene when present, so it has an outgoing
        # transition into moment 1) even though the hook itself never gets
        # scaled -- only the narration-driven moment durations do.
        boundary_durations = ([HOOK_DURATION_S] if has_hook else []) + targets
        transition_durations = compute_transition_durations(boundary_durations)
        targets = compensate_for_transitions(targets, transition_durations)
        # Transition caps depend on the pre-compensation targets; recompute
        # after scaling in case scaling shifted which scene is the shorter
        # one at each boundary (negligible in practice, but keeps the two
        # lists mutually consistent).
        boundary_durations = ([HOOK_DURATION_S] if has_hook else []) + targets
        transition_durations = compute_transition_durations(boundary_durations)

        expected_total = narration_duration + (HOOK_DURATION_S if has_hook else 0)
        quota_resp = requests.get(f"{J2V_API_BASE}/movies", headers={"x-api-key": api_key}, timeout=30)
        if quota_resp.status_code < 400:
            remaining = quota_resp.json().get("remaining_quota", {}).get("time")
            if remaining is not None:
                print(f"Cuota de render restante en la cuenta de JSON2Video: {remaining}s")
                if remaining < expected_total:
                    print(
                        f"  AVISO: la cuota restante ({remaining}s) es menor que la duracion "
                        f"esperada del reel ({expected_total:.1f}s). El render puede fallar por cuota."
                    )

        print("Subiendo assets a JSON2Video...")
        narration_ext = narration_path.suffix.lower()
        narration_name = f"{args.reel_slug}_narracion{narration_ext}"
        narration_url = upload_asset(narration_path, narration_name, api_key)
        uploaded_names.append(narration_name)

        music_url = None
        if args.music:
            music_path = Path(args.music)
            if not music_path.exists():
                raise RenderError(f"No existe el archivo de musica: {music_path}")
            music_name = f"{args.reel_slug}_musica{music_path.suffix.lower()}"
            music_url = upload_asset(music_path, music_name, api_key)
            uploaded_names.append(music_name)
        else:
            print("  (sin musica de fondo -- no se paso --music)")

        scenes = []
        first_clip_url = None
        first_clip_duration = None
        for i, ((m, path, is_photo, clip_duration), target) in enumerate(zip(selected, targets)):
            dest_name = f"{args.reel_slug}_{path.name}"
            clip_url = upload_asset(path, dest_name, api_key)
            uploaded_names.append(dest_name)
            if i == 0:
                first_clip_url, first_clip_duration = clip_url, clip_duration
            if has_hook:
                transition_duration = transition_durations[i]
            else:
                transition_duration = transition_durations[i - 1] if i > 0 else None
            scenes.append(build_scene(m, clip_url, is_photo, target, clip_duration, i, transition_duration))

        if has_hook:
            print(f"Gancho: \"{args.hook_main}\" / \"{args.hook_accent}\" ({HOOK_DURATION_S}s antes de la narracion)")
            scenes.insert(0, build_hook_scene(first_clip_url, first_clip_duration, args.hook_main, args.hook_accent))

        narration_start = HOOK_DURATION_S if has_hook else 0
        movie = build_movie(scenes, narration_url, narration_start, music_url, args.quality)

        print("Enviando movie JSON a JSON2Video...")
        project = submit_movie(movie, api_key)
        print(f"Proyecto: {project}. Esperando render (poll cada {POLL_INTERVAL_S}s)...")
        result = poll_movie(project, api_key)

        out_dir = Path(args.out_dir) / args.reel_slug
        out_path = out_dir / "reel_final.mp4"
        print(f"Descargando video final a {out_path}...")
        download_final(result["url"], out_path)

        credits = sum(c.get("credits", 0) for c in result.get("consumed_credits", []))
        print("\nListo.")
        print(f"  Archivo: {out_path}")
        print(f"  Duracion: {result.get('duration')}s  Resolucion: {result.get('width')}x{result.get('height')}")
        print(f"  Creditos consumidos: {credits}")

        flagged = [m for m in moments if m.notes]
        if flagged:
            print("\n  Momentos con advertencias heredadas de orden_edicion.txt (revisar el resultado visual):")
            for m in flagged:
                print(f"    {m.order:02d} {m.label}: {', '.join(m.notes)}")

    except RenderError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        if api_key and uploaded_names:
            print("Limpiando assets subidos a JSON2Video (liberar cuota de storage)...")
            for name in uploaded_names:
                delete_asset(name, api_key)

    return 0


if __name__ == "__main__":
    sys.exit(main())
