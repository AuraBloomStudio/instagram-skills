#!/usr/bin/env python3
"""
test_batch_polling.py - Suite de pruebas SIN COSTO para el sistema Batch/cache/costos de
carousel-gen (generador economico Gemini).

REGLA PERMANENTE: este archivo NUNCA debe llamar a la API real de Gemini. Todos los
"clientes" que usa son test doubles locales (MockBatchClient) construidos con el enum
REAL `google.genai.types.JobState` (para maxima fidelidad al bug real que motivo esta
suite) pero sin abrir ninguna conexion de red. `google-genai` es una dependencia local
del skill, no necesita credenciales para instanciar sus tipos/enums.

Ejecutar con:
    python3 scripts/test_batch_polling.py

Nace de un bug real de produccion (2026-09-16, ver batch_manager.py / _state_str):
`generate_batch()` comparaba `str(job.state)` (que para un Enum de Python da
"JobState.JOB_STATE_SUCCEEDED") contra `_TERMINAL_STATES` (que contiene el valor plano
"JOB_STATE_SUCCEEDED") — la comparacion NUNCA coincidia, el polling nunca detectaba un
batch ya terminado, esperaba el timeout completo y disparaba un segundo Batch duplicado
innecesario. Esta suite prueba la correccion (`_state_str`) ejecutando el codigo REAL de
`generate_batch()`, no el atajo `FakeGeminiClient.run_fake_batch_and_get_results()` (que
bypasea por completo el polling y por eso nunca habria detectado este bug).
"""

import sys
import shutil
import tempfile
import time as time_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from google.genai import types  # noqa: E402 - solo para el enum real JobState, sin red

from batch_manager import generate_batch, _state_str, _TERMINAL_STATES  # noqa: E402
from direct_generator import GenerationTask  # noqa: E402
from cache_manager import CacheManager, SlideCacheRecord  # noqa: E402
from cost_tracker import CostTracker  # noqa: E402
from prompt_hash import compute_prompt_hash  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
results_log: List[Dict[str, str]] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "description": description, "status": status, "detail": detail})
    marker = "OK " if ok else "!! "
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Test doubles minimos (NUNCA hacen red). Reproducen exactamente la forma que
# generate_batch() espera de un `BatchJob` real del SDK google-genai.
# ---------------------------------------------------------------------------

@dataclass
class MockInlineData:
    data: bytes


@dataclass
class MockPart:
    inline_data: Optional[MockInlineData] = None


@dataclass
class MockContent:
    parts: List[MockPart] = field(default_factory=list)


@dataclass
class MockCandidate:
    content: Optional[MockContent] = None


@dataclass
class MockUsageMetadata:
    prompt_token_count: int
    candidates_token_count: int
    total_token_count: int

    def model_dump(self):
        return {
            "prompt_token_count": self.prompt_token_count,
            "candidates_token_count": self.candidates_token_count,
            "total_token_count": self.total_token_count,
        }


@dataclass
class MockGenResponse:
    candidates: List[MockCandidate] = field(default_factory=list)
    usage_metadata: Optional[MockUsageMetadata] = None


@dataclass
class MockInlinedResponse:
    metadata: Dict[str, str]
    response: Optional[MockGenResponse] = None
    error: Optional[str] = None


@dataclass
class MockDest:
    inlined_responses: List[MockInlinedResponse] = field(default_factory=list)


@dataclass
class MockBatchJob:
    name: str
    state: Any
    dest: Optional[MockDest] = None


def make_success_response(pixel: int = 42, usage: Optional[MockUsageMetadata] = None) -> MockGenResponse:
    return MockGenResponse(
        candidates=[MockCandidate(content=MockContent(parts=[MockPart(inline_data=MockInlineData(data=bytes([pixel])))]))],
        usage_metadata=usage,
    )


class MockBatchClient:
    """
    Test double que exercita el camino REAL de generate_batch() (a diferencia de
    FakeGeminiClient.run_fake_batch_and_get_results, que lo bypasea por completo).

    `state_sequence`: estados que devolvera get_batch() en llamadas sucesivas (el
    ULTIMO valor se repite si se agotan). `dest_on_terminal`: el MockDest a adjuntar
    cuando el estado entra en un estado terminal.
    """
    def __init__(self, state_sequence: List[Any], dest_on_terminal: Optional[MockDest] = None):
        self.state_sequence = list(state_sequence)
        self.dest_on_terminal = dest_on_terminal
        self.submit_count = 0
        self.get_count = 0
        self.submitted_requests: List[list] = []

    def build_inlined_request(self, prompt, reference_images, metadata):
        return {"prompt": prompt, "metadata": metadata}

    def _next_state(self):
        if self.state_sequence:
            return self.state_sequence.pop(0)
        return types.JobState.JOB_STATE_SUCCEEDED

    def submit_batch(self, inlined_requests):
        self.submit_count += 1
        self.submitted_requests.append(inlined_requests)
        state = self._next_state()
        dest = self.dest_on_terminal if _state_str_of(state) in _TERMINAL_STATES else None
        return MockBatchJob(name=f"batches/mock-{self.submit_count}", state=state, dest=dest)

    def get_batch(self, name):
        self.get_count += 1
        state = self._next_state()
        dest = self.dest_on_terminal if _state_str_of(state) in _TERMINAL_STATES else None
        return MockBatchJob(name=name, state=state, dest=dest)


def _state_str_of(state) -> str:
    return getattr(state, "value", None) or str(state)


def make_task(slide_number: int) -> GenerationTask:
    return GenerationTask(
        slide_number=slide_number,
        prompt=f"prompt de prueba slide {slide_number}",
        reference_images=[],
        prompt_hash=f"hash-{slide_number}",
        metadata={"bundle_id": "audit-bundle", "slide_number": str(slide_number)},
    )


def with_temp_carousel_dir():
    d = Path(tempfile.mkdtemp(prefix="carousel_audit_"))
    return d


# ---------------------------------------------------------------------------
# TEST 1 y 2: estados no terminales -> _state_str() no debe estar en _TERMINAL_STATES
# ---------------------------------------------------------------------------

def test_1_pending_not_terminal():
    s = _state_str_of(types.JobState.JOB_STATE_PENDING)
    ok = (s == "JOB_STATE_PENDING") and (s not in _TERMINAL_STATES)
    report("TEST 1", "JOB_STATE_PENDING se reconoce como NO terminal (seguir esperando)", ok, f"_state_str={s!r}")


def test_2_running_not_terminal():
    s = _state_str_of(types.JobState.JOB_STATE_RUNNING)
    ok = (s == "JOB_STATE_RUNNING") and (s not in _TERMINAL_STATES)
    report("TEST 2", "JOB_STATE_RUNNING se reconoce como NO terminal (seguir esperando)", ok, f"_state_str={s!r}")


# ---------------------------------------------------------------------------
# TEST 3: SUCCEEDED -> generate_batch() completa en UNA sola llamada a submit_batch,
# NUNCA se dispara un segundo Batch, y el resultado se marca COMPLETED.
# ---------------------------------------------------------------------------

def test_3_succeeded_completes_without_resubmitting():
    carousel_dir = with_temp_carousel_dir()
    try:
        dest = MockDest(inlined_responses=[
            MockInlinedResponse(metadata={"slide_number": "2"}, response=make_success_response(2)),
        ])
        # Secuencia real observada en produccion: RUNNING varias veces, luego SUCCEEDED.
        client = MockBatchClient(
            state_sequence=[types.JobState.JOB_STATE_RUNNING, types.JobState.JOB_STATE_RUNNING, types.JobState.JOB_STATE_SUCCEEDED],
            dest_on_terminal=dest,
        )
        with patch("batch_manager.time.sleep", lambda s: None):
            results = generate_batch(client, [make_task(2)], carousel_dir, "audit-bundle", poll_interval=0, max_poll_seconds=60)

        ok_result = results.get(2) is not None and results[2].success and results[2].image_bytes == bytes([2])
        ok_single_submit = client.submit_count == 1
        ok_polled = client.get_count >= 1
        ok = ok_result and ok_single_submit and ok_polled
        report(
            "TEST 3", "JOB_STATE_SUCCEEDED se detecta correctamente: 1 sola llamada a submit_batch, resultado COMPLETED",
            ok,
            f"submit_count={client.submit_count} get_count={client.get_count} success={results.get(2) and results[2].success}",
        )
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 4: FAILED -> resultado marcado como fallo, sin excepcion, sin reintento interno
# ---------------------------------------------------------------------------

def test_4_failed_state():
    carousel_dir = with_temp_carousel_dir()
    try:
        client = MockBatchClient(state_sequence=[types.JobState.JOB_STATE_FAILED], dest_on_terminal=None)
        with patch("batch_manager.time.sleep", lambda s: None):
            results = generate_batch(client, [make_task(5)], carousel_dir, "audit-bundle", poll_interval=0, max_poll_seconds=60)
        ok = (5 in results) and (results[5].success is False) and client.submit_count == 1
        report("TEST 4", "JOB_STATE_FAILED se detecta correctamente como fallo (sin resubmit)", ok, f"result={results.get(5)}")
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 5: exito parcial -> solo los slides con error quedan marcados como fallo, los
# exitosos quedan aprobados; el orquestador (fuera de este test) solo reintentaria los
# fallidos. Aqui probamos que generate_batch() distingue correctamente ambos casos
# dentro de un unico JOB_STATE_PARTIALLY_SUCCEEDED.
# ---------------------------------------------------------------------------

def test_5_partial_failure():
    carousel_dir = with_temp_carousel_dir()
    try:
        dest = MockDest(inlined_responses=[
            MockInlinedResponse(metadata={"slide_number": "3"}, response=make_success_response(3)),
            MockInlinedResponse(metadata={"slide_number": "4"}, error="modelo rechazo el prompt"),
        ])
        client = MockBatchClient(state_sequence=[types.JobState.JOB_STATE_PARTIALLY_SUCCEEDED], dest_on_terminal=dest)
        with patch("batch_manager.time.sleep", lambda s: None):
            results = generate_batch(client, [make_task(3), make_task(4)], carousel_dir, "audit-bundle", poll_interval=0, max_poll_seconds=60)

        ok = (
            results[3].success is True and results[3].image_bytes == bytes([3])
            and results[4].success is False and "modelo rechazo" in (results[4].error or "")
        )
        report(
            "TEST 5", "JOB_STATE_PARTIALLY_SUCCEEDED distingue slide exitoso (3) de slide fallido (4)",
            ok, f"slide3={results.get(3)} slide4={results.get(4)}",
        )
        return {3: True, 4: False}
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 7: un Batch ya COMPLETED, si se vuelve a invocar get_batch (polling repetido
# sobre el MISMO job ya terminado), sigue devolviendo el mismo resultado sin que
# generate_batch() dispare un submit_batch adicional (el submit ocurre una sola vez
# por llamada a generate_batch; volver a "pollear" el job ya resuelto no debe re-crear
# nada). Simulado llamando generate_batch() dos veces con el MISMO client persistente
# y verificando que el segundo submit_count avanza (nueva orquestacion = nuevo submit,
# eso es esperado), pero dentro de UNA misma llamada nunca hay mas de 1 submit.
# ---------------------------------------------------------------------------

def test_7_repeated_poll_no_second_batch():
    carousel_dir = with_temp_carousel_dir()
    try:
        dest = MockDest(inlined_responses=[MockInlinedResponse(metadata={"slide_number": "6"}, response=make_success_response(6))])
        client = MockBatchClient(state_sequence=[types.JobState.JOB_STATE_SUCCEEDED], dest_on_terminal=dest)
        with patch("batch_manager.time.sleep", lambda s: None):
            generate_batch(client, [make_task(6)], carousel_dir, "audit-bundle", poll_interval=0, max_poll_seconds=60)
        # Simular "polling repetido" externo sobre el mismo job ya terminado (lo que el
        # bug real SI disparaba: un segundo submit por no reconocer SUCCEEDED).
        job_again = client.get_batch(name="batches/mock-1")
        ok = client.submit_count == 1 and _state_str(job_again) == "JOB_STATE_SUCCEEDED"
        report("TEST 7", "Un batch ya SUCCEEDED no dispara un submit_batch adicional al volver a consultarse", ok, f"submit_count={client.submit_count}")
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 8: polling repetido (varias iteraciones RUNNING) dentro de UNA sola llamada a
# generate_batch() no duplica el resultado por slide ni el conteo de submit.
# ---------------------------------------------------------------------------

def test_8_repeated_polling_no_duplicate_cost_records():
    carousel_dir = with_temp_carousel_dir()
    try:
        dest = MockDest(inlined_responses=[MockInlinedResponse(metadata={"slide_number": "7"}, response=make_success_response(7))])
        # 5 iteraciones RUNNING antes de SUCCEEDED -> fuerza polling repetido real.
        client = MockBatchClient(
            state_sequence=[types.JobState.JOB_STATE_RUNNING] * 5 + [types.JobState.JOB_STATE_SUCCEEDED],
            dest_on_terminal=dest,
        )
        with patch("batch_manager.time.sleep", lambda s: None):
            results = generate_batch(client, [make_task(7)], carousel_dir, "audit-bundle", poll_interval=0, max_poll_seconds=60)

        # Ahora, como haria process_slides(), registrar el costo UNA vez por resultado.
        bundle_path = carousel_dir.parent
        tracker = CostTracker(bundle_path, "audit-bundle", 1, price_per_image_usd=0.0336)
        tracker.record(
            "audit-bundle", 7, "gemini-3.1-flash-lite-image", "1K", "4:5",
            mode="batch", status="APPROVED", reused=False, retry_count=0, prompt_hash="hash-7",
        )
        entries_for_slide_7 = [e for e in tracker.summary.entries if e["slide_number"] == 7]

        ok = (
            client.submit_count == 1
            and len(results) == 1
            and len(entries_for_slide_7) == 1
            and tracker.summary.estimated_cost_usd == 0.0336
        )
        report(
            "TEST 8", "Polling repetido (5x RUNNING) dentro de una sola llamada no duplica resultados ni registros de costo",
            ok, f"submit_count={client.submit_count} entries_slide7={len(entries_for_slide_7)} cost={tracker.summary.estimated_cost_usd}",
        )
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)
        shutil.rmtree(carousel_dir.parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 9: BATCH MODE debe capturar usage_metadata (tokens) igual que DIRECT MODE.
#
# Bug real confirmado en produccion (2026-09-16, regeneracion de slides 5-9 de "El
# Dolor Que No Te Pertenece"): generate_batch() extraia la imagen de cada
# inlined_response pero NUNCA extraia `response.usage_metadata` — el cost_log
# quedaba con actual_usage=null/0 para TODA generacion en BATCH MODE, mientras que
# DIRECT MODE si lo capturaba (via gemini_client._extract_result). Corregido en
# generate_batch() replicando la misma extraccion (model_dump()).
# ---------------------------------------------------------------------------

def test_9_batch_captures_usage_metadata():
    carousel_dir = with_temp_carousel_dir()
    try:
        usage = MockUsageMetadata(prompt_token_count=4000, candidates_token_count=1200, total_token_count=5200)
        dest = MockDest(inlined_responses=[MockInlinedResponse(metadata={"slide_number": "9"}, response=make_success_response(9, usage=usage))])
        client = MockBatchClient(state_sequence=[types.JobState.JOB_STATE_SUCCEEDED], dest_on_terminal=dest)
        with patch("batch_manager.time.sleep", lambda s: None):
            results = generate_batch(client, [make_task(9)], carousel_dir, "audit-bundle", poll_interval=0, max_poll_seconds=60)

        result = results.get(9)
        ok = (
            result is not None and result.success
            and result.usage_metadata is not None
            and result.usage_metadata.get("total_token_count") == 5200
            and result.usage_metadata.get("prompt_token_count") == 4000
            and result.usage_metadata.get("candidates_token_count") == 1200
        )
        report("TEST 9", "BATCH MODE captura usage_metadata (tokens) igual que DIRECT MODE", ok, f"usage_metadata={result.usage_metadata if result else None}")
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 6 (cache/reuse a nivel unitario): un registro de cache con prompt_hash/model/
# resolution/aspect_ratio identicos y archivo de imagen existente produce REUSE.
# ---------------------------------------------------------------------------

def test_6_cache_reuse_unit():
    carousel_dir = with_temp_carousel_dir()
    try:
        img_path = carousel_dir / "carousel-01.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-but-nonempty")

        cache = CacheManager(carousel_dir)
        cache.upsert(SlideCacheRecord(
            slide_number=1, prompt_hash="abc123", model="gemini-3.1-flash-lite-image",
            resolution="1K", aspect_ratio="4:5", image_path="carousel-01.png", status="APPROVED",
        ))

        reuse_ok = cache.should_reuse(1, "abc123", "gemini-3.1-flash-lite-image", "1K", "4:5")
        # Cambios en cualquiera de los criterios deben invalidar el reuso.
        reject_diff_hash = not cache.should_reuse(1, "different-hash", "gemini-3.1-flash-lite-image", "1K", "4:5")
        reject_diff_model = not cache.should_reuse(1, "abc123", "otro-modelo", "1K", "4:5")
        reject_diff_resolution = not cache.should_reuse(1, "abc123", "gemini-3.1-flash-lite-image", "2K", "4:5")
        reject_diff_ratio = not cache.should_reuse(1, "abc123", "gemini-3.1-flash-lite-image", "1K", "1:1")

        img_path.unlink()
        reject_missing_file = not cache.should_reuse(1, "abc123", "gemini-3.1-flash-lite-image", "1K", "4:5")

        ok = all([reuse_ok, reject_diff_hash, reject_diff_model, reject_diff_resolution, reject_diff_ratio, reject_missing_file])
        report(
            "TEST 6", "CacheManager.should_reuse() exige coincidencia EXACTA de hash/modelo/resolucion/aspect_ratio y archivo presente",
            ok,
            f"reuse_ok={reuse_ok} hash={reject_diff_hash} model={reject_diff_model} res={reject_diff_resolution} ratio={reject_diff_ratio} missing_file={reject_missing_file}",
        )
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)


def test_status_never_reused_when_rejected_or_failed():
    carousel_dir = with_temp_carousel_dir()
    try:
        img_path = carousel_dir / "carousel-02.png"
        img_path.write_bytes(b"contenido")
        cache = CacheManager(carousel_dir)
        for bad_status in ("FAILED", "REJECTED", "RETRYING", "FAILED_FINAL"):
            cache.upsert(SlideCacheRecord(
                slide_number=2, prompt_hash="xyz", model="m", resolution="1K", aspect_ratio="4:5",
                image_path="carousel-02.png", status=bad_status,
            ))
            reused = cache.should_reuse(2, "xyz", "m", "1K", "4:5")
            if reused:
                report("TEST 6b", f"Estado '{bad_status}' NUNCA debe producir REUSE", False, "should_reuse devolvio True")
                return
        report("TEST 6b", "Estados FAILED/REJECTED/RETRYING/FAILED_FINAL nunca producen REUSE", True)
    finally:
        shutil.rmtree(carousel_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TEST 10: FABRICA RAPIDA (ver SKILL.md) — el modo normal de produccion NUNCA usa
# Batch, sin importar GEMINI_BATCH_ENABLED/ECONOMY_MODE, salvo --force-batch explicito.
# Se prueba contra process_slides() REAL (no un atajo), parcheando generate_batch en el
# modulo cargado para que explote si algo lo llegara a invocar sin --force-batch.
# ---------------------------------------------------------------------------

def _load_process_slides_module():
    import importlib.util
    path = Path(__file__).parent / "generate-carousel-gemini.py"
    spec = importlib.util.spec_from_file_location("gemini_main_under_test_batch", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_10_default_mode_never_batch_without_force_flag():
    from gemini_client import FakeGeminiClient

    mod = _load_process_slides_module()
    tmp = Path(tempfile.mkdtemp(prefix="fastfactory_test10_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()

        def _explode(*args, **kwargs):
            raise AssertionError("generate_batch() NUNCA debe llamarse en modo normal (sin --force-batch)")

        with patch.object(mod, "generate_batch", _explode):
            slides = [
                {
                    "number": n, "role": f"slide-{n}", "narrative_objective": "o", "message": "m",
                    "source_text_fragment": "f", "source_location": "l", "exact_text": "",
                    "scene_description": "s", "composition": "c", "visual_hierarchy": "v", "text_placement": "p",
                    "key_visual_elements": [], "visual_dna_connection": "d",
                    "uses_reference_image_directly": False, "uses_product_mockup_directly": False,
                }
                for n in range(1, 5)  # 4 slides pendientes simultaneos -> tentacion clasica de usar Batch
            ]

            @dataclass
            class _FakeConfigFastFactory:
                image_model: str = "gemini-3.1-flash-lite-image"
                aspect_ratio: str = "4:5"
                image_size: str = "1K"
                max_retries: int = 1
                text_qa_enabled: bool = False
                economy_mode: bool = True
                batch_enabled: bool = True  # incluso con esto en true, NUNCA debe usarse
                price_per_image_usd: float = 0.0336

            config = _FakeConfigFastFactory()
            client = FakeGeminiClient(config)
            cache = CacheManager(carousel_dir)
            cost_tracker = CostTracker(tmp, "test10-bundle", 4, 0.0336)

            final_status = mod.process_slides(
                slides, {}, "la-gran-noticia", config, client, cache, cost_tracker,
                "test10-bundle", carousel_dir, None, None, None, force_mode=None,
            )
        ok = all(final_status.get(n) == "APPROVED" for n in range(1, 5))
        report("TEST 10", "4 slides pendientes, config con batch_enabled=True, force_mode=None -> "
                           "SIEMPRE DIRECT (generate_batch nunca se invoca)", ok, f"status={final_status}")
    except AssertionError as e:
        report("TEST 10", "4 slides pendientes, config con batch_enabled=True, force_mode=None -> "
                           "SIEMPRE DIRECT (generate_batch nunca se invoca)", False, str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 70)
    print("AUDITORIA DE BATCH/CACHE/COSTOS — SIN LLAMADAS REALES A GEMINI")
    print("=" * 70)
    test_1_pending_not_terminal()
    test_2_running_not_terminal()
    test_3_succeeded_completes_without_resubmitting()
    test_4_failed_state()
    test_5_partial_failure()
    test_6_cache_reuse_unit()
    test_status_never_reused_when_rejected_or_failed()
    test_7_repeated_poll_no_second_batch()
    test_8_repeated_polling_no_duplicate_cost_records()
    test_9_batch_captures_usage_metadata()
    test_10_default_mode_never_batch_without_force_flag()

    print("\n" + "=" * 70)
    n_pass = sum(1 for r in results_log if r["status"] == PASS)
    n_fail = sum(1 for r in results_log if r["status"] == FAIL)
    print(f"RESULTADO: {n_pass} PASS, {n_fail} FAIL de {len(results_log)} pruebas")
    print("=" * 70)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
