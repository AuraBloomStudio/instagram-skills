#!/usr/bin/env python3
"""
test_skill_flow.py - Tests para las 5 reglas de flujo nuevas o corregidas en carousel-gen.

Cubre:
  TEST 1 — bundle_id disponible ANTES de guardar la referencia (no staging)
  TEST 2 — brief con TODOS los campos obligatorios pasa load_brief() sin error
  TEST 3 — source_text ausente -> STOP (accion correcta, mensaje correcto)
  TEST 4 — source_text explicito proporcionado -> USE_TEXT (no STOP)
  TEST 5 — "usar texto de la imagen" explicito -> EXTRACT_IMAGE (permitido)

Este archivo NO llama a Gemini, NO genera imágenes, NO crea bundles reales de produccion.
Opera sobre directorios temporales (tempfile.mkdtemp()) eliminados en bloques `finally`.

Ejecutar con:
    python3 scripts/test_skill_flow.py
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import load_brief, OUTPUTS_DIR, REQUIRED_SLIDE_FIELDS  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict[str, str]] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f"\n   detail: {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Helper: brief mínimo COMPLETO con todos los campos requeridos
# ---------------------------------------------------------------------------

def _complete_slide(number: int) -> dict:
    """Slide con TODOS los campos de REQUIRED_SLIDE_FIELDS en valores válidos."""
    return {
        "number": number,
        "role": "hook",
        "narrative_objective": "Objetivo narrativo del slide",
        "message": "Mensaje del slide",
        "source_text_fragment": "Fragmento literal del source_text",
        "source_location": "parrafo 1",
        "exact_text": "Texto exacto para generacion",
        "scene_description": "Descripcion de la escena",
        "composition": "full bleed foto BW",
        "visual_hierarchy": "1. Imagen 2. Texto",
        "text_placement": "tercio inferior centrado",
        "key_visual_elements": ["elemento_visual"],
        "visual_dna_connection": "Conexion con el ADN visual",
        "uses_reference_image_directly": number == 1,
        "uses_product_mockup_directly": False,
        # Campos de planificacion visual (los 6 que causaron el error en produccion)
        "word_count": 5,
        "text_density": "LOW",
        "estimated_text_area": "upper_third_centered",
        "text_area_percentage": 20,
        "visual_balance": "balanced",
        "text_break_reason": "natural_sentence_boundary",
    }


def _complete_brief(num_slides: int) -> dict:
    return {
        "bundle_id": "test-complete-brief",
        "source_text": "Texto fuente completo del post viral",
        "reference_image": {
            "local_path": "carousel/assets/viral-reference.png",
            "analysis": {"tema_mensaje": "test", "copy_estructura": "test",
                         "emocion_predominante": "test", "elementos_impacto": "test"},
        },
        "visual_dna": {"aesthetic": "test"},
        "carousel_type": "revelacion_progresiva",
        "slide_count": {"recommended": num_slides, "confirmed": num_slides},
        "product": {"product_name": "Producto Test", "purchase_url": "https://ejemplo.com"},
        "slides": [_complete_slide(n) for n in range(1, num_slides + 1)],
    }


# ---------------------------------------------------------------------------
# Helper: simulacion de la logica PASO 3 (source_text)
#   — replica la regla documentada en SKILL.md para hacerla verificable como test.
#   — NO es codigo de produccion; el comportamiento real lo ejecuta Claude segun SKILL.md.
# ---------------------------------------------------------------------------

_IMAGE_TEXT_PHRASES = [
    "usar texto de la imagen",
    "usa el texto de la imagen",
    "extrae el texto de la referencia",
    "el texto esta en la imagen",
    "el texto está en la imagen",
    "usa texto de la imagen",
]


def _evaluate_source_text_situation(
    user_message: str,
    source_text_provided: Optional[str],
) -> Tuple[str, str]:
    """
    Simula la decision de PASO 3 de SKILL.md.

    Parametros:
        user_message:        Mensaje completo del usuario (instrucciones, contexto, etc.)
        source_text_provided: Texto del post viral si el usuario lo pego explicitamente;
                              None si no lo proporciono.

    Retorna: (action, detail) donde action es uno de:
        "USE_TEXT"      — el usuario proporciono source_text, usarlo directamente
        "STOP"          — no hay source_text ni autorizacion para imagen -> pedir al usuario
        "EXTRACT_IMAGE" — el usuario dijo explicitamente usar el texto de la imagen
    """
    # Caso A: el usuario proporciono source_text
    if source_text_provided:
        return "USE_TEXT", source_text_provided

    # Caso C: el usuario explícitamente dijo usar texto de la imagen
    user_lower = user_message.lower()
    if any(phrase in user_lower for phrase in _IMAGE_TEXT_PHRASES):
        return "EXTRACT_IMAGE", "El usuario autorizo extraccion de texto de la imagen"

    # Caso B: no hay source_text y no hay autorizacion -> STOP
    return "STOP", "No recibi el source_text del carrusel. Pegalo completo para continuar."


# ---------------------------------------------------------------------------
# TEST 1 — bundle_id disponible ANTES de guardar la referencia
# ---------------------------------------------------------------------------

def test_1_bundle_dir_se_crea_antes_de_guardar_referencia():
    """
    El directorio bundle/carousel/assets/ se crea ANTES de intentar guardar
    viral-reference.png. No se usa staging/scratchpad temporal.
    La ruta final del bundle es deterministica desde el inicio (PASO 1 del skill).
    """
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    bundle_id = f"__test-flow-bundleid-{ts}__"
    bundle_path = OUTPUTS_DIR / bundle_id
    assets_path = bundle_path / "carousel" / "assets"
    try:
        # Simula PASO 1: determinar bundle_id y crear carpetas de inmediato
        assets_path.mkdir(parents=True, exist_ok=False)  # exist_ok=False: no deberia existir antes

        dir_exists_before_save = assets_path.is_dir()

        # La ruta donde se guardaria viral-reference.png es deterministica
        ref_path = assets_path / "viral-reference.png"
        path_is_final = (
            bundle_id in str(ref_path)
            and "scratchpad" not in str(ref_path).lower()
            and "temp" not in str(ref_path).lower()
            and str(ref_path).endswith("viral-reference.png")
        )

        ok = dir_exists_before_save and path_is_final
        report(
            "TEST 1",
            "bundle/carousel/assets/ se crea ANTES de guardar referencia; "
            "ruta final deterministica (sin staging/scratchpad)",
            ok,
            f"dir_exists_before_save={dir_exists_before_save} path_is_final={path_is_final} "
            f"ref_path={ref_path}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 2 — brief con TODOS los campos obligatorios pasa load_brief()
# ---------------------------------------------------------------------------

def test_2_brief_completo_con_todos_los_campos_pasa_load_brief():
    """
    Un brief.json que incluye TODOS los campos de REQUIRED_SLIDE_FIELDS
    (incluyendo word_count, text_density, estimated_text_area, text_area_percentage,
    visual_balance, text_break_reason) pasa load_brief() sin error.
    """
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_flow_complete_"))
    try:
        (tmp / "brief.json").write_text(json.dumps(_complete_brief(2)), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = load_brief(tmp)
        ok = result is not None
        output = buf.getvalue()
        report(
            "TEST 2",
            "brief completo con TODOS los campos de REQUIRED_SLIDE_FIELDS "
            "(incl. word_count/text_density/visual_balance/etc.) pasa load_brief() sin rechazar",
            ok,
            output[:300] if not ok else f"OK: {len(result['slides'])} slides aceptados",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 3 — source_text ausente -> STOP
# ---------------------------------------------------------------------------

def test_3_sin_source_text_resultado_es_stop():
    """
    Cuando el usuario no proporciona source_text y no dice 'usar texto de la imagen',
    la logica de PASO 3 debe retornar STOP con el mensaje correcto.
    """
    action, msg = _evaluate_source_text_situation(
        user_message="Crea un carrusel con esta imagen. Ejecuta el flujo completo.",
        source_text_provided=None,
    )
    ok = action == "STOP" and "Pegalo completo" in msg
    report(
        "TEST 3",
        "Sin source_text y sin autorizacion de imagen -> accion STOP con mensaje correcto",
        ok,
        f"action={action!r} msg={msg!r}",
    )


# ---------------------------------------------------------------------------
# TEST 4 — source_text explicito -> USE_TEXT (no STOP, no EXTRACT_IMAGE)
# ---------------------------------------------------------------------------

def test_4_source_text_explicito_retorna_use_text():
    """
    Cuando el usuario proporciona source_text explicito en su mensaje, la logica de
    PASO 3 debe retornar USE_TEXT — nunca STOP ni EXTRACT_IMAGE.
    """
    texto = "Tener el umbral del dolor tan alto no es una fortaleza, es la adaptacion de una nina"
    action, returned_text = _evaluate_source_text_situation(
        user_message="Crea un carrusel con esta imagen.",
        source_text_provided=texto,
    )
    ok = action == "USE_TEXT" and returned_text == texto
    report(
        "TEST 4",
        "source_text explicito proporcionado -> accion USE_TEXT, texto literal conservado",
        ok,
        f"action={action!r}",
    )


# ---------------------------------------------------------------------------
# TEST 5 — "usar texto de la imagen" explicito -> EXTRACT_IMAGE
# ---------------------------------------------------------------------------

def test_5_usar_texto_de_imagen_explicito_retorna_extract_image():
    """
    Cuando el usuario dice EXPLICITAMENTE 'usar texto de la imagen' (u equivalente),
    la logica de PASO 3 debe retornar EXTRACT_IMAGE — nunca STOP.
    Verifica todas las frases equivalentes reconocidas.
    """
    test_cases = [
        "Crea el carrusel, usar texto de la imagen como source_text",
        "Ejecuta el flujo. usa el texto de la imagen",
        "Extrae el texto de la referencia para el carrusel",
        "El texto está en la imagen, usalo",
        "el texto esta en la imagen",
        "Procede con todo, usa texto de la imagen",
    ]
    all_ok = True
    failed_case = ""
    for msg in test_cases:
        action, _ = _evaluate_source_text_situation(
            user_message=msg,
            source_text_provided=None,
        )
        if action != "EXTRACT_IMAGE":
            all_ok = False
            failed_case = f"message={msg!r} -> action={action!r} (esperado EXTRACT_IMAGE)"
            break

    report(
        "TEST 5",
        "Frases equivalentes a 'usar texto de la imagen' retornan EXTRACT_IMAGE (no STOP)",
        all_ok,
        failed_case if not all_ok else f"{len(test_cases)} frases evaluadas correctamente",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("TEST SUITE — REGLAS DE FLUJO carousel-gen (SIN GEMINI / SIN IMAGENES)")
    print("=" * 70)
    for fn in [
        test_1_bundle_dir_se_crea_antes_de_guardar_referencia,
        test_2_brief_completo_con_todos_los_campos_pasa_load_brief,
        test_3_sin_source_text_resultado_es_stop,
        test_4_source_text_explicito_retorna_use_text,
        test_5_usar_texto_de_imagen_explicito_retorna_extract_image,
    ]:
        fn()

    print("\n" + "=" * 70)
    n_pass = sum(1 for r in results_log if r["status"] == PASS)
    n_fail = sum(1 for r in results_log if r["status"] == FAIL)
    print(f"RESULTADO: {n_pass} PASS, {n_fail} FAIL de {len(results_log)} pruebas")
    print("=" * 70)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
