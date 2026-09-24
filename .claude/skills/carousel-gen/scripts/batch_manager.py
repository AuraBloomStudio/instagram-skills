"""
batch_manager.py - BATCH MODE: agrupa varios slides en un unico trabajo Batch de Gemini
(ver SKILL.md, seccion "BATCH API"). Pensado para la generacion COMPLETA de un carrusel
cuando conviene (varios slides pendientes a la vez) — nunca para un solo slide faltante,
donde DIRECT MODE es preferible (ver seccion "IMPORTANTE SOBRE BATCH").

Usa el MISMO `GeminiClient` (o `FakeGeminiClient` en tests) que direct_generator.py.
Registra, para cada request enviada, la relacion slide_number <-> request/metadata
(ver `carousel/.batch_state.json`) para poder identificar EXACTAMENTE que slide fallo
si el trabajo termina en PARTIAL_FAILURE — nunca se regenera el carrusel completo por
eso, solo los slides que realmente fallaron.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from direct_generator import GenerationTask
from gemini_client import GeminiImageResult

BATCH_STATE_FILENAME = ".batch_state.json"

# Estados terminales del SDK google-genai (types.JobState) que detienen el polling.
_TERMINAL_STATES = {
    "JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED", "JOB_STATE_PARTIALLY_SUCCEEDED",
}

DEFAULT_POLL_INTERVAL_SECONDS = 10
DEFAULT_MAX_POLL_SECONDS = 600  # 10 minutos


def _state_str(job) -> str:
    """
    Extrae el valor PLANO del estado del batch (ej. 'JOB_STATE_SUCCEEDED'), nunca la
    representacion `str()` del enum de Python (que incluye el prefijo de la clase, ej.
    'JobState.JOB_STATE_SUCCEEDED' y por lo tanto NUNCA coincide con _TERMINAL_STATES).

    BUG REAL CONFIRMADO en produccion (2026-09-16): usar `str(job.state)` directamente
    hacia que el polling nunca detectara un batch ya terminado (`JOB_STATE_SUCCEEDED`),
    esperando los 600s completos de max_poll_seconds y reportando un "Timeout" falso
    sobre un trabajo que en realidad ya habia completado ~500s antes — y disparando una
    regeneracion Batch completa innecesaria. Esta funcion es la unica forma correcta de
    leer el estado; nunca volver a usar `str(job.state)` en otro lugar del codigo.
    """
    state_obj = getattr(job, "state", "")
    value = getattr(state_obj, "value", None)
    if value:
        return value
    name = getattr(state_obj, "name", None)
    if name:
        return name
    return str(state_obj)


def _save_batch_state(carousel_dir: Path, bundle_id: str, batch_name: str, tasks: List[GenerationTask]) -> None:
    state = {
        "bundle_id": bundle_id,
        "batch_name": batch_name,
        "requests": [
            {
                "slide_number": t.slide_number,
                "prompt_hash": t.prompt_hash,
                "status": "SUBMITTED",
            }
            for t in tasks
        ],
    }
    (carousel_dir / BATCH_STATE_FILENAME).write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _update_batch_state_status(carousel_dir: Path, slide_number: int, status: str) -> None:
    state_file = carousel_dir / BATCH_STATE_FILENAME
    if not state_file.exists():
        return
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    for req in state.get("requests", []):
        if req.get("slide_number") == slide_number:
            req["status"] = status
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def generate_batch(
    client,
    tasks: List[GenerationTask],
    carousel_dir: Path,
    bundle_id: str,
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    max_poll_seconds: int = DEFAULT_MAX_POLL_SECONDS,
) -> Dict[int, GeminiImageResult]:
    """
    Ejecuta un trabajo Batch con `tasks` (uno o mas slides). Devuelve
    {slide_number: GeminiImageResult}, identificando exactamente que slide vino de
    cada respuesta via `metadata["slide_number"]` — NUNCA por orden de la lista (el
    orden de resultados de un batch no esta garantizado).
    """
    results: Dict[int, GeminiImageResult] = {}
    if not tasks:
        return results

    inlined_requests = [
        client.build_inlined_request(
            task.prompt,
            task.reference_images,
            metadata={
                "bundle_id": bundle_id,
                "slide_number": str(task.slide_number),
                "prompt_hash": task.prompt_hash,
            },
        )
        for task in tasks
    ]

    # Atajo de test: FakeGeminiClient resuelve el batch sin red ni espera.
    if hasattr(client, "run_fake_batch_and_get_results"):
        _save_batch_state(carousel_dir, bundle_id, "fake-batch-job", tasks)
        for metadata, result in client.run_fake_batch_and_get_results(inlined_requests):
            slide_number = int(metadata["slide_number"])
            results[slide_number] = result
            _update_batch_state_status(carousel_dir, slide_number, "COMPLETED" if result.success else "FAILED")
        return results

    job = client.submit_batch(inlined_requests)
    _save_batch_state(carousel_dir, bundle_id, job.name, tasks)
    print(f"   [OK] Trabajo Batch enviado: {job.name} ({len(tasks)} slides)")

    elapsed = 0
    state = _state_str(job)
    while state not in _TERMINAL_STATES and elapsed < max_poll_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval
        job = client.get_batch(name=job.name)
        state = _state_str(job)
        print(f"   [Batch {job.name}] estado: {state} ({elapsed}s)")

    if state not in _TERMINAL_STATES:
        error_msg = f"Timeout esperando el trabajo Batch tras {max_poll_seconds}s (ultimo estado: {state})"
        for task in tasks:
            results[task.slide_number] = GeminiImageResult(success=False, error=error_msg)
            _update_batch_state_status(carousel_dir, task.slide_number, "FAILED")
        return results

    dest = getattr(job, "dest", None)
    inlined_responses = getattr(dest, "inlined_responses", None) if dest else None

    if not inlined_responses:
        error_msg = f"El trabajo Batch termino en estado {state} pero no devolvio 'inlined_responses'"
        for task in tasks:
            results[task.slide_number] = GeminiImageResult(success=False, error=error_msg)
            _update_batch_state_status(carousel_dir, task.slide_number, "FAILED")
        return results

    for response_item in inlined_responses:
        metadata = getattr(response_item, "metadata", None) or {}
        slide_number_raw = metadata.get("slide_number")
        if slide_number_raw is None:
            continue
        slide_number = int(slide_number_raw)

        error = getattr(response_item, "error", None)
        if error:
            results[slide_number] = GeminiImageResult(success=False, error=str(error))
            _update_batch_state_status(carousel_dir, slide_number, "FAILED")
            continue

        gen_response = getattr(response_item, "response", None)
        if gen_response is None:
            results[slide_number] = GeminiImageResult(success=False, error="Respuesta de batch sin 'response' ni 'error'")
            _update_batch_state_status(carousel_dir, slide_number, "FAILED")
            continue

        image_bytes = None
        for candidate in getattr(gen_response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is not None and getattr(inline_data, "data", None):
                    image_bytes = inline_data.data
                    break
            if image_bytes:
                break

        # BUG REAL CONFIRMADO (2026-09-16): esta funcion nunca extraia usage_metadata de
        # la respuesta del batch, asi que actual_usage quedaba en null/0 para TODA
        # generacion en BATCH MODE (el registro de tokens solo funcionaba en DIRECT
        # MODE, via gemini_client._extract_result). Corregido aqui replicando la misma
        # extraccion (model_dump() del objeto usage_metadata del SDK).
        usage = None
        usage_obj = getattr(gen_response, "usage_metadata", None)
        if usage_obj is not None:
            try:
                usage = usage_obj.model_dump()
            except Exception:  # noqa: BLE001
                usage = {"raw": str(usage_obj)}

        if image_bytes:
            results[slide_number] = GeminiImageResult(success=True, image_bytes=image_bytes, usage_metadata=usage)
            _update_batch_state_status(carousel_dir, slide_number, "COMPLETED")
        else:
            results[slide_number] = GeminiImageResult(success=False, error="Respuesta de batch sin imagen (inline_data vacio)", usage_metadata=usage)
            _update_batch_state_status(carousel_dir, slide_number, "FAILED")

    # Cualquier task cuyo slide_number no aparecio en absoluto en inlined_responses
    # (caso raro, pero posible) se marca como fallido explicitamente — nunca se asume
    # exito por omision.
    for task in tasks:
        if task.slide_number not in results:
            results[task.slide_number] = GeminiImageResult(success=False, error="El slide no aparecio en las respuestas del batch")
            _update_batch_state_status(carousel_dir, task.slide_number, "FAILED")

    return results
