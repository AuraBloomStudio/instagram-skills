"""
gemini_config.py - Configuracion CENTRAL y UNICA para el generador economico de
carousel-gen (Google Gemini / Nano Banana 2 Lite).

Regla obligatoria de la migracion: "NO hardcodear el modelo en multiples lugares. Debe
existir una unica configuracion central." Todo lo que otro modulo necesite saber sobre
que modelo usar, que resolucion, si Batch esta activo, si Kie esta activo, etc., se lee
de aqui — nunca se repite un valor por defecto en otro archivo.

Todas las variables se leen de `.env` (raiz del skill) via python-dotenv. Ningun valor
sensible (API keys) se imprime nunca por consola.
"""

import sys
import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from carousel_common import MAX_SLIDES as _HARD_MAX_SLIDES  # noqa: E402

_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class GeminiConfig:
    # --- Proveedor principal: Google Gemini (Nano Banana 2 Lite) ---
    api_key: str
    image_model: str
    aspect_ratio: str
    image_size: str

    # --- Modo economico y modo de ejecucion (Batch vs Direct) ---
    economy_mode: bool
    batch_enabled: bool

    # --- Limites y reintentos ---
    # Presupuesto UNICO de reintentos, compartido por fallos de generacion, QA
    # estructural Y Text QA (ver SKILL.md "FABRICA RAPIDA"): 1 intento inicial + hasta
    # `max_retries` regeneraciones. Por defecto 1 (maximo 2 intentos totales por slide,
    # y esa unica regeneracion solo se dispara por error CRITICO) — nunca dos
    # presupuestos separados que se puedan apilar.
    max_slides: int
    max_retries: int

    # --- Text QA: verificacion LOCAL (OCR, sin llamadas a Gemini) del texto realmente
    # renderizado dentro de cada imagen contra exact_text de brief.json — ver
    # SKILL.md "TEXT QA" y scripts/text_qa.py. Puede desactivarse por completo si el
    # entorno no tiene OCR disponible o el usuario prefiere no usarlo.
    text_qa_enabled: bool

    # --- Costos ---
    price_per_image_usd: float

    # --- Kie / Flow: DESACTIVADOS por defecto en esta migracion (ver SKILL.md
    # "COST OPTIMIZATION" y "Migracion desde Kie"). Solo se activan si el usuario los
    # habilita explicitamente en .env — nunca automaticamente como fallback. ---
    kie_enabled: bool
    flow_enabled: bool

    def has_api_key(self) -> bool:
        return bool(self.api_key)


def load_config() -> GeminiConfig:
    """Punto unico de lectura de configuracion. Cualquier modulo que necesite saber el
    modelo, la resolucion, si Batch esta activo, etc., debe llamar a esta funcion —
    nunca leer os.environ directamente en otro lugar del codigo.

    IMPORTANTE sobre max_slides: el limite de 10 slides es una regla PERMANENTE del
    skill (ver SKILL.md "LÍMITE OBLIGATORIO DE SLIDES") y su fuente de verdad tecnica es
    `carousel_common.MAX_SLIDES` (compartida con el generador legacy de Kie) — nunca
    `carousel_common.MAX_SLIDES` en si mismo es configurable. La variable `MAX_SLIDES` en
    `.env` es solo informativa/documental: si alguien la sube por encima del limite
    permanente, se ignora silenciosamente en favor del limite duro y se advierte por
    consola — nunca se permite debilitar esta regla desde configuracion.
    """
    env_max_slides = _get_int("MAX_SLIDES", _HARD_MAX_SLIDES)
    if env_max_slides > _HARD_MAX_SLIDES:
        print(f"[WARN] Advertencia: MAX_SLIDES={env_max_slides} en .env supera el límite "
              f"permanente de {_HARD_MAX_SLIDES} slides (ver SKILL.md, 'LÍMITE OBLIGATORIO "
              f"DE SLIDES'). Se ignora y se aplica {_HARD_MAX_SLIDES} — esta regla nunca es "
              f"configurable hacia arriba.")
    effective_max_slides = min(env_max_slides, _HARD_MAX_SLIDES) if env_max_slides > 0 else _HARD_MAX_SLIDES

    return GeminiConfig(
        api_key=os.environ.get("GEMINI_API_KEY", "").strip(),
        image_model=os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-lite-image").strip(),
        aspect_ratio=os.environ.get("IMAGE_ASPECT_RATIO", "4:5").strip(),
        image_size=os.environ.get("IMAGE_SIZE", "1K").strip(),
        economy_mode=_get_bool("ECONOMY_MODE", True),
        # FABRICA RAPIDA (regla obligatoria y permanente, ver SKILL.md): el modo normal
        # de produccion NUNCA usa Batch por defecto — Batch puede tardar hasta 24h segun
        # documentacion de Google y es la fuente de la peor latencia del pipeline. Batch
        # queda reservado para una futura modalidad explicita de produccion masiva/
        # economica, activada UNICAMENTE via --force-batch en esa corrida especifica,
        # nunca automaticamente. Si se pone GEMINI_BATCH_ENABLED=true en .env, sigue sin
        # activarse solo por eso — process_slides() ya no lee este flag para decidir el
        # modo (ver generate-carousel-gemini.py); se mantiene aqui unicamente para no
        # romper .env existentes y para uso informativo en el manifest.
        batch_enabled=_get_bool("GEMINI_BATCH_ENABLED", False),
        max_slides=effective_max_slides,
        max_retries=_get_int("MAX_RETRIES", 1),
        text_qa_enabled=_get_bool("TEXT_QA_ENABLED", True),
        price_per_image_usd=_get_float("GEMINI_IMAGE_PRICE_PER_IMAGE", 0.0),
        kie_enabled=_get_bool("KIE_ENABLED", False),
        flow_enabled=_get_bool("FLOW_ENABLED", False),
    )
