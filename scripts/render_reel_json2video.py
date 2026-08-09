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
     "instagram-story" resolution) and poll until it renders.
  6. Download the final MP4 to scripts/output_reels/<slug>/reel_final.mp4 and
     delete the uploaded source assets from JSON2Video's media library (its
     free tier only grants ~50MB of storage, so cleaning up after every
     render matters).

JSON2VIDEO_API_KEY is never hardcoded. If it is not already set as an
environment variable, this script prompts for it (input is masked) and
offers to save it to the local .env file, which is already gitignored --
same pattern as generate_post_image.py and generate_reel_narration.py.

Usage:
  python scripts/render_reel_json2video.py <reel_slug> [--music PATH] [--quality high|medium|low]
"""
from __future__ import annotations

import argparse
import getpass
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

# "Dorado" from the brand's BRAND_COLORS palette (scripts/references/
# image_prompt_style.md) -- reused here as the active-word highlight color so
# the subtitle style matches the rest of the brand's visual identity.
SUBTITLE_WORD_COLOR = "#B8985E"
SUBTITLE_LINE_COLOR = "#FFFFFF"

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


def build_scene(moment: Moment, clip_url: str, is_photo: bool, target_duration: float,
                 clip_duration: Optional[float], moment_index: int) -> dict:
    if is_photo:
        pan = "right" if moment_index % 2 == 0 else "left"
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
    return {"elements": [element]}


def build_movie(scenes: list, narration_url: str, music_url: Optional[str], quality: str) -> dict:
    elements = [
        {"type": "audio", "src": narration_url, "volume": 1},
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
    parser.add_argument("--clips-dir", default=str(DEFAULT_CLIPS_DIR), help="Carpeta base de clips (default: scripts/output_clips)")
    parser.add_argument("--audio-dir", default=str(DEFAULT_AUDIO_DIR), help="Carpeta base de audio (default: scripts/output_audio)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR), help="Carpeta base de salida (default: scripts/output_reels)")
    args = parser.parse_args()

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

        quota_resp = requests.get(f"{J2V_API_BASE}/movies", headers={"x-api-key": api_key}, timeout=30)
        if quota_resp.status_code < 400:
            remaining = quota_resp.json().get("remaining_quota", {}).get("time")
            if remaining is not None:
                print(f"Cuota de render restante en la cuenta de JSON2Video: {remaining}s")
                if remaining < narration_duration:
                    print(
                        f"  AVISO: la cuota restante ({remaining}s) es menor que la duracion "
                        f"del reel ({narration_duration:.1f}s). El render puede fallar por cuota."
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
        for i, ((m, path, is_photo, clip_duration), target) in enumerate(zip(selected, targets)):
            dest_name = f"{args.reel_slug}_{path.name}"
            clip_url = upload_asset(path, dest_name, api_key)
            uploaded_names.append(dest_name)
            scenes.append(build_scene(m, clip_url, is_photo, target, clip_duration, i))

        movie = build_movie(scenes, narration_url, music_url, args.quality)

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
