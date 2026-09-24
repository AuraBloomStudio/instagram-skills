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
             ├─ resuelve producto / URL de products.json
             ├─ copia mockup si existe
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
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from carousel_common import OUTPUTS_DIR, REQUIRED_SLIDE_FIELDS, load_brief  # noqa: E402
from text_qa import verify_source_text_fragments  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

PRODUCTS_JSON = Path(__file__).parent.parent / "products.json"
SAVE_REF_SCRIPT = Path(__file__).parent / "save_reference_image.py"

# Productos conocidos que tienen mockup — nombre exacto (case-sensitive) -> ruta relativa al bundle raiz
_PRODUCT_MOCKUP_SEARCH_DIRS = [
    OUTPUTS_DIR,
]
_BOOK_MOCKUP_BASENAME = "book-mockup-original.png"

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

def save_reference(bundle_path: Path, session_id: str, skip: bool, fake_ref: Optional[str]) -> Tuple[bool, str]:
    """
    Guarda viral-reference.png en bundle_path/carousel/assets/.
    Retorna (ok, mensaje).
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

    if not session_id:
        return False, "STOP: CLAUDE_CODE_SESSION_ID no encontrado en el entorno"

    env = dict(os.environ)
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    result = subprocess.run(
        [sys.executable, str(SAVE_REF_SCRIPT), str(dest)],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )
    if result.returncode != 0:
        msg = (result.stdout or result.stderr or "Error desconocido").strip()
        return False, f"STOP: save_reference_image.py fallo: {msg}"
    return True, f"[T2] Referencia guardada: {dest}\n{result.stdout.strip()}"


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

def find_product_mockup(bundle_path: Path) -> Optional[Path]:
    """
    Busca el mockup del producto copiado en algun bundle anterior.
    Solo mira 1 nivel: outputs/bundles/*/carousel/assets/book-mockup-original.png
    Retorna la ruta si existe, None si no.
    """
    bundles_dir = OUTPUTS_DIR
    if not bundles_dir.exists():
        return None
    for candidate_dir in sorted(bundles_dir.iterdir(), reverse=True):
        if not candidate_dir.is_dir():
            continue
        candidate = candidate_dir / "carousel" / "assets" / _BOOK_MOCKUP_BASENAME
        if candidate.exists() and candidate_dir != bundle_path:
            return candidate
    return None


def copy_mockup_to_bundle(bundle_path: Path, uses_mockup: bool) -> Optional[str]:
    """
    Si algun slide usa mockup directamente, copia el mockup al bundle.
    Retorna la ruta relativa al bundle si se copio, None si no.
    """
    if not uses_mockup:
        return None
    dest = bundle_path / "carousel" / "assets" / _BOOK_MOCKUP_BASENAME
    if dest.exists():
        return f"carousel/assets/{_BOOK_MOCKUP_BASENAME}"
    src = find_product_mockup(bundle_path)
    if src:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return f"carousel/assets/{_BOOK_MOCKUP_BASENAME}"
    return None


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
    if len(slides) > 10:
        errors.append(f"brief tiene {len(slides)} slides, maximo 10")
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

    # 2. Crear bundle + directorios
    bundle_path = OUTPUTS_DIR / bundle_id
    (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
    timing["T1"] = _now_iso()
    print(f"[T1] Bundle creado: {bundle_path}")

    # 3. Extraer referencia
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    ok, ref_msg = save_reference(bundle_path, session_id, args.skip_reference, args.fake_reference)
    print(ref_msg)
    if not ok:
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
    brief = build_brief(decisions, bundle_id, bundle_path, timing)
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
