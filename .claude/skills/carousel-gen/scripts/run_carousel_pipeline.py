#!/usr/bin/env python3
"""
run_carousel_pipeline.py - Controlador autonomo del pipeline de carousel-gen.

Claude lo llama UNA VEZ tras tener brief.json + copy.json listos.
Delega toda la generacion a generate-carousel-gemini.py y emite un resultado
estructurado en pipeline_result.json (+ RESULT_JSON:<json> al final de stdout)
para que Claude lo lea con una sola operacion de Read.

Uso:
    python3 scripts/run_carousel_pipeline.py <bundle_id> [--copy-json COPY_JSON_PATH]
    python3 scripts/run_carousel_pipeline.py <bundle_id> --copy-json copy.json --fake-provider
    python3 scripts/run_carousel_pipeline.py <bundle_id> --dry-run

Salida:
    Stdout normal durante la ejecucion.
    Al final: RESULT_JSON:<json>   (Claude captura solo esa linea)
    pipeline_result.json escrito en la raiz del bundle.

Checkpoints de tiempo T0-T5:
    T0: inicio del pipeline (antes de cualquier I/O)
    T1: modulo cargado, brief pendiente de carga
    T2: generacion arrancando (inicio de Fase A + Fase B + retries)
    T3: generacion + QA + retries completados
    T4: igual que T3 (retries incluidos en run_generation, no hay fase separada)
    T5: finalizacion completa (pipeline_result.json escrito)
"""

import sys
import json
import argparse
import importlib.util
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from carousel_common import OUTPUTS_DIR  # noqa: E402


def _now_iso() -> str:
    return datetime.now().isoformat()


def _load_gemini_main():
    """Carga generate-carousel-gemini.py como modulo para delegar la generacion."""
    path = Path(__file__).parent / "generate-carousel-gemini.py"
    spec = importlib.util.spec_from_file_location("gemini_main_pipeline_ctrl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_result(
    bundle_path: Path,
    bundle_id: str,
    rc: int,
    timing: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    """
    Lee cost_log.json + manifest.json del bundle y construye el resultado estructurado.
    Nunca inventa datos: cualquier campo sin informacion real queda ausente del dict.
    """
    result: Dict[str, Any] = {
        "bundle_id": bundle_id,
        "status": "UNKNOWN",
        "timing": timing,
    }

    # cost_log.json -> contadores de generacion y costo
    cost_log_path = bundle_path / "cost_log.json"
    if cost_log_path.exists():
        try:
            cost_log = json.loads(cost_log_path.read_text(encoding="utf-8"))
            result["gemini_calls"] = cost_log.get("generated", 0)
            retries = cost_log.get("retries", 0)
            result["retries"] = retries
            result["initial_generations"] = max(0, result["gemini_calls"] - retries)
            result["total_generations"] = result["gemini_calls"]
            result["cost_usd"] = round(float(cost_log.get("estimated_cost_usd") or 0.0), 4)
            phase_seconds = cost_log.get("phase_seconds") or {}
            result["wall_clock_python_seconds"] = round(
                (phase_seconds.get("generation_qa") or 0.0)
                + (phase_seconds.get("finalization") or 0.0)
                + (phase_seconds.get("export") or 0.0),
                1,
            )
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    # carousel/manifest.json -> estado de slides y Text QA
    # NOTA: el manifest usa la clave "carousel" (no "slides") para la lista de slides.
    manifest_path = bundle_path / "carousel" / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            slides = manifest.get("carousel") or []
            result["slides_total"] = len(slides)
            result["slides_pass"] = sum(
                1 for s in slides
                if s.get("status") in ("APPROVED", "TEXT_QA_APPROVED", "REUSED")
                and not (
                    s.get("expected_text_hash") is not None
                    and s.get("expected_text_hash") != s.get("rendered_text_hash")
                )
            )
            # UNCERTAIN: aprobado por QA pero con baja confianza OCR (hashes distintos)
            result["slides_uncertain"] = sum(
                1 for s in slides
                if s.get("status") in ("APPROVED", "TEXT_QA_APPROVED", "REUSED")
                and s.get("expected_text_hash") is not None
                and s.get("expected_text_hash") != s.get("rendered_text_hash")
            )
            result["slides_failed"] = sum(
                1 for s in slides
                if "FAILED" in s.get("status", "") and "REGENERATING" not in s.get("status", "")
            )
            errors = [
                {
                    "slide": s.get("id"),
                    "status": s.get("status", "UNKNOWN"),
                    "reason": s.get("text_qa_rejection_reason"),
                }
                for s in slides
                if "FAILED" in s.get("status", "") and "REGENERATING" not in s.get("status", "")
            ]
            if errors:
                result["errors"] = errors
            text_qa = manifest.get("text_qa") or {}
            result["text_qa_status"] = text_qa.get("status", "UNKNOWN")
        except (json.JSONDecodeError, OSError):
            pass

    # duration_seconds: total wall-clock T0 → T5
    try:
        t0_str = timing.get("T0_pipeline_start")
        t5_str = timing.get("T5_finalization_done")
        if t0_str and t5_str:
            dt0 = datetime.fromisoformat(t0_str)
            dt5 = datetime.fromisoformat(t5_str)
            # strip tz info si difieren (aware vs naive) para evitar TypeError
            if (dt0.tzinfo is None) != (dt5.tzinfo is None):
                dt0 = dt0.replace(tzinfo=None)
                dt5 = dt5.replace(tzinfo=None)
            result["duration_seconds"] = round(max(0.0, (dt5 - dt0).total_seconds()), 1)
    except (ValueError, TypeError, AttributeError):
        pass

    # Status global
    slides_total = result.get("slides_total", 0)
    slides_pass = result.get("slides_pass", 0)
    slides_uncertain = result.get("slides_uncertain", 0)
    if (slides_pass + slides_uncertain) == slides_total and slides_total > 0:
        result["status"] = "COMPLETED"
    elif slides_pass + slides_uncertain > 0:
        result["status"] = "PARTIAL"
    else:
        result["status"] = "FAILED" if rc != 0 else "COMPLETED"

    # Output path: preferir Downloads si existe
    downloads_dir = Path.home() / "Downloads" / "Carruseles Carousel-Gen" / bundle_id
    carousel_dir = bundle_path / "carousel"
    if downloads_dir.exists():
        result["output_path"] = str(downloads_dir)
        result["files"] = sorted(f.name for f in downloads_dir.glob("carousel-*.png"))
    elif carousel_dir.exists():
        result["output_path"] = str(carousel_dir)
        result["files"] = sorted(f.name for f in carousel_dir.glob("carousel-*.png"))
    else:
        result["output_path"] = str(bundle_path)
        result["files"] = []

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Pipeline autonomo de carousel-gen. Delega a generate-carousel-gemini.py "
            "y emite RESULT_JSON + pipeline_result.json para Claude."
        )
    )
    parser.add_argument("bundle_id")
    parser.add_argument(
        "--copy-json", type=str, default=None, metavar="COPY_JSON_PATH",
        help="Ruta al copy.json con description/cta/hashtags/product/purchase_url",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--fake-provider", action="store_true",
        help="SOLO PRUEBAS: sin llamadas reales a Gemini (ver generate-carousel-gemini.py)",
    )
    parser.add_argument(
        "--fake-fail-slides", type=str, default=None,
        help="SOLO PRUEBAS con --fake-provider: slides que deben fallar",
    )
    parser.add_argument("--force-direct", action="store_true")
    parser.add_argument("--regenerate-slides", type=str, default=None)
    args = parser.parse_args()

    bundle_path = OUTPUTS_DIR / args.bundle_id

    # T0: inicio real del pipeline, antes de cualquier I/O
    t0 = _now_iso()
    print(f"\n[PIPELINE] run_carousel_pipeline.py — bundle: {args.bundle_id}")
    print(f"[T0] Inicio pipeline: {t0}")

    # Cargar modulo de generacion (sin ejecutar todavia)
    mod = _load_gemini_main()
    t1 = _now_iso()
    print(f"[T1] Modulo cargado: {t1}")

    # Preparar Namespace identico al que esperaria main() del script de generacion
    gen_args = Namespace(
        bundle_id=args.bundle_id,
        dry_run=args.dry_run,
        fake_provider=args.fake_provider,
        fake_fail_slides=args.fake_fail_slides,
        regenerate_slides=args.regenerate_slides,
        force_direct=args.force_direct,
        force_batch=False,      # Batch desactivado por defecto (ver SKILL.md FABRICA RAPIDA)
        copy_json=args.copy_json,
        add_copy=None,          # Solo para --add-copy sobre bundles ya generados
        skip_interactive=True,
    )

    t2 = _now_iso()
    print(f"[T2] Generacion iniciando (Fase A ancla + Fase B paralela + retries): {t2}")

    # Ejecutar pipeline completo: generacion + QA + retries + export + copy + costo
    rc = mod.run_generation(gen_args)

    t3 = _now_iso()
    print(f"[T3] Generacion + QA + retries completados: {t3}")
    t4 = t3           # Retries incluidos en run_generation — no hay fase separada posterior
    t5 = _now_iso()
    print(f"[T5] Finalizacion completa: {t5}")

    timing: Dict[str, Optional[str]] = {
        "T0_pipeline_start": t0,
        "T1_module_loaded": t1,
        "T2_generation_start": t2,
        "T3_generation_done": t3,
        "T4_retries_done": t4,
        "T5_finalization_done": t5,
    }

    # Construir resultado estructurado leyendo los archivos ya escritos por run_generation
    result = _build_result(bundle_path, args.bundle_id, rc, timing)

    # Escribir pipeline_result.json en la raiz del bundle
    if bundle_path.exists():
        result_path = bundle_path / "pipeline_result.json"
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[PIPELINE] Resultado estructurado: {result_path}")

    # Emitir RESULT_JSON para que Claude lo capture leyendo la ultima linea de stdout
    print(f"\nRESULT_JSON:{json.dumps(result, ensure_ascii=False)}")

    sys.exit(rc)


if __name__ == "__main__":
    main()
