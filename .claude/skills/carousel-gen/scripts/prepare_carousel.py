#!/usr/bin/env python3
"""
prepare_carousel.py - Controlador DETERMINISTA de preparacion para carousel-gen.

Claude entrega sus decisiones visuales en UN archivo JSON (claude_decisions.json).
Este script ejecuta TODA la preparacion determinista sin ninguna intervencion adicional:

    [Claude] 1 Write (claude_decisions.json)
             |
    [Python] prepare_carousel.py <decisions_path>
             |
             ├─ crea bundle + directorios
             ├─ extrae referencia del transcript JSONL
             ├─ impone la CONFIGURACION FIJA (formato, 10 slides, producto, URL, 8 hashtags)
             ├─ copia el mockup original aprobado (verificado por sha256) si un slide lo usa
             ├─ calcula campos derivados (word_count, text_density, ...)
             ├─ valida los 21 REQUIRED_SLIDE_FIELDS por slide
             ├─ escribe brief.json (UNA vez, ya validado)
             ├─ escribe copy.json
             ├─ escribe pipeline_input.json
             └─ imprime PREPARE_RESULT:<json> para que Claude lo lea

Timing T0-T8:
    T0: inicio del script (antes de cualquier I/O)
    T1: bundle + directorios creados
    T2: referencia visual guardada en bundle/carousel/assets/viral-reference.png
    T3: source_text validado + producto/URL resueltos
    T4: analisis visual parseado (de la entrada Claude)
    T5: slide plan parseado y enriquecido
    T6: brief construido en memoria (campos computados incluidos)
    T7: validacion de todos los REQUIRED_SLIDE_FIELDS pasada
    T8: archivos escritos — listo para run_carousel_pipeline.py

Salida:
    brief.json             en outputs/bundles/<bundle_id>/
    copy.json              en outputs/bundles/<bundle_id>/
    pipeline_input.json    en outputs/bundles/<bundle_id>/
    PREPARE_RESULT:<json>  al final de stdout (Claude lee esta linea)

Campos calculados automaticamente por este script (NO los proporciona Claude):
    word_count           <- len(exact_text.split())
    text_density         <- LOW(<=8) / MEDIUM(9-15) / HIGH(>15)
    estimated_text_area  <- mismo valor que text_placement
    text_area_percentage <- LOW->15 / MEDIUM->25 / HIGH->40
    visual_balance       <- lower/upper third -> "balanced"; center -> "text_heavy"

Campos que Claude DEBE proporcionar por slide (16 campos, no 21):
    number, role, narrative_objective, message,
    source_text_fragment, source_location, exact_text,
    scene_description, composition, visual_hierarchy,
    text_placement, key_visual_elements,
    visual_dna_connection, uses_reference_image_directly,
    uses_product_mockup_directly, text_break_reason

Uso:
    python3 scripts/prepare_carousel.py <decisions_json_path>
    python3 scripts/prepare_carousel.py <decisions_json_path> --skip-reference
    python3 scripts/prepare_carousel.py <decisions_json_path> --fake-reference <png_path>
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from carousel_common import (  # noqa: E402
    OUTPUTS_DIR, REQUIRED_SLIDE_FIELDS, load_brief,
    FIXED_CAROUSEL_TYPE, FIXED_SLIDE_COUNT, FIXED_PRODUCT_NAME, FIXED_PURCHASE_URL,
    FIXED_HASHTAG_COUNT,
)
from text_qa import verify_source_text_fragments  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PRODUCTS_JSON = Path(__file__).parent.parent / "products.json"
SAVE_REF_SCRIPT = Path(__file__).parent / "save_reference_image.py"

# Nombre con el que el mockup original aprobado se copia dentro de cada bundle. El ORIGEN
# es siempre products.json -> mockup_path (verificado con mockup_sha256), nunca otro bundle.
_BOOK_MOCKUP_BASENAME = "book-mockup-original.png"

_URL_RE = re.compile(r"https?://\S+")

# Umbrales para text_density
_DENSITY_LOW_MAX = 8
_DENSITY_MEDIUM_MAX = 15

# Porcentaje de area de texto por densidad
_TEXT_AREA_PCT = {"LOW": 15, "MEDIUM": 25, "HIGH": 40}


# ---------------------------------------------------------------------------
# Helpers de tiempo
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Calculo de campos derivados
# ---------------------------------------------------------------------------

def compute_slide_fields(slide_in: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recibe un slide con los 16 campos que Claude proporciona y devuelve
    el slide completo con los 5 campos computados anadidos.
    No modifica el dict original.
    """
    slide = dict(slide_in)
    exact_text = str(slide.get("exact_text", ""))
    text_placement = str(slide.get("text_placement", ""))

    # word_count
    word_count = len(exact_text.split()) if exact_text.strip() else 0
    slide["word_count"] = word_count

    # text_density
    if word_count <= _DENSITY_LOW_MAX:
        density = "LOW"
    elif word_count <= _DENSITY_MEDIUM_MAX:
        density = "MEDIUM"
    else:
        density = "HIGH"
    slide["text_density"] = density

    # estimated_text_area: mismo valor que text_placement
    slide["estimated_text_area"] = text_placement

    # text_area_percentage
    slide["text_area_percentage"] = _TEXT_AREA_PCT[density]

    # visual_balance: heuristica sobre text_placement
    lower_kw = ("lower", "inferior", "bottom")
    upper_kw = ("upper", "superior", "top")
    tpl = text_placement.lower()
    if any(k in tpl for k in lower_kw) or any(k in tpl for k in upper_kw):
        slide["visual_balance"] = "balanced"
    else:
        slide["visual_balance"] = "text_heavy" if density == "HIGH" else "balanced"

    return slide


# ---------------------------------------------------------------------------
# Extraccion de referencia
# ---------------------------------------------------------------------------

REFERENCE_NOT_IDENTIFIED = "REFERENCE_IMAGE_NOT_IDENTIFIED"


def save_reference(bundle_path: Path, session_id: str, skip: bool, fake_ref: Optional[str],
                   selection: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """
    Guarda la REFERENCE_IMAGE como viral-reference.png en bundle_path/carousel/assets/.
    La referencia es SIEMPRE la imagen que el usuario adjunta con el copy, identificada
    EXPLICITAMENTE en claude_decisions.json -> reference_image:
      {"message_text_contains": "<fragmento del copy>"} |
      {"attachment_index": N, "sha256_prefix": "<8+ hex>"}
    Nunca "la ultima imagen adjunta"; el mockup del producto es un asset interno
    (products.json) y nunca es la referencia. Si no se identifica de forma inequivoca:
    REFERENCE_IMAGE_NOT_IDENTIFIED (error claro, nunca una pregunta). Retorna (ok, mensaje).
    """
    dest_dir = bundle_path / "carousel" / "assets"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "viral-reference.png"

    if fake_ref:
        shutil.copy2(fake_ref, dest)
        return True, f"[T2] Referencia (fake): {dest}"

    if skip:
        if not dest.exists():
            return False, "STOP: --skip-reference pero viral-reference.png no existe en el bundle"
        return True, f"[T2] Referencia reutilizada: {dest}"

    selection = selection or {}
    if selection.get("attachment_index") is not None:
        selector = ["--attachment-index", str(selection["attachment_index"]),
                    "--sha256-prefix", str(selection.get("sha256_prefix") or "")]
    elif selection.get("message_text_contains"):
        selector = ["--message-text-contains", str(selection["message_text_contains"])]
    else:
        return False, (f"STOP: {REFERENCE_NOT_IDENTIFIED}: claude_decisions.json no indica que imagen es la "
                       f"referencia (reference_image). Nunca se usa la ultima imagen adjunta.")

    if not session_id:
        return False, "STOP: CLAUDE_CODE_SESSION_ID no encontrado en el entorno"

    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    result = subprocess.run(
        [sys.executable, str(SAVE_REF_SCRIPT), str(dest)] + selector,
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    if result.returncode != 0:
        msg = (result.stdout or result.stderr or "Error desconocido").strip()
        return False, f"STOP: {msg}"
    return True, f"[T2] REFERENCE_IMAGE guardada: {dest}\n{result.stdout.strip()}"


def reference_is_product_mockup(bundle_path: Path) -> bool:
    """True si la REFERENCE_IMAGE guardada es el mockup interno del producto (mismo
    sha256 que products.json -> mockup_sha256). El mockup nunca puede ser la referencia."""
    ref = bundle_path / "carousel" / "assets" / "viral-reference.png"
    try:
        entry = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))["products"][FIXED_PRODUCT_NAME]
        expected = (entry.get("mockup_sha256") or "").lower()
    except (OSError, json.JSONDecodeError, KeyError):
        return False
    return bool(expected) and ref.is_file() and _sha256(ref) == expected


# ---------------------------------------------------------------------------
# Resolucion de producto
# ---------------------------------------------------------------------------

def resolve_product(product_decision: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dado el bloque product del decisions JSON, resuelve la URL desde products.json
    si purchase_url es None y product_name coincide con una entrada conocida.
    """
    product_name = product_decision.get("product_name") or None
    purchase_url = product_decision.get("purchase_url") or None

    if product_name and not purchase_url and PRODUCTS_JSON.exists():
        try:
            db = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
            entry = db.get("products", {}).get(product_name)
            if entry:
                purchase_url = entry.get("purchase_url")
        except (json.JSONDecodeError, OSError):
            pass

    return {"product_name": product_name, "purchase_url": purchase_url}


# ---------------------------------------------------------------------------
# Busqueda de mockup de producto
# ---------------------------------------------------------------------------

class MockupError(Exception):
    """El mockup original aprobado no esta disponible o no coincide con su sha256."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_skill_relative(mockup_path: str, skill_dir: Path) -> Path:
    """
    PORTABILIDAD (2026-09-26): el mockup vive versionado DENTRO de la skill y mockup_path
    es relativo al directorio de la skill (el de products.json). Se rechaza cualquier ruta
    absoluta (C:\\..., /home/..., /root/...) o que salga de la skill (../), en cualquier SO.
    """
    posix = mockup_path.replace("\\", "/")
    if PureWindowsPath(mockup_path).drive or posix.startswith("/"):
        raise MockupError(f"ERROR DE CONFIGURACION DE LA SKILL: mockup_path debe ser relativo a la skill, "
                          f"no una ruta absoluta: {mockup_path}")
    root = skill_dir.resolve()
    candidate = root.joinpath(*PurePosixPath(posix).parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise MockupError(f"ERROR DE CONFIGURACION DE LA SKILL: mockup_path sale del directorio de la skill: {mockup_path}")
    return candidate


def find_product_mockup() -> Path:
    """
    Devuelve la ruta del mockup ORIGINAL APROBADO de FIXED_PRODUCT_NAME, leida de
    products.json (mockup_path, RELATIVO a la skill) y verificada contra mockup_sha256.
    Nunca busca en bundles anteriores ni crea un sustituto: si falta o no coincide, lanza
    MockupError (error de configuracion de la skill, nunca una pregunta al usuario).
    """
    try:
        entry = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))["products"][FIXED_PRODUCT_NAME]
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise MockupError(f"products.json no tiene la entrada '{FIXED_PRODUCT_NAME}' ({e})")
    mockup_path = entry.get("mockup_path")
    expected_sha = (entry.get("mockup_sha256") or "").lower()
    if not mockup_path or not expected_sha:
        raise MockupError(f"products.json no define 'mockup_path' y 'mockup_sha256' para '{FIXED_PRODUCT_NAME}'")
    src = _resolve_skill_relative(mockup_path, PRODUCTS_JSON.parent)
    if not src.is_file():
        raise MockupError(f"el mockup original aprobado no existe en: {src}")
    actual_sha = _sha256(src)
    if actual_sha != expected_sha:
        raise MockupError(f"el archivo {src} no es el mockup aprobado "
                          f"(sha256 {actual_sha[:12]}... != esperado {expected_sha[:12]}...)")
    return src


def copy_mockup_to_bundle(bundle_path: Path, uses_mockup: bool) -> Optional[str]:
    """
    Si algun slide usa mockup directamente, copia el mockup ORIGINAL APROBADO al bundle
    (copia binaria exacta). Si el bundle ya tiene un mockup distinto, se reemplaza por el
    aprobado. Retorna la ruta relativa al bundle, None si ningun slide usa mockup.
    Lanza MockupError si el mockup aprobado no esta disponible — nunca genera sustituto.
    """
    if not uses_mockup:
        return None
    src = find_product_mockup()
    dest = bundle_path / "carousel" / "assets" / _BOOK_MOCKUP_BASENAME
    if not dest.exists() or _sha256(dest) != _sha256(src):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return f"carousel/assets/{_BOOK_MOCKUP_BASENAME}"


# ---------------------------------------------------------------------------
# Configuracion fija (ver SKILL.md "CONFIGURACION FIJA")
# ---------------------------------------------------------------------------

def apply_fixed_config(decisions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Impone formato, producto y enlace fijos sobre claude_decisions.json (cualquier valor
    distinto que traiga se ignora). Devuelve una copia; no modifica el dict original.
    """
    fixed = dict(decisions)
    fixed["carousel_type"] = FIXED_CAROUSEL_TYPE
    fixed["product"] = {"product_name": FIXED_PRODUCT_NAME, "purchase_url": FIXED_PURCHASE_URL}
    copy_data = dict(decisions.get("copy") or {})
    copy_data["product"] = FIXED_PRODUCT_NAME
    copy_data["purchase_url"] = FIXED_PURCHASE_URL
    fixed["copy"] = copy_data
    return fixed


def validate_fixed_rules(decisions: Dict[str, Any]) -> List[str]:
    """
    Reglas fijas que NO dependen del brief construido: 10 slides exactos (sin repetir
    texto para rellenar), descripcion/CTA no vacios, exactamente 8 hashtags y ningun
    enlace distinto del fijo dentro del copy. Retorna lista de errores (vacia = OK).
    """
    errors: List[str] = []
    slides = decisions.get("slides") or []
    if len(slides) < FIXED_SLIDE_COUNT:
        errors.append(
            f"El copy no alcanza para construir exactamente {FIXED_SLIDE_COUNT} slides sin "
            f"inventar ni repetir texto (se recibieron {len(slides)} slides). Proporciona un "
            f"copy mas extenso."
        )
    elif len(slides) > FIXED_SLIDE_COUNT:
        errors.append(f"brief tiene {len(slides)} slides, se requieren exactamente {FIXED_SLIDE_COUNT}")

    seen: Dict[str, Any] = {}
    for s in slides:
        key = " ".join(str(s.get("exact_text", "")).lower().split())
        if key and key in seen:
            errors.append(
                f"Slides {seen[key]} y {s.get('number', '?')} repiten el mismo texto — no se "
                f"permite repetir contenido para completar {FIXED_SLIDE_COUNT} slides"
            )
        elif key:
            seen[key] = s.get("number", "?")

    copy_data = decisions.get("copy") or {}
    for field in ("description", "cta"):
        if not str(copy_data.get(field) or "").strip():
            errors.append(f"copy.{field} esta vacio — nunca puede omitirse")
    hashtags = copy_data.get("hashtags") or []
    if len(hashtags) != FIXED_HASHTAG_COUNT:
        errors.append(f"copy.hashtags tiene {len(hashtags)} hashtags, se requieren exactamente {FIXED_HASHTAG_COUNT}")
    bad = [h for h in hashtags if not isinstance(h, str) or not re.fullmatch(r"#\S+", h)]
    if bad:
        errors.append(f"hashtags invalidos (deben empezar con # y no tener espacios): {bad}")
    if len({str(h).lower() for h in hashtags}) != len(hashtags):
        errors.append("copy.hashtags tiene hashtags repetidos")
    for field in ("description", "cta"):
        for url in _URL_RE.findall(str(copy_data.get(field) or "")):
            if url.rstrip(".,;:)") != FIXED_PURCHASE_URL:
                errors.append(f"copy.{field} contiene un enlace distinto del fijo: {url}")
    return errors


# ---------------------------------------------------------------------------
# Construccion y validacion del brief
# ---------------------------------------------------------------------------

def build_brief(decisions: Dict[str, Any], bundle_id: str, bundle_path: Path, timing: Dict) -> Dict[str, Any]:
    """
    Construye el brief.json completo en memoria a partir de decisions.
    No escribe ningun archivo.
    """
    slides_raw = decisions.get("slides") or []
    slides = [compute_slide_fields(s) for s in slides_raw]

    uses_mockup_any = any(s.get("uses_product_mockup_directly") for s in slides)
    mockup_rel = copy_mockup_to_bundle(bundle_path, uses_mockup_any)

    product = resolve_product(decisions.get("product") or {})

    ref_local = "carousel/assets/viral-reference.png"
    brief = {
        "bundle_id": bundle_id,
        "source_text": decisions.get("source_text", ""),
        "reference_image": {
            "local_path": ref_local,
            "analysis": decisions.get("reference_analysis") or {},
        },
        "visual_dna": decisions.get("visual_dna") or {},
        "carousel_type": decisions.get("carousel_type", ""),
        "slide_count": {
            "recommended": len(slides),
            "confirmed": len(slides),
        },
        "product": product,
        "slides": slides,
        "timing": {
            "skill_started_at": timing.get("T0"),
            "reference_received_at": timing.get("T2"),
            "source_text_confirmed_at": timing.get("T3"),
            "brief_approved_at": timing.get("T7"),
        },
    }
    if mockup_rel:
        brief["product_mockup"] = {
            "local_path": mockup_rel,
            "description": f"Mockup del producto '{product.get('product_name', '')}' copiado automaticamente por prepare_carousel.py",
        }
    return brief


def validate_brief_in_memory(brief: Dict[str, Any]) -> List[str]:
    """
    Valida todos los REQUIRED_SLIDE_FIELDS en todos los slides.
    Retorna lista de errores (vacia = OK).
    """
    errors = []
    slides = brief.get("slides") or []
    if not slides:
        errors.append("brief no tiene slides")
        return errors
    if len(slides) != FIXED_SLIDE_COUNT:
        errors.append(f"brief tiene {len(slides)} slides, se requieren exactamente {FIXED_SLIDE_COUNT}")
    for s in slides:
        n = s.get("number", "?")
        for field in REQUIRED_SLIDE_FIELDS:
            if field not in s:
                errors.append(f"Slide {n}: campo faltante '{field}'")
    # Validar source_text
    if not brief.get("source_text", "").strip():
        errors.append("source_text esta vacio")
    # Validar carousel_type
    if not brief.get("carousel_type", "").strip():
        errors.append("carousel_type esta vacio")
    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preparacion determinista de carousel-gen: "
                    "Claude entrega decisions JSON, Python hace el resto."
    )
    parser.add_argument("decisions_path", help="Ruta a claude_decisions.json")
    parser.add_argument(
        "--skip-reference", action="store_true",
        help="No extrae la referencia (usa la que ya existe en el bundle)",
    )
    parser.add_argument(
        "--fake-reference", default=None, metavar="PNG_PATH",
        help="SOLO PRUEBAS: usar esta imagen como referencia en vez del transcript",
    )
    args = parser.parse_args()

    timing: Dict[str, Optional[str]] = {}
    timing["T0"] = _now_iso()
    print(f"\n[PREPARE] prepare_carousel.py")
    print(f"[T0] Inicio: {timing['T0']}")

    # 1. Leer decisions JSON
    try:
        decisions = json.loads(Path(args.decisions_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"STOP: No se pudo leer {args.decisions_path}: {e}")
        return 1

    bundle_id = decisions.get("bundle_id", "").strip()
    if not bundle_id:
        print("STOP: decisions JSON no tiene 'bundle_id'")
        return 1

    # Configuracion fija (formato, producto, enlace) + reglas fijas, ANTES de crear nada
    decisions = apply_fixed_config(decisions)
    fixed_errors = validate_fixed_rules(decisions)
    if fixed_errors:
        print("STOP: Configuracion fija no cumplida:")
        for e in fixed_errors:
            print(f"  - {e}")
        return 1

    # 2. Crear bundle + directorios
    bundle_path = OUTPUTS_DIR / bundle_id
    (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
    timing["T1"] = _now_iso()
    print(f"[T1] Bundle creado: {bundle_path}")

    # 3. Extraer referencia
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    ok, ref_msg = save_reference(bundle_path, session_id, args.skip_reference, args.fake_reference,
                                 decisions.get("reference_image"))
    print(ref_msg)
    if not ok:
        return 1
    if reference_is_product_mockup(bundle_path):
        print(f"STOP: {REFERENCE_NOT_IDENTIFIED}: la imagen seleccionada es el mockup interno del producto, "
              f"no la imagen de referencia del usuario.")
        return 1
    timing["T2"] = _now_iso()

    # 4. Validar source_text
    source_text = decisions.get("source_text", "").strip()
    if not source_text:
        print("STOP: source_text esta vacio — no se puede generar sin contenido")
        return 1

    # Resolver producto
    product = resolve_product(decisions.get("product") or {})
    timing["T3"] = _now_iso()
    pname = product.get("product_name") or "ninguno"
    purl = product.get("purchase_url") or "ninguna"
    print(f"[T3] source_text OK ({len(source_text.split())} palabras) | producto: {pname} | url: {purl[:60] if purl != 'ninguna' else 'ninguna'}")

    # 5. Parsear analisis visual
    ref_analysis = decisions.get("reference_analysis") or {}
    visual_dna = decisions.get("visual_dna") or {}
    timing["T4"] = _now_iso()
    print(f"[T4] Analisis visual parseado ({len(visual_dna)} claves visual_dna)")

    # 6. Parsear slide plan + computar campos derivados
    slides_raw = decisions.get("slides") or []
    slides_enriched = [compute_slide_fields(s) for s in slides_raw]
    timing["T5"] = _now_iso()
    print(f"[T5] Slide plan: {len(slides_enriched)} slides enriquecidos (word_count, text_density, ...)")

    # Verificacion no bloqueante: source_text_fragments deben rastrearse al source_text
    src_frag_warnings = verify_source_text_fragments(source_text, slides_raw)
    for w in src_frag_warnings:
        print(f"[WARN] {w}")

    # 7. Construir brief en memoria
    try:
        brief = build_brief(decisions, bundle_id, bundle_path, timing)
    except MockupError as e:
        print(f"STOP: ERROR DE CONFIGURACION DE LA SKILL (mockup de {FIXED_PRODUCT_NAME}): {e}")
        print("      El mockup aprobado debe estar versionado en la skill (assets/, ver products.json). "
              "No se genera ningun mockup sustituto.")
        return 1
    timing["T6"] = _now_iso()
    print(f"[T6] Brief construido en memoria")

    # 8. Validar
    errors = validate_brief_in_memory(brief)
    if errors:
        print("STOP: Validacion fallida:")
        for e in errors:
            print(f"  - {e}")
        return 1
    timing["T7"] = _now_iso()
    print(f"[T7] Validacion OK — todos los {len(REQUIRED_SLIDE_FIELDS)} campos presentes en {len(slides_enriched)} slides")

    # 9. Escribir archivos (UNA sola vez cada uno, ya validados)
    brief_path = bundle_path / "brief.json"
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[WRITE] brief.json -> {brief_path}")

    copy_data = decisions.get("copy") or {}
    copy_path = bundle_path / "copy.json"
    copy_path.write_text(json.dumps(copy_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[WRITE] copy.json -> {copy_path}")

    timing["T8"] = _now_iso()

    # pipeline_input.json: handoff estructurado para run_carousel_pipeline.py
    pipeline_input = {
        "bundle_id": bundle_id,
        "bundle_path": str(bundle_path),
        "brief_path": str(brief_path),
        "copy_json_path": str(copy_path),
        "slides_count": len(slides_enriched),
        "carousel_type": decisions.get("carousel_type", ""),
        "product": product,
        "timing": timing,
        "next_command": (
            f'PYTHONUNBUFFERED=1 python3 "{Path(__file__).parent / "run_carousel_pipeline.py"}" '
            f'"{bundle_id}" --copy-json "{copy_path}"'
        ),
    }
    pipeline_input_path = bundle_path / "pipeline_input.json"
    pipeline_input_path.write_text(json.dumps(pipeline_input, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[WRITE] pipeline_input.json -> {pipeline_input_path}")

    print(f"\n[PREPARE] Preparacion completa en {(datetime.fromisoformat(timing['T8']) - datetime.fromisoformat(timing['T0'])).total_seconds():.1f}s")
    print(f"[PREPARE] Siguiente paso: run_carousel_pipeline.py \"{bundle_id}\" --copy-json \"{copy_path}\"")

    result = {
        "status": "READY",
        "bundle_id": bundle_id,
        "bundle_path": str(bundle_path),
        "brief_path": str(brief_path),
        "copy_json_path": str(copy_path),
        "pipeline_input_path": str(pipeline_input_path),
        "slides_count": len(slides_enriched),
        "timing": timing,
        "next_command": pipeline_input["next_command"],
    }
    print(f"\nPREPARE_RESULT:{json.dumps(result, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
