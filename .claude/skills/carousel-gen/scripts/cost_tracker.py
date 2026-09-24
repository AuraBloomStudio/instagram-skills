"""
cost_tracker.py - Registro de costos por generacion (ver SKILL.md, seccion "CONTROL DE
COSTOS"). Escribe `cost_log.json` en la raiz del bundle (NUNCA se copia a Descargas).

Distingue explicitamente:
  - estimated_cost_usd: generated_count * GEMINI_IMAGE_PRICE_PER_IMAGE (configurable,
    puede ser 0.0 si el usuario no lo ha configurado todavia — nunca se inventa un precio).
  - actual_usage: lo que la API de Gemini reporto realmente (usage_metadata: tokens de
    prompt/salida) para cada llamada que sí se ejecuto. Si Google llega a facturar por
    tokens en vez de precio fijo por imagen para este modelo, la conversion a USD debe
    hacerse aqui explicitamente (hoy no se inventa una tasa) — mientras tanto se reporta
    el uso crudo en tokens, nunca disfrazado de "costo real en USD".

Nunca se presenta un costo estimado como si fuera un costo real facturado.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GenerationLogEntry:
    timestamp: str
    bundle_id: str
    slide_number: int
    model: str
    resolution: str
    aspect_ratio: str
    mode: str  # "batch" | "direct"
    status: str
    reused: bool
    retry_count: int
    prompt_hash: str
    estimated_cost_usd: float
    actual_usage: Optional[Dict[str, Any]] = None
    # True si esta llamada SI produjo una imagen real (billable), False si nunca llego a
    # producir una imagen (fallo de red/API, o el slide se omitio sin llamar a Gemini) —
    # ver SKILL.md "COSTO REAL". Entradas `reused=True` siempre quedan en False aqui
    # (ya son gratis por definicion, no necesitan esta distincion).
    billable: bool = False


@dataclass
class CostSummary:
    bundle_id: str
    slides_total: int
    generated: int = 0
    reused: int = 0
    retries: int = 0
    failed: int = 0
    estimated_cost_usd: float = 0.0
    price_per_image_usd: float = 0.0
    entries: List[Dict[str, Any]] = field(default_factory=list)
    # Marca de tiempo real del pipeline completo de ESTE bundle (ver COSTO_CARRUSEL.txt
    # en carousel_common.py). `run_started_at` se fija UNA sola vez (primera invocacion
    # real, normalmente run_generation) y se conserva en invocaciones posteriores del
    # mismo bundle (--add-copy, --regenerate-slides); `run_finished_at` se actualiza cada
    # vez que se llama `mark_finished()` — refleja el ultimo punto conocido de
    # finalizacion, nunca un dato inventado.
    run_started_at: Optional[str] = None
    run_finished_at: Optional[str] = None
    phase_seconds: Dict[str, float] = field(default_factory=dict)
    # Marca de inicio/fin de ESTA ejecucion concreta del script (wall-clock real, siempre
    # fresca — nunca cargada desde disco ni sobreescrita por pipeline_started_at historico).
    # `run_started_at` puede ser un timestamp historico de sesiones anteriores (ej. si el
    # bundle ya tenia un cost_log.json de una corrida previa abortada); estas dos marcas
    # garantizan que "Duracion total" en COSTO_CARRUSEL.txt siempre refleje el tiempo real
    # de ESTA invocacion, sin importar lo que haya pasado antes.
    execution_started_at: Optional[str] = None
    execution_finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CostTracker:
    def __init__(
        self,
        bundle_path: Path,
        bundle_id: str,
        slides_total: int,
        price_per_image_usd: float,
        pipeline_started_at: Optional[str] = None,
    ):
        """`pipeline_started_at` (ISO 8601, opcional): permite fijar el inicio REAL del
        cronometro global de la fabrica (ver SKILL.md "CRONOMETRO GLOBAL REAL") a un
        momento anterior a la primera llamada a Gemini — tipicamente el instante en que
        Claude recibio/guardo la imagen de referencia, ANTES de que existiera siquiera
        el bundle. Solo se usa si este bundle todavia no tiene `run_started_at` guardado
        en disco (nunca se sobrescribe un inicio ya registrado por una corrida previa)."""
        self.bundle_path = bundle_path
        self.cost_log_file = bundle_path / "cost_log.json"
        self.summary = CostSummary(
            bundle_id=bundle_id, slides_total=slides_total, price_per_image_usd=price_per_image_usd
        )
        self._price_per_image = price_per_image_usd
        self._load_existing()
        if not self.summary.run_started_at:
            self.summary.run_started_at = pipeline_started_at or datetime.now().isoformat()
        # execution_started_at se fija SIEMPRE en esta invocacion — nunca se carga desde
        # disco ni se hereda de un run anterior. Es el cronometro real de ESTA corrida.
        self.summary.execution_started_at = datetime.now().isoformat()
        self.summary.execution_finished_at = None  # se fija al llamar mark_finished()
        self._save()

    def _load_existing(self) -> None:
        if not self.cost_log_file.exists():
            return
        try:
            raw = json.loads(self.cost_log_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        # Se conservan las entradas anteriores (ej. de una corrida --regenerate-slides
        # previa, o de --add-copy sobre un bundle ya generado); esta corrida solo AGREGA
        # nuevas entradas, nunca borra el historial.
        self.summary.entries = raw.get("entries", [])
        self.summary.run_started_at = raw.get("run_started_at")
        self.summary.run_finished_at = raw.get("run_finished_at")
        self.summary.phase_seconds = raw.get("phase_seconds", {})
        if raw.get("slides_total"):
            self.summary.slides_total = raw["slides_total"]
        # BUG CORREGIDO (ver SKILL.md "COSTO REAL"): los contadores agregados
        # (generated/reused/retries/failed/estimated_cost_usd) NUNCA se restauraban aqui,
        # solo `entries` — asi que cualquier segunda invocacion sobre el mismo bundle
        # (tipicamente --add-copy) creaba un CostTracker nuevo con esos contadores en 0 y
        # los volvia a escribir en cost_log.json, borrando el costo real ya calculado
        # aunque las entradas seguian intactas. Ahora TODOS los agregados se recalculan
        # siempre desde `entries` (fuente de verdad unica) en vez de cargarse o
        # incrementarse por separado — asi nunca pueden desincronizarse ni quedar en 0
        # mientras existan llamadas reales registradas.
        self._recompute_aggregates()

    def _recompute_aggregates(self) -> None:
        """Recalcula generated/reused/retries/failed/estimated_cost_usd DESDE
        `self.summary.entries` — nunca se acumulan de forma incremental por separado,
        para que una recarga (ej. --add-copy, una segunda invocacion sobre el mismo
        bundle) jamas pueda pisar el costo real ya calculado con ceros (ver SKILL.md
        "COSTO REAL": "No sobrescribir cost_log.json con valores cero al ejecutar
        --add-copy" / "No guardar generated=0 si existen llamadas reales")."""
        entries = self.summary.entries
        reused_count = sum(1 for e in entries if e.get("reused"))
        # "generated" = TODAS las llamadas reales a Gemini que produjeron una imagen
        # (billable=True), sin importar si esa imagen despues aprobo o no el QA — cada
        # una de esas llamadas ya se le facturo a la API, y por eso cuenta (ver SKILL.md
        # "COSTO REAL": "Cada llamada real a Gemini que produzca una imagen debe contar
        # como generación billable... Contar: generación inicial, retries,
        # regeneraciones"). Llamadas que NUNCA llegaron a producir una imagen (fallo de
        # red/API, o el slide se omitio por falta de un mockup obligatorio) tienen
        # billable=False y no cuentan aqui ni se cobran.
        generated_count = sum(1 for e in entries if not e.get("reused") and e.get("billable"))
        retries_count = sum(1 for e in entries if not e.get("reused") and e.get("billable") and (e.get("retry_count") or 0) > 0)
        failed_count = sum(1 for e in entries if e.get("status") in ("FAILED", "FAILED_FINAL", "TEXT_QA_FAILED"))
        total_cost = round(sum(e.get("estimated_cost_usd") or 0.0 for e in entries), 4)

        self.summary.reused = reused_count
        self.summary.generated = generated_count
        self.summary.retries = retries_count
        self.summary.failed = failed_count
        self.summary.estimated_cost_usd = total_cost

    def record(
        self,
        bundle_id: str,
        slide_number: int,
        model: str,
        resolution: str,
        aspect_ratio: str,
        mode: str,
        status: str,
        reused: bool,
        retry_count: int,
        prompt_hash: str,
        actual_usage: Optional[Dict[str, Any]] = None,
        billable: bool = True,
    ) -> None:
        """Registra un intento real. `billable` (ver SKILL.md "COSTO REAL") distingue
        una llamada que SI produjo una imagen (siempre billable, sin importar si el QA
        despues la rechazo) de una que NUNCA llego a producir una imagen (fallo de
        red/API antes de recibir bytes, o el slide se omitio sin llamar a Gemini) — solo
        la primera cuenta como generacion real y genera costo. Nunca se aplica a
        entradas `reused=True` (esas ya son gratis por definicion)."""
        is_billable = bool(billable) and not reused
        estimated_cost = self._price_per_image if is_billable else 0.0
        entry = GenerationLogEntry(
            timestamp=datetime.now().isoformat(),
            bundle_id=bundle_id,
            slide_number=slide_number,
            model=model,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            mode=mode,
            status=status,
            reused=reused,
            retry_count=retry_count,
            prompt_hash=prompt_hash,
            estimated_cost_usd=estimated_cost,
            actual_usage=actual_usage,
            billable=is_billable,
        )
        self.summary.entries.append(asdict(entry))
        self._recompute_aggregates()
        self._save()

    def mark_finished(self) -> None:
        """Marca el ultimo punto conocido de finalizacion del pipeline de este bundle
        (ver COSTO_CARRUSEL.txt). Se llama al final de run_generation Y al final de
        run_add_copy — la ultima llamada real siempre gana, nunca se inventa un fin
        antes de que el trabajo termine de verdad."""
        now = datetime.now().isoformat()
        self.summary.run_finished_at = now
        self.summary.execution_finished_at = now
        self._save()

    def record_phase_seconds(self, phase: str, seconds: float) -> None:
        """Registra cuanto tardo (en segundos reales, medidos con time.time()) una fase
        con nombre `phase` (ej. "generation_qa", "export"). Sobrescribe el valor previo
        de esa fase si ya existia (ej. una regeneracion parcial vuelve a medir esa fase)."""
        self.summary.phase_seconds[phase] = round(seconds, 2)
        self._save()

    def _save(self) -> None:
        self.cost_log_file.write_text(
            json.dumps(self.summary.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def print_summary(self) -> None:
        s = self.summary
        print(f"\n   [COST] Resumen de costos ({s.bundle_id}):")
        print(f"      Slides totales: {s.slides_total} | Generados: {s.generated} | "
              f"Reutilizados: {s.reused} | Fallidos: {s.failed}")
        if s.price_per_image_usd <= 0:
            print(f"      Costo estimado: N/D (GEMINI_IMAGE_PRICE_PER_IMAGE no configurado en .env)")
        else:
            print(f"      Costo estimado: ~${s.estimated_cost_usd:.4f} USD "
                  f"(${s.price_per_image_usd:.4f}/imagen x {s.generated} generadas; "
                  f"{s.reused} reutilizadas no generaron costo)")
        print(f"      Detalle completo en: {self.cost_log_file}")
