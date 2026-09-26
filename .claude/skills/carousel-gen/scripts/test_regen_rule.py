#!/usr/bin/env python3
"""
test_regen_rule.py - REGLA PERMANENTE DE REGENERACION + TEXT QA sin falsos
positivos/negativos (ver SKILL.md "CONFIGURACIÓN FIJA", 2026-09-26).

  TEST 1  — 13 imagenes REALES de la prueba 2026-09-26: los 5 slides con errores de
            texto confirmados visualmente se rechazan (CRITICAL) y los 8 correctos se
            aprueban (incluido el falso positivo del slide 10 en cursiva con mockup).
  TEST 2  — Fallo de Text QA persistente -> exactamente 3 intentos (1 + 2
            regeneraciones), TEXT_QA_FAILED, se CONSERVA la ultima imagen.
  TEST 3  — Aunque la config pida mas regeneraciones, process_slides nunca pasa de 3
            intentos (techo duro MAX_REGENERATIONS=2) -> sin loop.
  TEST 4  — Pipeline completo (--fake-provider) con un slide que NUNCA devuelve imagen:
            el carrusel termina igual, entrega copy/ + brief + COSTO, y registra el slide
            pendiente en COSTO_CARRUSEL.txt y pipeline_result.json.
  TEST 5  — Cliente Gemini real construido con tiempo maximo por llamada (120 s).
  TEST 6  — load_config: MAX_RETRIES en .env nunca sube el techo de 2.

Sin llamadas reales a Gemini ($0). Los tests con OCR se omiten si Tesseract no esta.
"""

import json
import os
import shutil
import sys
import tempfile
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import OUTPUTS_DIR, DOWNLOADS_EXPORT_DIR, COPY_FILENAMES, FIXED_PURCHASE_URL  # noqa: E402
from cache_manager import CacheManager  # noqa: E402
from cost_tracker import CostTracker  # noqa: E402
from gemini_client import GeminiImageResult  # noqa: E402
import gemini_config  # noqa: E402
from text_qa import run_text_qa  # noqa: E402
from test_text_qa import (  # noqa: E402
    DrawnTextClient, _FakeConfig, _load_process_slides, _make_slide, _ocr_available,
)
from test_pipeline import _make_brief, _tiny_png, _load_gemini_main, _load_pipeline_main  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict] = []
FIXTURES = Path(__file__).parent / "test_fixtures" / "text_qa_real_2026-09-26"


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    line = f"[{status}] {test_id}: {description}" + (f"\n   {detail}" if detail else "")
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))


def test_1_imagenes_reales():
    if not _ocr_available():
        report("TEST 1", "SKIPPED (Tesseract/pytesseract no disponible)", True)
        return
    if not (FIXTURES / "cases.json").exists():
        report("TEST 1", "SKIPPED (faltan las imagenes de test_fixtures/text_qa_real_2026-09-26)", True)
        return
    data = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
    wrong = []
    for case in data["cases"]:
        phrases = [("PRODUCT_TITLE_MISMATCH", data["product_name"])] if case["uses_product_mockup"] else []
        r = run_text_qa(FIXTURES / case["file"], case["expected_text"], phrases,
                        [data["product_name"]], uses_product_mockup=case["uses_product_mockup"])
        if r.approved != case["should_approve"]:
            wrong.append(f"{case['file']}: approved={r.approved} sev={r.severity} {r.reason}")
    report("TEST 1", f"{len(data['cases'])} imagenes reales: errores reales rechazados, imagenes "
                     f"correctas aprobadas (sin falsos positivos ni negativos)",
           not wrong, "; ".join(wrong))


def test_2_tres_intentos_y_conserva_ultima():
    if not _ocr_available():
        report("TEST 2", "SKIPPED (Tesseract/pytesseract no disponible)", True)
        return
    mod = _load_process_slides()
    tmp = Path(tempfile.mkdtemp(prefix="regen_test2_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        corrupted = ["Texto texto correcto del slide", "Texto correcto correcto del slide",
                     "Texto correcto del del slide"]
        client = DrawnTextClient(attempts_by_slide={5: corrupted}, tmp_dir=tmp)
        final_status = mod.process_slides(
            [_make_slide(5, "Texto correcto del slide")], {}, "carrusel_interactivo",
            _FakeConfig(max_retries=2), client, CacheManager(carousel_dir),
            CostTracker(tmp, "regen-test2", 1, 0.0336), "regen-test2", carousel_dir,
            None, None, None, force_mode="direct",
        )
        attempts = client.attempt_count.get(5, 0)
        png = carousel_dir / "carousel-05.png"
        last_attempt_bytes = (tmp / "drawn_5_2.png").read_bytes()
        kept_last = png.exists() and png.read_bytes() == last_attempt_bytes
        ok = final_status.get(5) == "TEXT_QA_FAILED" and attempts == 3 and kept_last
        report("TEST 2", "Error persistente -> exactamente 3 intentos (1 + 2 regeneraciones), "
                         "TEXT_QA_FAILED y se conserva la ULTIMA imagen", ok,
               f"status={final_status} attempts={attempts} kept_last={kept_last}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class _AlwaysFailClient:
    """Gemini nunca devuelve imagen (API caida)."""
    def __init__(self):
        self.attempt_count: Dict[int, int] = {}

    def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
        self.attempt_count[_slide_number] = self.attempt_count.get(_slide_number, 0) + 1
        return GeminiImageResult(success=False, error="[TEST] sin imagen")


def test_3_techo_duro_sin_loop():
    mod = _load_process_slides()
    tmp = Path(tempfile.mkdtemp(prefix="regen_test3_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        client = _AlwaysFailClient()
        final_status = mod.process_slides(
            [_make_slide(n, f"Texto {n}") for n in (1, 2)], {}, "carrusel_interactivo",
            _FakeConfig(max_retries=50, text_qa_enabled=False), client, CacheManager(carousel_dir),
            CostTracker(tmp, "regen-test3", 2, 0.0336), "regen-test3", carousel_dir,
            None, None, None, force_mode="direct",
        )
        ok = client.attempt_count == {1: 3, 2: 3} and all(v == "FAILED_FINAL" for v in final_status.values())
        report("TEST 3", "Config con max_retries=50 -> igual maximo 3 intentos por slide (techo "
                         "MAX_REGENERATIONS=2), sin loop", ok,
               f"attempts={client.attempt_count} status={final_status}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_4_pipeline_termina_y_registra():
    bundle_id = "__test-regen-rule-pipeline__"
    bundle_path = OUTPUTS_DIR / bundle_id
    archive = DOWNLOADS_EXPORT_DIR / bundle_id
    try:
        (bundle_path / "carousel" / "assets").mkdir(parents=True, exist_ok=True)
        (bundle_path / "carousel" / "assets" / "viral-reference.png").write_bytes(_tiny_png())
        (bundle_path / "brief.json").write_text(json.dumps(_make_brief(10, bundle_id)), encoding="utf-8")
        copy_json = bundle_path / "copy.json"
        copy_json.write_text(json.dumps({
            "description": "Descripcion", "cta": "CTA",
            "hashtags": [f"#t{i}" for i in range(1, 9)],
            "product": "EL DOLOR QUE NO TE PERTENECE",
            "purchase_url": FIXED_PURCHASE_URL,
        }), encoding="utf-8")
        gen = _load_gemini_main()
        gen_args = Namespace(
            bundle_id=bundle_id, dry_run=False, fake_provider=True, fake_fail_slides="3",
            regenerate_slides=None, force_direct=True, force_batch=False,
            copy_json=str(copy_json), add_copy=None, skip_interactive=True,
        )
        gen.run_generation(gen_args)
        pipe = _load_pipeline_main()
        result = pipe._build_result(bundle_path, bundle_id, 0,
                                    {"T0_pipeline_start": datetime.now().isoformat(),
                                     "T5_finalization_done": datetime.now().isoformat()})
        cost_log = json.loads((bundle_path / "cost_log.json").read_text(encoding="utf-8"))
        attempts_3 = sum(1 for e in cost_log.get("entries", []) if e.get("slide_number") == 3)
        costo = (bundle_path / "COSTO_CARRUSEL.txt").read_text(encoding="utf-8")
        copy_ok = all((bundle_path / "copy" / n).exists() for n in COPY_FILENAMES)
        warnings = result.get("warnings") or []
        ok = (attempts_3 == 3 and copy_ok and (bundle_path / "brief.json").exists()
              and "SLIDES CON ADVERTENCIA" in costo and "Slide 3: MISSING_PNG" in costo
              and any(w.get("slide") == 3 and not w.get("png_delivered") for w in warnings)
              and len(list((bundle_path / "carousel").glob("carousel-*.png"))) == 9)
        report("TEST 4", "Slide sin imagen en los 3 intentos -> el carrusel TERMINA, entrega copy/ + "
                         "brief + COSTO y registra el slide pendiente (COSTO + pipeline_result)", ok,
               f"attempts_slide3={attempts_3} copy_ok={copy_ok} warnings={warnings}")
    finally:
        shutil.rmtree(bundle_path, ignore_errors=True)
        shutil.rmtree(archive, ignore_errors=True)


def test_5_timeout_cliente():
    from gemini_client import GeminiClient
    cfg = gemini_config.load_config()
    cfg = type(cfg)(**{**cfg.__dict__, "api_key": "clave-de-prueba-sin-red"})
    client = GeminiClient(cfg)
    http_options = client._client._api_client._http_options
    ok = http_options.timeout == gemini_config.GEMINI_REQUEST_TIMEOUT_SECONDS * 1000
    report("TEST 5", "Cliente Gemini con tiempo maximo por llamada (120 s = 120000 ms)", ok,
           f"timeout={http_options.timeout}")


def test_6_config_techo_2():
    original = os.environ.get("MAX_RETRIES")
    try:
        os.environ["MAX_RETRIES"] = "7"
        high = gemini_config.load_config().max_retries
        os.environ["MAX_RETRIES"] = "1"
        low = gemini_config.load_config().max_retries
    finally:
        if original is None:
            os.environ.pop("MAX_RETRIES", None)
        else:
            os.environ["MAX_RETRIES"] = original
    ok = high == 2 and low == 1 and gemini_config.MAX_REGENERATIONS == 2
    report("TEST 6", "MAX_RETRIES=7 en .env -> 2 (techo duro); MAX_RETRIES=1 -> 1", ok,
           f"high={high} low={low}")


def main():
    print("=" * 70)
    print("REGLA DE REGENERACION + TEXT QA — SIN LLAMADAS A GEMINI")
    print("=" * 70)
    for fn in [test_1_imagenes_reales, test_2_tres_intentos_y_conserva_ultima,
               test_3_techo_duro_sin_loop, test_4_pipeline_termina_y_registra,
               test_5_timeout_cliente, test_6_config_techo_2]:
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
