#!/usr/bin/env python3
"""
test_qa_monochrome.py — Tests para la regla estructural permanente de blanco y negro
(ver carousel_common.GLOBAL_DESIGN_RULES punto 2 y qa.check_monochrome / qa.run_qa).

Cubre:
  TEST 1 — check_monochrome aprueba una imagen en escala de grises real
  TEST 2 — check_monochrome rechaza una imagen claramente a color
  TEST 3 — check_monochrome tolera ruido minimo de compresion (pocos pixeles fuera de gris)
  TEST 4 — run_qa rechaza una imagen a color con aspect ratio valido (check_color=True)
  TEST 5 — run_qa con check_color=False (slides de mockup) aprueba pese al color
  TEST 6 — run_qa sigue rechazando dimensiones invalidas aunque la imagen sea B&N
  TEST 7 — check_monochrome NO rechaza el acento de texto autorizado (accent_color) —
           hallazgo real de produccion 2026-09-28: sin esto, el propio acento de texto
           permitido por "Paleta de texto" se contaba como color de la fotografia
  TEST 8 — check_monochrome SI rechaza un color que no coincide con el accent_color
           autorizado (la exclusion es especifica de ese tono, no un pase libre)

NO ejecuta Gemini real ni genera imagenes vía red.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image

from qa import run_qa, check_monochrome

PASS_S, FAIL_S = "PASS", "FAIL"
results_log = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS_S if ok else FAIL_S
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))
    assert ok, f"{test_id} FAILED: {description} -- {detail}"


def _make_image(tmp_dir: Path, name: str, size=(216, 270), fill=(120, 120, 120)) -> Path:
    path = tmp_dir / name
    Image.new("RGB", size, color=fill).save(path)
    return path


def _make_gradient_grayscale(tmp_dir: Path, name: str, size=(216, 270)) -> Path:
    """Imagen B&N real con variacion tonal (no un solo gris plano) — mas representativa
    de una fotografia real que un fill solido."""
    img = Image.new("RGB", size)
    pixels = img.load()
    w, h = size
    for x in range(w):
        for y in range(h):
            v = int(255 * (x / w))
            pixels[x, y] = (v, v, v)
    path = tmp_dir / name
    img.save(path)
    return path


def _make_color_with_noise(tmp_dir: Path, name: str, size=(216, 270),
                            base=(30, 30, 30), noisy_fraction: float = 0.005) -> Path:
    """Imagen casi-gris con un pequeño porcentaje de pixeles con ruido de color,
    simulando artefactos de compresion en una foto B&N real."""
    img = Image.new("RGB", size, color=base)
    pixels = img.load()
    w, h = size
    total = w * h
    noisy_count = int(total * noisy_fraction)
    i = 0
    for x in range(w):
        for y in range(h):
            if i < noisy_count:
                pixels[x, y] = (base[0] + 20, base[1], base[2] - 10)
            i += 1
    path = tmp_dir / name
    img.save(path)
    return path


def _make_grayscale_with_color_patch(tmp_dir: Path, name: str, patch_rgb, size=(216, 270),
                                      patch_fraction: float = 0.08) -> Path:
    """Gradiente B&N real (ver _make_gradient_grayscale) con un parche rectangular de un
    color especifico cubriendo `patch_fraction` del area — simula el texto de acento (o
    una mancha de color real) superpuesto sobre una foto en blanco y negro."""
    img = Image.new("RGB", size)
    pixels = img.load()
    w, h = size
    for x in range(w):
        for y in range(h):
            v = int(255 * (x / w))
            pixels[x, y] = (v, v, v)
    patch_h = int(h * patch_fraction)
    for x in range(w):
        for y in range(h - patch_h, h):
            pixels[x, y] = patch_rgb
    path = tmp_dir / name
    img.save(path)
    return path


def test_1_check_monochrome_approves_real_grayscale():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        path = _make_gradient_grayscale(tmp, "bw.png")
        result = check_monochrome(path)
        report("TEST 1", "check_monochrome aprueba escala de grises real con gradiente",
               result.approved, result.reason)


def test_2_check_monochrome_rejects_color():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        path = _make_image(tmp, "color.png", fill=(200, 40, 40))  # rojo saturado
        result = check_monochrome(path)
        report("TEST 2", "check_monochrome rechaza una foto claramente a color",
               not result.approved, result.reason)


def test_3_check_monochrome_tolerates_compression_noise():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        path = _make_color_with_noise(tmp, "bw_noise.png", noisy_fraction=0.005)
        result = check_monochrome(path)
        report("TEST 3", "check_monochrome tolera un 0.5% de ruido de color (bajo el 2%)",
               result.approved, result.reason)


def test_4_run_qa_rejects_color_photo():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # 216x270 respeta 4:5 exacto
        path = _make_image(tmp, "color_4x5.png", size=(216, 270), fill=(20, 120, 200))
        result = run_qa(path, expected_aspect_ratio="4:5")
        ok = not result.approved and "blanco y negro" in result.reason.lower()
        report("TEST 4", "run_qa rechaza una foto a color con aspect ratio valido "
               "(check_color=True por defecto)", ok, result.reason)


def test_5_run_qa_skips_color_check_for_mockup():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        path = _make_image(tmp, "mockup_4x5.png", size=(216, 270), fill=(20, 120, 200))
        result = run_qa(path, expected_aspect_ratio="4:5", check_color=False)
        report("TEST 5", "run_qa con check_color=False aprueba un mockup a color",
               result.approved, result.reason)


def test_6_run_qa_still_rejects_bad_aspect_ratio_on_bw_image():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        path = _make_gradient_grayscale(tmp, "bw_wrong_ratio.png", size=(300, 300))  # 1:1, no 4:5
        result = run_qa(path, expected_aspect_ratio="4:5")
        ok = not result.approved and "aspecto" in result.reason.lower()
        report("TEST 6", "run_qa sigue validando aspect ratio aunque la imagen sea B&N",
               ok, result.reason)


def test_7_check_monochrome_excludes_authorized_accent_text():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # F5C518 (dorado) es un accent_color real usado en produccion (ver
        # outputs/bundles/2026-09-26-fabrica-autonoma-real/brief.json)
        gold = (0xF5, 0xC5, 0x18)
        path = _make_grayscale_with_color_patch(tmp, "bw_with_accent.png", gold, patch_fraction=0.08)
        result = check_monochrome(path, accent_color="#F5C518")
        report("TEST 7", "check_monochrome NO rechaza un 8% de acento de texto autorizado "
               "(#F5C518) sobre una foto B&N real", result.approved, result.reason)


def test_8_check_monochrome_still_rejects_unauthorized_color():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Un azul saturado NO es el accent_color declarado — debe seguir rechazandose:
        # la exclusion es especifica del tono autorizado, no un pase libre para cualquier color.
        blue = (20, 60, 220)
        path = _make_grayscale_with_color_patch(tmp, "bw_with_wrong_color.png", blue, patch_fraction=0.08)
        result = check_monochrome(path, accent_color="#F5C518")
        report("TEST 8", "check_monochrome SI rechaza un color que no coincide con el "
               "accent_color autorizado", not result.approved, result.reason)


def main():
    print("=" * 65)
    print("test_qa_monochrome.py — Regla estructural permanente de blanco y negro")
    print("=" * 65)

    test_1_check_monochrome_approves_real_grayscale()
    test_2_check_monochrome_rejects_color()
    test_3_check_monochrome_tolerates_compression_noise()
    test_4_run_qa_rejects_color_photo()
    test_5_run_qa_skips_color_check_for_mockup()
    test_6_run_qa_still_rejects_bad_aspect_ratio_on_bw_image()
    test_7_check_monochrome_excludes_authorized_accent_text()
    test_8_check_monochrome_still_rejects_unauthorized_color()

    passed = sum(1 for r in results_log if r["status"] == PASS_S)
    failed = sum(1 for r in results_log if r["status"] == FAIL_S)
    print("=" * 65)
    print(f"RESULTADO: {passed}/{passed + failed} PASS" + (f" — {failed} FAIL" if failed else ""))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
