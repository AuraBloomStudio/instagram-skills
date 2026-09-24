"""
cache_manager.py - Cache local por bundle para la REUTILIZACION INTELIGENTE de slides ya
generados (ver SKILL.md, secciones "REUTILIZACIÓN INTELIGENTE" y "CACHE").

Vive en `carousel/.generation_cache.json` dentro de cada bundle (archivo interno, NUNCA
se copia a Descargas — ver `export_final_slides_to_downloads` en carousel_common.py).

Antes de generar un slide, el orquestador SIEMPRE consulta `should_reuse()`. Si ya existe
una imagen valida con el mismo prompt_hash/model/resolution/aspect_ratio y no esta
marcada FAILED/REJECTED, se reutiliza y se registra como REUSED — nunca se vuelve a
gastar credito en ese slide.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

CACHE_FILENAME = ".generation_cache.json"

# Estados permitidos (ver SKILL.md "BATCH API"), mas REUSED y REJECTED que se agregan
# para la reutilizacion inteligente y el QA respectivamente, mas los estados TEXT_QA_*
# (ver SKILL.md "TEXT QA" y scripts/text_qa.py) para la verificacion local del texto
# realmente renderizado dentro de la imagen.
VALID_STATUSES = {
    "CREATED", "SUBMITTED", "PROCESSING", "COMPLETED", "PARTIAL_FAILURE",
    "FAILED", "RETRYING", "APPROVED", "REUSED", "REJECTED", "FAILED_FINAL",
    "TEXT_QA_PENDING", "TEXT_QA_APPROVED", "TEXT_QA_REJECTED",
    "TEXT_QA_REGENERATING", "TEXT_QA_FAILED",
}

# Estados que NUNCA se reutilizan silenciosamente, aunque el hash coincida — deben
# regenerarse explicitamente. TEXT_QA_APPROVED SI es reutilizable (es un exito, igual
# que APPROVED) — solo los estados de rechazo/fallo/reintento quedan bloqueados aqui.
_NON_REUSABLE_STATUSES = {
    "FAILED", "REJECTED", "RETRYING", "FAILED_FINAL",
    "TEXT_QA_REJECTED", "TEXT_QA_REGENERATING", "TEXT_QA_FAILED",
}


@dataclass
class SlideCacheRecord:
    slide_number: int
    prompt_hash: str
    model: str
    resolution: str
    aspect_ratio: str
    image_path: str  # relativo a carousel/, ej. "carousel-03.png"
    status: str = "CREATED"
    retry_count: int = 0
    last_error: Optional[str] = None
    request_id: Optional[str] = None
    updated_at: str = ""
    # Campos de Text QA (ver SKILL.md "TEXT QA" seccion 23, manifest.json por slide).
    # Opcionales con default None/0 para que registros de cache anteriores a esta
    # funcionalidad se sigan cargando sin error (backward compatible).
    expected_text_hash: Optional[str] = None
    rendered_text_hash: Optional[str] = None
    text_qa_status: Optional[str] = None
    text_qa_retry_count: int = 0
    text_qa_rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CacheManager:
    def __init__(self, carousel_dir: Path):
        self.carousel_dir = carousel_dir
        self.cache_file = carousel_dir / CACHE_FILENAME
        self._records: Dict[int, SlideCacheRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for slide_num_str, entry in raw.get("slides", {}).items():
            try:
                self._records[int(slide_num_str)] = SlideCacheRecord(**entry)
            except (TypeError, ValueError):
                continue

    def save(self) -> None:
        data = {
            "slides": {str(num): rec.to_dict() for num, rec in self._records.items()},
        }
        self.cache_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, slide_number: int) -> Optional[SlideCacheRecord]:
        return self._records.get(slide_number)

    def upsert(self, record: SlideCacheRecord) -> None:
        record.updated_at = datetime.now().isoformat()
        self._records[record.slide_number] = record
        self.save()

    def should_reuse(
        self,
        slide_number: int,
        prompt_hash: str,
        model: str,
        resolution: str,
        aspect_ratio: str,
        force_regenerate: bool = False,
    ) -> bool:
        """
        Compuerta obligatoria de reutilizacion (ver SKILL.md "REUTILIZACIÓN
        INTELIGENTE"). Verifica, en este orden:
          0. Si force_regenerate=True (ej. --regenerate-slides), siempre False — el
             slide fue explicitamente solicitado para regeneracion y el cache no aplica.
          1. Existe un registro de cache para este slide.
          2. prompt_hash / model / resolution / aspect_ratio coinciden EXACTAMENTE.
          3. El estado registrado no es FAILED/REJECTED/RETRYING/FAILED_FINAL.
          4. El archivo de imagen referenciado existe de verdad en disco y no esta vacio.
        Si CUALQUIERA falla, no se reutiliza (se debe generar).
        """
        if force_regenerate:
            return False
        record = self._records.get(slide_number)
        if record is None:
            return False
        if (record.prompt_hash != prompt_hash or record.model != model
                or record.resolution != resolution or record.aspect_ratio != aspect_ratio):
            return False
        if record.status in _NON_REUSABLE_STATUSES:
            return False
        image_file = self.carousel_dir / record.image_path
        if not image_file.exists() or image_file.stat().st_size == 0:
            return False
        return True

    def mark_reused(self, slide_number: int) -> None:
        record = self._records.get(slide_number)
        if record:
            record.status = "REUSED"
            self.upsert(record)
