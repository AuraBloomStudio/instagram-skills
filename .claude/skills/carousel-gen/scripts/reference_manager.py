"""
reference_manager.py - Decide, para cada slide, cual es su REFERENCE_MODE y resuelve la
imagen (bytes) real que corresponde adjuntar.

Regla de referencias (maximo 2 imagenes por slide, priorizacion por rol):
  1. Slide 1: recibe SPECIFIC_REFERENCE (viral-reference.png real del usuario).
  2. Slides 2+ sin mockup: reciben SLIDE_1 (ancla) + VIRAL_CONTEXT (referencia original
     como contexto fotografico) — 2 imagenes. Si no hay ancla aun, solo VIRAL_CONTEXT.
  3. Slides 2+ con mockup: reciben SLIDE_1 (ancla) + BOOK_MOCKUP — 2 imagenes. El mockup
     tiene prioridad sobre VIRAL_CONTEXT para no superar el maximo de 2 imagenes. Si no
     hay ancla, VIRAL_CONTEXT sustituye al ancla: VIRAL_CONTEXT + BOOK_MOCKUP.
  4. Nunca 3 o mas imagenes a la vez.
  5. El Visual DNA estructurado en texto NO cuenta como "imagen adjunta".
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReferenceMode(str, Enum):
    NONE = "NONE"
    SLIDE_1 = "SLIDE_1"                # usa el Slide 1 (real, ya generado) como ancla
    SPECIFIC_REFERENCE = "SPECIFIC_REFERENCE"  # usa la imagen de referencia viral original (Slide 1)
    VIRAL_CONTEXT = "VIRAL_CONTEXT"    # referencia viral original como contexto fotografico (Slides 2+)
    BOOK_MOCKUP = "BOOK_MOCKUP"        # usa el mockup real del producto


@dataclass
class ResolvedReference:
    mode: ReferenceMode
    image_path: Optional[Path]
    role_tag: str  # "reference" | "anchor" | "mockup" — coincide con IMAGE_ROLE_INSTRUCTIONS


def decide_reference_plan(
    slide: Dict[str, Any],
    slide1_anchor_path: Optional[Path],
    reference_image_path: Optional[Path],
    product_mockup_path: Optional[Path],
) -> List[ResolvedReference]:
    """
    Devuelve la lista (0, 1 o maximo 2) de referencias que este slide debe recibir,
    en orden de prioridad. Nunca mas de 2 imagenes adjuntas por slide.

    SLIDE 1 (uses_reference_image_directly=True):
      - Recibe SPECIFIC_REFERENCE: la imagen viral original. Nada mas.

    SLIDES 2+ SIN MOCKUP:
      - Si hay ancla (Slide 1 ya generado): [SLIDE_1, VIRAL_CONTEXT]
        → El ancla garantiza continuidad con el Slide 1 real.
        → La referencia viral original ancla el realismo fotografico de partida.
      - Si no hay ancla: [VIRAL_CONTEXT]
        → La referencia viral como unico anclaje fotografico.
      - Si no hay ancla ni referencia: [NONE]

    SLIDES 2+ CON MOCKUP (uses_product_mockup_directly=True):
      - Si hay ancla: [SLIDE_1, BOOK_MOCKUP] — mockup tiene prioridad sobre viral_context
        para no superar 2 imagenes (la ancla ya garantiza continuidad).
      - Si no hay ancla: [VIRAL_CONTEXT, BOOK_MOCKUP]
        → La referencia viral sustituye al ancla (continuidad fotografica minima).
      - Si el mockup no esta disponible: se registra BOOK_MOCKUP con path=None
        (el llamador debe reportar este slide como bloqueado y no generarlo).
    """
    plan: List[ResolvedReference] = []

    uses_reference = bool(slide.get("uses_reference_image_directly"))
    uses_mockup = bool(slide.get("uses_product_mockup_directly"))

    # --- Slide 1: recibe la referencia viral original directamente ---
    if uses_reference and reference_image_path and reference_image_path.exists():
        plan.append(ResolvedReference(ReferenceMode.SPECIFIC_REFERENCE, reference_image_path, "reference"))
        return plan

    # --- Slides 2+: ancla visual (Slide 1 ya generado, si existe) ---
    has_anchor = bool(slide1_anchor_path and slide1_anchor_path.exists())
    has_viral = bool(reference_image_path and reference_image_path.exists())

    if uses_mockup:
        # Con mockup: ancla + mockup (o viral_context + mockup si no hay ancla)
        if has_anchor:
            plan.append(ResolvedReference(ReferenceMode.SLIDE_1, slide1_anchor_path, "anchor"))
        elif has_viral:
            # Viral sustituye al ancla cuando no existe Slide 1 generado aun
            plan.append(ResolvedReference(ReferenceMode.VIRAL_CONTEXT, reference_image_path, "viral_context"))

        if product_mockup_path and product_mockup_path.exists():
            plan.append(ResolvedReference(ReferenceMode.BOOK_MOCKUP, product_mockup_path, "mockup"))
        else:
            # Regla obligatoria: nunca inventar/generar una portada si el slide la
            # requiere y el mockup real no esta disponible — el llamador detiene ese slide.
            plan.append(ResolvedReference(ReferenceMode.BOOK_MOCKUP, None, "mockup"))
    else:
        # Sin mockup: ancla + viral_context (continuidad maxima, 2 imagenes)
        if has_anchor:
            plan.append(ResolvedReference(ReferenceMode.SLIDE_1, slide1_anchor_path, "anchor"))
        if has_viral:
            plan.append(ResolvedReference(ReferenceMode.VIRAL_CONTEXT, reference_image_path, "viral_context"))

    if not plan:
        plan.append(ResolvedReference(ReferenceMode.NONE, None, "none"))

    return plan


def reference_identifier(resolved_refs: List[ResolvedReference], hash_fn) -> Optional[str]:
    """
    Construye un identificador estable de las referencias usadas por un slide, para
    incluir en el prompt_hash (ver SKILL.md "HASH DE PROMPT" — "reference image
    identifier si aplica"). `hash_fn` recibe bytes y devuelve un hash corto.
    """
    parts = []
    for ref in resolved_refs:
        if ref.image_path is None:
            continue
        try:
            data = ref.image_path.read_bytes()
        except OSError:
            continue
        parts.append(f"{ref.mode.value}:{hash_fn(data)}")
    return "|".join(parts) if parts else None
