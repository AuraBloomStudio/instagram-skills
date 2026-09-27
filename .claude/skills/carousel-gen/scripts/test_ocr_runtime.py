#!/usr/bin/env python3
"""
test_ocr_runtime.py - Ejecucion del OCR (Tesseract) con recursos acotados (2026-09-26).

  TEST 1 — Limite de OCR simultaneos: 4 CPU -> 3, 2 CPU -> 1, nunca mas de 3.
  TEST 2 — Cada Tesseract recibe OMP_THREAD_LIMIT=1.
  TEST 3 — Un Tesseract que se cuelga se mata al superar el tiempo maximo (OCRTimeout)
           y no queda vivo ni registrado.
  TEST 4 — Nunca hay mas procesos Tesseract vivos que el limite, aunque se pidan muchos.
  TEST 5 — kill_active_ocr() mata los procesos vivos (pipeline detenido).
  TEST 6 — Lectura normal agotada -> slide "no verificado" (SKIPPED, OCR_TIMEOUT),
           aprobado sin regenerar: no bloquea el carrusel.
  TEST 7 — Lectura alternativa agotada -> decide la lectura normal: un error real
           sigue siendo CRITICAL (nunca se aprueba por un timeout).
  TEST 8 — process_slides con OCR agotado: 1 solo intento, slide aprobado y marcado
           para el reporte (_ocr_timeout_slides); el carrusel sigue.

Sin Tesseract real para los tests de procesos: se usa un "Tesseract falso" hecho con
el propio Python. Sin llamadas a Gemini ($0).
"""

import os
import shutil
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import text_qa  # noqa: E402
from cache_manager import CacheManager  # noqa: E402
from cost_tracker import CostTracker  # noqa: E402
from test_text_qa import DrawnTextClient, _FakeConfig, _load_process_slides, _make_slide  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    line = f"[{status}] {test_id}: {description}" + (f"\n   {detail}" if detail else "")
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))


def _tiny_image():
    from PIL import Image
    return Image.new("RGB", (8, 8), "white")


def _fake_tesseract(tmp: Path, body: str):
    """Parchea text_qa para que 'Tesseract' sea un script de Python con `body`."""
    script = tmp / "fake_tesseract.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    return (
        patch.object(text_qa, "_tesseract_cmd", return_value="fake"),
        patch.object(text_qa, "_build_tesseract_args",
                     side_effect=lambda cmd, image_file, timeout: [sys.executable, str(script), image_file]),
    )


def test_1_limite_concurrencia():
    values = {n: text_qa._ocr_max_concurrency(n) for n in (1, 2, 4, 8, 64, None)}
    ok = values[4] == 3 and values[2] == 1 and values[1] == 1 and max(values.values()) == 3
    report("TEST 1", "Limite de OCR simultaneos: 4 CPU -> 3, 2 CPU -> 1, maximo 3", ok, f"{values}")


def test_2_omp_thread_limit():
    tmp = Path(tempfile.mkdtemp(prefix="ocr_t2_"))
    try:
        p1, p2 = _fake_tesseract(tmp, 'import os; print(os.environ.get("OMP_THREAD_LIMIT"))')
        with p1, p2:
            out = text_qa._run_tesseract(_tiny_image()).strip()
        report("TEST 2", "Cada Tesseract recibe OMP_THREAD_LIMIT=1", out == "1", f"OMP_THREAD_LIMIT={out!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_3_timeout_mata_el_proceso():
    tmp = Path(tempfile.mkdtemp(prefix="ocr_t3_"))
    try:
        p1, p2 = _fake_tesseract(tmp, "import time; time.sleep(60)")
        started = time.time()
        raised = False
        with p1, p2:
            try:
                text_qa._run_tesseract(_tiny_image(), timeout=1)
            except text_qa.OCRTimeout:
                raised = True
        elapsed = time.time() - started
        ok = raised and elapsed < 15 and not text_qa._ACTIVE_OCR
        report("TEST 3", "Tesseract colgado -> OCRTimeout al superar el tiempo maximo, proceso muerto y "
                         "sin registro", ok, f"raised={raised} elapsed={elapsed:.1f}s activos={len(text_qa._ACTIVE_OCR)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_4_nunca_mas_procesos_que_el_limite():
    tmp = Path(tempfile.mkdtemp(prefix="ocr_t4_"))
    peak = {"value": 0}
    stop = threading.Event()

    def _monitor():
        while not stop.is_set():
            with text_qa._ACTIVE_OCR_LOCK:
                alive = sum(1 for p in text_qa._ACTIVE_OCR if p.poll() is None)
            peak["value"] = max(peak["value"], alive)
            time.sleep(0.02)

    try:
        p1, p2 = _fake_tesseract(tmp, "import time; time.sleep(0.6); print('ok')")
        # Se fuerza el limite de un contenedor de 4 CPU (3) para que el test demuestre
        # paralelismo real acotado en cualquier maquina.
        with p1, p2, patch.object(text_qa, "_OCR_SEMAPHORE", threading.BoundedSemaphore(3)):
            monitor = threading.Thread(target=_monitor)
            monitor.start()
            workers = [threading.Thread(target=text_qa._run_tesseract, args=(_tiny_image(),)) for _ in range(8)]
            for w in workers:
                w.start()
            for w in workers:
                w.join(timeout=60)
            stop.set()
            monitor.join()
        ok = 2 <= peak["value"] <= 3
        report("TEST 4", "8 lecturas pedidas a la vez con limite 3 -> paralelismo real, nunca mas de 3 "
                         "Tesseract vivos", ok, f"pico={peak['value']}")
    finally:
        stop.set()
        shutil.rmtree(tmp, ignore_errors=True)


def test_5_kill_active_ocr():
    tmp = Path(tempfile.mkdtemp(prefix="ocr_t5_"))
    outcome = {}
    try:
        p1, p2 = _fake_tesseract(tmp, "import time; time.sleep(60)")
        with p1, p2:
            def _call():
                try:
                    text_qa._run_tesseract(_tiny_image(), timeout=50)
                    outcome["result"] = "termino normal"
                except Exception as exc:  # noqa: BLE001
                    outcome["result"] = type(exc).__name__
            worker = threading.Thread(target=_call)
            worker.start()
            deadline = time.time() + 10
            while not text_qa._ACTIVE_OCR and time.time() < deadline:
                time.sleep(0.05)
            procs = list(text_qa._ACTIVE_OCR)
            killed = text_qa.kill_active_ocr()
            worker.join(timeout=15)
        dead = all(p.poll() is not None for p in procs)
        ok = killed == 1 and dead and not worker.is_alive() and outcome.get("result") != "termino normal"
        report("TEST 5", "kill_active_ocr() mata el Tesseract vivo y libera al pipeline", ok,
               f"killed={killed} dead={dead} resultado={outcome.get('result')}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_6_lectura_normal_agotada_no_bloquea():
    tmp = Path(tempfile.mkdtemp(prefix="ocr_t6_"))
    try:
        img = tmp / "slide.png"
        _tiny_image().save(img)
        with patch.object(text_qa, "_run_tesseract", side_effect=text_qa.OCRTimeout("simulado")):
            r = text_qa.run_text_qa(img, "Texto correcto del slide")
        ok = r.approved and r.skipped and r.reason == text_qa.REASON_OCR_TIMEOUT and r.severity == "SKIPPED"
        report("TEST 6", "Lectura normal agotada -> 'texto no verificado' (SKIPPED/OCR_TIMEOUT), no bloquea",
               ok, f"approved={r.approved} skipped={r.skipped} reason={r.reason} sev={r.severity}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_7_alternativa_agotada_no_aprueba_error_real():
    tmp = Path(tempfile.mkdtemp(prefix="ocr_t7_"))
    try:
        img = tmp / "slide.png"
        _tiny_image().save(img)
        with patch.object(text_qa, "extract_text_from_image", return_value="Texto texto correcto del slide"), \
             patch.object(text_qa, "_run_tesseract", side_effect=text_qa.OCRTimeout("simulado")):
            r = text_qa.run_text_qa(img, "Texto correcto del slide")
        ok = (not r.approved) and r.severity == "CRITICAL" and r.reason == text_qa.REASON_DUPLICATED_TOKEN
        report("TEST 7", "Lectura alternativa agotada -> el error real de la lectura normal sigue CRITICAL",
               ok, f"approved={r.approved} sev={r.severity} reason={r.reason}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_8_process_slides_sigue_con_ocr_agotado():
    mod = _load_process_slides()
    tmp = Path(tempfile.mkdtemp(prefix="ocr_t8_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        client = DrawnTextClient(attempts_by_slide={4: ["Texto correcto del slide"]}, tmp_dir=tmp)
        summary: Dict = {}
        with patch.object(text_qa, "_run_tesseract", side_effect=text_qa.OCRTimeout("simulado")):
            final_status = mod.process_slides(
                [_make_slide(4, "Texto correcto del slide")], {}, "carrusel_interactivo",
                _FakeConfig(max_retries=2), client, CacheManager(carousel_dir),
                CostTracker(tmp, "ocr-test8", 1, 0.0336), "ocr-test8", carousel_dir,
                None, None, None, force_mode="direct", text_qa_summary=summary,
            )
        attempts = client.attempt_count.get(4, 0)
        ok = (attempts == 1 and final_status.get(4) == "APPROVED"
              and summary.get("_ocr_timeout_slides") == {4} and (carousel_dir / "carousel-04.png").exists())
        report("TEST 8", "process_slides con OCR agotado -> 1 intento, sin regenerar, slide entregado y "
                         "marcado 'no verificado' para el reporte", ok,
               f"attempts={attempts} status={final_status} timeouts={summary.get('_ocr_timeout_slides')}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 70)
    print("OCR CON RECURSOS ACOTADOS — SIN LLAMADAS A GEMINI")
    print("=" * 70)
    for fn in [test_1_limite_concurrencia, test_2_omp_thread_limit, test_3_timeout_mata_el_proceso,
               test_4_nunca_mas_procesos_que_el_limite, test_5_kill_active_ocr,
               test_6_lectura_normal_agotada_no_bloquea, test_7_alternativa_agotada_no_aprueba_error_real,
               test_8_process_slides_sigue_con_ocr_agotado]:
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
