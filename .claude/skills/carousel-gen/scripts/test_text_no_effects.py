#!/usr/bin/env python3
"""
test_text_no_effects.py — Tests para la regla estructural permanente de texto sin
sombras/glow/halo/capas oscuras (ver SKILL.md "TEXTO SIN SOMBRAS NI CAPAS" y
carousel_common.GLOBAL_DESIGN_RULES punto 8), aplicada al respaldo deterministico de
texto (`text_fallback.compose_exact_text`) — el unico lugar del skill donde se dibuja
texto con Pillow.

Cubre:
  TEST 1 — compose_exact_text no introduce ningun pixel negro puro (la sombra vieja
           dibujaba el texto en (0,0,0) antes del blanco; sin sombra, un fondo sin negro
           debe seguir sin tener negro)
  TEST 2 — compose_exact_text NO oscurece/difumina la franja de texto fuera de las letras
           (el margen lateral, dentro de la banda de texto, debe conservar el color
           original exacto del fondo — antes ese margen quedaba oscurecido por la banda)
  TEST 3 — compose_exact_text dibuja el texto en blanco puro (255,255,255) directamente,
           sin mezclarlo con ningun overlay (debe existir al menos un pixel blanco puro)
  TEST 4 — el resumen devuelto conserva las mismas claves de siempre (compatibilidad con
           cierre_bundle.py / manifest.json)

NO ejecuta Gemini real ni depende de red.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image

import text_fallback

PASS_S, FAIL_S = "PASS", "FAIL"
results_log = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS_S if ok else FAIL_S
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))
    assert ok, f"{test_id} FAILED: {description} -- {detail}"


_BG_COLOR = (130, 90, 60)  # tono solido, sin negro, distinto de blanco/amarillo/acento
_EXACT_TEXT = "Esta es una prueba de texto sin sombras ni capas oscuras detras"
_SIZE = (480, 600)  # 4:5, tamaño reducido para tests rapidos


def _make_base_image(tmp_dir: Path) -> Path:
    path = tmp_dir / "base.png"
    Image.new("RGB", _SIZE, color=_BG_COLOR).save(path)
    return path


def test_1_no_pure_black_pixels_from_shadow():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src = _make_base_image(tmp)
        out = tmp / "out.png"
        text_fallback.compose_exact_text(src, _EXACT_TEXT, "lower_third_centered", out)
        img = Image.open(out).convert("RGB")
        px = img.load()
        has_black = any(px[x, y] == (0, 0, 0) for x in range(img.width) for y in range(img.height))
        report("TEST 1", "compose_exact_text no dibuja ningun pixel negro puro (sin sombra)",
               not has_black, f"has_black={has_black}")


def test_2_side_margin_inside_band_untouched():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src = _make_base_image(tmp)
        out = tmp / "out.png"
        info = text_fallback.compose_exact_text(src, _EXACT_TEXT, "lower_third_centered", out)
        img = Image.open(out).convert("RGB")
        y0, y1 = info["band"]
        mid_y = (y0 + y1) // 2
        # Un par de pixeles justo dentro del margen lateral izquierdo (fuera de cualquier
        # letra) pero DENTRO de la franja vertical de texto -- con la banda vieja
        # (blur + brightness 0.30) estos pixeles quedaban oscurecidos aunque no tuvieran
        # texto encima. Sin banda, deben conservar el color original exacto.
        sample_points = [(1, mid_y), (2, mid_y), (img.width - 2, mid_y)]
        mismatches = [(x, y, img.getpixel((x, y))) for x, y in sample_points
                      if img.getpixel((x, y)) != _BG_COLOR]
        report("TEST 2", "el margen lateral dentro de la banda de texto conserva el color "
               "original (sin oscurecer/difuminar)", not mismatches, f"mismatches={mismatches}")


def test_3_white_text_drawn_directly():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src = _make_base_image(tmp)
        out = tmp / "out.png"
        text_fallback.compose_exact_text(src, _EXACT_TEXT, "lower_third_centered", out)
        img = Image.open(out).convert("RGB")
        px = img.load()
        has_white = any(px[x, y] == (255, 255, 255) for x in range(img.width) for y in range(img.height))
        report("TEST 3", "el texto se dibuja en blanco puro directamente sobre la foto",
               has_white, f"has_white={has_white}")


def test_4_summary_keys_unchanged():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        src = _make_base_image(tmp)
        out = tmp / "out.png"
        info = text_fallback.compose_exact_text(src, _EXACT_TEXT, "lower_third_centered", out)
        expected_keys = {"band", "detected_band", "font_size", "lines"}
        ok = expected_keys.issubset(info.keys())
        report("TEST 4", "el resumen conserva las claves band/detected_band/font_size/lines",
               ok, f"keys={sorted(info.keys())}")


def main():
    print("=" * 65)
    print("test_text_no_effects.py — Texto sin sombras ni capas oscuras")
    print("=" * 65)

    test_1_no_pure_black_pixels_from_shadow()
    test_2_side_margin_inside_band_untouched()
    test_3_white_text_drawn_directly()
    test_4_summary_keys_unchanged()

    passed = sum(1 for r in results_log if r["status"] == PASS_S)
    failed = sum(1 for r in results_log if r["status"] == FAIL_S)
    print("=" * 65)
    print(f"RESULTADO: {passed}/{passed + failed} PASS" + (f" — {failed} FAIL" if failed else ""))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
