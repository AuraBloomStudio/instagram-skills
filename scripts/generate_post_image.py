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

The visual style (lighting, composition options, how metaphors get reinterpreted)
lives entirely in scripts/references/image_prompt_style.md, not in this file --
edit that reference to tune the output without touching code.

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
from PIL import Image

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
STATE_PATH = REPO_ROOT / "testing" / "image_gen_state.json"
ROTATION_HISTORY = 2  # avoid repeating any of the last N picks per category


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


def _extract_marked_block(text: str, name: str) -> str:
    match = re.search(
        rf"<!--\s*BEGIN:{name}\s*-->(.*?)<!--\s*END:{name}\s*-->",
        text,
        re.DOTALL,
    )
    if not match:
        raise GenerationError(
            f"No se encontró el bloque {name} en {STYLE_GUIDE_PATH}. "
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
    }


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


def _extract_json_object(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        raise GenerationError(f"No se pudo interpretar la respuesta de Gemini: {text[:300]}")
    return json.loads(match.group(0))


def analyze_copy(
    copy_text: str, api_key: str, style: dict, archetype: str, camera_angle: str, setting: str
) -> dict:
    rules = (
        style["analysis_rules"]
        .replace("__COMPOSITION_ARCHETYPE__", archetype)
        .replace("__CAMERA_ANGLE__", camera_angle)
        .replace("__SETTING__", setting)
    )
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
    analysis["composition_archetype"] = archetype
    analysis["camera_angle"] = camera_angle
    analysis["setting"] = setting
    return analysis


def build_image_prompt(analysis: dict, style: dict, aspect_ratio: str) -> str:
    return (
        f"{analysis['visual_concept_en']} "
        f"Central emotional tone: {analysis['emotion_en']} "
        f"({analysis['theme_en']}). "
        f"{style['brand_style']} "
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
    args = parser.parse_args()

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
        api_key = ensure_gemini_api_key()

        state = _load_state()
        archetype = _pick_avoiding_recent(style["archetypes"], "composition", state)
        camera_angle = _pick_avoiding_recent(style["camera_angles"], "camera_angle", state)
        setting = _pick_avoiding_recent(style["settings"], "setting", state)

        print(f"Leyendo copy: {copy_path.name}")
        copy_text = read_copy_text(copy_path)

        print("Analizando emoción central y tema con Gemini...")
        analysis = analyze_copy(copy_text, api_key, style, archetype, camera_angle, setting)
        print(f"  Emoción central: {analysis['emotion_es']} ({analysis['emotion_en']})")
        print(f"  Tema: {analysis['theme_en']}")
        print(f"  Ubicación elegida: {analysis['setting']}")
        print(f"  Composición elegida: {analysis['composition_archetype']}")
        print(f"  Ángulo de cámara elegido: {analysis['camera_angle']}")

        image_prompt = build_image_prompt(analysis, style, aspect_ratio)
        print(f"Prompt de imagen:\n  {image_prompt}\n")

        print(f"Generando imagen con {IMAGE_MODEL} (aspect {aspect_ratio})...")
        image_bytes = generate_image(image_prompt, api_key, aspect_ratio)

        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        if image.size != output_size:
            image = image.resize(output_size, Image.LANCZOS)
        image.save(out_path, "PNG")
        print(f"Imagen guardada en: {out_path} ({output_size[0]}x{output_size[1]})")

        _save_state(state)
    except GenerationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
