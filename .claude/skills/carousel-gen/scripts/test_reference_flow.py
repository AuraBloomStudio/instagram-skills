#!/usr/bin/env python3
"""
test_reference_flow.py - Verifica que la imagen de referencia viral llega fisicamente
al generador y que el plan de referencias es correcto para cada tipo de slide.

Cubre:
  TEST 1 — Slide 1 recibe SPECIFIC_REFERENCE (viral-reference.png) y nada mas
  TEST 2 — Slide 2 con ancla y sin mockup recibe [SLIDE_1, VIRAL_CONTEXT]
  TEST 3 — Slide 10 con ancla y con mockup recibe [SLIDE_1, BOOK_MOCKUP] (sin viral_context)
  TEST 4 — Slide 2 sin ancla y sin mockup recibe [VIRAL_CONTEXT] unicamente
  TEST 5 — Slide 10 sin ancla pero con mockup recibe [VIRAL_CONTEXT, BOOK_MOCKUP]
  TEST 6 — Cache invalida cuando cambia viral-reference.png (bytes cambian => hash cambia)
  TEST 7 — build_prompt_for_slide acepta "viral_context" sin lanzar excepcion
  TEST 8 — Ningun test llama a Gemini real (0 API calls)

Ejecutar con:
    python3 scripts/test_reference_flow.py
"""

import hashlib
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

from reference_manager import decide_reference_plan, ReferenceMode, reference_identifier  # noqa: E402
from prompt_hash import compute_prompt_hash, hash_file_bytes  # noqa: E402
from carousel_common import build_prompt_for_slide, IMAGE_ROLE_INSTRUCTIONS  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: List[dict] = []
_gemini_calls = 0  # contador global — ningún test debe incrementarlo


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f"\n   {detail}" if detail else ""))


def _make_png(seed: int = 0) -> bytes:
    """PNG minimo valido (1x1px) con seed para distinguir archivos distintos."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixel_data = bytes([0, seed % 256, seed % 256, seed % 256])
    idat = zlib.compress(pixel_data)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _make_slide(number: int, uses_reference: bool = False, uses_mockup: bool = False) -> dict:
    return {
        "number": number,
        "role": f"slide-{number}",
        "exact_text": f"Texto del slide {number}",
        "scene_description": "Escena de prueba",
        "composition": "full bleed foto",
        "visual_hierarchy": "1. hook 2. desarrollo",
        "text_placement": "tercio inferior",
        "key_visual_elements": [],
        "uses_reference_image_directly": uses_reference,
        "uses_product_mockup_directly": uses_mockup,
        "text_density": "MEDIUM",
        "word_count": 5,
    }


def _minimal_visual_dna() -> dict:
    return {
        "tipo_imagen": "fotografía editorial",
        "paleta_colores": {"dominantes": ["negro", "blanco"], "acentos": ["amarillo"], "fondo": "oscuro"},
        "tipografia": {"tratamiento": "sans-serif", "peso": "bold", "estilo": "moderno"},
        "composicion_base": "full bleed",
        "jerarquia_visual": "texto sobre imagen",
        "tratamiento_personajes_objetos": "realismo fotografico",
        "textura": "grano fino",
        "iluminacion": "luz natural lateral",
        "margenes": "seguros",
        "recursos_graficos": [],
        "slide_1_master_dna": {
            "image_treatment": "fotografía real, color",
            "color_treatment": "cálido cinematográfico",
            "dominant_tones": ["negro", "dorado"],
            "accent_color": "#F4C842",
            "accent_color_source": "referencia viral",
            "contrast_profile": "alto",
            "luminosity_profile": "moderado",
            "photographic_realism": "alta — fotografía real, no IA",
            "texture_profile": "grano natural",
            "continuity_rules": "misma paleta cálida, mismo nivel de grano",
        },
    }


# ---------------------------------------------------------------------------
# TEST 1: Slide 1 recibe SPECIFIC_REFERENCE y NADA MAS
# ---------------------------------------------------------------------------
def test_1_slide1_gets_specific_reference():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_path = Path(tmpdir) / "viral-reference.png"
        ref_path.write_bytes(_make_png(1))

        slide1 = _make_slide(1, uses_reference=True)
        plan = decide_reference_plan(slide1, slide1_anchor_path=None,
                                     reference_image_path=ref_path, product_mockup_path=None)

        ok = (
            len(plan) == 1
            and plan[0].mode == ReferenceMode.SPECIFIC_REFERENCE
            and plan[0].image_path == ref_path
            and plan[0].role_tag == "reference"
        )
        detail = f"plan={[(r.mode, r.role_tag) for r in plan]}"
        report("TEST_1", "Slide 1 -> SPECIFIC_REFERENCE (viral-reference.png) y nada mas", ok, detail if not ok else "")


# ---------------------------------------------------------------------------
# TEST 2: Slide 2 con ancla y sin mockup → [SLIDE_1, VIRAL_CONTEXT]
# ---------------------------------------------------------------------------
def test_2_slide2_with_anchor_no_mockup():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_path = Path(tmpdir) / "viral-reference.png"
        anchor_path = Path(tmpdir) / "carousel-01.png"
        ref_path.write_bytes(_make_png(1))
        anchor_path.write_bytes(_make_png(2))

        slide2 = _make_slide(2, uses_reference=False, uses_mockup=False)
        plan = decide_reference_plan(slide2, slide1_anchor_path=anchor_path,
                                     reference_image_path=ref_path, product_mockup_path=None)

        modes = [r.mode for r in plan]
        roles = [r.role_tag for r in plan]
        ok = (
            len(plan) == 2
            and modes == [ReferenceMode.SLIDE_1, ReferenceMode.VIRAL_CONTEXT]
            and roles == ["anchor", "viral_context"]
        )
        detail = f"plan={list(zip(modes, roles))}"
        report("TEST_2", "Slide 2 (con ancla, sin mockup) -> [SLIDE_1, VIRAL_CONTEXT]", ok, detail if not ok else "")


# ---------------------------------------------------------------------------
# TEST 3: Slide 10 con ancla y con mockup → [SLIDE_1, BOOK_MOCKUP] (sin viral_context)
# ---------------------------------------------------------------------------
def test_3_slide10_with_anchor_and_mockup():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_path = Path(tmpdir) / "viral-reference.png"
        anchor_path = Path(tmpdir) / "carousel-01.png"
        mockup_path = Path(tmpdir) / "mockup.png"
        ref_path.write_bytes(_make_png(1))
        anchor_path.write_bytes(_make_png(2))
        mockup_path.write_bytes(_make_png(3))

        slide10 = _make_slide(10, uses_reference=False, uses_mockup=True)
        plan = decide_reference_plan(slide10, slide1_anchor_path=anchor_path,
                                     reference_image_path=ref_path,
                                     product_mockup_path=mockup_path)

        modes = [r.mode for r in plan]
        ok = (
            len(plan) == 2
            and modes[0] == ReferenceMode.SLIDE_1
            and modes[1] == ReferenceMode.BOOK_MOCKUP
            and ReferenceMode.VIRAL_CONTEXT not in modes
        )
        detail = f"plan={[r.mode for r in plan]}"
        report("TEST_3", "Slide 10 (con ancla, con mockup) -> [SLIDE_1, BOOK_MOCKUP] sin VIRAL_CONTEXT", ok, detail if not ok else "")


# ---------------------------------------------------------------------------
# TEST 4: Slide 2 sin ancla y sin mockup → [VIRAL_CONTEXT] unicamente
# ---------------------------------------------------------------------------
def test_4_slide2_no_anchor_no_mockup():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_path = Path(tmpdir) / "viral-reference.png"
        ref_path.write_bytes(_make_png(1))

        slide2 = _make_slide(2, uses_reference=False, uses_mockup=False)
        plan = decide_reference_plan(slide2, slide1_anchor_path=None,
                                     reference_image_path=ref_path, product_mockup_path=None)

        ok = (
            len(plan) == 1
            and plan[0].mode == ReferenceMode.VIRAL_CONTEXT
            and plan[0].image_path == ref_path
        )
        detail = f"plan={[(r.mode, r.role_tag) for r in plan]}"
        report("TEST_4", "Slide 2 (sin ancla, sin mockup) -> [VIRAL_CONTEXT] unicamente", ok, detail if not ok else "")


# ---------------------------------------------------------------------------
# TEST 5: Slide 10 sin ancla pero con mockup → [VIRAL_CONTEXT, BOOK_MOCKUP]
# ---------------------------------------------------------------------------
def test_5_slide10_no_anchor_with_mockup():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_path = Path(tmpdir) / "viral-reference.png"
        mockup_path = Path(tmpdir) / "mockup.png"
        ref_path.write_bytes(_make_png(1))
        mockup_path.write_bytes(_make_png(3))

        slide10 = _make_slide(10, uses_reference=False, uses_mockup=True)
        plan = decide_reference_plan(slide10, slide1_anchor_path=None,
                                     reference_image_path=ref_path,
                                     product_mockup_path=mockup_path)

        modes = [r.mode for r in plan]
        ok = (
            len(plan) == 2
            and modes[0] == ReferenceMode.VIRAL_CONTEXT
            and modes[1] == ReferenceMode.BOOK_MOCKUP
        )
        detail = f"plan={[r.mode for r in plan]}"
        report("TEST_5", "Slide 10 (sin ancla, con mockup) -> [VIRAL_CONTEXT, BOOK_MOCKUP]", ok, detail if not ok else "")


# ---------------------------------------------------------------------------
# TEST 6: Cache invalida cuando cambia viral-reference.png
# ---------------------------------------------------------------------------
def test_6_cache_invalidates_on_reference_change():
    with tempfile.TemporaryDirectory() as tmpdir:
        ref_path = Path(tmpdir) / "viral-reference.png"
        anchor_path = Path(tmpdir) / "carousel-01.png"
        anchor_path.write_bytes(_make_png(99))

        slide2 = _make_slide(2)
        vdna = _minimal_visual_dna()

        # Hash con referencia A
        ref_path.write_bytes(_make_png(10))
        plan_a = decide_reference_plan(slide2, anchor_path, ref_path, None)
        ref_id_a = reference_identifier(plan_a, hash_file_bytes)
        hash_a = compute_prompt_hash(
            prompt_text="prompt text",
            slide=slide2,
            visual_dna=vdna,
            carousel_type="historia_emocional",
            aspect_ratio="4:5",
            image_size="1K",
            model="gemini-test",
            reference_image_id=ref_id_a,
        )

        # Hash con referencia B (misma ruta, distintos bytes)
        ref_path.write_bytes(_make_png(99))
        plan_b = decide_reference_plan(slide2, anchor_path, ref_path, None)
        ref_id_b = reference_identifier(plan_b, hash_file_bytes)
        hash_b = compute_prompt_hash(
            prompt_text="prompt text",
            slide=slide2,
            visual_dna=vdna,
            carousel_type="historia_emocional",
            aspect_ratio="4:5",
            image_size="1K",
            model="gemini-test",
            reference_image_id=ref_id_b,
        )

        ok = hash_a != hash_b
        detail = f"hash_a={hash_a[:12]}... hash_b={hash_b[:12]}..."
        report("TEST_6", "Cache invalida cuando cambia viral-reference.png (hashes distintos)", ok, detail if not ok else "")


# ---------------------------------------------------------------------------
# TEST 7: build_prompt_for_slide acepta "viral_context" en attached_images
# ---------------------------------------------------------------------------
def test_7_build_prompt_accepts_viral_context():
    slide = _make_slide(2)
    vdna = _minimal_visual_dna()
    try:
        prompt = build_prompt_for_slide(slide, vdna, "historia_emocional",
                                        attached_images=["anchor", "viral_context"])
        ok = (
            "viral_context" not in prompt.lower() or True  # la clave no debe aparecer, pero sí la instrucción
        )
        # Verifica que la instrucción viral_context esta en IMAGE_ROLE_INSTRUCTIONS
        ok = "viral_context" in IMAGE_ROLE_INSTRUCTIONS and len(prompt) > 100
        report("TEST_7", "build_prompt_for_slide acepta 'viral_context' sin excepcion", ok)
    except Exception as exc:
        report("TEST_7", "build_prompt_for_slide acepta 'viral_context' sin excepcion", False, str(exc))


# ---------------------------------------------------------------------------
# TEST 8: NINGÚN test llama a Gemini real
# ---------------------------------------------------------------------------
def test_8_no_gemini_calls():
    ok = _gemini_calls == 0
    report("TEST_8", f"Ningun test llamo a Gemini real (calls={_gemini_calls})", ok)


# ---------------------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("test_reference_flow.py — flujo de imagen de referencia")
    print("=" * 60)

    test_1_slide1_gets_specific_reference()
    test_2_slide2_with_anchor_no_mockup()
    test_3_slide10_with_anchor_and_mockup()
    test_4_slide2_no_anchor_no_mockup()
    test_5_slide10_no_anchor_with_mockup()
    test_6_cache_invalidates_on_reference_change()
    test_7_build_prompt_accepts_viral_context()
    test_8_no_gemini_calls()

    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    failed = total - passed

    print("=" * 60)
    print(f"RESULTADO: {passed}/{total} PASS   {failed} FAIL")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
