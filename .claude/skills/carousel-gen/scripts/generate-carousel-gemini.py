#!/usr/bin/env python3
"""
generate-carousel-gemini.py - Genera carruseles Instagram usando Google Gemini
(Nano Banana 2 Lite), el generador ECONOMICO de carousel-gen (ver SKILL.md, seccion
"COST OPTIMIZATION").

Este es el generador PRINCIPAL desde la migracion economica. El generador legacy de Kie
AI (`generate-carousel.py`) sigue existiendo pero esta DESACTIVADO por defecto
(KIE_ENABLED=false) — nunca se llama automaticamente.

Uso (interfaz de linea de comandos identica al script legacy, para no romper SKILL.md):
    python3 generate-carousel-gemini.py <bundle_id>
    python3 generate-carousel-gemini.py <bundle_id> --regenerate-slides "2,4,6"
    python3 generate-carousel-gemini.py <bundle_id> --dry-run
    python3 generate-carousel-gemini.py <bundle_id> --add-copy "/ruta/copy.json"

Flags adicionales de esta migracion:
    --skip-interactive   (igual que en el script legacy; se acepta por compatibilidad,
                           este script nunca pregunta interactivamente por logos)
    --force-direct       Fuerza DIRECT MODE para todos los slides pendientes de esta corrida
    --force-batch        Fuerza BATCH MODE para todos los slides pendientes de esta corrida
    --fake-provider       SOLO PRUEBAS: usa un proveedor Gemini falso (sin red, sin costo,
                           genera PNGs validos deterministas) para validar toda la
                           orquestacion (cache/retries/QA/batch-direct) sin GEMINI_API_KEY
                           real. Puede combinarse con --fake-fail-slides "N,M" para simular
                           fallos y probar el flujo de reintentos.

Requisitos:
    - Variable de entorno GEMINI_API_KEY configurada (salvo con --fake-provider)
    - Archivo brief.json en el bundle (creado por el workflow de SKILL.md)
"""

import sys
import json
import time
import argparse
import dataclasses
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import (  # noqa: E402
    OUTPUTS_DIR, MAX_SLIDES,
    load_brief, detect_entities_in_slides, build_prompt_for_slide,
    generate_assets_needed_md, generate_manifest, export_final_slides_to_downloads,
    save_copy_deliverables, save_costo_carrusel,
)
from gemini_config import load_config, GeminiConfig  # noqa: E402
from gemini_client import GeminiClient, FakeGeminiClient, GeminiImageResult  # noqa: E402
from reference_manager import decide_reference_plan, reference_identifier, ReferenceMode  # noqa: E402
from prompt_hash import compute_prompt_hash, hash_file_bytes  # noqa: E402
from cache_manager import CacheManager, SlideCacheRecord  # noqa: E402
from qa import run_qa  # noqa: E402
from cost_tracker import CostTracker  # noqa: E402
from direct_generator import GenerationTask, generate_direct  # noqa: E402
from batch_manager import generate_batch  # noqa: E402
from text_qa import run_text_qa, TextQAResult  # noqa: E402

# FABRICA RAPIDA / PARALELIZACION (ver SKILL.md): el Text QA (OCR local) de los slides
# de una misma tanda es independiente slide-a-slide, asi que se ejecuta en paralelo con
# el mismo tope de workers que la generacion (direct_generator._MAX_WORKERS) — nunca
# secuencial imagen-por-imagen.
_QA_MAX_WORKERS = 9


def _iso_delta_seconds(start_iso: Optional[str], end_iso: Optional[str]) -> Optional[float]:
    """Diferencia en segundos entre dos timestamps ISO 8601, o None si cualquiera falta
    o no se puede parsear — NUNCA se inventa una duracion (ver SKILL.md "CRONOMETRO
    GLOBAL REAL": "Si algún dato no está disponible, poner N/D. Nunca poner 0 por
    defecto si no fue medido")."""
    if not start_iso or not end_iso:
        return None
    try:
        from datetime import datetime, timezone
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        # Normalize: if one is aware and the other naive, treat naive as UTC
        if (start.tzinfo is None) != (end.tzinfo is None):
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            else:
                end = end.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0.0, (end - start).total_seconds())


def _record_pre_generation_phase_seconds(cost_tracker: CostTracker, timing_markers: Dict[str, Any]) -> None:
    """Convierte las marcas de tiempo opcionales de `brief.json["timing"]` (ver SKILL.md
    "CRONOMETRO GLOBAL REAL") en las fases "preparation"/"reference"/"brief" de
    cost_log.json. Cada marca es un timestamp ISO 8601 que Claude registra durante el
    workflow (PASO 0/1/3/8), ANTES de que este script exista:
      - skill_started_at: justo al empezar el PASO 0 (antes de pedir la imagen).
      - reference_received_at: justo despues de guardar carousel/assets/viral-reference.png.
      - source_text_confirmed_at: justo despues de confirmar source_text (fin PASO 3).
      - brief_approved_at: justo despues de que el usuario aprueba brief.json (fin PASO 8).
    Cualquier marca ausente deja esa fase sin registrar (N/D en COSTO_CARRUSEL.txt) —
    nunca se escribe 0 por una fase que no se pudo medir."""
    skill_started = timing_markers.get("skill_started_at")
    reference_received = timing_markers.get("reference_received_at")
    text_confirmed = timing_markers.get("source_text_confirmed_at")
    brief_approved = timing_markers.get("brief_approved_at")

    preparation = _iso_delta_seconds(skill_started, reference_received)
    if preparation is not None:
        cost_tracker.record_phase_seconds("preparation", preparation)

    reference = _iso_delta_seconds(reference_received, text_confirmed)
    if reference is not None:
        cost_tracker.record_phase_seconds("reference", reference)

    brief_phase = _iso_delta_seconds(text_confirmed, brief_approved)
    if brief_phase is not None:
        cost_tracker.record_phase_seconds("brief", brief_phase)


def _accumulate_phase_seconds(cost_tracker: CostTracker, phase: str, delta_seconds: float) -> None:
    """Suma `delta_seconds` al tiempo ya acumulado de `phase` en cost_log.json (ver
    SKILL.md "CRONOMETRO GLOBAL REAL"). Se usa para fases que se repiten varias veces
    dentro de la misma corrida (una ronda de generacion/QA por cada retry_round) — cada
    ronda SUMA a la fase, nunca la sobrescribe."""
    previous = cost_tracker.summary.phase_seconds.get(phase) or 0.0
    cost_tracker.record_phase_seconds(phase, previous + delta_seconds)


def _build_authorized_extra_tokens(brief: Dict[str, Any]) -> List[str]:
    """Textos autorizados que pueden aparecer en la imagen ADEMÁS del exact_text del slide:
    firma/atribucion, handle, nombre del producto, CTA. Usados por Text QA para distinguir
    UNAUTHORIZED_TEXT_ELEMENT (texto no autorizado) de OCR noise."""
    auth_texts: List[str] = []
    vdna = brief.get("visual_dna") or {}
    for key in ("attribution", "attribution_text", "footer_text", "signature_text"):
        if vdna.get(key):
            auth_texts.append(str(vdna[key]))
    product = brief.get("product") or {}
    for key in ("product_name", "cta", "author"):
        if product.get(key):
            auth_texts.append(str(product[key]))
    return auth_texts


def build_critical_phrases(brief: Dict[str, Any], slide: Dict[str, Any]) -> List[tuple]:
    """
    Construye la lista de (label, phrase) que Text QA debe verificar con maxima
    exigencia en este slide especifico (ver SKILL.md "TEXT QA", seccion "PRODUCTOS" y
    "CTA"): el nombre del producto/titulo del libro cuando el slide lo muestra
    (uses_product_mockup_directly), y el propio exact_text del slide de CTA. Nunca
    aplica a slides que no tienen relacion con el producto — evita falsos positivos.
    """
    phrases = []
    if slide.get("uses_product_mockup_directly"):
        product_name = (brief.get("product") or {}).get("product_name")
        if product_name:
            phrases.append(("PRODUCT_TITLE_MISMATCH", product_name))
    return phrases


def build_reference_prompt_and_hash(
    slide: Dict[str, Any],
    visual_dna: Dict[str, Any],
    carousel_type: str,
    config: GeminiConfig,
    slide1_anchor_path: Optional[Path],
    reference_image_path: Optional[Path],
    product_mockup_path: Optional[Path],
) -> Optional[Dict[str, Any]]:
    """
    Resuelve el plan de referencias de un slide (REGLA DE REFERENCIAS), construye su
    prompt final y su prompt_hash. Devuelve None si el slide requiere un mockup real que
    no esta disponible (caso bloqueante para ESE slide especifico).
    """
    resolved_refs = decide_reference_plan(slide, slide1_anchor_path, reference_image_path, product_mockup_path)

    if any(r.mode == ReferenceMode.BOOK_MOCKUP and r.image_path is None for r in resolved_refs):
        return None

    attached_roles = [r.role_tag for r in resolved_refs if r.role_tag != "none"]
    prompt = build_prompt_for_slide(slide, visual_dna, carousel_type, attached_images=attached_roles)

    reference_images_bytes = []
    for ref in resolved_refs:
        if ref.image_path is not None:
            reference_images_bytes.append(ref.image_path.read_bytes())

    ref_id = reference_identifier(resolved_refs, hash_file_bytes)
    p_hash = compute_prompt_hash(
        prompt_text=prompt,
        slide=slide,
        visual_dna=visual_dna,
        carousel_type=carousel_type,
        aspect_ratio=config.aspect_ratio,
        image_size=config.image_size,
        model=config.image_model,
        reference_image_id=ref_id,
    )

    return {
        "prompt": prompt,
        "reference_images": reference_images_bytes,
        "prompt_hash": p_hash,
        "attached_roles": attached_roles,
    }


def save_image_and_qa(
    carousel_dir: Path,
    slide_number: int,
    image_bytes: bytes,
    config: GeminiConfig,
    expected_text: str,
    critical_phrases: Optional[List[tuple]] = None,
    authorized_extra_tokens: Optional[List[str]] = None,
    uses_product_mockup: bool = False,
) -> tuple:
    """
    Descarga (guarda) la imagen generada y corre el QA en DOS capas (ver SKILL.md
    "TEXT QA"):
      1. QA ESTRUCTURAL (qa.py): archivo valido, dimensiones, relacion de aspecto.
      2. TEXT QA (text_qa.py): el texto REALMENTE renderizado en la imagen (via OCR
         100% local, sin llamar a Gemini) coincide con `expected_text` (exact_text del
         slide en brief.json). Solo se ejecuta si la capa 1 aprobo — no tiene sentido
         hacer OCR sobre un archivo corrupto o con dimensiones incorrectas.

    Devuelve (ok: bool, path, reason: str, text_qa_result: Optional[TextQAResult]).
    `ok=False` si CUALQUIERA de las dos capas rechaza.
    """
    output_path = carousel_dir / f"carousel-{slide_number:02d}.png"
    output_path.write_bytes(image_bytes)

    qa_result = run_qa(output_path, expected_aspect_ratio=config.aspect_ratio)
    if not qa_result.approved:
        return False, output_path, qa_result.reason, None

    if not config.text_qa_enabled:
        return True, output_path, qa_result.reason, None

    text_qa_result = run_text_qa(output_path, expected_text, critical_phrases=critical_phrases,
                                  authorized_extra_tokens=authorized_extra_tokens,
                                  uses_product_mockup=uses_product_mockup)
    if text_qa_result.skipped:
        print(f"   [WARN] Slide {slide_number} - Text QA omitido: {text_qa_result.detail}")
        return True, output_path, qa_result.reason, text_qa_result
    if text_qa_result.severity == "UNCERTAIN":
        # Politica obligatoria (ver SKILL.md "TEXT QA" / "FABRICA RAPIDA"): un hallazgo
        # UNCERTAIN (lectura de OCR dudosa, no un error de render confirmado) NUNCA
        # dispara una regeneracion — se registra como WARNING y se continua con la
        # imagen ya generada.
        print(f"   [WARN] Slide {slide_number} - Text QA UNCERTAIN (lectura de OCR dudosa, "
              f"NO se regenera): {text_qa_result.detail}")
        return True, output_path, qa_result.reason, text_qa_result
    if not text_qa_result.approved:
        return False, output_path, f"TEXT_QA:{text_qa_result.reason} — {text_qa_result.detail}", text_qa_result

    return True, output_path, qa_result.reason, text_qa_result


def process_slides(
    slides_to_process: List[Dict[str, Any]],
    visual_dna: Dict[str, Any],
    carousel_type: str,
    config: GeminiConfig,
    client,
    cache: CacheManager,
    cost_tracker: CostTracker,
    bundle_id: str,
    carousel_dir: Path,
    reference_image_path: Optional[Path],
    product_mockup_path: Optional[Path],
    slide1_anchor_path: Optional[Path],
    force_mode: Optional[str],
    critical_phrases_by_slide: Optional[Dict[int, List[tuple]]] = None,
    text_qa_summary: Optional[Dict[str, Any]] = None,
    authorized_extra_tokens: Optional[List[str]] = None,
) -> Dict[int, str]:
    """
    Procesa una lista de slides (ya excluidos los REUSED): construye sus tareas, genera
    SIEMPRE en DIRECT MODE paralelo (salvo --force-batch explicito, ver SKILL.md
    "FABRICA RAPIDA"), corre QA ESTRUCTURAL + TEXT QA (ver save_image_and_qa) y aplica
    UN UNICO presupuesto de reintentos (config.max_retries, por defecto 1 = maximo 2
    intentos totales por slide) compartido por cualquier causa de fallo — generacion,
    QA estructural o Text QA. Devuelve
    {slide_number: "APPROVED" | "TEXT_QA_APPROVED" | "FAILED_FINAL" | "TEXT_QA_FAILED"}.

    `text_qa_summary`, si se pasa, se actualiza in-place con los contadores agregados
    para el manifest.json (slides_checked/rejected/regenerated/retries/errors_detected/
    errors_fixed) — ver SKILL.md seccion 23.
    """
    final_status: Dict[int, str] = {}
    plans: Dict[int, Dict[str, Any]] = {}
    tasks: List[GenerationTask] = []
    slides_by_number = {s["number"]: s for s in slides_to_process}
    critical_phrases_by_slide = critical_phrases_by_slide or {}
    # Slides que en ALGUNA ronda anterior fueron rechazados especificamente por Text QA
    # (no por QA estructural ni por fallo de generacion) — permite saber, cuando el
    # slide finalmente aprueba, si el error de texto se "arreglo" (para el contador
    # text_errors_fixed del manifest) en vez de asumirlo por la ronda actual.
    slides_with_prior_text_qa_rejection: set = set()

    for slide in slides_to_process:
        slide_number = slide["number"]
        plan = build_reference_prompt_and_hash(
            slide, visual_dna, carousel_type, config,
            slide1_anchor_path, reference_image_path, product_mockup_path,
        )
        if plan is None:
            print(f"   [ERROR] Slide {slide_number} - requiere 'product_mockup' pero no esta disponible en el bundle. "
                  f"Se omite (nunca se inventa una portada generica).")
            final_status[slide_number] = "FAILED_FINAL"
            # billable=False: nunca se llamo a Gemini para este slide (se omitio antes
            # de intentarlo por falta del mockup obligatorio) — ver SKILL.md "COSTO REAL".
            cost_tracker.record(
                bundle_id, slide_number, config.image_model, config.image_size, config.aspect_ratio,
                mode="none", status="FAILED_FINAL", reused=False, retry_count=0, prompt_hash="",
                billable=False,
            )
            continue
        plans[slide_number] = plan
        tasks.append(GenerationTask(
            slide_number=slide_number,
            prompt=plan["prompt"],
            reference_images=plan["reference_images"],
            prompt_hash=plan["prompt_hash"],
            metadata={"bundle_id": bundle_id, "slide_number": str(slide_number)},
        ))

    retry_round = 0
    while tasks:
        # FABRICA RAPIDA (regla obligatoria y permanente, ver SKILL.md): el modo normal
        # de produccion SIEMPRE es DIRECT (paralelo, ver direct_generator.py) sin
        # importar ECONOMY_MODE/GEMINI_BATCH_ENABLED — Batch puede tardar hasta 24h
        # (documentado por Google) y es incompatible con el objetivo de ~5 min por
        # carrusel. BATCH queda reservado para una futura modalidad explicita de
        # produccion masiva, activada UNICAMENTE con --force-batch en esa corrida.
        if force_mode == "batch":
            mode = "batch"
        else:
            mode = "direct"

        label = "reintento" if retry_round > 0 else "generacion inicial"
        print(f"\n   [RUN] {mode.upper()} MODE — {label}: {len(tasks)} slide(s) "
              f"({', '.join(str(t.slide_number) for t in tasks)})")

        generation_started_at = time.time()
        if mode == "direct":
            results = generate_direct(client, tasks)
        else:
            results = generate_batch(client, tasks, carousel_dir, bundle_id)
        _accumulate_phase_seconds(
            cost_tracker, "retry" if retry_round > 0 else "generation", time.time() - generation_started_at,
        )

        next_round_tasks: List[GenerationTask] = []

        # Fase 2a (secuencial, rapida): separar los slides sin imagen real (fallo de
        # generacion, nada que auditar) de los que SI tienen imagen y necesitan QA.
        qa_pending: List[GenerationTask] = []
        for task in tasks:
            slide_number = task.slide_number
            result: GeminiImageResult = results.get(slide_number) or GeminiImageResult(False, error="Sin resultado")

            if not result.success:
                print(f"   [ERROR] Slide {slide_number} - fallo generando: {result.error}")
                should_retry = retry_round < config.max_retries
                # billable=False: la llamada a Gemini NUNCA produjo una imagen (fallo de
                # red/API/respuesta vacia) — no hay nada que facturar (ver SKILL.md
                # "COSTO REAL": "Cada llamada real a Gemini que produzca una imagen debe
                # contar como generación billable" — esta no produjo ninguna).
                cost_tracker.record(
                    bundle_id, slide_number, config.image_model, config.image_size, config.aspect_ratio,
                    mode=mode, status="RETRYING" if should_retry else "FAILED_FINAL",
                    reused=False, retry_count=retry_round, prompt_hash=task.prompt_hash,
                    actual_usage=result.usage_metadata, billable=False,
                )
                if should_retry:
                    next_round_tasks.append(task)
                else:
                    final_status[slide_number] = "FAILED_FINAL"
                    print(f"      -> Agotados los reintentos (MAX_RETRIES={config.max_retries}). "
                          f"Slide {slide_number} queda FAILED_FINAL.")
                    # Actualizar cache para que el manifest registre FAILED_FINAL (no UNKNOWN).
                    # Esta ruta (respuesta vacia/fallo de generacion) no pasa por save_image_and_qa,
                    # asi que el upsert debe hacerse aqui explicitamente.
                    cache.upsert(SlideCacheRecord(
                        slide_number=slide_number,
                        prompt_hash=task.prompt_hash,
                        model=config.image_model,
                        resolution=config.image_size,
                        aspect_ratio=config.aspect_ratio,
                        image_path="",
                        status="FAILED_FINAL",
                        retry_count=retry_round,
                        last_error=result.error,
                    ))
                continue

            qa_pending.append(task)

        # Fase 2b (PARALELA — ver SKILL.md "PARALELIZACION"): QA estructural + Text QA
        # (OCR 100% local) de TODOS los slides con imagen real de esta ronda, a la vez —
        # nunca slide por slide. El OCR es la parte mas lenta de esta fase (llamada a un
        # binario externo), y como cada slide es completamente independiente de los
        # demas, correrlos en paralelo reduce directamente la latencia de esta etapa.
        qa_started_at = time.time()
        qa_results: Dict[int, tuple] = {}

        def _run_qa(qa_task: GenerationTask) -> tuple:
            sn = qa_task.slide_number
            res = results[sn]
            slide_def = slides_by_number[sn]
            expected_text = slide_def.get("exact_text", "")
            critical_phrases = critical_phrases_by_slide.get(sn)
            outcome = save_image_and_qa(
                carousel_dir, sn, res.image_bytes, config,
                expected_text=expected_text, critical_phrases=critical_phrases,
                authorized_extra_tokens=authorized_extra_tokens,
                uses_product_mockup=bool(slide_def.get("uses_product_mockup_directly")),
            )
            return sn, outcome

        if len(qa_pending) == 1:
            sn, outcome = _run_qa(qa_pending[0])
            qa_results[sn] = outcome
        elif qa_pending:
            with ThreadPoolExecutor(max_workers=min(_QA_MAX_WORKERS, len(qa_pending))) as executor:
                futures = [executor.submit(_run_qa, t) for t in qa_pending]
                for future in as_completed(futures):
                    sn, outcome = future.result()
                    qa_results[sn] = outcome
        _accumulate_phase_seconds(
            cost_tracker, "retry" if retry_round > 0 else "qa", time.time() - qa_started_at,
        )

        # Fase 2c (secuencial, rapida): accounting/cache/costo/logs por cada resultado
        # de QA ya calculado — nunca vuelve a tocar disco ni a llamar a Gemini/OCR.
        for task in qa_pending:
            slide_number = task.slide_number
            result = results[slide_number]
            plan = plans[slide_number]
            ok, image_path, reason, text_qa_result = qa_results[slide_number]
            is_text_qa_failure = reason.startswith("TEXT_QA:") if isinstance(reason, str) else False

            if text_qa_summary is not None and text_qa_result is not None and not text_qa_result.skipped:
                text_qa_summary.setdefault("_checked_slides", set()).add(slide_number)
                if not text_qa_result.approved:
                    text_qa_summary["text_errors_detected"] = text_qa_summary.get("text_errors_detected", 0) + 1
                    text_qa_summary.setdefault("_rejected_slides", set()).add(slide_number)

            if not ok:
                # FABRICA RAPIDA: presupuesto UNICO de reintentos (config.max_retries),
                # compartido por fallos de generacion, QA estructural Y Text QA — nunca
                # dos presupuestos apilables (ver SKILL.md). Por defecto 1: 1 intento
                # inicial + 1 regeneracion como maximo, y solo por error CRITICO (Text QA
                # ya reclasifica UNCERTAIN -> approved=True antes de llegar aqui).
                budget = config.max_retries
                cause_label = "TEXT QA" if is_text_qa_failure else "QA estructural"
                print(f"   [ERROR] Slide {slide_number} - rechazado por {cause_label}: {reason}")
                should_retry = retry_round < budget
                retrying_status = "TEXT_QA_REGENERATING" if is_text_qa_failure else "RETRYING"
                failed_status = "TEXT_QA_FAILED" if is_text_qa_failure else "FAILED_FINAL"
                # billable=True (default): Gemini SI devolvio una imagen aqui (result.success
                # ya fue True para llegar a este punto) — el QA la rechazo despues, pero la
                # llamada ya se factura igual (ver SKILL.md "COSTO REAL").
                cost_tracker.record(
                    bundle_id, slide_number, config.image_model, config.image_size, config.aspect_ratio,
                    mode=mode, status=retrying_status if should_retry else failed_status,
                    reused=False, retry_count=retry_round, prompt_hash=task.prompt_hash,
                    actual_usage=result.usage_metadata, billable=True,
                )
                if should_retry:
                    if is_text_qa_failure:
                        slides_with_prior_text_qa_rejection.add(slide_number)
                        if text_qa_summary is not None:
                            text_qa_summary.setdefault("_regenerated_slides", set()).add(slide_number)
                            text_qa_summary["retries"] = text_qa_summary.get("retries", 0) + 1
                    next_round_tasks.append(task)
                else:
                    final_status[slide_number] = failed_status
                    cache.upsert(SlideCacheRecord(
                        slide_number=slide_number, prompt_hash=task.prompt_hash, model=config.image_model,
                        resolution=config.image_size, aspect_ratio=config.aspect_ratio,
                        image_path=image_path.name if image_path else "", status=failed_status,
                        retry_count=retry_round, last_error=reason,
                        text_qa_status=failed_status if is_text_qa_failure else None,
                        text_qa_rejection_reason=(text_qa_result.reason if text_qa_result else None),
                    ))
                    print(f"      -> Agotados los reintentos (MAX_RETRIES={budget}). "
                          f"Slide {slide_number} queda {failed_status} — se acepta que no "
                          f"paso QA y se continua (nunca ciclos de correccion sin limite).")
                continue

            final_cache_status = "TEXT_QA_APPROVED" if (text_qa_result is not None and not text_qa_result.skipped) else "APPROVED"
            final_status[slide_number] = final_cache_status
            if slide_number in slides_with_prior_text_qa_rejection and text_qa_summary is not None:
                # Este slide fue rechazado por Text QA en una ronda anterior y ahora aprobo:
                # la regeneracion selectiva efectivamente corrigio el error de texto.
                text_qa_summary.setdefault("_fixed_slides", set()).add(slide_number)
            print(f"   [OK] Slide {slide_number} - generado y aprobado por QA{' + Text QA' if final_cache_status == 'TEXT_QA_APPROVED' else ''}: {image_path.name}")
            cache.upsert(SlideCacheRecord(
                slide_number=slide_number,
                prompt_hash=task.prompt_hash,
                model=config.image_model,
                resolution=config.image_size,
                aspect_ratio=config.aspect_ratio,
                image_path=image_path.name,
                status=final_cache_status,
                retry_count=retry_round,
                expected_text_hash=(text_qa_result.expected_text_hash if text_qa_result else None),
                rendered_text_hash=(text_qa_result.rendered_text_hash if text_qa_result else None),
                text_qa_status=final_cache_status,
            ))
            cost_tracker.record(
                bundle_id, slide_number, config.image_model, config.image_size, config.aspect_ratio,
                mode=mode, status=final_cache_status, reused=False, retry_count=retry_round,
                prompt_hash=task.prompt_hash, actual_usage=result.usage_metadata,
            )

        tasks = next_round_tasks
        retry_round += 1

    return final_status


def _apply_copy_json(bundle_path: Path, copy_json_path: Path) -> Optional[str]:
    """Valida y guarda el copy final (descripcion/CTA/hashtags/producto) leido de
    `copy_json_path` — la MISMA logica que antes vivia solo en `run_add_copy`, ahora
    compartida para poder invocarse dentro de la corrida principal via --copy-json (ver
    SKILL.md "FABRICA RAPIDA" / "UNA SOLA EJECUCION"). Devuelve un mensaje de error (str)
    si algo es invalido, o None si se guardo correctamente."""
    if not copy_json_path.exists():
        return f"no se encontró el archivo de copy en {copy_json_path}"
    with open(copy_json_path, "r", encoding="utf-8") as f:
        copy_data = json.load(f)

    missing = [k for k in ("description", "cta", "hashtags") if k not in copy_data]
    if missing:
        return f"faltan campos obligatorios en el JSON de copy: {missing}"

    if copy_data.get("product") and not copy_data.get("purchase_url"):
        return (f"el producto '{copy_data['product']}' no tiene 'purchase_url'. "
                f"El paquete no se guarda sin el enlace de compra.")

    n_hashtags = len(copy_data.get("hashtags") or [])
    if not (8 <= n_hashtags <= 10):
        print(f"[WARN] Advertencia: se esperaban entre 8 y 10 hashtags, hay {n_hashtags}. Continua igualmente.")

    save_copy_deliverables(
        bundle_path,
        description=copy_data["description"],
        cta=copy_data["cta"],
        hashtags=copy_data["hashtags"],
        product=copy_data.get("product"),
        purchase_url=copy_data.get("purchase_url"),
    )
    return None


def run_generation(args) -> int:
    bundle_id = args.bundle_id
    bundle_path = OUTPUTS_DIR / bundle_id

    print(f"\n{'='*60}")
    print(f"CAROUSEL GENERATOR - Gemini (Nano Banana 2 Lite) — modo economico")
    print(f"{'='*60}")
    print(f"\n[BUNDLE] Bundle: {bundle_id}")

    if not bundle_path.exists():
        print(f"[ERROR] Error: el bundle no existe: {bundle_path}")
        return 1
    print(f"[DIR] Path: {bundle_path}\n")

    print("[LOAD] Cargando brief.json...")
    brief = load_brief(bundle_path)  # <- COMPUERTA MAX_SLIDES, antes de tocar Gemini
    if not brief:
        return 1

    slides = brief["slides"]
    visual_dna = brief["visual_dna"]
    carousel_type = brief["carousel_type"]
    slide_count = brief["slide_count"]
    reference_image_info = brief["reference_image"]
    product_mockup_info = brief.get("product_mockup")

    carousel_dir = bundle_path / "carousel"
    carousel_dir.mkdir(exist_ok=True)
    assets_dir = carousel_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    print("\n" + "=" * 60)
    print("BRIEF DEL CARRUSEL")
    print("=" * 60)
    print(f"\nFormato: {carousel_type}")
    print(f"Total slides: {len(slides)} (recomendado: {slide_count.get('recommended')}, "
          f"confirmado: {slide_count.get('confirmed')})")
    print(f"Formato de imagen: {load_config().aspect_ratio} @ {load_config().image_size}")
    for slide in slides:
        print(f"  Slide {slide['number']} [{slide.get('role', '')}]: {slide.get('narrative_objective', '')}")
    print(f"\n{'='*60}")

    if args.dry_run:
        print(f"\n(dry-run) Brief mostrado. No se generaron imagenes. No se llamo a Gemini.")
        return 0

    config = load_config()

    if args.fake_provider:
        fail_slides = set()
        fail_until_attempt: Dict[int, int] = {}
        if args.fake_fail_slides:
            for spec in args.fake_fail_slides.split(","):
                spec = spec.strip()
                if ":" in spec:
                    num_str, succeed_at_str = spec.split(":")
                    num = int(num_str)
                    fail_slides.add(num)
                    fail_until_attempt[num] = int(succeed_at_str)
                elif spec:
                    fail_slides.add(int(spec))
        print(f"\n[WARN] --fake-provider activo: NO se llama a Gemini real, NO se gasta credito. "
              f"Slides con fallo simulado: {sorted(fail_slides) or 'ninguno'}")
        client = FakeGeminiClient(config, fail_slides=fail_slides, fail_until_attempt=fail_until_attempt)
        # Text QA hace OCR sobre la imagen real generada — las imagenes sinteticas de
        # FakeGeminiClient (PNGs de 1x1 pixel) nunca contienen texto legible, asi que
        # Text QA se desactiva automaticamente en --fake-provider (evita rechazos
        # falsos en pruebas de orquestacion que no son sobre fidelidad de texto). La
        # suite dedicada de Text QA (test_text_qa.py) prueba esa capa por separado,
        # con imagenes locales generadas via PIL que si contienen texto real.
        if config.text_qa_enabled:
            config = dataclasses.replace(config, text_qa_enabled=False)
            print("   (Text QA desactivado automaticamente en modo --fake-provider)")
    else:
        if not config.has_api_key():
            print("\n[ERROR] Error: GEMINI_API_KEY no configurada en .env. "
                  "Crea/actualiza $HOME/.claude/skills/carousel-gen/.env con GEMINI_API_KEY=tu-api-key.")
            return 1
        client = GeminiClient(config)

    reference_local_path = bundle_path / reference_image_info["local_path"]
    if not reference_local_path.exists():
        print(f"\n[ERROR] Error: no se encontró la imagen de referencia en {reference_local_path}")
        return 1

    product_mockup_local_path = None
    if product_mockup_info:
        candidate = bundle_path / product_mockup_info["local_path"]
        if candidate.exists():
            product_mockup_local_path = candidate
        else:
            print(f"\n[WARN] Advertencia: brief.json referencia 'product_mockup' pero no se encontró "
                  f"el archivo en {candidate}")

    only_slides: Optional[Set[int]] = None
    if args.regenerate_slides:
        only_slides = set(int(s.strip()) for s in args.regenerate_slides.split(","))
        print(f"\n[REGEN] Regenerando solo slides: {sorted(only_slides)}\n")

    cache = CacheManager(carousel_dir)

    # CRONOMETRO GLOBAL REAL (ver SKILL.md): `brief.json` puede llevar un bloque opcional
    # "timing" con marcas de tiempo ISO 8601 que Claude registra durante el workflow
    # ANTES de que exista este script (PASO 0/1: recepcion de la imagen adjunta; PASO 3:
    # texto confirmado; PASO 8: brief aprobado) — asi el cronometro total cubre el
    # pipeline completo, no solo el tiempo dentro de Python. Si el bloque no existe (ej.
    # bundles historicos, o Claude no lo registro), cada fase queda N/D — nunca se
    # inventa un 0.
    timing_markers = brief.get("timing") or {}
    pipeline_started_at = timing_markers.get("skill_started_at")
    cost_tracker = CostTracker(
        bundle_path, bundle_id, len(slides), config.price_per_image_usd,
        pipeline_started_at=pipeline_started_at,
    )
    _record_pre_generation_phase_seconds(cost_tracker, timing_markers)

    force_mode = "direct" if args.force_direct else ("batch" if args.force_batch else None)

    if not config.text_qa_enabled:
        print("\n[WARN] TEXT_QA_ENABLED=false — se omite la verificacion local de texto renderizado.")

    critical_phrases_by_slide = {s["number"]: build_critical_phrases(brief, s) for s in slides}
    authorized_extra_tokens = _build_authorized_extra_tokens(brief)
    text_qa_summary: Dict[str, Any] = {}

    generation_qa_started_at = time.time()  # ver COSTO_CARRUSEL.txt ("Tiempo generación + QA")

    # --- FASE A: Slide 1 (ancla visual maestra) — SIEMPRE se resuelve primero, igual
    # que en el generador legacy, porque los slides 2+ lo necesitan como referencia. ---
    slide1 = next((s for s in slides if s.get("uses_reference_image_directly")), None)
    slide1_num = slide1["number"] if slide1 else None
    slide1_in_scope = slide1 is not None and (only_slides is None or slide1_num in only_slides)
    slide1_path = carousel_dir / f"carousel-{slide1_num:02d}.png" if slide1_num else None

    if slide1 is not None and slide1_in_scope:
        plan = build_reference_prompt_and_hash(
            slide1, visual_dna, carousel_type, config, None, reference_local_path, product_mockup_local_path,
        )
        force_regen_s1 = only_slides is not None and slide1_num in only_slides
        if cache.should_reuse(slide1_num, plan["prompt_hash"], config.image_model, config.image_size, config.aspect_ratio, force_regenerate=force_regen_s1):
            print(f"\n   [REUSED] Slide {slide1_num} (ancla) - REUSED: ya existe con el mismo prompt_hash, no se regenera.")
            cache.mark_reused(slide1_num)
            cost_tracker.record(
                bundle_id, slide1_num, config.image_model, config.image_size, config.aspect_ratio,
                mode="none", status="REUSED", reused=True, retry_count=0, prompt_hash=plan["prompt_hash"],
            )
        else:
            print(f"\n{'='*60}\nFASE A: GENERANDO SLIDE 1 (ANCLA VISUAL MAESTRA)\n{'='*60}")
            status_map = process_slides(
                [slide1], visual_dna, carousel_type, config, client, cache, cost_tracker,
                bundle_id, carousel_dir, reference_local_path, product_mockup_local_path,
                slide1_anchor_path=None, force_mode="direct",
                critical_phrases_by_slide=critical_phrases_by_slide, text_qa_summary=text_qa_summary,
                authorized_extra_tokens=authorized_extra_tokens,
            )
            if status_map.get(slide1_num) not in ("APPROVED", "TEXT_QA_APPROVED"):
                print(f"\n[ERROR] El Slide 1 (ancla) no pudo generarse — los slides 2+ perderian su ancla visual real.")
                if not slide1_path.exists():
                    print("   No se puede continuar con los demas slides sin, al menos, el ADN visual en texto.")
    elif slide1 is not None and not slide1_path.exists():
        print(f"\n[WARN] Slide 1 no esta en esta regeneracion y no existe {slide1_path.name} en disco — "
              f"los slides 2+ se generaran solo con el ADN visual en texto, sin ancla real.")

    slide1_anchor_for_others = slide1_path if (slide1_path and slide1_path.exists()) else None

    # --- FASE B: resto de slides — reuse-check + generacion (direct o batch) ---
    remaining_slides = [s for s in slides if s["number"] != slide1_num]
    if only_slides is not None:
        remaining_slides = [s for s in remaining_slides if s["number"] in only_slides]

    to_generate: List[Dict[str, Any]] = []
    for slide in remaining_slides:
        slide_number = slide["number"]
        plan = build_reference_prompt_and_hash(
            slide, visual_dna, carousel_type, config,
            slide1_anchor_for_others, reference_local_path, product_mockup_local_path,
        )
        if plan is None:
            print(f"   [ERROR] Slide {slide_number} - requiere 'product_mockup' pero no esta disponible. Se omite.")
            continue
        force_regen = only_slides is not None and slide_number in only_slides
        if force_regen:
            print(f"   [FORCE_REGEN] Slide {slide_number} - regeneracion forzada por --regenerate-slides (cache ignorado).")
        if cache.should_reuse(slide_number, plan["prompt_hash"], config.image_model, config.image_size, config.aspect_ratio, force_regenerate=force_regen):
            print(f"   [REUSED] Slide {slide_number} - REUSED: ya existe con el mismo prompt_hash, no se regenera.")
            cache.mark_reused(slide_number)
            cost_tracker.record(
                bundle_id, slide_number, config.image_model, config.image_size, config.aspect_ratio,
                mode="none", status="REUSED", reused=True, retry_count=0, prompt_hash=plan["prompt_hash"],
            )
        else:
            to_generate.append(slide)

    if to_generate:
        print(f"\n{'='*60}\nFASE B: GENERANDO {len(to_generate)} SLIDE(S) PENDIENTE(S)\n{'='*60}")
        process_slides(
            to_generate, visual_dna, carousel_type, config, client, cache, cost_tracker,
            bundle_id, carousel_dir, reference_local_path, product_mockup_local_path,
            slide1_anchor_for_others, force_mode,
            critical_phrases_by_slide=critical_phrases_by_slide, text_qa_summary=text_qa_summary,
            authorized_extra_tokens=authorized_extra_tokens,
        )
    else:
        print(f"\n   Todos los slides restantes ya estaban REUSED — nada nuevo que generar en Fase B.")

    cost_tracker.record_phase_seconds("generation_qa", time.time() - generation_qa_started_at)
    finalization_started_at = time.time()

    # --- Post-proceso (identico al generador legacy, via carousel_common) ---
    slides_for_detection = [
        {"number": s["number"], "title": s.get("role", ""),
         "content": " ".join(filter(None, [s.get("message", ""), s.get("exact_text", ""), s.get("scene_description", "")]))}
        for s in slides
    ]
    entities_by_slide = detect_entities_in_slides(slides_for_detection)
    print("\nGenerando guia de logos opcionales...")
    generate_assets_needed_md(bundle_id, bundle_path, slides_for_detection, entities_by_slide)

    slide_files = sorted(carousel_dir.glob("carousel-*.png"))
    slides_generated_manifest = []
    for f in slide_files:
        num = int(f.stem.split("-")[1])
        slide_def = next((s for s in slides if s["number"] == num), {})
        record = cache.get(num)
        slides_generated_manifest.append({
            "id": num,
            "role": slide_def.get("role", ""),
            "narrative_objective": slide_def.get("narrative_objective", ""),
            "filename": f.name,
            "success": True,
            "used_reference_directly": bool(slide_def.get("uses_reference_image_directly")),
            "used_product_mockup_directly": bool(slide_def.get("uses_product_mockup_directly")),
            "status": record.status if record else "UNKNOWN",
            "expected_text_hash": record.expected_text_hash if record else None,
            "rendered_text_hash": record.rendered_text_hash if record else None,
            "text_qa_status": record.text_qa_status if record else None,
            "text_qa_retry_count": record.retry_count if record else 0,
            "text_qa_rejection_reason": record.text_qa_rejection_reason if record else None,
        })

    # Consolidar el resumen de Text QA para el manifest (ver SKILL.md seccion 23) —
    # convierte los sets internos de seguimiento en los contadores finales.
    any_text_qa_failed = any(
        (cache.get(s["number"]) and cache.get(s["number"]).status == "TEXT_QA_FAILED") for s in slides
    )
    text_qa_manifest_block = {
        "status": "FAILED" if any_text_qa_failed else ("APPROVED" if text_qa_summary.get("_checked_slides") else "SKIPPED"),
        "slides_checked": len(text_qa_summary.get("_checked_slides", set())),
        "slides_rejected": len(text_qa_summary.get("_rejected_slides", set())),
        "slides_regenerated": len(text_qa_summary.get("_regenerated_slides", set())),
        "retries": text_qa_summary.get("retries", 0),
        "text_errors_detected": text_qa_summary.get("text_errors_detected", 0),
        "text_errors_fixed": len(text_qa_summary.get("_fixed_slides", set())),
    }

    print("Generando manifest...")
    generate_manifest(
        bundle_id, carousel_dir, slides_generated_manifest, carousel_type,
        slide_count.get("confirmed"), reference_local_path.name,
        extra_fields={
            "provider": "gemini",
            "model": config.image_model,
            "aspect_ratio": config.aspect_ratio,
            "image_size": config.image_size,
            "economy_mode": config.economy_mode,
            "batch_enabled": config.batch_enabled,
            "text_qa": text_qa_manifest_block,
        },
    )

    _accumulate_phase_seconds(cost_tracker, "finalization", time.time() - finalization_started_at)

    export_started_at = time.time()
    print("\nCopiando slides finales a Descargas...")
    downloads_dest = export_final_slides_to_downloads(
        bundle_id, bundle_path, carousel_dir,
    )
    cost_tracker.record_phase_seconds("export", time.time() - export_started_at)

    finalization_started_at = time.time()

    # PASO 4 (FABRICA RAPIDA — "UNA SOLA EJECUCION", ver SKILL.md): si el copy final
    # (descripcion/CTA/hashtags) ya esta disponible en esta misma invocacion (via
    # --copy-json), se guarda AHORA — nunca hace falta una segunda invocacion completa
    # del script solo para escribir COPY_FINAL.txt. --add-copy sigue existiendo aparte
    # para completar/corregir el copy de un bundle ya generado sin tocar imagenes.
    copy_error = None
    if args.copy_json:
        copy_error = _apply_copy_json(bundle_path, Path(args.copy_json))
        if copy_error:
            print(f"[ERROR] {copy_error}")

    if args.copy_json and not copy_error:
        print("\nActualizando copia en Descargas con el paquete completo (copy incluido)...")
        downloads_dest = export_final_slides_to_downloads(
            bundle_id, bundle_path, carousel_dir,
        ) or downloads_dest

    _accumulate_phase_seconds(cost_tracker, "finalization", time.time() - finalization_started_at)
    cost_tracker.mark_finished()

    # COSTO_CARRUSEL.txt (regla obligatoria y permanente, ver SKILL.md "FABRICA
    # RAPIDA"): se escribe SIEMPRE, sin pedir permiso, con los datos reales disponibles
    # hasta este punto. Si --copy-json no se paso en esta misma corrida (o --add-copy
    # todavia no corrio sobre este bundle), "Contenido inventado"/el copy final del
    # paquete se completan despues — run_add_copy vuelve a llamar a esta misma funcion
    # con datos mas completos (igual que ya hace COPY_FINAL.txt).
    save_costo_carrusel(
        bundle_path, bundle_id, cost_tracker.summary.to_dict(),
        config.image_model, config.image_size, config.aspect_ratio, len(slides),
        text_qa_manifest_block, str(downloads_dest or bundle_path),
    )

    cost_tracker.print_summary()

    print(f"\n{'='*60}")
    print(f"CARRUSEL PROCESADO (Gemini economico)")
    print(f"{'='*60}")
    print(f"Ubicacion: {carousel_dir}")
    print(f"Modelo: {config.image_model} @ {config.image_size} ({config.aspect_ratio})")
    if downloads_dest:
        print(f"Carrusel guardado en: {downloads_dest}")
    print(f"{'='*60}\n")

    total_slides_expected = len(only_slides) if only_slides else len(slides)
    total_ok = len([f for f in carousel_dir.glob("carousel-*.png")])
    return 0 if total_ok >= total_slides_expected else 1


def run_add_copy(args) -> int:
    """Modo COMPATIBILIDAD/CORRECCION PUNTUAL (ver SKILL.md "UNA SOLA EJECUCION"): guarda
    o corrige el copy final de un bundle YA generado, sin tocar ninguna imagen. El flujo
    normal de una generacion nueva ya no necesita esto — pasa --copy-json a la corrida
    principal (run_generation) para que todo el paquete (imagenes + copy + manifest +
    costo + export) salga de UNA sola invocacion del script."""
    bundle_id = args.bundle_id
    bundle_path = OUTPUTS_DIR / bundle_id
    print(f"\n{'='*60}\nCAROUSEL GENERATOR - Gemini (modo copy)\n{'='*60}\n\n[BUNDLE] Bundle: {bundle_id}")

    copy_error = _apply_copy_json(bundle_path, Path(args.add_copy))
    if copy_error:
        print(f"[ERROR] {copy_error}")
        return 1

    # COSTO_CARRUSEL.txt final (regla obligatoria, ver SKILL.md "FABRICA RAPIDA"): en
    # este punto el paquete ya esta completo (slides + COPY_FINAL.txt), asi que se marca
    # el fin real del pipeline y se reescribe el resumen con los datos definitivos —
    # incluye el bloque "text_qa" ya consolidado en manifest.json por run_generation.
    config = load_config()
    manifest_file = bundle_path / "carousel" / "manifest.json"
    text_qa_block = None
    slides_total = 0
    if manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            text_qa_block = manifest.get("text_qa")
            slides_total = len(manifest.get("slides", []) or [])
        except (json.JSONDecodeError, OSError):
            pass
    cost_tracker = CostTracker(bundle_path, bundle_id, slides_total, config.price_per_image_usd)
    cost_tracker.mark_finished()
    save_costo_carrusel(
        bundle_path, bundle_id, cost_tracker.summary.to_dict(),
        config.image_model, config.image_size, config.aspect_ratio,
        slides_total or cost_tracker.summary.slides_total,
        text_qa_block, str(bundle_path),
    )

    print("\nActualizando copia en Descargas con el paquete completo...")
    export_final_slides_to_downloads(
        bundle_id, bundle_path, bundle_path / "carousel",
    )

    print(f"\n{'='*60}\nENTREGABLES DE COPY GUARDADOS (sin generar ni tocar ninguna imagen)\n{'='*60}\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera carruseles Instagram con Gemini (Nano Banana 2 Lite) a partir de brief.json")
    parser.add_argument("bundle_id")
    parser.add_argument("--skip-interactive", action="store_true", help="Aceptado por compatibilidad; este script nunca pregunta interactivamente")
    parser.add_argument("--regenerate-slides", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--add-copy", type=str, default=None, metavar="COPY_JSON_PATH",
                         help="Modo COMPATIBILIDAD/CORRECCION PUNTUAL: guarda/corrige el copy de un bundle YA "
                              "generado, sin generar nada. Para una generacion nueva usar --copy-json en la "
                              "corrida principal (ver 'UNA SOLA EJECUCION' en SKILL.md).")
    parser.add_argument("--copy-json", type=str, default=None, metavar="COPY_JSON_PATH",
                         help="UNA SOLA EJECUCION (ver SKILL.md): ruta a un JSON con description/cta/hashtags/"
                              "product/purchase_url YA listo (ver PASO 7/10) — se guarda como parte de ESTA "
                              "misma corrida de generacion, sin necesitar una segunda invocacion (--add-copy).")
    parser.add_argument("--force-direct", action="store_true", help="Fuerza DIRECT MODE para esta corrida")
    parser.add_argument("--force-batch", action="store_true", help="Fuerza BATCH MODE para esta corrida")
    parser.add_argument("--fake-provider", action="store_true",
                         help="SOLO PRUEBAS: usa un proveedor Gemini falso, sin red y sin costo")
    parser.add_argument("--fake-fail-slides", type=str, default=None,
                         help="SOLO PRUEBAS con --fake-provider: 'N,M' fallan siempre; 'N:2' falla hasta el intento 2")

    args = parser.parse_args()

    if args.add_copy:
        sys.exit(run_add_copy(args))
    else:
        sys.exit(run_generation(args))


if __name__ == "__main__":
    main()
