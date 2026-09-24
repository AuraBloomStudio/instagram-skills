"""
prompt_hash.py - Calcula el `prompt_hash` de un slide: la huella digital de TODO lo que
afecta realmente su generacion.

Regla de la migracion economica: "Si el hash no cambio: reutilizar imagen. Si el hash
cambio: considerar regeneracion." Este modulo es la UNICA fuente de ese hash — nunca se
recalcula de otra forma en otro archivo, para que cache_manager y batch_manager siempre
comparen el mismo criterio.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional


def compute_prompt_hash(
    prompt_text: str,
    slide: Dict[str, Any],
    visual_dna: Dict[str, Any],
    carousel_type: str,
    aspect_ratio: str,
    image_size: str,
    model: str,
    reference_image_id: Optional[str] = None,
) -> str:
    """
    Deriva el hash de los elementos que REALMENTE afectan la generacion (ver
    SKILL.md, seccion "HASH DE PROMPT"):
      - prompt visual completo ya construido (incluye exact_text y el resto de campos
        narrativos del slide, el ADN visual y las reglas de diseño)
      - exact_text (redundante con el prompt, pero se incluye explicito por si el
        prompt builder cambia de forma en el futuro sin cambiar exact_text)
      - slide number
      - visual DNA completo (paleta, tipografia, ADN maestro, etc.)
      - carousel type
      - aspect ratio / image size / model
      - identificador de la imagen de referencia usada (si aplica) — para que un
        cambio de la imagen de referencia adjunta invalide el cache aunque el texto
        del prompt no haya cambiado
    """
    payload = {
        "prompt_text": prompt_text,
        "exact_text": slide.get("exact_text", ""),
        "slide_number": slide.get("number"),
        "visual_dna": visual_dna,
        "carousel_type": carousel_type,
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
        "model": model,
        "reference_image_id": reference_image_id,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hash_file_bytes(data: bytes) -> str:
    """Hash de contenido binario (usado para identificar una imagen de referencia por su
    contenido real, no por su ruta — asi si el archivo cambia, el prompt_hash cambia)."""
    return hashlib.sha256(data).hexdigest()[:16]
