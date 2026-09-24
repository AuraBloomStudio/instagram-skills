#!/usr/bin/env python3
"""
test_copy_final.py - Suite de pruebas SIN COSTO para el archivo unico de copy de
publicacion (COPY_FINAL.txt) de carousel-gen.

REGLA PERMANENTE probada aqui (ver SKILL.md, seccion "COPY_FINAL.txt — archivo unico de
copy de publicacion"): el copy de publicacion (descripcion, CTA, enlace de compra,
hashtags) se entrega UNICAMENTE en COPY_FINAL.txt. Los archivos independientes
description.txt / cta.txt / hashtags.txt ya NO se generan.

Este archivo NUNCA llama a Gemini ni a Kie AI, ni a ninguna API de red. Los tests operan
sobre archivos temporales locales (`tempfile.mkdtemp()`), nunca sobre bundles reales de
`outputs/bundles/`, con dos excepciones acotadas y limpiadas en `finally`:
  - TEST 8 crea un bundle temporal bajo `outputs/bundles/__test-copy-final-gate__/` para
    ejercitar la compuerta real del CLI (`--add-copy`) end-to-end, y lo elimina al terminar.
    Como la compuerta rechaza ANTES de guardar nada, nunca escribe en la carpeta real de
    Descargas de Windows.
Ningun bundle historico existente se lee, modifica ni elimina.

Ejecutar con:
    python3 scripts/test_copy_final.py
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import (  # noqa: E402
    build_copy_final_text, save_copy_deliverables, COPY_FINAL_FILENAME, OUTPUTS_DIR,
)

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict[str, str]] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))


# ===========================================================================
# PARTE 1 — build_copy_final_text() en memoria, sin tocar disco
# ===========================================================================

def test_1_secciones_obligatorias_en_orden():
    text = build_copy_final_text(
        description="Descripcion de prueba.",
        cta="CTA de prueba.",
        purchase_url="https://ejemplo.com/producto",
        hashtags=["#uno", "#dos", "#tres"],
    )
    order_ok = (
        text.index("DESCRIPCIÓN") < text.index("Descripcion de prueba.") <
        text.index("CTA") < text.index("CTA de prueba.") <
        text.index("ENLACE DE COMPRA") < text.index("https://ejemplo.com/producto") <
        text.index("HASHTAGS") < text.index("#uno")
    )
    report("TEST 1", "Las 4 secciones aparecen en el orden obligatorio: "
                      "DESCRIPCION -> CTA -> ENLACE DE COMPRA -> HASHTAGS", order_ok)


def test_2_url_exacta_sin_alteraciones():
    url = "https://tienda.example.com/libro?ref=ig&utm=carrusel"
    text = build_copy_final_text("d", "c", url, ["#x"])
    report("TEST 2", "La URL en ENLACE DE COMPRA es EXACTAMENTE purchase_url, sin recortes "
                      "ni normalizaciones", url in text and text.count(url) == 1)


def test_3_sin_producto_no_inventa_url():
    text = build_copy_final_text("d", "c", None, ["#x"])
    ok = "http" not in text and "sin producto asociado" in text
    report("TEST 3", "Sin purchase_url -> nunca inventa una URL, usa leyenda explicita", ok, text.split("ENLACE DE COMPRA")[1][:80])


def test_4_hashtags_unidos_por_espacio():
    text = build_copy_final_text("d", "c", None, ["#uno", "#dos", "#tres"])
    ok = "#uno #dos #tres" in text
    report("TEST 4", "Hashtags se unen con espacio simple, en el orden dado", ok)


# ===========================================================================
# PARTE 2 — save_copy_deliverables() sobre un bundle temporal (disco real,
# siempre bajo tempfile.mkdtemp(), nunca outputs/bundles/)
# ===========================================================================

def test_5_solo_copy_final_se_crea():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_copyfinal_"))
    try:
        save_copy_deliverables(
            tmp, description="Descripcion completa.", cta="CTA completo.",
            hashtags=["#a", "#b", "#c", "#d", "#e", "#f", "#g", "#h"],
            product="Libro X", purchase_url="https://ejemplo.com/x",
        )
        copy_final_exists = (tmp / COPY_FINAL_FILENAME).exists()
        legacy_absent = not any(
            (tmp / name).exists() for name in ("description.txt", "cta.txt", "hashtags.txt")
        )
        report("TEST 5", "save_copy_deliverables crea UNICAMENTE COPY_FINAL.txt — nunca "
                          "description.txt/cta.txt/hashtags.txt",
               copy_final_exists and legacy_absent,
               f"COPY_FINAL.txt={copy_final_exists} legacy_absent={legacy_absent}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_6_manifest_actualizado_correctamente():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_copyfinal_"))
    try:
        (tmp / "carousel").mkdir(parents=True, exist_ok=True)
        existing_manifest = {"carousel_type": "interactivo", "slides": [{"n": 1}]}
        manifest_file = tmp / "carousel" / "manifest.json"
        manifest_file.write_text(json.dumps(existing_manifest), encoding="utf-8")

        save_copy_deliverables(
            tmp, description="D", cta="C", hashtags=["#a"] * 8,
            product="Libro Y", purchase_url="https://ejemplo.com/y",
        )

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        ok = (
            manifest.get("copy_final_file") == COPY_FINAL_FILENAME
            and manifest.get("description") == "D"
            and manifest.get("cta") == "C"
            and manifest.get("product") == "Libro Y"
            and manifest.get("purchase_url") == "https://ejemplo.com/y"
            # el manifest preexistente (carousel_type, slides) no se pisa
            and manifest.get("carousel_type") == "interactivo"
            and manifest.get("slides") == [{"n": 1}]
        )
        report("TEST 6", "manifest.json se fusiona con copy_final_file + metadatos "
                          "estructurados, sin pisar campos existentes", ok, json.dumps(manifest))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_7_brief_json_nunca_tocado():
    tmp = Path(tempfile.mkdtemp(prefix="carouselgen_test_copyfinal_"))
    try:
        brief_file = tmp / "brief.json"
        original_brief = {"slides": [{"exact_text": "hola"}], "product": {"product_name": "Z"}}
        brief_file.write_text(json.dumps(original_brief), encoding="utf-8")

        save_copy_deliverables(
            tmp, description="D", cta="C", hashtags=["#a"] * 8,
            product="Z", purchase_url="https://ejemplo.com/z",
        )

        after = json.loads(brief_file.read_text(encoding="utf-8"))
        ok = after == original_brief
        report("TEST 7", "brief.json permanece exactamente igual (fuente de verdad "
                          "estructurada, nunca tocada por el copy final)", ok)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# PARTE 3 — compuerta real del CLI (--add-copy) end-to-end, bundle temporal
# limpiado en finally, CERO llamadas a Gemini/Kie (run_add_copy no las usa)
# ===========================================================================

def test_8_cli_rechaza_producto_sin_purchase_url():
    bundle_id = "__test-copy-final-gate__"
    bundle_path = OUTPUTS_DIR / bundle_id
    try:
        bundle_path.mkdir(parents=True, exist_ok=True)
        (bundle_path / "brief.json").write_text(json.dumps({
            "reference_image": {"local_path": "x", "analysis": {}},
            "visual_dna": {}, "carousel_type": "interactivo",
            "slide_count": {"recommended": 1, "confirmed": 1}, "slides": [],
        }), encoding="utf-8")

        copy_json = bundle_path / "copy_input.json"
        copy_json.write_text(json.dumps({
            "description": "D", "cta": "C", "hashtags": ["#a"] * 8,
            "product": "Producto Sin Link", "purchase_url": None,
        }), encoding="utf-8")

        script = Path(__file__).parent / "generate-carousel-gemini.py"
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [sys.executable, str(script), bundle_id, "--add-copy", str(copy_json)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30, env=env,
        )

        copy_final_created = (bundle_path / COPY_FINAL_FILENAME).exists()
        ok = result.returncode != 0 and not copy_final_created
        report("TEST 8", "CLI --add-copy RECHAZA (exit != 0) un producto sin purchase_url "
                          "y nunca crea COPY_FINAL.txt (compuerta de no finalizar incompleto)",
               ok, f"returncode={result.returncode} stdout_tail={result.stdout[-200:]!r}")
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)


def main():
    print("=" * 70)
    print("AUDITORIA DE COPY_FINAL.txt — SIN LLAMADAS A GEMINI, SIN LLAMADAS A KIE, $0")
    print("=" * 70)
    for fn in [
        test_1_secciones_obligatorias_en_orden, test_2_url_exacta_sin_alteraciones,
        test_3_sin_producto_no_inventa_url, test_4_hashtags_unidos_por_espacio,
        test_5_solo_copy_final_se_crea, test_6_manifest_actualizado_correctamente,
        test_7_brief_json_nunca_tocado, test_8_cli_rechaza_producto_sin_purchase_url,
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
