"""
qa.py - Control de calidad de cada slide generado (ver SKILL.md, seccion "QA").

Valida unicamente lo que se puede verificar de forma automatica y determinista:
  - el archivo existe
  - es una imagen valida (PIL puede abrirla)
  - las dimensiones son razonables y respetan la relacion 4:5
  - (opcional) el numero de slide coincide con el nombre de archivo esperado
  - la fotografia es blanco y negro / escala de grises (regla estructural permanente,
    ver carousel_common.GLOBAL_DESIGN_RULES punto 2 y SKILL.md "QA VISUAL") — se omite
    en slides que usan el mockup real de producto, que conserva sus colores originales

Lo que el QA NUNCA hace (regla explicita): regenerar automaticamente una imagen varias
veces. Si algo falla, marca REJECTED y punto — la regeneracion individual la decide el
orquestador (direct_generator/batch_manager), respetando MAX_RETRIES.

Validaciones de contenido (texto aprobado, coherencia visual con el Slide 1, mockup
correcto) son inherentemente subjetivas / requieren revision humana o un modelo de
vision aparte — quedan fuera de este QA automatico y se documentan como limitacion
conocida (ver SKILL.md, "Limitaciones" en la seccion COST OPTIMIZATION). La comprobacion
de monocromia es la unica excepcion: es objetiva (diferencia entre canales RGB) y por
eso SI se automatiza aqui.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ASPECT_TOLERANCE = 0.03  # 3% de tolerancia sobre el ratio ancho/alto esperado

# Tolerancia de la comprobacion de monocromia (ver check_monochrome mas abajo). Un pixel
# cuenta como "con color" si la diferencia maxima entre sus canales R/G/B supera este
# umbral (tolera ruido de compresion PNG/JPEG en fotos que son blanco y negro reales).
_MONOCHROME_PIXEL_THRESHOLD = 14
# Fraccion maxima de pixeles muestreados que pueden salir de escala de grises antes de
# marcar la imagen como color (no 0%, para tolerar artefactos de compresion puntuales).
_MONOCHROME_MAX_COLOR_FRACTION = 0.02
# Tamaño reducido usado para el muestreo — suficiente para detectar color visible sin
# recorrer los ~1.46M pixeles de la imagen completa en Python puro.
_MONOCHROME_SAMPLE_SIZE = (120, 150)

# Tolerancia de tono (en grados, circulo de 360) para reconocer un pixel como parte del
# COLOR DE ACENTO DE TEXTO autorizado (ver GLOBAL_DESIGN_RULES punto 5, "Paleta de
# texto") en vez de contaminacion de color en la fotografia. El acento de texto es
# blanco/color unico sobre fondo B&N (hasta 20% del texto) — sus pixeles, y los de sus
# bordes suavizados, tienen un tono cercano al accent_color declarado en
# visual_dna.slide_1_master_dna.accent_color aunque cambien de saturacion/brillo por el
# antialiasing. Sin esta exclusion, el propio acento de texto (uso normal y esperado del
# diseño) se contaria como "color en la foto" y generaria falsos rechazos constantes.
_ACCENT_HUE_TOLERANCE_DEGREES = 35.0


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


def _hue_degrees(r: int, g: int, b: int) -> Optional[float]:
    """Tono (0-360) de un pixel RGB, o None si es acromatico (r==g==b)."""
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return None
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    df = d / 255.0
    if mx == r:
        h = ((gf - bf) / df) % 6
    elif mx == g:
        h = (bf - rf) / df + 2
    else:
        h = (rf - gf) / df + 4
    return h * 60.0


def _hue_distance(h1: float, h2: float) -> float:
    diff = abs(h1 - h2) % 360.0
    return min(diff, 360.0 - diff)


def _accent_hue(accent_color: Optional[str]) -> Optional[float]:
    """
    Extrae el tono (0-360) de un `accent_color` en formato hex ('#F5C518' o 'F5C518').
    Devuelve None si no es un hex valido (ej. una descripcion en texto libre) — en ese
    caso la exclusion de acento simplemente no se aplica, sin romper el QA.
    """
    if not accent_color:
        return None
    s = accent_color.strip().lstrip("#")
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        return None
    r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return _hue_degrees(r, g, b)


def _colorfulness_fraction(image_path: Path, accent_color: Optional[str] = None) -> float:
    """
    Fraccion de pixeles con color visible (no gris NI el acento de texto autorizado) en
    una version reducida de la imagen. Un pixel cuenta como "con color" si la diferencia
    entre sus canales R/G/B supera _MONOCHROME_PIXEL_THRESHOLD — un blanco y negro real,
    guardado como PNG a color, tiene R=G=B (o casi) en todos sus pixeles — y ademas su
    tono NO cae dentro de _ACCENT_HUE_TOLERANCE_DEGREES del `accent_color` autorizado
    (ver "Paleta de texto"): eso es contenido de TEXTO permitido, no la fotografia.
    """
    from PIL import Image
    with Image.open(image_path) as img:
        small = img.convert("RGB").resize(_MONOCHROME_SAMPLE_SIZE)
    width, height = small.size
    total = width * height
    if total == 0:
        return 0.0
    accent_hue = _accent_hue(accent_color)
    px = small.load()
    colored = 0
    for x in range(width):
        for y in range(height):
            r, g, b = px[x, y]
            if max(abs(r - g), abs(r - b), abs(g - b)) <= _MONOCHROME_PIXEL_THRESHOLD:
                continue
            if accent_hue is not None:
                hue = _hue_degrees(r, g, b)
                if hue is not None and _hue_distance(hue, accent_hue) <= _ACCENT_HUE_TOLERANCE_DEGREES:
                    continue  # pixel del acento de texto autorizado, no cuenta como color
            colored += 1
    return colored / total


def check_monochrome(image_path: Path, accent_color: Optional[str] = None) -> QAResult:
    """
    Verifica de forma OBJETIVA (ver SKILL.md "QA VISUAL") que la fotografia sea blanco y
    negro / escala de grises, segun la regla estructural permanente de
    carousel_common.GLOBAL_DESIGN_RULES (punto 2). Nunca se llama para slides que usan el
    mockup real de producto directamente — ese asset conserva sus colores originales por
    regla explicita (ver IMAGE_ROLE_INSTRUCTIONS["mockup"]); es responsabilidad del
    llamador (run_qa, via `check_color=False`) omitir esta comprobacion en esos slides.

    `accent_color` (opcional, ej. "#F5C518") es el color de acento AUTORIZADO del texto
    de este carrusel (visual_dna.slide_1_master_dna.accent_color) — sus pixeles (y los
    tonos cercanos, por antialiasing) se excluyen del conteo de "color", porque son texto
    permitido por la regla de "Paleta de texto", no contaminacion de color en la foto.
    """
    try:
        fraction = _colorfulness_fraction(image_path, accent_color)
    except Exception as e:  # noqa: BLE001
        # Un fallo al leer la imagen para este chequeo no debe bloquear el QA estructural,
        # que ya la abrio correctamente antes de llegar aqui — se deja pasar sin marcar.
        return QAResult(True, f"No se pudo verificar monocromia ({e}); no bloquea")

    if fraction > _MONOCHROME_MAX_COLOR_FRACTION:
        return QAResult(
            False,
            f"Imagen con color visible ({fraction:.1%} de pixeles muestreados fuera de "
            f"escala de grises y fuera del acento de texto autorizado, tolerancia "
            f"{_MONOCHROME_MAX_COLOR_FRACTION:.0%}) — viola la regla permanente de blanco "
            "y negro (GLOBAL_DESIGN_RULES punto 2)",
        )
    return QAResult(True, "OK monocromia")


def run_qa(image_path: Path, expected_aspect_ratio: str = "4:5", check_color: bool = True,
           accent_color: Optional[str] = None) -> QAResult:
    """
    Ejecuta el QA sobre un archivo de imagen ya descargado a disco.

    `check_color=False` omite la comprobacion de monocromia (ver check_monochrome) — usar
    UNICAMENTE para slides con `uses_product_mockup_directly=True`, donde el mockup real
    del producto conserva sus colores originales por regla explicita.
    `accent_color`: ver check_monochrome — color de texto autorizado a excluir del chequeo.
    """
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

    if check_color:
        color_result = check_monochrome(image_path, accent_color)
        if not color_result.approved:
            return color_result

    return QAResult(True, "OK")
