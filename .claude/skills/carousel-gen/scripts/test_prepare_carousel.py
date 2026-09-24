#!/usr/bin/env python3
"""
test_prepare_carousel.py — Tests para prepare_carousel.py.

Cubre:
  TEST 1 — pipeline_input: prepare_carousel produce brief.json + copy.json + pipeline_input.json
  TEST 2 — timing: T0 < T1 < ... < T8 (orden correcto, todos presentes)
  TEST 3 — bundle: directorios creados en outputs/bundles/<bundle_id>/carousel/assets/
  TEST 4 — referencia: --fake-reference copia el PNG correcto como viral-reference.png
  TEST 5 — source_text STOP: sin source_text el script devuelve exit code 1
  TEST 6 — products: product_name conocido → URL auto-resuelta desde products.json
  TEST 7 — brief campos computados: word_count / text_density / estimated_text_area / text_area_percentage / visual_balance
  TEST 8 — brief validacion: brief con campo faltante es rechazado (no escribe archivo)
  TEST 9 — concurrencia: dos prepare_carousel simultáneos escriben en bundles SEPARADOS sin colisión
  TEST 10 — tool calls: la preparación completa equivale a 1 Write + 1 Bash (no más) desde la perspectiva de Claude

NO ejecuta Gemini real ni genera imágenes.
"""

import contextlib
import io
import json
import shutil
import struct
import subprocess
import sys
import threading
import time
import tempfile
import zlib
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import OUTPUTS_DIR, REQUIRED_SLIDE_FIELDS  # noqa: E402
from prepare_carousel import (  # noqa: E402
    compute_slide_fields,
    validate_brief_in_memory,
    build_brief,
    resolve_product,
    _DENSITY_LOW_MAX,
    _DENSITY_MEDIUM_MAX,
    _TEXT_AREA_PCT,
)

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict] = []
PREPARE_SCRIPT = Path(__file__).parent / "prepare_carousel.py"


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    line = f"[{status}] {test_id}: {description}" + (f"\n   {detail}" if detail else "")
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))


def _tiny_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes([0, 5, 5, 5]))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _make_slide_decision(number: int, exact_text: str = "Texto del slide", text_placement: str = "lower_third_centered") -> Dict:
    """Slide con los 16 campos que Claude proporciona (sin los 5 computados)."""
    return {
        "number": number,
        "role": f"slide-{number}",
        "narrative_objective": f"Objetivo slide {number}",
        "message": f"Mensaje del slide {number}",
        "source_text_fragment": f"Fragmento literal {number}",
        "source_location": f"parrafo {number}",
        "exact_text": exact_text,
        "scene_description": f"Escena slide {number}",
        "composition": "full bleed BW",
        "visual_hierarchy": "1. Imagen 2. Texto",
        "text_placement": text_placement,
        "key_visual_elements": ["elemento"],
        "visual_dna_connection": f"Conexion DNA slide {number}",
        "uses_reference_image_directly": number == 1,
        "uses_product_mockup_directly": False,
        "text_break_reason": "natural_sentence_boundary",
    }


def _make_decisions(bundle_id: str, n_slides: int = 3, source_text: str = "Texto fuente completo del post viral") -> Dict:
    return {
        "bundle_id": bundle_id,
        "source_text": source_text,
        "carousel_type": "revelacion_progresiva",
        "visual_dna": {"slide_1_master_dna": {"color": "BW", "composicion": "full bleed"}},
        "reference_analysis": {
            "tema_mensaje": "test",
            "copy_estructura": "test",
            "emocion_predominante": "test",
            "elementos_impacto": "test",
        },
        "product": {"product_name": None, "purchase_url": None},
        "copy": {
            "description": "Descripcion del carrusel",
            "cta": "CTA de publicacion",
            "hashtags": ["#a", "#b", "#c", "#d", "#e", "#f", "#g", "#h"],
        },
        "slides": [_make_slide_decision(n) for n in range(1, n_slides + 1)],
    }


def _run_prepare(decisions: Dict, extra_args: List[str] = None, fake_ref_path: str = None) -> subprocess.CompletedProcess:
    """Escribe decisions a tempfile y ejecuta prepare_carousel.py."""
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    json.dump(decisions, tmp)
    tmp.close()
    try:
        cmd = [sys.executable, str(PREPARE_SCRIPT), tmp.name]
        if fake_ref_path:
            cmd += ["--fake-reference", fake_ref_path]
        if extra_args:
            cmd += extra_args
        env = dict(__import__("os").environ)
        env.pop("CLAUDE_CODE_SESSION_ID", None)  # Evitar extraer sesion real
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


# ============================================================
# TEST 1 — pipeline_input: brief.json + copy.json + pipeline_input.json
# ============================================================

def test_1_produce_todos_los_archivos():
    bundle_id = "__test-prepare-files__"
    bundle_path = OUTPUTS_DIR / bundle_id
    fake_ref = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fake_ref.write(_tiny_png())
    fake_ref.close()
    try:
        decisions = _make_decisions(bundle_id)
        result = _run_prepare(decisions, fake_ref_path=fake_ref.name)

        brief_exists = (bundle_path / "brief.json").exists()
        copy_exists = (bundle_path / "copy.json").exists()
        pi_exists = (bundle_path / "pipeline_input.json").exists()
        rc_ok = result.returncode == 0

        # Verificar que PREPARE_RESULT existe en stdout
        prepare_result_line = next((l for l in result.stdout.splitlines() if l.startswith("PREPARE_RESULT:")), None)
        parsed_result = None
        if prepare_result_line:
            try:
                parsed_result = json.loads(prepare_result_line[len("PREPARE_RESULT:"):])
            except json.JSONDecodeError:
                pass

        ok = rc_ok and brief_exists and copy_exists and pi_exists and parsed_result is not None
        report(
            "TEST 1",
            "prepare_carousel.py produce: brief.json + copy.json + pipeline_input.json + PREPARE_RESULT",
            ok,
            f"rc={result.returncode} brief={brief_exists} copy={copy_exists} "
            f"pipeline_input={pi_exists} PREPARE_RESULT={'OK' if parsed_result else 'MISSING'}\n"
            + (result.stderr[:200] if not rc_ok else ""),
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        Path(fake_ref.name).unlink(missing_ok=True)


# ============================================================
# TEST 2 — timing: T0 < T1 < ... < T8 presentes y en orden
# ============================================================

def test_2_timing_t0_a_t8():
    bundle_id = "__test-prepare-timing__"
    bundle_path = OUTPUTS_DIR / bundle_id
    fake_ref = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fake_ref.write(_tiny_png())
    fake_ref.close()
    try:
        decisions = _make_decisions(bundle_id)
        result = _run_prepare(decisions, fake_ref_path=fake_ref.name)

        pi_path = bundle_path / "pipeline_input.json"
        if not pi_path.exists():
            report("TEST 2", "T0-T8 en orden correcto", False, "pipeline_input.json no existe")
            return

        pi = json.loads(pi_path.read_text(encoding="utf-8"))
        timing = pi.get("timing") or {}
        required_keys = ["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]
        missing = [k for k in required_keys if k not in timing]
        if missing:
            report("TEST 2", "T0-T8 presentes en pipeline_input.json", False, f"Faltan: {missing}")
            return

        from datetime import datetime
        timestamps = [datetime.fromisoformat(timing[k]) for k in required_keys]
        # T0 <= T1 <= ... <= T8 (no estrictamente mayor porque pueden ser muy rapidos)
        in_order = all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))
        delta = (timestamps[-1] - timestamps[0]).total_seconds()
        ok = in_order and delta >= 0
        report(
            "TEST 2",
            "Timing T0-T8 todos presentes, en orden cronológico, delta >= 0",
            ok,
            f"delta_T0_T8={delta:.3f}s in_order={in_order} keys={list(timing.keys())}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        Path(fake_ref.name).unlink(missing_ok=True)


# ============================================================
# TEST 3 — bundle: directorios creados correctamente
# ============================================================

def test_3_bundle_directorios():
    bundle_id = "__test-prepare-dirs__"
    bundle_path = OUTPUTS_DIR / bundle_id
    fake_ref = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fake_ref.write(_tiny_png())
    fake_ref.close()
    try:
        # Asegurar que el bundle NO existe antes
        shutil.rmtree(bundle_path, ignore_errors=True)
        decisions = _make_decisions(bundle_id)
        result = _run_prepare(decisions, fake_ref_path=fake_ref.name)

        bundle_exists = bundle_path.exists()
        carousel_exists = (bundle_path / "carousel").exists()
        assets_exists = (bundle_path / "carousel" / "assets").exists()
        ok = result.returncode == 0 and bundle_exists and carousel_exists and assets_exists
        report(
            "TEST 3",
            "Bundle dir + carousel/ + assets/ creados automaticamente por prepare_carousel.py",
            ok,
            f"rc={result.returncode} bundle={bundle_exists} carousel={carousel_exists} assets={assets_exists}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        Path(fake_ref.name).unlink(missing_ok=True)


# ============================================================
# TEST 4 — referencia: --fake-reference copia correctamente
# ============================================================

def test_4_fake_reference_copiada():
    bundle_id = "__test-prepare-ref__"
    bundle_path = OUTPUTS_DIR / bundle_id
    fake_ref = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fake_png = _tiny_png()
    fake_ref.write(fake_png)
    fake_ref.close()
    try:
        decisions = _make_decisions(bundle_id)
        result = _run_prepare(decisions, fake_ref_path=fake_ref.name)

        ref_dest = bundle_path / "carousel" / "assets" / "viral-reference.png"
        ref_exists = ref_dest.exists()
        ref_bytes_ok = ref_dest.read_bytes() == fake_png if ref_exists else False
        ok = result.returncode == 0 and ref_exists and ref_bytes_ok
        report(
            "TEST 4",
            "--fake-reference copia el PNG correcto como viral-reference.png en bundle/carousel/assets/",
            ok,
            f"rc={result.returncode} ref_exists={ref_exists} bytes_match={ref_bytes_ok}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        Path(fake_ref.name).unlink(missing_ok=True)


# ============================================================
# TEST 5 — source_text STOP: sin source_text → exit 1
# ============================================================

def test_5_sin_source_text_stop():
    bundle_id = "__test-prepare-stop__"
    bundle_path = OUTPUTS_DIR / bundle_id
    fake_ref = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fake_ref.write(_tiny_png())
    fake_ref.close()
    try:
        decisions = _make_decisions(bundle_id)
        decisions["source_text"] = ""   # Vacío → STOP
        result = _run_prepare(decisions, fake_ref_path=fake_ref.name)

        # No debe haber escrito brief.json
        brief_written = (bundle_path / "brief.json").exists()
        ok = result.returncode == 1 and not brief_written and "STOP" in (result.stdout + result.stderr)
        report(
            "TEST 5",
            "source_text vacío → exit 1 con 'STOP', no escribe brief.json",
            ok,
            f"rc={result.returncode} brief_written={brief_written} "
            f"STOP_in_output={'STOP' in result.stdout + result.stderr}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        Path(fake_ref.name).unlink(missing_ok=True)


# ============================================================
# TEST 6 — products: product_name conocido → URL auto-resuelta
# ============================================================

def test_6_product_url_resuelta():
    """
    Si product_name coincide con una entrada en products.json y purchase_url es None,
    prepare_carousel.py debe resolver la URL automaticamente.
    """
    from carousel_common import OUTPUTS_DIR as _od
    products_path = Path(__file__).parent.parent / "products.json"
    if not products_path.exists():
        report("TEST 6", "URL de producto resuelta desde products.json", False,
               "products.json no existe — test saltado")
        return

    db = json.loads(products_path.read_text(encoding="utf-8"))
    known_products = db.get("products", {})
    if not known_products:
        report("TEST 6", "URL de producto resuelta desde products.json", False,
               "products.json no tiene entradas — test saltado")
        return

    product_name, product_entry = next(iter(known_products.items()))
    expected_url = product_entry.get("purchase_url", "")

    # Verificar resolve_product directamente (unit test, sin subproceso)
    resolved = resolve_product({"product_name": product_name, "purchase_url": None})
    ok = resolved.get("purchase_url") == expected_url and resolved.get("product_name") == product_name
    report(
        "TEST 6",
        f"resolve_product('{product_name[:40]}', url=None) resuelve URL desde products.json",
        ok,
        f"resolved_url={resolved.get('purchase_url', '')[:60]} expected={expected_url[:60]}",
    )


# ============================================================
# TEST 7 — campos computados correctos
# ============================================================

def test_7_campos_computados():
    """
    compute_slide_fields() calcula correctamente:
    word_count, text_density, estimated_text_area, text_area_percentage, visual_balance
    """
    cases = [
        # (exact_text, text_placement, expected_wc, expected_density, expected_pct, expected_balance)
        ("Umbral del dolor",           "lower_third_centered", 3,  "LOW",    15, "balanced"),
        ("Palabra " * 10,              "upper_third_centered", 10, "MEDIUM", 25, "balanced"),
        ("Palabra " * 20,              "center",               20, "HIGH",   40, "text_heavy"),
        ("Solo ocho palabras exactas aqui con las suficientes", "lower_half", 8, "LOW", 15, "balanced"),
        ("Nueve palabras en este texto exactamente aquí con todo",    "center", 9, "MEDIUM", 25, "balanced"),
    ]

    all_ok = True
    detail_parts = []
    for exact_text, text_placement, exp_wc, exp_density, exp_pct, exp_balance in cases:
        slide_in = _make_slide_decision(1, exact_text.strip(), text_placement)
        result = compute_slide_fields(slide_in)
        wc_ok = result["word_count"] == exp_wc
        den_ok = result["text_density"] == exp_density
        eta_ok = result["estimated_text_area"] == text_placement
        pct_ok = result["text_area_percentage"] == exp_pct
        bal_ok = result["visual_balance"] == exp_balance
        case_ok = wc_ok and den_ok and eta_ok and pct_ok and bal_ok
        if not case_ok:
            all_ok = False
        detail_parts.append(
            f"wc={result['word_count']}(exp={exp_wc}) den={result['text_density']}(exp={exp_density}) "
            f"pct={result['text_area_percentage']}(exp={exp_pct}) bal={result['visual_balance']}(exp={exp_balance})"
        )

    report(
        "TEST 7",
        "compute_slide_fields() calcula word_count, text_density, estimated_text_area, "
        "text_area_percentage, visual_balance correctamente para LOW/MEDIUM/HIGH",
        all_ok,
        "\n   ".join(detail_parts),
    )


# ============================================================
# TEST 8 — validacion: campo faltante rechaza el brief
# ============================================================

def test_8_campo_faltante_rechazado():
    """
    validate_brief_in_memory() rechaza un brief con un campo faltante en los slides.
    """
    timing = {k: "2026-01-01T10:00:00" for k in ["T0","T1","T2","T3","T4","T5","T6","T7","T8"]}
    tmp = Path(tempfile.mkdtemp(prefix="test_prepare_validate_"))
    try:
        # Brief con slide correcto → OK
        decisions_ok = _make_decisions("__test-validate-ok__", n_slides=1)
        bundle_path_ok = tmp / "__test-validate-ok__"
        bundle_path_ok.mkdir()
        (bundle_path_ok / "carousel" / "assets").mkdir(parents=True)
        brief_ok = build_brief(decisions_ok, "__test-validate-ok__", bundle_path_ok, timing)
        errors_ok = validate_brief_in_memory(brief_ok)

        # Brief con campo faltante → FAIL
        decisions_bad = _make_decisions("__test-validate-bad__", n_slides=1)
        del decisions_bad["slides"][0]["role"]  # Eliminar campo requerido
        bundle_path_bad = tmp / "__test-validate-bad__"
        bundle_path_bad.mkdir()
        (bundle_path_bad / "carousel" / "assets").mkdir(parents=True)
        brief_bad = build_brief(decisions_bad, "__test-validate-bad__", bundle_path_bad, timing)
        errors_bad = validate_brief_in_memory(brief_bad)

        ok = len(errors_ok) == 0 and len(errors_bad) > 0 and any("role" in e for e in errors_bad)
        report(
            "TEST 8",
            "validate_brief_in_memory(): brief completo → 0 errores; brief con campo faltante → rechazado",
            ok,
            f"errors_ok={errors_ok} errors_bad={errors_bad}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 9 — concurrencia: dos prepare_carousel simultáneos sin colisión
# ============================================================

def test_9_concurrencia_bundles_separados():
    """
    Dos ejecuciones simultáneas de prepare_carousel.py con bundle_ids distintos
    deben escribir en carpetas separadas sin corromperse mutuamente.
    """
    bundle_a = "__test-prepare-concurrent-A__"
    bundle_b = "__test-prepare-concurrent-B__"
    bundle_path_a = OUTPUTS_DIR / bundle_a
    bundle_path_b = OUTPUTS_DIR / bundle_b
    fake_ref = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fake_ref.write(_tiny_png())
    fake_ref.close()

    results_concurrent: List[Dict] = []
    lock = threading.Lock()

    def run_one(bundle_id: str, n_slides: int) -> None:
        decisions = _make_decisions(bundle_id, n_slides=n_slides)
        proc = _run_prepare(decisions, fake_ref_path=fake_ref.name)
        with lock:
            results_concurrent.append({"bundle_id": bundle_id, "rc": proc.returncode})

    try:
        t_a = threading.Thread(target=run_one, args=(bundle_a, 3))
        t_b = threading.Thread(target=run_one, args=(bundle_b, 5))
        t_a.start()
        t_b.start()
        t_a.join(timeout=60)
        t_b.join(timeout=60)

        both_ok = all(r["rc"] == 0 for r in results_concurrent)
        a_brief = bundle_path_a / "brief.json"
        b_brief = bundle_path_b / "brief.json"
        a_slides = len(json.loads(a_brief.read_text()).get("slides", [])) if a_brief.exists() else 0
        b_slides = len(json.loads(b_brief.read_text()).get("slides", [])) if b_brief.exists() else 0
        # Cada bundle tiene sus propios slides, sin mezclar
        slides_ok = a_slides == 3 and b_slides == 5
        ok = both_ok and slides_ok
        report(
            "TEST 9",
            "Dos prepare_carousel simultáneos con bundle_ids distintos no colisionan "
            "(slides_A=3 y slides_B=5 correctos en cada bundle)",
            ok,
            f"rcs={[r['rc'] for r in results_concurrent]} slides_A={a_slides} slides_B={b_slides}",
        )
    finally:
        shutil.rmtree(bundle_path_a, ignore_errors=True)
        shutil.rmtree(bundle_path_b, ignore_errors=True)
        Path(fake_ref.name).unlink(missing_ok=True)


# ============================================================
# TEST 10 — tool calls equivalentes: 1 Write + 1 Bash desde Claude
# ============================================================

def test_10_reduccion_tool_calls():
    """
    Verifica que prepare_carousel.py hace TODO el trabajo determinista internamente
    sin requerir tool calls adicionales de Claude:
    - Crea bundle (no mkdir de Claude)
    - Extrae/copia referencia (no save_reference_image separado)
    - Carga products.json (no Read de Claude)
    - Valida brief (no script de validacion separado)
    - Escribe brief.json (no Write de Claude)
    - Escribe copy.json (no Write de Claude)
    - Escribe pipeline_input.json (no Write de Claude)

    Todo esto queda encapsulado en 1 subprocess (equivale a 1 Bash de Claude).
    Claude solo necesita: 1 Write (decisions.json) + 1 Bash (prepare_carousel.py).
    """
    bundle_id = "__test-prepare-toolcalls__"
    bundle_path = OUTPUTS_DIR / bundle_id
    fake_ref = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fake_ref.write(_tiny_png())
    fake_ref.close()
    try:
        decisions = _make_decisions(bundle_id, n_slides=10)
        result = _run_prepare(decisions, fake_ref_path=fake_ref.name)

        # Verificar que TODOS los artefactos existen (ninguno requirió tool call adicional)
        artifacts = {
            "bundle_dir":       bundle_path.exists(),
            "carousel_dir":     (bundle_path / "carousel").exists(),
            "assets_dir":       (bundle_path / "carousel" / "assets").exists(),
            "viral_reference":  (bundle_path / "carousel" / "assets" / "viral-reference.png").exists(),
            "brief.json":       (bundle_path / "brief.json").exists(),
            "copy.json":        (bundle_path / "copy.json").exists(),
            "pipeline_input":   (bundle_path / "pipeline_input.json").exists(),
        }
        all_present = all(artifacts.values())

        # Verificar que el brief tiene 10 slides con todos los 21 campos (computados incluidos)
        if (bundle_path / "brief.json").exists():
            brief = json.loads((bundle_path / "brief.json").read_text())
            slides = brief.get("slides", [])
            slides_count_ok = len(slides) == 10
            all_fields_ok = all(
                all(f in s for f in REQUIRED_SLIDE_FIELDS)
                for s in slides
            )
        else:
            slides_count_ok = False
            all_fields_ok = False

        ok = result.returncode == 0 and all_present and slides_count_ok and all_fields_ok
        missing = [k for k, v in artifacts.items() if not v]
        report(
            "TEST 10",
            "prepare_carousel.py encapsula TODA la preparacion determinista en 1 subprocess: "
            "7 artefactos creados (dirs, ref, brief, copy, pipeline_input), "
            f"10 slides con los {len(REQUIRED_SLIDE_FIELDS)} REQUIRED_SLIDE_FIELDS",
            ok,
            f"rc={result.returncode} missing={missing} slides={len(slides) if 'slides' in dir() else 'N/A'} "
            f"all_fields={all_fields_ok}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        Path(fake_ref.name).unlink(missing_ok=True)


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 70)
    print("TEST SUITE — prepare_carousel.py (SIN GEMINI REAL)")
    print("=" * 70)
    for fn in [
        test_1_produce_todos_los_archivos,
        test_2_timing_t0_a_t8,
        test_3_bundle_directorios,
        test_4_fake_reference_copiada,
        test_5_sin_source_text_stop,
        test_6_product_url_resuelta,
        test_7_campos_computados,
        test_8_campo_faltante_rechazado,
        test_9_concurrencia_bundles_separados,
        test_10_reduccion_tool_calls,
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
