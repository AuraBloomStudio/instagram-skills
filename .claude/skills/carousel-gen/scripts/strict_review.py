"""
strict_review.py - REVISION FINAL ESTRICTA del texto de cada slide (2026-09-26).

El Text QA de la generacion es tolerante a proposito (no gasta regeneraciones en malas
lecturas del OCR). En una prueba real eso dejo pasar errores visibles: "necesisitaste"
(palabra deformada), "no determes;" (texto inventado en el slide del mockup) y
"pe rsonas" (palabra partida). Esta revision se ejecuta en el CIERRE, sobre los PNG
finales, y marca un error como REAL solo si aparece en TODAS las lecturas OCR de la
imagen (normal + ampliada/binarizada): un fallo del OCR cambia de una lectura a otra; un
error dibujado en la imagen, no.

Se toleran unicamente confusiones tipicas del OCR que no cambian la palabra: acentos,
una letra confundida en una palabra de la misma longitud, la eñe leida como "fi"/"ii" y
el signo de apertura "¿"/"¡" pegado a la palabra ("gpor") SOLO donde el texto original
lo tiene.
En slides con mockup solo se lee la mitad del texto (text_placement), para no mezclar
el texto impreso en la portada del libro.
"""

import difflib
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from PIL import Image

import text_qa
from text_qa import tokenize


def _edit(a: str, b: str) -> int:
    return text_qa._edit_distance(a, b)


_OPENING_MARK_READINGS = ("g", "i", "l", "j", "¢", "¿", "¡", "c")


def opening_mark_positions(exact_text: str) -> Set[int]:
    """Indices (en tokenize(exact_text)) de las palabras precedidas por ¿ o ¡."""
    positions: Set[int] = set()
    index = 0
    for chunk in exact_text.split():
        chunk_tokens = tokenize(chunk)
        if chunk_tokens and chunk.lstrip("\"'«“(").startswith(("¿", "¡")):
            positions.add(index)
        index += len(chunk_tokens)
    return positions


def tokens_equivalent(expected: str, rendered: str, after_opening_mark: bool = False) -> bool:
    """Misma palabra salvo ruido tipico del OCR que NO cambia la palabra."""
    if expected == rendered:
        return True
    if (after_opening_mark and len(rendered) == len(expected) + 1
            and rendered[0] in _OPENING_MARK_READINGS
            and tokens_equivalent(expected, rendered[1:])):
        return True
    for variant in (rendered, rendered.replace("fi", "n"), rendered.replace("ii", "n")):
        if variant == expected:
            return True
        if len(variant) == len(expected) and len(expected) >= 2 and _edit(variant, expected) <= 1:
            return True
    return False


def _signatures(expected: List[str], rendered: List[str],
                marks: Set[int] = frozenset()) -> Set[Tuple]:
    """Errores de UNA lectura, como posiciones del texto esperado (comparables entre lecturas)."""
    found: Set[Tuple] = set()
    matcher = difflib.SequenceMatcher(None, expected, rendered, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace" and (i2 - i1) == (j2 - j1) and all(
                tokens_equivalent(expected[i], rendered[j], i in marks)
                for i, j in zip(range(i1, i2), range(j1, j2))):
            continue
        if tag == "insert":
            found.add(("insert", i1))
            continue
        # replace/delete: emparejar palabra a palabra dentro del bloque (un fallo menor del
        # OCR junto a un texto añadido no debe ocultar la insercion).
        j, leftover = j1, 0
        for i in range(i1, i2):
            k = next((k for k in range(j, j2) if tokens_equivalent(expected[i], rendered[k], i in marks)), None)
            if k is None:
                found.add(("token", i))
                continue
            leftover += k - j
            j = k + 1
        leftover += j2 - j
        unmatched = sum(1 for t in found if t[0] == "token" and i1 <= t[1] < i2)
        if leftover > unmatched:
            found.add(("insert", i1))
    return found


_INSERT_WINDOW = 2


def _confirmed(per_reading: List[Set[Tuple]]) -> Set[Tuple]:
    """
    Errores presentes en TODAS las lecturas. Una palabra mal/faltante debe coincidir en
    posicion exacta; un texto AÑADIDO puede quedar alineado +-2 posiciones segun la lectura
    (con palabras repetidas como "no ... no" o "de de" hay alineaciones equivalentes).
    """
    first, rest = per_reading[0], per_reading[1:]
    confirmed: Set[Tuple] = set()
    for kind, i in first:
        if kind == "token":
            if all((kind, i) in other for other in rest):
                confirmed.add((kind, i))
        elif all(any(k == "insert" and abs(j - i) <= _INSERT_WINDOW for k, j in other) for other in rest):
            confirmed.add((kind, i))
    return confirmed


def _crop_for_slide(img: Image.Image, text_placement: str, uses_mockup: bool) -> Image.Image:
    if not uses_mockup:
        return img
    tp = (text_placement or "").lower()
    w, h = img.size
    if any(k in tp for k in ("upper", "superior", "top")):
        return img.crop((0, 0, w, int(h * 0.50)))
    if any(k in tp for k in ("lower", "inferior", "bottom")):
        return img.crop((0, int(h * 0.50), w, h))
    return img


def _readings(img: Image.Image) -> List[str]:
    texts: List[str] = []
    try:
        texts.append(text_qa._run_tesseract(img))
    except Exception:  # noqa: BLE001 - lectura no disponible: se omite
        pass
    tmp = Path(text_qa.tempfile.mkdtemp(prefix="strict_review_"))
    try:
        path = tmp / "slide.png"
        img.save(path)
        texts.extend(t for _, t in text_qa.extract_text_variants(path))
    finally:
        text_qa.shutil.rmtree(tmp, ignore_errors=True)
    return texts


def review_slide(png: Path, exact_text: str, text_placement: str = "",
                 uses_mockup: bool = False) -> Dict[str, Any]:
    """
    Devuelve {"ok": bool, "errors": [...], "readings": n}. ok=False si algun error aparece
    en TODAS las lecturas. Sin OCR disponible devuelve ok=None (no verificable).
    """
    with Image.open(png) as im:
        img = _crop_for_slide(im.convert("RGB"), text_placement, uses_mockup)
    texts = _readings(img)
    if not texts:
        return {"ok": None, "errors": [], "readings": 0, "detail": "OCR no disponible"}
    expected = tokenize(exact_text)
    marks = opening_mark_positions(exact_text)
    common = _confirmed([_signatures(expected, tokenize(text), marks) for text in texts])
    errors = []
    for kind, i in sorted(common, key=lambda x: x[1]):
        if kind == "insert":
            errors.append(f"texto añadido antes de '{expected[i] if i < len(expected) else 'FIN'}'")
        else:
            errors.append(f"palabra '{expected[i]}' faltante o deformada")
    return {"ok": not errors, "errors": errors, "readings": len(texts)}
