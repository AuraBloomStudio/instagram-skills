#!/usr/bin/env python3
"""
test_costo_carrusel.py - Suite de pruebas SIN COSTO para la FABRICA RAPIDA de
carousel-gen: compuerta MAX_SLIDES=10 y el archivo obligatorio COSTO_CARRUSEL.txt (ver
SKILL.md, seccion "FABRICA RAPIDA").

REGLA PERMANENTE probada aqui: ningun carrusel puede superar 10 slides, y todo carrusel
real termina con un COSTO_CARRUSEL.txt que refleja costo/tiempo REALES (nunca
inventados) — cualquier dato no disponible se imprime como "N/D".

Este archivo NUNCA llama a Gemini ni a Kie AI. Opera sobre bundles temporales
(`tempfile.mkdtemp()`) y, para la compuerta MAX_SLIDES, un bundle bajo
outputs/bundles/__test-max-slides-gate__/ eliminado en `finally` (la compuerta rechaza
ANTES de generar nada, asi que nunca llama a Gemini ni escribe en Descargas).

Ejecutar con:
    python3 scripts/test_costo_carrusel.py
"""

import os
import io
import sys
import json
import shutil
import subprocess
import tempfile
import contextlib
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import (  # noqa: E402
    load_brief, build_costo_carrusel_text, save_costo_carrusel,
    COSTO_CARRUSEL_FILENAME, MAX_SLIDES, OUTPUTS_DIR,
)
from cost_tracker import CostTracker  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict[str, str]] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))


def _minimal_brief(num_slides: int) -> dict:
    return {
        "reference_image": {"local_path": "carousel/assets/viral-reference.png", "analysis": {}},
        "visual_dna": {},
        "carousel_type": "interactivo",
        "slide_count": {"recommended": min(num_slides, MAX_SLIDES), "confirmed": num_slides},
        "product": {"product_name": None, "purchase_url": None},
        "slides": [{"number": n} for n in range(1, num_slides + 1)],
    }


# ===========================================================================
# PARTE 1 — Compuerta MAX_SLIDES=10 (load_brief), sin tocar Gemini/Kie
# ===========================================================================

def test_1_diez_slides_pasa_la_compuerta():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_maxslides_"))
    try:
        (tmp / "brief.json").write_text(json.dumps(_minimal_brief(10)), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            load_brief(tmp)
        # Con solo "number" por slide, load_brief() puede rechazar mas adelante por
        # campos faltantes de slide propios de cada slide — lo que importa para ESTE
        # test es que NUNCA rechace por el motivo MAX_SLIDES (10 es el limite exacto,
        # no una violacion).
        ok = "máximo" not in buf.getvalue().lower()
        report("TEST 1", "10 slides nunca dispara el rechazo por límite de slides (10 = límite exacto, permitido)",
               ok, buf.getvalue()[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_2_once_slides_rechazado():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_maxslides_"))
    try:
        (tmp / "brief.json").write_text(json.dumps(_minimal_brief(11)), encoding="utf-8")
        brief = load_brief(tmp)
        ok = brief is None
        report("TEST 2", "11 slides -> load_brief() rechaza (devuelve None), nunca continua hacia Gemini/Kie", ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_3_cli_rechaza_11_slides_sin_llamar_a_gemini():
    bundle_id = "__test-max-slides-gate__"
    bundle_path = OUTPUTS_DIR / bundle_id
    try:
        bundle_path.mkdir(parents=True, exist_ok=True)
        (bundle_path / "brief.json").write_text(json.dumps(_minimal_brief(11)), encoding="utf-8")

        script = Path(__file__).parent / "generate-carousel-gemini.py"
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [sys.executable, str(script), bundle_id, "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, env=env,
        )
        ok = result.returncode != 0 and "máximo" in (result.stdout + result.stderr).lower()
        report("TEST 3", "CLI con 11 slides sale con error ANTES de get_api_key()/Gemini (compuerta real end-to-end)",
               ok, f"returncode={result.returncode} tail={(result.stdout + result.stderr)[-200:]!r}")
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)


# ===========================================================================
# PARTE 2 — COSTO_CARRUSEL.txt: contenido, costo real (nunca inventado), N/D honesto
# ===========================================================================

def test_4_costo_carrusel_se_crea_y_no_description_files():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_costo_"))
    try:
        tracker = CostTracker(tmp, "bundle-costo-test", 3, price_per_image_usd=0.0336)
        for n in (1, 2, 3):
            tracker.record(
                "bundle-costo-test", n, "gemini-3.1-flash-lite-image", "1K", "4:5",
                mode="direct", status="TEXT_QA_APPROVED", reused=False, retry_count=0,
                prompt_hash=f"hash-{n}",
                actual_usage={"prompt_token_count": 1000, "candidates_token_count": 300, "total_token_count": 1300},
            )
        tracker.mark_finished()

        save_costo_carrusel(
            tmp, "bundle-costo-test", tracker.summary.to_dict(),
            "gemini-3.1-flash-lite-image", "1K", "4:5", 3,
            {"status": "APPROVED", "slides_checked": 3, "slides_rejected": 0, "slides_regenerated": 0,
             "retries": 0, "text_errors_detected": 0, "text_errors_fixed": 0},
            str(tmp),
        )

        costo_file = tmp / COSTO_CARRUSEL_FILENAME
        exists = costo_file.exists()
        text = costo_file.read_text(encoding="utf-8") if exists else ""
        no_legacy = not any((tmp / n).exists() for n in ("description.txt", "cta.txt", "hashtags.txt"))
        has_real_cost = "$0.1008" in text or "0.1008" in text  # 3 imagenes x 0.0336
        has_tokens = "3000" in text and "900" in text  # 3x1000 input, 3x300 output
        ok = exists and no_legacy and has_real_cost and has_tokens
        report("TEST 4", "COSTO_CARRUSEL.txt se crea con costo/tokens REALES (nunca inventados); "
                          "no reaparecen description.txt/cta.txt/hashtags.txt",
               ok, f"exists={exists} has_real_cost={has_real_cost} has_tokens={has_tokens}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_5_sin_precio_configurado_costo_es_nd():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_costo_nd_"))
    try:
        tracker = CostTracker(tmp, "bundle-nd-test", 1, price_per_image_usd=0.0)
        tracker.record(
            "bundle-nd-test", 1, "gemini-3.1-flash-lite-image", "1K", "4:5",
            mode="direct", status="APPROVED", reused=False, retry_count=0, prompt_hash="h1",
        )
        tracker.mark_finished()
        text = build_costo_carrusel_text(
            "bundle-nd-test", tracker.summary.to_dict(), "gemini-3.1-flash-lite-image",
            "1K", "4:5", 1, None, str(tmp),
        )
        costo_line = text.split("COSTO TOTAL:\n")[1].split("\n")[0]
        ok = costo_line.strip() == "N/D"
        report("TEST 5", "Sin GEMINI_IMAGE_PRICE_PER_IMAGE configurado -> COSTO TOTAL es 'N/D', nunca un numero inventado",
               ok, f"costo_line={costo_line!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_6_sin_finished_at_tiempo_es_nd():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_costo_tiempo_"))
    try:
        tracker = CostTracker(tmp, "bundle-tiempo-test", 1, price_per_image_usd=0.0336)
        # NUNCA se llama mark_finished() -> run_finished_at debe quedar None.
        text = build_costo_carrusel_text(
            "bundle-tiempo-test", tracker.summary.to_dict(), "gemini-3.1-flash-lite-image",
            "1K", "4:5", 1, None, str(tmp),
        )
        duracion_line = text.split("Duración total:\n")[1].split("\n")[0]
        fin_line = text.split("Fin:\n")[1].split("\n")[0]
        ok = duracion_line.strip() == "N/D" and fin_line.strip() == "N/D"
        report("TEST 6", "Sin mark_finished() -> 'Fin'/'Duración total' son 'N/D', nunca un tiempo inventado",
               ok, f"fin={fin_line!r} duracion={duracion_line!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_7_regeneraciones_se_cuentan_correctamente():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_costo_retries_"))
    try:
        tracker = CostTracker(tmp, "bundle-retry-test", 2, price_per_image_usd=0.0336)
        # Slide 1: 1 intento exitoso. Slide 2: falla, se regenera 1 vez (FABRICA RAPIDA:
        # maximo 1 regeneracion), aprueba en el 2do intento -> 3 generaciones reales.
        tracker.record("bundle-retry-test", 1, "m", "1K", "4:5", mode="direct",
                        status="APPROVED", reused=False, retry_count=0, prompt_hash="h1")
        tracker.record("bundle-retry-test", 2, "m", "1K", "4:5", mode="direct",
                        status="RETRYING", reused=False, retry_count=0, prompt_hash="h2")
        tracker.record("bundle-retry-test", 2, "m", "1K", "4:5", mode="direct",
                        status="APPROVED", reused=False, retry_count=1, prompt_hash="h2")
        tracker.mark_finished()
        text = build_costo_carrusel_text(
            "bundle-retry-test", tracker.summary.to_dict(), "m", "1K", "4:5", 2, None, str(tmp),
        )
        total_gen_line = text.split("Total de generaciones reales:\n")[1].split("\n")[0].strip()
        retries_line = text.split("Retries:\n")[1].split("\n")[0].strip()
        regen_line = text.split("Slides regenerados:\n")[1].split("\n")[0].strip()
        ok = total_gen_line == "3" and retries_line == "1" and regen_line == "1"
        report("TEST 7", "1 slide regenerado 1 vez -> 3 generaciones reales, 1 retry, 1 slide regenerado (nunca infinito)",
               ok, f"total_gen={total_gen_line} retries={retries_line} regen={regen_line}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 70)
    print("AUDITORIA DE FABRICA RAPIDA — MAX_SLIDES + COSTO_CARRUSEL.txt — SIN GEMINI/KIE")
    print("=" * 70)
    for fn in [
        test_1_diez_slides_pasa_la_compuerta, test_2_once_slides_rechazado,
        test_3_cli_rechaza_11_slides_sin_llamar_a_gemini,
        test_4_costo_carrusel_se_crea_y_no_description_files,
        test_5_sin_precio_configurado_costo_es_nd,
        test_6_sin_finished_at_tiempo_es_nd,
        test_7_regeneraciones_se_cuentan_correctamente,
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
