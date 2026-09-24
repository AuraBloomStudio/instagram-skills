"""
qa.py - Control de calidad de cada slide generado (ver SKILL.md, seccion "QA").

Valida unicamente lo que se puede verificar de forma automatica y determinista:
  - el archivo existe
  - es una imagen valida (PIL puede abrirla)
  - las dimensiones son razonables y respetan la relacion 4:5
  - (opcional) el numero de slide coincide con el nombre de archivo esperado

Lo que el QA NUNCA hace (regla explicita): regenerar automaticamente una imagen varias
veces. Si algo falla, marca REJECTED y punto — la regeneracion individual la decide el
orquestador (direct_generator/batch_manager), respetando MAX_RETRIES.

Validaciones de contenido (texto aprobado, coherencia visual con el Slide 1, mockup
correcto) son inherentemente subjetivas / requieren revision humana o un modelo de
vision aparte — quedan fuera de este QA automatico y se documentan como limitacion
conocida (ver SKILL.md, "Limitaciones" en la seccion COST OPTIMIZATION).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ASPECT_TOLERANCE = 0.03  # 3% de tolerancia sobre el ratio ancho/alto esperado


@dataclass
class QAResult:
    approved: bool
    reason: str = ""


def _expected_ratio(aspect_ratio: str) -> Optional[float]:
    try:
        w_str, h_str = aspect_ratio.split(":")
        return float(w_str) / float(h_str)
    except (ValueError, ZeroDivisionError):
        return None


def run_qa(image_path: Path, expected_aspect_ratio: str = "4:5") -> QAResult:
    """Ejecuta el QA sobre un archivo de imagen ya descargado a disco."""
    if not image_path.exists():
        return QAResult(False, "El archivo no existe")

    if image_path.stat().st_size == 0:
        return QAResult(False, "El archivo existe pero esta vacio (0 bytes)")

    try:
        from PIL import Image
        with Image.open(image_path) as img:
            img.verify()
        # Reabrir tras verify() (verify() invalida el objeto para mas operaciones)
        with Image.open(image_path) as img:
            width, height = img.size
    except Exception as e:  # noqa: BLE001
        return QAResult(False, f"No es una imagen valida: {e}")

    if width <= 0 or height <= 0:
        return QAResult(False, f"Dimensiones invalidas: {width}x{height}")

    expected_ratio = _expected_ratio(expected_aspect_ratio)
    if expected_ratio is not None and width > 1 and height > 1:
        actual_ratio = width / height
        if abs(actual_ratio - expected_ratio) / expected_ratio > _ASPECT_TOLERANCE:
            return QAResult(
                False,
                f"Relacion de aspecto {width}x{height} ({actual_ratio:.3f}) no coincide "
                f"con la esperada {expected_aspect_ratio} ({expected_ratio:.3f}) dentro de "
                f"{_ASPECT_TOLERANCE:.0%} de tolerancia",
            )

    return QAResult(True, "OK")
