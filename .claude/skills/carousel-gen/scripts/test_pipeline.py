#!/usr/bin/env python3
"""
test_pipeline.py - 8 tests nuevos para run_carousel_pipeline.py y mejoras de rendimiento.

Cubre:
  TEST 1 — pipeline completo (--fake-provider) produce TODOS los archivos esperados
  TEST 2 — _seconds_between maneja correctamente datetimes mixtos (aware/naive)
  TEST 3 — brief con los 21 campos de REQUIRED_SLIDE_FIELDS pasa load_brief()
  TEST 4 — slides 2-N se generan en paralelo (solapamiento real de intervalos)
  TEST 5 — maximo 1 retry por slide (MAX_RETRIES=1), nunca 2 retries aunque todo falle
  TEST 6 — pipeline_result.json tiene el esquema correcto (todos los campos requeridos)
  TEST 7 — no se crea carpeta PARA FACEBOOK/ en el bundle ni en Descargas
  TEST 8 — T0 < T5, delta >= 0 (wall-clock Python medido correctamente)

Este archivo NUNCA llama a Gemini real (usa --fake-provider / FakeGeminiClient).
Ejecutar con:
    python3 scripts/test_pipeline.py
"""

import contextlib
import io
import json
import shutil
import struct
import sys
import tempfile
import threading
import time
import zlib
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import OUTPUTS_DIR, load_brief, REQUIRED_SLIDE_FIELDS  # noqa: E402
from carousel_common import _seconds_between  # noqa: E402
from cost_tracker import CostTracker  # noqa: E402
from cache_manager import CacheManager  # noqa: E402
from direct_generator import GenerationTask, generate_direct  # noqa: E402
from gemini_client import GeminiImageResult  # noqa: E402
from gemini_config import GeminiConfig  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f"\n   {detail}" if detail else ""))


def _tiny_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes([0, 5, 5, 5]))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _make_full_slide(number: int) -> dict:
    """Slide con TODOS los campos de REQUIRED_SLIDE_FIELDS."""
    return {
        "number": number,
        "role": f"slide-{number}",
        "narrative_objective": "Objetivo narrativo",
        "message": "Mensaje del slide",
        "source_text_fragment": "Fragmento literal del source_text",
        "source_location": f"parrafo {number}",
        "exact_text": f"Texto exacto del slide {number}",
        "scene_description": "Escena descriptiva",
        "composition": "full bleed foto BW",
        "visual_hierarchy": "1. Imagen 2. Texto",
        "text_placement": "tercio inferior centrado",
        "key_visual_elements": ["elemento_visual"],
        "visual_dna_connection": "Conexion con el ADN visual del Slide 1",
        "uses_reference_image_directly": number == 1,
        "uses_product_mockup_directly": False,
        "word_count": 5,
        "text_density": "LOW",
        "estimated_text_area": "upper_third_centered",
        "text_area_percentage": 20,
        "visual_balance": "balanced",
        "text_break_reason": "natural_sentence_boundary",
    }


def _make_brief(num_slides: int, bundle_id: str = "test-brief") -> dict:
    return {
        "bundle_id": bundle_id,
        "source_text": "Texto fuente completo del post viral",
        "reference_image": {
            "local_path": "carousel/assets/viral-reference.png",
            "analysis": {
                "tema_mensaje": "test", "copy_estructura": "test",
                "emocion_predominante": "test", "elementos_impacto": "test",
            },
        },
        "visual_dna": {"slide_1_master_dna": {}},
        "carousel_type": "revelacion_progresiva",
        "slide_count": {"recommended": num_slides, "confirmed": num_slides},
        "product": {"product_name": None, "purchase_url": None},
        "slides": [_make_full_slide(n) for n in range(1, num_slides + 1)],
    }


def _load_gemini_main():
    import importlib.util
    path = Path(__file__).parent / "generate-carousel-gemini.py"
    spec = importlib.util.spec_from_file_location("gemini_main_for_pipeline_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pipeline_main():
    import importlib.util
    path = Path(__file__).parent / "run_carousel_pipeline.py"
    spec = importlib.util.spec_from_file_location("pipeline_main_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ============================================================
# TEST 1 — Pipeline completo produce TODOS los archivos
# ============================================================

def test_1_pipeline_completo_produce_todos_los_archivos():
    """
    Con --fake-provider: una sola llamada a run_generation produce imagen, COPY_FINAL.txt,
    COSTO_CARRUSEL.txt, manifest.json. Luego _build_result escribe pipeline_result.json.
    """
    bundle_id = "__test-pipeline-complete__"
    bundle_path = OUTPUTS_DIR / bundle_id
    downloads_dir = Path.home() / "Downloads" / "Carruseles Carousel-Gen" / bundle_id
    try:
        (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
        (bundle_path / "carousel" / "assets" / "viral-reference.png").write_bytes(_tiny_png())
        (bundle_path / "brief.json").write_text(
            json.dumps(_make_brief(1, bundle_id)), encoding="utf-8"
        )
        copy_json_path = bundle_path / "copy.json"
        copy_json_path.write_text(json.dumps({
            "description": "Descripcion de prueba",
            "cta": "CTA de prueba",
            "hashtags": ["#a", "#b", "#c", "#d", "#e", "#f", "#g", "#h"],
        }), encoding="utf-8")

        gemini_mod = _load_gemini_main()
        gen_args = Namespace(
            bundle_id=bundle_id, dry_run=False, fake_provider=True, fake_fail_slides=None,
            regenerate_slides=None, force_direct=True, force_batch=False,
            copy_json=str(copy_json_path), add_copy=None, skip_interactive=True,
        )
        rc = gemini_mod.run_generation(gen_args)

        # Simular lo que run_carousel_pipeline.py hace al terminar
        pipeline_mod = _load_pipeline_main()
        timing = {k: datetime.now().isoformat() for k in
                  ["T0_pipeline_start", "T1_module_loaded", "T2_generation_start",
                   "T3_generation_done", "T4_retries_done", "T5_finalization_done"]}
        result = pipeline_mod._build_result(bundle_path, bundle_id, rc, timing)
        (bundle_path / "pipeline_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        image_exists = (bundle_path / "carousel" / "carousel-01.png").exists()
        copy_exists = (bundle_path / "COPY_FINAL.txt").exists()
        costo_exists = (bundle_path / "COSTO_CARRUSEL.txt").exists()
        manifest_exists = (bundle_path / "carousel" / "manifest.json").exists()
        result_json_exists = (bundle_path / "pipeline_result.json").exists()

        ok = rc == 0 and image_exists and copy_exists and costo_exists and manifest_exists and result_json_exists
        report(
            "TEST 1",
            "Pipeline completo (--fake-provider) produce: imagen + COPY_FINAL.txt + COSTO_CARRUSEL.txt "
            "+ manifest.json + pipeline_result.json",
            ok,
            f"rc={rc} imagen={image_exists} copy={copy_exists} costo={costo_exists} "
            f"manifest={manifest_exists} pipeline_result={result_json_exists}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        shutil.rmtree(downloads_dir, ignore_errors=True)


# ============================================================
# TEST 2 — _seconds_between: datetimes mixtos aware/naive
# ============================================================

def test_2_timezone_mixed_datetimes():
    """
    Verifica que _seconds_between (carousel_common.py) maneja correctamente:
    - aware + naive (caso real del bug 2026-09-19: brief.timing aware, run_finished_at naive)
    - naive + naive
    - aware + aware (mismo offset)
    - None input
    - end < start (resultado = 0.0 por max(0, ...))
    """
    # Caso 1: aware(-05:00) y naive — debe ser positivo y no None (no TypeError)
    result1 = _seconds_between("2026-09-19T09:51:16-05:00", "2026-09-19T10:18:21")
    case1_ok = result1 is not None and result1 >= 0

    # Caso 2: naive y naive — diferencia exacta de 90 segundos
    result2 = _seconds_between("2026-01-01T10:00:00", "2026-01-01T10:01:30")
    case2_ok = result2 == 90.0

    # Caso 3: aware y aware (mismo offset) — 60 segundos exactos
    result3 = _seconds_between("2026-01-01T10:00:00-05:00", "2026-01-01T10:01:00-05:00")
    case3_ok = result3 == 60.0

    # Caso 4: None en cualquier argumento -> None (sin crash)
    result4 = _seconds_between(None, "2026-01-01T10:00:00")
    case4_ok = result4 is None

    # Caso 5: end < start -> 0.0 (nunca negativo)
    result5 = _seconds_between("2026-01-01T10:01:00", "2026-01-01T10:00:00")
    case5_ok = result5 == 0.0

    ok = case1_ok and case2_ok and case3_ok and case4_ok and case5_ok
    report(
        "TEST 2",
        "_seconds_between maneja aware+naive, naive+naive, aware+aware, None, invertidos — sin TypeError",
        ok,
        f"aware+naive={result1} (>=0:{case1_ok}) naive+naive={result2} (90s:{case2_ok}) "
        f"aware+aware={result3} (60s:{case3_ok}) None={result4} (None:{case4_ok}) "
        f"invertido={result5} (0.0:{case5_ok})",
    )


# ============================================================
# TEST 3 — Brief con 21 campos pasa load_brief()
# ============================================================

def test_3_brief_con_21_campos_pasa_load_brief():
    """
    Un brief.json que incluye todos los campos de REQUIRED_SLIDE_FIELDS pasa load_brief()
    sin error. Esto es la compuerta tecnica que protege la generacion de briefs incompletos.
    """
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_brief_"))
    try:
        brief = _make_brief(3)
        # Verificar que el brief tiene todos los campos requeridos antes del test
        missing_fields = set(REQUIRED_SLIDE_FIELDS) - set(brief["slides"][0].keys())
        if missing_fields:
            report("TEST 3", "Brief tiene todos los campos de REQUIRED_SLIDE_FIELDS",
                   False, f"Campos faltantes en la fixture: {missing_fields}")
            return

        (tmp / "brief.json").write_text(json.dumps(brief), encoding="utf-8")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = load_brief(tmp)

        ok = result is not None and len(result.get("slides", [])) == 3
        output = buf.getvalue()
        report(
            "TEST 3",
            f"brief con todos los {len(REQUIRED_SLIDE_FIELDS)} campos de REQUIRED_SLIDE_FIELDS "
            f"pasa load_brief() sin rechazar",
            ok,
            (output[:300] if not ok else f"OK: {len(result['slides'])} slides aceptados"),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 4 — Generacion paralela de slides 2-N
# ============================================================

def test_4_generacion_paralela_slides():
    """
    direct_generator.generate_direct() ejecuta los slides en paralelo.
    Prueba con 7 slides, cada uno con delay de 250ms:
    - tiempo total << 7 * 250ms (ejecucion paralela)
    - hay solapamiento real de intervalos (no secuencial)
    """
    delay = 1.0  # debe ser suficientemente largo para dominar el overhead de threads en Windows
    lock = threading.Lock()
    intervals: List[tuple] = []

    class _SlowClient:
        def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
            start = time.time()
            time.sleep(delay)
            end = time.time()
            with lock:
                intervals.append((start, end))
            return GeminiImageResult(success=True, image_bytes=_tiny_png(), usage_metadata=None)

    tasks = [GenerationTask(slide_number=n, prompt=f"prompt-slide-{n}") for n in range(2, 9)]
    client = _SlowClient()

    started = time.time()
    results = generate_direct(client, tasks)
    elapsed = time.time() - started

    serial_would_be = delay * len(tasks)
    overlap = any(
        a_start < b_end and b_start < a_end
        for i, (a_start, a_end) in enumerate(intervals)
        for j, (b_start, b_end) in enumerate(intervals)
        if i != j
    )
    all_ok = all(r.success for r in results.values())
    ok = elapsed < (serial_would_be * 0.7) and overlap and all_ok
    report(
        "TEST 4",
        "Slides 2-N se generan en paralelo (elapsed < 70% del tiempo serial, solapamiento real medido)",
        ok,
        f"elapsed={elapsed:.2f}s serial_would_be={serial_would_be:.2f}s overlap={overlap} "
        f"n_slides={len(tasks)} all_ok={all_ok}",
    )


# ============================================================
# TEST 5 — Maximo 1 retry por slide, nunca 2
# ============================================================

def test_5_max_1_retry_por_slide():
    """
    Con MAX_RETRIES=1: aunque todos los slides fallen siempre, cada uno se intenta
    maximo 2 veces (intento inicial + 1 retry) y nunca 3+.
    """
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_retry_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()

        attempt_count: Dict[int, int] = {}
        lock = threading.Lock()

        class _AlwaysFailClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                with lock:
                    attempt_count[_slide_number] = attempt_count.get(_slide_number, 0) + 1
                return GeminiImageResult(
                    success=False, error="Simulated persistent API failure", usage_metadata=None,
                )

        config = GeminiConfig(
            api_key="fake-key-for-test",
            image_model="gemini-test",
            aspect_ratio="4:5",
            image_size="1K",
            economy_mode=True,
            batch_enabled=False,
            max_slides=10,
            max_retries=1,
            text_qa_enabled=False,
            price_per_image_usd=0.0336,
            kie_enabled=False,
            flow_enabled=False,
        )

        n_slides = 4
        slides = [_make_full_slide(n) for n in range(1, n_slides + 1)]
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-retry-bundle", n_slides, 0.0336)

        final_status = mod.process_slides(
            slides, {}, "la-gran-noticia", config, _AlwaysFailClient(), cache, cost_tracker,
            "test-retry-bundle", carousel_dir, None, None, None, force_mode="direct",
        )

        max_attempts = max(attempt_count.values()) if attempt_count else 0
        all_failed = all("FAILED" in v for v in final_status.values())
        # Con MAX_RETRIES=1: intento inicial (attempt 1) + 1 retry (attempt 2) = 2 max
        ok = max_attempts <= 2 and all_failed and len(final_status) == n_slides
        report(
            "TEST 5",
            "Con MAX_RETRIES=1, cada slide se intenta maximo 2 veces (nunca 3+) aunque siempre falle",
            ok,
            f"attempt_count={dict(attempt_count)} max={max_attempts} "
            f"all_failed={all_failed} n_slides={len(final_status)}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 6 — pipeline_result.json tiene el esquema correcto
# ============================================================

def test_6_resultado_json_esquema_correcto():
    """
    _build_result() produce un dict con todos los campos requeridos en los tipos correctos.
    """
    pipeline_mod = _load_pipeline_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_schema_"))
    try:
        (tmp / "carousel").mkdir()

        # Simular cost_log.json escrito por un CostTracker real
        cost_log: Dict[str, Any] = {
            "bundle_id": "test-schema-bundle",
            "slides_total": 10,
            "generated": 12,
            "reused": 0,
            "retries": 3,
            "failed": 0,
            "estimated_cost_usd": 0.4032,
            "price_per_image_usd": 0.0336,
            "entries": [],
            "run_started_at": "2026-09-19T10:00:00",
            "run_finished_at": "2026-09-19T10:02:00",
            "phase_seconds": {"generation_qa": 95.0, "finalization": 1.5, "export": 0.8},
            "execution_started_at": "2026-09-19T10:00:05",
            "execution_finished_at": "2026-09-19T10:02:00",
        }
        (tmp / "cost_log.json").write_text(json.dumps(cost_log), encoding="utf-8")

        # Simular manifest.json escrito por generate_manifest()
        # NOTA: la clave es "carousel", no "slides" (BUG 1 corregido).
        manifest: Dict[str, Any] = {
            "carousel": (
                [{"id": n, "status": "TEXT_QA_APPROVED",
                  "expected_text_hash": "same", "rendered_text_hash": "same"}
                 for n in range(1, 6)]         # 5 slides: PASS limpio (hashes iguales)
                + [{"id": n, "status": "TEXT_QA_APPROVED",
                    "expected_text_hash": "abc", "rendered_text_hash": "xyz"}
                   for n in range(6, 8)]        # 2 slides: UNCERTAIN (hash distinto)
                + [{"id": n, "status": "TEXT_QA_FAILED",
                    "text_qa_rejection_reason": "MISSING_TOKEN"}
                   for n in range(8, 11)]       # 3 slides: FAILED
            ),
            "text_qa": {"status": "PARTIAL"},
        }
        (tmp / "carousel" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        timing = {
            "T0_pipeline_start": "2026-09-19T10:00:00",
            "T1_module_loaded": "2026-09-19T10:00:01",
            "T2_generation_start": "2026-09-19T10:00:02",
            "T3_generation_done": "2026-09-19T10:01:40",
            "T4_retries_done": "2026-09-19T10:01:40",
            "T5_finalization_done": "2026-09-19T10:01:42",
        }
        result = pipeline_mod._build_result(tmp, "test-schema-bundle", 0, timing)

        required_keys = {
            "bundle_id", "status", "timing",
            "gemini_calls", "retries", "initial_generations", "total_generations",
            "cost_usd", "wall_clock_python_seconds", "duration_seconds",
            "slides_total", "slides_pass", "slides_failed", "slides_uncertain",
            "text_qa_status", "output_path", "files",
        }
        timing_keys = {
            "T0_pipeline_start", "T1_module_loaded", "T2_generation_start",
            "T3_generation_done", "T4_retries_done", "T5_finalization_done",
        }
        missing_keys = required_keys - set(result.keys())
        missing_timing = timing_keys - set(result.get("timing", {}).keys())

        values_ok = (
            result.get("slides_total") == 10
            and result.get("slides_pass") == 5           # 5 slides con hashes iguales
            and result.get("slides_uncertain") == 2      # 2 slides con hashes distintos
            and result.get("slides_failed") == 3
            and result.get("gemini_calls") == 12
            and result.get("retries") == 3
            and result.get("initial_generations") == 9   # 12 - 3 = 9
            and result.get("total_generations") == 12
            and abs(result.get("cost_usd", 0) - 0.4032) < 0.001
            and result.get("duration_seconds", -1) > 0  # T0..T5 = 102s
        )
        ok = not missing_keys and not missing_timing and values_ok
        report(
            "TEST 6",
            "pipeline_result.json tiene todos los campos requeridos: status, slides_* "
            "(con UNCERTAIN via hash), timing T0-T5, duration_seconds, initial_generations, "
            "total_generations, cost_usd, gemini_calls, output_path, files",
            ok,
            f"missing_keys={missing_keys} missing_timing={missing_timing} "
            f"slides_pass={result.get('slides_pass')} uncertain={result.get('slides_uncertain')} "
            f"duration={result.get('duration_seconds')} initial_gen={result.get('initial_generations')}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 7 — No se crea PARA FACEBOOK/ en el bundle ni en Descargas
# ============================================================

def test_7_sin_carpeta_para_facebook():
    """
    export_final_slides_to_downloads() no debe crear 'PARA FACEBOOK/' en ningun lugar.
    (Eliminada de produccion — ver carousel_common.py, eliminacion de build_para_facebook_folder)
    """
    bundle_id = "__test-no-para-facebook__"
    bundle_path = OUTPUTS_DIR / bundle_id
    downloads_dir = Path.home() / "Downloads" / "Carruseles Carousel-Gen" / bundle_id
    try:
        (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
        (bundle_path / "carousel" / "assets" / "viral-reference.png").write_bytes(_tiny_png())
        (bundle_path / "brief.json").write_text(
            json.dumps(_make_brief(1, bundle_id)), encoding="utf-8"
        )
        copy_json_path = bundle_path / "copy.json"
        copy_json_path.write_text(json.dumps({
            "description": "desc", "cta": "cta",
            "hashtags": ["#a", "#b", "#c", "#d", "#e", "#f", "#g", "#h"],
        }), encoding="utf-8")

        gemini_mod = _load_gemini_main()
        gen_args = Namespace(
            bundle_id=bundle_id, dry_run=False, fake_provider=True, fake_fail_slides=None,
            regenerate_slides=None, force_direct=True, force_batch=False,
            copy_json=str(copy_json_path), add_copy=None, skip_interactive=True,
        )
        rc = gemini_mod.run_generation(gen_args)

        # Verificar ausencia de PARA FACEBOOK/ en todas las ubicaciones posibles
        para_fb_in_bundle_carousel = (bundle_path / "carousel" / "PARA FACEBOOK").exists()
        para_fb_in_bundle_root = (bundle_path / "PARA FACEBOOK").exists()
        para_fb_in_downloads = (downloads_dir / "PARA FACEBOOK").exists() if downloads_dir.exists() else False

        ok = rc == 0 and not para_fb_in_bundle_carousel and not para_fb_in_bundle_root and not para_fb_in_downloads
        report(
            "TEST 7",
            "No se crea 'PARA FACEBOOK/' en el bundle (carousel/ ni raiz) ni en Descargas "
            "(eliminada definitivamente de produccion)",
            ok,
            f"rc={rc} en_carousel={para_fb_in_bundle_carousel} en_bundle={para_fb_in_bundle_root} "
            f"en_downloads={para_fb_in_downloads}",
        )
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        shutil.rmtree(downloads_dir, ignore_errors=True)


# ============================================================
# TEST 8 — Wall-clock Python: T0 < T5 y delta razonable
# ============================================================

def test_8_wall_clock_python_medido_correctamente():
    """
    run_carousel_pipeline.py captura T0 antes de iniciar y T5 despues de terminar.
    La diferencia T5-T0 debe ser >= 0 y < 60s (en modo fake con operaciones minimas).
    Ademas, _seconds_between(T0, T5) debe devolver el mismo delta sin errores de timezone.
    """
    # Simular los timestamps como lo hace run_carousel_pipeline.py
    t0 = datetime.now().isoformat()
    time.sleep(0.1)   # minimo trabajo simulado para que T0 != T5
    t5 = datetime.now().isoformat()

    t0_dt = datetime.fromisoformat(t0)
    t5_dt = datetime.fromisoformat(t5)
    delta_direct = (t5_dt - t0_dt).total_seconds()

    # _seconds_between debe dar el mismo resultado (ambos naive en este caso)
    delta_via_fn = _seconds_between(t0, t5)

    delta_ok = 0 < delta_direct < 60
    fn_ok = delta_via_fn is not None and abs(delta_via_fn - delta_direct) < 0.01
    ok = delta_ok and fn_ok
    report(
        "TEST 8",
        "T0 < T5 y delta T5-T0 esta entre 0 y 60s; _seconds_between da el mismo resultado",
        ok,
        f"T0={t0} T5={t5} delta_direct={delta_direct:.3f}s delta_via_fn={delta_via_fn} "
        f"delta_ok={delta_ok} fn_ok={fn_ok}",
    )


# ============================================================
# TEST 9 — BUG 1: _build_result usa clave "carousel" (no "slides")
# ============================================================

def test_9_build_result_usa_clave_carousel():
    """
    _build_result() debe leer manifest["carousel"], no manifest["slides"].
    Verifica ademas la deteccion de UNCERTAIN via hashes distintos.
    """
    pipeline_mod = _load_pipeline_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_carousel_key_"))
    try:
        (tmp / "carousel").mkdir()
        manifest: Dict[str, Any] = {
            "carousel": (
                [{"id": n, "status": "TEXT_QA_APPROVED",
                  "expected_text_hash": "same", "rendered_text_hash": "same"}
                 for n in range(1, 5)]          # 4 slides: PASS limpio
                + [{"id": 5, "status": "TEXT_QA_APPROVED",
                    "expected_text_hash": "abc", "rendered_text_hash": "xyz"}]  # 1 UNCERTAIN
                + [{"id": 6, "status": "TEXT_QA_FAILED",
                    "text_qa_rejection_reason": "MISSING_TOKEN"}]               # 1 FAILED
            ),
            "text_qa": {"status": "FAILED"},
        }
        (tmp / "carousel" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        timing = {k: datetime.now().isoformat() for k in [
            "T0_pipeline_start", "T1_module_loaded", "T2_generation_start",
            "T3_generation_done", "T4_retries_done", "T5_finalization_done",
        ]}
        result = pipeline_mod._build_result(tmp, "test-carousel-key", 0, timing)

        ok = (
            result.get("slides_total") == 6
            and result.get("slides_pass") == 4
            and result.get("slides_uncertain") == 1
            and result.get("slides_failed") == 1
        )
        report(
            "TEST 9",
            "_build_result lee clave 'carousel' del manifest y detecta UNCERTAIN via hashes distintos",
            ok,
            f"total={result.get('slides_total')} pass={result.get('slides_pass')} "
            f"uncertain={result.get('slides_uncertain')} failed={result.get('slides_failed')}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 10 — BUG 2: respuesta vacía INICIAL dispara retry
# ============================================================

def test_10_empty_response_inicial_dispara_retry():
    """
    Un slide con empty response en el intento inicial DEBE reintentarse.
    El cliente falla vacío la primera vez y tiene éxito en la segunda.
    Resultado esperado: 2 intentos totales, slide termina en estado PASS.
    """
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_empty_init_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        attempt_count: Dict[int, int] = {}
        lock = threading.Lock()

        class _FailThenSucceedClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                with lock:
                    n = attempt_count.get(_slide_number, 0) + 1
                    attempt_count[_slide_number] = n
                if n == 1:
                    return GeminiImageResult(success=False, error="inline_data vacio", usage_metadata=None)
                return GeminiImageResult(success=True, image_bytes=_tiny_png(), usage_metadata=None)

        config = GeminiConfig(
            api_key="fake", image_model="m", aspect_ratio="4:5", image_size="1K",
            economy_mode=True, batch_enabled=False, max_slides=10, max_retries=1,
            text_qa_enabled=False, price_per_image_usd=0.0336, kie_enabled=False, flow_enabled=False,
        )
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-empty-init", 1, 0.0336)

        final_status = mod.process_slides(
            [_make_full_slide(1)], {}, "revelacion_progresiva", config,
            _FailThenSucceedClient(), cache, cost_tracker,
            "test-empty-init", carousel_dir, None, None, None, force_mode="direct",
        )

        attempts = attempt_count.get(1, 0)
        passed = final_status.get(1, "UNKNOWN") in ("APPROVED", "TEXT_QA_APPROVED", "REUSED")
        ok = attempts == 2 and passed
        report(
            "TEST 10",
            "Respuesta vacia inicial -> slide se reintenta (2 intentos totales, slide termina PASS)",
            ok,
            f"intentos={attempts} status={final_status.get(1)}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 11 - BUG 2: respuesta vacia en RETRY -> FAILED_FINAL inmediato
# ============================================================

def test_11_empty_response_en_retry_es_failed_final():
    """
    Cuando AMBOS intentos devuelven empty response:
    - 2 intentos totales (intento inicial + 1 retry = MAX_RETRIES=1)
    - final_status == FAILED_FINAL
    - No se hace un tercer intento
    """
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_empty_retry_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        attempt_count: Dict[int, int] = {}
        lock = threading.Lock()

        class _AlwaysEmptyClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                with lock:
                    attempt_count[_slide_number] = attempt_count.get(_slide_number, 0) + 1
                return GeminiImageResult(success=False, error="inline_data vacio", usage_metadata=None)

        config = GeminiConfig(
            api_key="fake", image_model="m", aspect_ratio="4:5", image_size="1K",
            economy_mode=True, batch_enabled=False, max_slides=10, max_retries=1,
            text_qa_enabled=False, price_per_image_usd=0.0336, kie_enabled=False, flow_enabled=False,
        )
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-empty-retry", 1, 0.0336)

        final_status = mod.process_slides(
            [_make_full_slide(1)], {}, "revelacion_progresiva", config,
            _AlwaysEmptyClient(), cache, cost_tracker,
            "test-empty-retry", carousel_dir, None, None, None, force_mode="direct",
        )

        attempts = attempt_count.get(1, 0)
        status = final_status.get(1, "UNKNOWN")
        ok = attempts == 2 and status == "FAILED_FINAL"
        report(
            "TEST 11",
            "Respuesta vacia en retry -> FAILED_FINAL tras 2 intentos (nunca intento 3)",
            ok,
            f"intentos={attempts} status={status}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 12 — BUG 2: MAX_RETRIES=1 con empty responses — 2 intentos máximo
# ============================================================

def test_12_max_retries_con_empty_responses():
    """
    Con MAX_RETRIES=1 y todas las respuestas vacías:
    - cada slide tiene EXACTAMENTE 2 intentos (nunca 3+)
    - todos terminan FAILED_FINAL
    Prueba con 3 slides para verificar el comportamiento en paralelo.
    """
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_max_retries_empty_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        attempt_count: Dict[int, int] = {}
        lock = threading.Lock()

        class _AlwaysEmptyClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                with lock:
                    attempt_count[_slide_number] = attempt_count.get(_slide_number, 0) + 1
                return GeminiImageResult(success=False, error="inline_data vacio", usage_metadata=None)

        config = GeminiConfig(
            api_key="fake", image_model="m", aspect_ratio="4:5", image_size="1K",
            economy_mode=True, batch_enabled=False, max_slides=10, max_retries=1,
            text_qa_enabled=False, price_per_image_usd=0.0336, kie_enabled=False, flow_enabled=False,
        )
        n_slides = 3
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-max-empty", n_slides, 0.0336)

        final_status = mod.process_slides(
            [_make_full_slide(n) for n in range(1, n_slides + 1)],
            {}, "revelacion_progresiva", config,
            _AlwaysEmptyClient(), cache, cost_tracker,
            "test-max-empty", carousel_dir, None, None, None, force_mode="direct",
        )

        max_attempts = max(attempt_count.values()) if attempt_count else 0
        all_failed_final = all(v == "FAILED_FINAL" for v in final_status.values())
        ok = max_attempts == 2 and all_failed_final and len(final_status) == n_slides
        report(
            "TEST 12",
            "MAX_RETRIES=1 con empty responses: max 2 intentos por slide, todos FAILED_FINAL",
            ok,
            f"attempt_count={dict(attempt_count)} max_intentos={max_attempts} "
            f"all_failed_final={all_failed_final}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 13 — BUG 2 (fix): cache tiene FAILED_FINAL tras empty response en retry
# ============================================================

def test_13_cache_failed_final_tras_empty_response():
    """
    Tras agotar reintentos con respuesta vacía, cache.get(slide).status
    debe ser "FAILED_FINAL" (no None/"UNKNOWN").
    Este es el fix central del BUG 2: antes del fix, cache.get() devolvía None.
    """
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_cache_empty_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()

        class _AlwaysEmptyClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                return GeminiImageResult(success=False, error="inline_data vacio", usage_metadata=None)

        config = GeminiConfig(
            api_key="fake", image_model="m", aspect_ratio="4:5", image_size="1K",
            economy_mode=True, batch_enabled=False, max_slides=10, max_retries=1,
            text_qa_enabled=False, price_per_image_usd=0.0336, kie_enabled=False, flow_enabled=False,
        )
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-cache-empty", 1, 0.0336)

        mod.process_slides(
            [_make_full_slide(1)], {}, "revelacion_progresiva", config,
            _AlwaysEmptyClient(), cache, cost_tracker,
            "test-cache-empty", carousel_dir, None, None, None, force_mode="direct",
        )

        record = cache.get(1)
        # Antes del fix: record era None -> manifest reportaba "UNKNOWN"
        # Despues del fix: record.status == "FAILED_FINAL"
        ok = record is not None and record.status == "FAILED_FINAL"
        report(
            "TEST 13",
            "Cache actualizado con FAILED_FINAL tras empty response — manifest no quedará UNKNOWN",
            ok,
            f"cache_record={record} status={record.status if record else 'None (BUG sin fix)'}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 14 — BUG 2: pipeline continúa con otros slides si uno falla empty
# ============================================================

def test_14_pipeline_continua_si_slide_falla_empty():
    """
    Si slide 1 falla con empty response (y agota retries), los slides 2 y 3
    deben procesarse normalmente y terminar en estado PASS.
    """
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_continua_empty_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()

        class _Slide1EmptyRestOkClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                if _slide_number == 1:
                    return GeminiImageResult(success=False, error="inline_data vacio", usage_metadata=None)
                return GeminiImageResult(success=True, image_bytes=_tiny_png(), usage_metadata=None)

        config = GeminiConfig(
            api_key="fake", image_model="m", aspect_ratio="4:5", image_size="1K",
            economy_mode=True, batch_enabled=False, max_slides=10, max_retries=1,
            text_qa_enabled=False, price_per_image_usd=0.0336, kie_enabled=False, flow_enabled=False,
        )
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-continua-empty", 3, 0.0336)

        final_status = mod.process_slides(
            [_make_full_slide(n) for n in range(1, 4)],
            {}, "revelacion_progresiva", config,
            _Slide1EmptyRestOkClient(), cache, cost_tracker,
            "test-continua-empty", carousel_dir, None, None, None, force_mode="direct",
        )

        slide1_failed = final_status.get(1) == "FAILED_FINAL"
        PASS_STATUSES = {"APPROVED", "TEXT_QA_APPROVED", "REUSED"}
        slides_2_3_ok = (
            final_status.get(2) in PASS_STATUSES
            and final_status.get(3) in PASS_STATUSES
        )
        ok = slide1_failed and slides_2_3_ok
        report(
            "TEST 14",
            "Pipeline continua con slides 2-3 aunque slide 1 falle con empty response",
            ok,
            f"slide1={final_status.get(1)} slide2={final_status.get(2)} slide3={final_status.get(3)}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# TEST 15 — BUG 2: empty response no genera costo (billable=False)
# ============================================================

def test_15_empty_response_costo_cero():
    """
    Las respuestas vacías de Gemini no son billables (billable=False).
    Tras un run donde todos los slides fallan con empty response,
    el costo registrado debe ser $0.
    """
    mod = _load_gemini_main()
    tmp = Path(tempfile.mkdtemp(prefix="pipeline_test_cost_empty_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()

        class _AlwaysEmptyClient:
            def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
                return GeminiImageResult(success=False, error="inline_data vacio", usage_metadata=None)

        config = GeminiConfig(
            api_key="fake", image_model="m", aspect_ratio="4:5", image_size="1K",
            economy_mode=True, batch_enabled=False, max_slides=10, max_retries=1,
            text_qa_enabled=False, price_per_image_usd=0.0336, kie_enabled=False, flow_enabled=False,
        )
        n_slides = 3
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test-cost-empty", n_slides, 0.0336)

        mod.process_slides(
            [_make_full_slide(n) for n in range(1, n_slides + 1)],
            {}, "revelacion_progresiva", config,
            _AlwaysEmptyClient(), cache, cost_tracker,
            "test-cost-empty", carousel_dir, None, None, None, force_mode="direct",
        )
        cost_tracker.mark_finished()

        cost_log_path = tmp / "cost_log.json"
        cost_usd = None
        if cost_log_path.exists():
            cost_data = json.loads(cost_log_path.read_text(encoding="utf-8"))
            cost_usd = float(cost_data.get("estimated_cost_usd") or 0.0)

        ok = cost_log_path.exists() and cost_usd == 0.0
        report(
            "TEST 15",
            "Empty responses no generan costo (billable=False -> estimated_cost_usd = $0.00)",
            ok,
            f"cost_log_exists={cost_log_path.exists()} cost_usd={cost_usd}",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 70)
    print("TEST SUITE — run_carousel_pipeline.py + reingenieria de rendimiento (SIN GEMINI REAL)")
    print("=" * 70)
    for fn in [
        test_1_pipeline_completo_produce_todos_los_archivos,
        test_2_timezone_mixed_datetimes,
        test_3_brief_con_21_campos_pasa_load_brief,
        test_4_generacion_paralela_slides,
        test_5_max_1_retry_por_slide,
        test_6_resultado_json_esquema_correcto,
        test_7_sin_carpeta_para_facebook,
        test_8_wall_clock_python_medido_correctamente,
        # BUG 1 — clave "carousel" en manifest
        test_9_build_result_usa_clave_carousel,
        # BUG 2 — manejo de respuesta vacía de Gemini
        test_10_empty_response_inicial_dispara_retry,
        test_11_empty_response_en_retry_es_failed_final,
        test_12_max_retries_con_empty_responses,
        test_13_cache_failed_final_tras_empty_response,
        test_14_pipeline_continua_si_slide_falla_empty,
        test_15_empty_response_costo_cero,
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
