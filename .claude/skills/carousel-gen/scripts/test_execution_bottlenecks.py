#!/usr/bin/env python3
"""
test_execution_bottlenecks.py - Suite de pruebas SIN COSTO para la auditoria de
cuellos de botella de ejecucion (2026-09-17, carrusel "abuela-materna"). Cubre
EXCLUSIVAMENTE los puntos de esa auditoria (ver SKILL.md "FABRICA RAPIDA" / "COSTO
REAL" / "CRONOMETRO GLOBAL REAL" / "TEXT QA"):

  1. Si la imagen de referencia no esta disponible en el bundle, el script falla
     INMEDIATAMENTE (rapido) con un mensaje claro y NUNCA fabrica un placeholder.
  2. Un hallazgo de Text QA UNCERTAIN (OCR dudoso) NUNCA dispara una regeneracion.
  3. Los slides 2-10 se generan en paralelo (direct_generator.generate_direct).
  4. El Text QA (OCR) de slides independientes de una misma tanda corre en paralelo
     (generate-carousel-gemini.process_slides), nunca slide-por-slide.
  5. El script nunca lanza UnicodeEncodeError bajo la codepage por defecto de Windows
     (cp1252), sin depender de PYTHONIOENCODING.
  6. Una sola invocacion (--copy-json) puede producir el paquete COMPLETO (imagenes +
     COPY_FINAL.txt + COSTO_CARRUSEL.txt) sin una segunda invocacion --add-copy.
  7. cost_tracker cuenta TODAS las generaciones reales (incluyendo retries/
     regeneraciones) como billable, y NUNCA cuenta llamadas que no produjeron imagen.
  8. --add-copy (una invocacion nueva, con un CostTracker reconstruido desde disco)
     NUNCA pone los contadores agregados de cost_log.json en cero.
  9. El cronometro global (phase_seconds) mide preparacion/referencia/brief a partir de
     marcas de tiempo de brief.json, y el "inicio" real del pipeline puede fijarse
     ANTES de la primera llamada a Gemini.

Este archivo NUNCA llama a Gemini ni a Kie AI (usa FakeGeminiClient/--fake-provider y
clientes de prueba locales). Ejecutar con:
    python3 scripts/test_execution_bottlenecks.py
"""

import os
import sys
import json
import time
import shutil
import struct
import zlib
import tempfile
import subprocess
import threading
from argparse import Namespace
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import OUTPUTS_DIR  # noqa: E402
from cost_tracker import CostTracker  # noqa: E402
from cache_manager import CacheManager  # noqa: E402
from direct_generator import GenerationTask, generate_direct  # noqa: E402
from gemini_client import GeminiImageResult  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict[str, str]] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))


def _load_gemini_main():
    """Carga generate-carousel-gemini.py como modulo (no importable con `import`
    normal por el guion en el nombre) — mismo patron que test_text_qa.py."""
    import importlib.util
    path = Path(__file__).parent / "generate-carousel-gemini.py"
    spec = importlib.util.spec_from_file_location("gemini_main_under_test_bottlenecks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tiny_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes([0, 5, 5, 5]))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _make_slide(number: int, exact_text: str = "texto") -> dict:
    return {
        "number": number, "role": f"slide-{number}", "narrative_objective": "o", "message": "m",
        "source_text_fragment": "f", "source_location": "l", "exact_text": exact_text,
        "scene_description": "s", "composition": "c", "visual_hierarchy": "v", "text_placement": "p",
        "key_visual_elements": [], "visual_dna_connection": "d", "connects_prev": None, "connects_next": None,
        "uses_reference_image_directly": False, "uses_product_mockup_directly": False,
    }


class _FakeConfig:
    image_model = "gemini-3.1-flash-lite-image"
    aspect_ratio = "4:5"
    image_size = "1K"
    max_retries = 1
    text_qa_enabled = True
    economy_mode = True
    batch_enabled = False
    price_per_image_usd = 0.0336


# ===========================================================================
# 1 — Referencia visual: falla rapido, sin placeholder, ante attachment ausente
# ===========================================================================

def test_1_referencia_ausente_falla_rapido_sin_placeholder():
    bundle_id = "__test-missing-reference__"
    bundle_path = OUTPUTS_DIR / bundle_id
    try:
        (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
        brief = {
            "reference_image": {"local_path": "carousel/assets/viral-reference.png", "analysis": {}},
            "visual_dna": {}, "carousel_type": "interactivo",
            "slide_count": {"recommended": 1, "confirmed": 1},
            "product": {"product_name": None, "purchase_url": None},
            "slides": [dict(_make_slide(1), **{
                "word_count": 1, "text_density": "LOW", "estimated_text_area": "c",
                "text_area_percentage": 10, "visual_balance": "balanced",
                "text_break_reason": "natural_sentence_boundary",
            })],
        }
        (bundle_path / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
        # OJO: nunca se crea carousel/assets/viral-reference.png -> simula un attachment
        # que nunca se pudo resolver (ver SKILL.md "REFERENCIA VISUAL").

        mod = _load_gemini_main()
        args = Namespace(
            bundle_id=bundle_id, dry_run=False, fake_provider=True, fake_fail_slides=None,
            regenerate_slides=None, force_direct=False, force_batch=False,
            copy_json=None,
        )
        started = time.time()
        rc = mod.run_generation(args)
        elapsed = time.time() - started

        placeholder_created = (bundle_path / "carousel" / "assets" / "viral-reference.png").exists()
        ok = rc == 1 and not placeholder_created and elapsed < 5.0
        report("TEST 1", "Referencia visual ausente -> falla rapido (rc=1), nunca fabrica un placeholder",
               ok, f"rc={rc} elapsed={elapsed:.2f}s placeholder_created={placeholder_created}")
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)


# ===========================================================================
# 2 — TEXT QA: UNCERTAIN nunca regenera
# ===========================================================================

def test_2_uncertain_nunca_regenera():
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="bottlenecks_uncertain_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()

        class _OneShotClient:
            def __init__(self):
                self.attempt_count: Dict[int, int] = {}

            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                self.attempt_count[_slide_number] = self.attempt_count.get(_slide_number, 0) + 1
                return GeminiImageResult(success=True, image_bytes=_tiny_png(), usage_metadata=None)

        client = _OneShotClient()
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-uncertain-bundle", 1, 0.0336)
        config = _FakeConfig()
        slide = _make_slide(1, "texto esperado del slide")

        # Simula un OCR que SI detecta una diferencia (CRITICAL por defecto) pero con
        # confianza baja -> debe degradarse a UNCERTAIN y aprobar sin regenerar.
        from text_qa import TextQAResult, _OCR_UNCERTAIN_CONFIDENCE_THRESHOLD

        def _fake_run_text_qa(image_path, expected_text, critical_phrases=None, authorized_extra_tokens=None):
            base = TextQAResult(
                approved=False, reason="TEXT_CORRUPTION", detail="simulado",
                expected_text_hash="e", rendered_text_hash="r",
            )
            with patch("text_qa.extract_ocr_confidence", return_value=_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD - 10):
                from text_qa import _apply_ocr_confidence_downgrade
                return _apply_ocr_confidence_downgrade(base, image_path)

        with patch.object(mod, "run_text_qa", side_effect=_fake_run_text_qa):
            final_status = mod.process_slides(
                [slide], {}, "la-gran-noticia", config, client, cache, cost_tracker,
                "test-uncertain-bundle", carousel_dir, None, None, None, force_mode="direct",
            )

        attempts = client.attempt_count.get(1, 0)
        ok = attempts == 1 and final_status.get(1) in ("APPROVED", "TEXT_QA_APPROVED")
        report("TEST 2", "Text QA UNCERTAIN (OCR dudoso) NUNCA regenera -- 1 sola llamada, aprueba igual",
               ok, f"attempts={attempts} status={final_status}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# 3 — Generacion paralela de slides 2-10 (direct_generator)
# ===========================================================================

def test_3_generacion_slides_en_paralelo():
    delay = 0.25
    lock = threading.Lock()
    intervals: List[tuple] = []

    class _SleepyClient:
        def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
            start = time.time()
            time.sleep(delay)
            end = time.time()
            with lock:
                intervals.append((start, end))
            return GeminiImageResult(success=True, image_bytes=_tiny_png(), usage_metadata=None)

    tasks = [GenerationTask(slide_number=n, prompt=f"p{n}") for n in range(2, 8)]  # 6 tasks
    client = _SleepyClient()

    started = time.time()
    results = generate_direct(client, tasks)
    elapsed = time.time() - started

    serial_would_be = delay * len(tasks)
    # Prueba de solapamiento REAL (no solo tiempo total bajo): al menos un intervalo
    # empieza antes de que otro haya terminado.
    overlap = any(
        a_start < b_end and b_start < a_end
        for i, (a_start, a_end) in enumerate(intervals)
        for j, (b_start, b_end) in enumerate(intervals)
        if i != j
    )
    all_ok = all(r.success for r in results.values())
    ok = elapsed < (serial_would_be * 0.7) and overlap and all_ok and len(results) == len(tasks)
    report("TEST 3", "Slides 2-10 se generan en paralelo (nunca uno-por-uno, solapamiento real medido)",
           ok, f"elapsed={elapsed:.2f}s serial_would_be={serial_would_be:.2f}s overlap={overlap}")


# ===========================================================================
# 4 — Text QA / OCR de una misma tanda corre en paralelo (process_slides)
# ===========================================================================

def test_4_text_qa_de_la_tanda_en_paralelo():
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="bottlenecks_qa_parallel_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()

        class _FastClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                return GeminiImageResult(success=True, image_bytes=_tiny_png(), usage_metadata=None)

        delay = 0.25
        lock = threading.Lock()
        intervals: List[tuple] = []

        def _slow_save_image_and_qa(carousel_dir_, slide_number, image_bytes, config, expected_text, critical_phrases=None, authorized_extra_tokens=None):
            start = time.time()
            time.sleep(delay)
            end = time.time()
            with lock:
                intervals.append((start, end))
            out_path = carousel_dir_ / f"carousel-{slide_number:02d}.png"
            out_path.write_bytes(image_bytes)
            return True, out_path, "OK_SIMULADO", None

        n_slides = 5
        slides = [_make_slide(n) for n in range(1, n_slides + 1)]
        client = _FastClient()
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-qa-parallel-bundle", n_slides, 0.0336)
        config = _FakeConfig()

        with patch.object(mod, "save_image_and_qa", side_effect=_slow_save_image_and_qa):
            started = time.time()
            final_status = mod.process_slides(
                slides, {}, "la-gran-noticia", config, client, cache, cost_tracker,
                "test-qa-parallel-bundle", carousel_dir, None, None, None, force_mode="direct",
            )
            elapsed = time.time() - started

        serial_would_be = delay * n_slides
        overlap = any(
            a_start < b_end and b_start < a_end
            for i, (a_start, a_end) in enumerate(intervals)
            for j, (b_start, b_end) in enumerate(intervals)
            if i != j
        )
        all_approved = all(v in ("APPROVED", "TEXT_QA_APPROVED") for v in final_status.values())
        ok = elapsed < (serial_would_be * 0.7) and overlap and all_approved
        report("TEST 4", "Text QA/OCR de slides independientes de la misma tanda corre en paralelo "
                          "(nunca slide-por-slide)",
               ok, f"elapsed={elapsed:.2f}s serial_would_be={serial_would_be:.2f}s overlap={overlap} status={final_status}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# 5 — UTF-8/Windows: nunca UnicodeEncodeError bajo cp1252, sin PYTHONIOENCODING
# ===========================================================================

def test_5_sin_unicode_encode_error_en_cp1252():
    bundle_id = "__test-cp1252-smoke__"
    bundle_path = OUTPUTS_DIR / bundle_id
    try:
        (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
        (bundle_path / "carousel" / "assets" / "viral-reference.png").write_bytes(_tiny_png())
        slide = dict(_make_slide(1, "texto de prueba"), **{
            "word_count": 3, "text_density": "LOW", "estimated_text_area": "c",
            "text_area_percentage": 10, "visual_balance": "balanced",
            "text_break_reason": "natural_sentence_boundary", "uses_reference_image_directly": True,
        })
        brief = {
            "reference_image": {"local_path": "carousel/assets/viral-reference.png", "analysis": {}},
            "visual_dna": {"slide_1_master_dna": {}}, "carousel_type": "interactivo",
            "slide_count": {"recommended": 1, "confirmed": 1},
            "product": {"product_name": None, "purchase_url": None},
            "slides": [slide],
        }
        (bundle_path / "brief.json").write_text(json.dumps(brief), encoding="utf-8")

        script = Path(__file__).parent / "generate-carousel-gemini.py"
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)  # ver SKILL.md "UTF-8 WINDOWS": nunca debe depender de esto
        env["PYTHONUTF8"] = "0"
        result = subprocess.run(
            [sys.executable, str(script), bundle_id, "--fake-provider"],
            capture_output=True, text=True, encoding="cp1252", errors="strict",
            timeout=60, env=env,
        )
        combined = (result.stdout or "") + (result.stderr or "")
        ok = result.returncode == 0 and "UnicodeEncodeError" not in combined
        report("TEST 5", "El script nunca lanza UnicodeEncodeError bajo cp1252, sin PYTHONIOENCODING",
               ok, f"returncode={result.returncode} tiene_unicode_error={'UnicodeEncodeError' in combined}")
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        shutil.rmtree(Path.home() / "Downloads" / "Carruseles Carousel-Gen" / bundle_id, ignore_errors=True)


# ===========================================================================
# 6 — UNA SOLA EJECUCION: --copy-json completa el paquete sin una 2da invocacion
# ===========================================================================

def test_6_una_sola_ejecucion_con_copy_json():
    bundle_id = "__test-single-run__"
    bundle_path = OUTPUTS_DIR / bundle_id
    try:
        (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
        (bundle_path / "carousel" / "assets" / "viral-reference.png").write_bytes(_tiny_png())
        slide = dict(_make_slide(1, "texto de prueba"), **{
            "word_count": 3, "text_density": "LOW", "estimated_text_area": "c",
            "text_area_percentage": 10, "visual_balance": "balanced",
            "text_break_reason": "natural_sentence_boundary", "uses_reference_image_directly": True,
        })
        brief = {
            "reference_image": {"local_path": "carousel/assets/viral-reference.png", "analysis": {}},
            "visual_dna": {"slide_1_master_dna": {}}, "carousel_type": "interactivo",
            "slide_count": {"recommended": 1, "confirmed": 1},
            "product": {"product_name": None, "purchase_url": None},
            "slides": [slide],
        }
        (bundle_path / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
        copy_json_path = bundle_path / "copy.json"
        copy_json_path.write_text(json.dumps({
            "description": "Descripcion", "cta": "CTA",
            "hashtags": ["#a", "#b", "#c", "#d", "#e", "#f", "#g", "#h"],
        }), encoding="utf-8")

        mod = _load_gemini_main()
        args = Namespace(
            bundle_id=bundle_id, dry_run=False, fake_provider=True, fake_fail_slides=None,
            regenerate_slides=None, force_direct=False, force_batch=False,
            copy_json=str(copy_json_path),
        )
        rc = mod.run_generation(args)

        copy_final_exists = (bundle_path / "COPY_FINAL.txt").exists()
        costo_exists = (bundle_path / "COSTO_CARRUSEL.txt").exists()
        image_exists = (bundle_path / "carousel" / "carousel-01.png").exists()
        ok = rc == 0 and copy_final_exists and costo_exists and image_exists
        report("TEST 6", "--copy-json en la corrida principal produce el paquete COMPLETO en UNA sola invocacion",
               ok, f"rc={rc} copy_final={copy_final_exists} costo={costo_exists} imagen={image_exists}")
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        shutil.rmtree(Path.home() / "Downloads" / "Carruseles Carousel-Gen" / bundle_id, ignore_errors=True)


# ===========================================================================
# 7 — cost_tracker: cuenta TODAS las generaciones reales, nunca las que no
#     produjeron imagen
# ===========================================================================

def test_7_costo_cuenta_todas_las_generaciones_reales():
    tmp = Path(tempfile.mkdtemp(prefix="bottlenecks_cost_"))
    try:
        tracker = CostTracker(tmp, "bundle-billable-test", 1, price_per_image_usd=0.0336)
        # Intento 1: fallo de RED (nunca produjo imagen) -> NO billable, NO cuenta.
        tracker.record("bundle-billable-test", 1, "m", "1K", "4:5", mode="direct",
                        status="RETRYING", reused=False, retry_count=0, prompt_hash="h1", billable=False)
        # Intento 2 (retry): SI produjo imagen pero el QA la rechazo -> billable, cuenta.
        tracker.record("bundle-billable-test", 1, "m", "1K", "4:5", mode="direct",
                        status="TEXT_QA_REGENERATING", reused=False, retry_count=1, prompt_hash="h1", billable=True)
        # Intento 3 (2do retry, dentro del presupuesto en este escenario de prueba):
        # produjo imagen y aprobo -> billable, cuenta.
        tracker.record("bundle-billable-test", 1, "m", "1K", "4:5", mode="direct",
                        status="TEXT_QA_APPROVED", reused=False, retry_count=2, prompt_hash="h1", billable=True)

        s = tracker.summary
        # 3 entradas en total, pero solo 2 fueron billable (produjeron imagen real).
        ok = (
            len(s.entries) == 3 and s.generated == 2 and s.retries == 2
            and round(s.estimated_cost_usd, 4) == round(0.0336 * 2, 4)
        )
        report("TEST 7", "cost_tracker cuenta generacion inicial + retries/regeneraciones reales, "
                          "nunca las llamadas que no produjeron imagen",
               ok, f"entries={len(s.entries)} generated={s.generated} retries={s.retries} cost={s.estimated_cost_usd}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# 8 — --add-copy (CostTracker reconstruido) NUNCA pone los contadores en cero
# ===========================================================================

def test_8_add_copy_no_pone_contadores_en_cero():
    tmp = Path(tempfile.mkdtemp(prefix="bottlenecks_addcopy_"))
    try:
        # Corrida 1 (simula run_generation): 3 generaciones reales.
        tracker1 = CostTracker(tmp, "bundle-addcopy-test", 3, price_per_image_usd=0.0336)
        for n in (1, 2, 3):
            tracker1.record("bundle-addcopy-test", n, "m", "1K", "4:5", mode="direct",
                             status="TEXT_QA_APPROVED", reused=False, retry_count=0, prompt_hash=f"h{n}")
        tracker1.mark_finished()
        cost_after_run1 = tracker1.summary.estimated_cost_usd
        generated_after_run1 = tracker1.summary.generated

        # Corrida 2 (simula --add-copy en un proceso NUEVO): un CostTracker
        # RECONSTRUIDO desde cero, que recarga cost_log.json ya escrito por la corrida 1
        # y NO agrega ninguna entrada nueva (--add-copy nunca genera imagenes).
        tracker2 = CostTracker(tmp, "bundle-addcopy-test", 3, price_per_image_usd=0.0336)
        tracker2.mark_finished()

        ok = (
            cost_after_run1 > 0 and generated_after_run1 == 3
            and tracker2.summary.generated == 3
            and round(tracker2.summary.estimated_cost_usd, 4) == round(cost_after_run1, 4)
        )
        report("TEST 8", "Un CostTracker reconstruido (--add-copy) preserva generated/costo reales, nunca los pone en 0",
               ok, f"run1(generated={generated_after_run1}, cost={cost_after_run1}) "
                   f"run2(generated={tracker2.summary.generated}, cost={tracker2.summary.estimated_cost_usd})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
# 9 — Cronometro global: preparacion/referencia/brief desde brief.json["timing"],
#     e inicio del pipeline puede fijarse ANTES de la primera llamada a Gemini
# ===========================================================================

def test_9_cronometro_global_usa_marcas_de_tiempo_del_brief():
    tmp = Path(tempfile.mkdtemp(prefix="bottlenecks_timer_"))
    try:
        mod = _load_gemini_main()
        timing_markers = {
            "skill_started_at": "2026-01-01T10:00:00",
            "reference_received_at": "2026-01-01T10:00:10",
            "source_text_confirmed_at": "2026-01-01T10:00:40",
            "brief_approved_at": "2026-01-01T10:01:30",
        }
        tracker = CostTracker(tmp, "bundle-timer-test", 1, 0.0336, pipeline_started_at=timing_markers["skill_started_at"])
        mod._record_pre_generation_phase_seconds(tracker, timing_markers)

        ps = tracker.summary.phase_seconds
        ok = (
            tracker.summary.run_started_at == "2026-01-01T10:00:00"
            and ps.get("preparation") == 10.0
            and ps.get("reference") == 30.0
            and ps.get("brief") == 50.0
        )
        report("TEST 9", "El cronometro global fija el inicio real ANTES de Gemini y mide "
                          "preparacion/referencia/brief desde brief.json['timing']",
               ok, f"run_started_at={tracker.summary.run_started_at} phase_seconds={ps}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 70)
    print("AUDITORIA DE CUELLOS DE BOTELLA DE EJECUCION (2026-09-17 abuela-materna) — SIN GEMINI/KIE")
    print("=" * 70)
    for fn in [
        test_1_referencia_ausente_falla_rapido_sin_placeholder,
        test_2_uncertain_nunca_regenera,
        test_3_generacion_slides_en_paralelo,
        test_4_text_qa_de_la_tanda_en_paralelo,
        test_5_sin_unicode_encode_error_en_cp1252,
        test_6_una_sola_ejecucion_con_copy_json,
        test_7_costo_cuenta_todas_las_generaciones_reales,
        test_8_add_copy_no_pone_contadores_en_cero,
        test_9_cronometro_global_usa_marcas_de_tiempo_del_brief,
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
