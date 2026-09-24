#!/usr/bin/env python3
"""
test_qa_classification.py - 21 tests automatizados para la politica QA + BUGs 1-5.

REGLA: sin llamadas Gemini, sin generacion de imagenes, sin creditos.
Todos los tests operan sobre strings, mocks, o PIL local.

Tests 1-8: cache bypass + politica QA basica
Tests A-F: TEXT_CORRUPTION -> UNCERTAIN, MISSING/DUPLICATED/EXTRA -> CRITICAL
Tests G-M: BUGs 1-3 — OCR noise mixto, mockup, source_text fidelity, retry policy

Ejecutar con:
    python3 scripts/test_qa_classification.py
"""

import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from text_qa import (
    compare_text, run_text_qa, verify_source_text_fragments,
    REASON_DUPLICATED_TOKEN, REASON_MISSING_TOKEN,
    REASON_EXTRA_TOKEN, REASON_UNAUTHORIZED_TEXT_ELEMENT, REASON_TEXT_CORRUPTION,
    REASON_OCR_LIKELY_MISREAD,
    _OCR_UNCERTAIN_CONFIDENCE_THRESHOLD,
)
from cache_manager import CacheManager, SlideCacheRecord

PASS_S, FAIL_S = "PASS", "FAIL"
results_log: List[Dict[str, str]] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS_S if ok else FAIL_S
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))


# ===========================================================================
# TEST 1: --regenerate-slides bypasses cache (force_regenerate=True)
# ===========================================================================

def test_1_force_regenerate_bypasses_cache():
    """CacheManager.should_reuse() con force_regenerate=True debe retornar False
    incluso cuando hay un hit valido (TEXT_QA_APPROVED, hash coincide, imagen existe)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        carousel_dir = Path(tmpdir)
        # Crear imagen falsa para que la validacion de archivo pase
        fake_img = carousel_dir / "carousel-02.png"
        fake_img.write_bytes(b"\x89PNG\r\n")  # header minimo
        cache = CacheManager(carousel_dir)
        rec = SlideCacheRecord(
            slide_number=2,
            prompt_hash="abc123",
            model="gemini-3.1-flash-lite-image",
            resolution="1K",
            aspect_ratio="4:5",
            image_path="carousel-02.png",
            status="TEXT_QA_APPROVED",
        )
        cache.upsert(rec)

        # Sin force_regenerate: deberia reusar (hit normal)
        reuse_normal = cache.should_reuse(2, "abc123", "gemini-3.1-flash-lite-image", "1K", "4:5", force_regenerate=False)
        # Con force_regenerate: NUNCA reusar, aunque el hit sea perfecto
        reuse_forced = cache.should_reuse(2, "abc123", "gemini-3.1-flash-lite-image", "1K", "4:5", force_regenerate=True)

        ok = reuse_normal and not reuse_forced
        report(
            "TEST 1",
            "--regenerate-slides (force_regenerate=True) ignora cache aunque haya hit valido",
            ok,
            f"normal={reuse_normal}, forced={reuse_forced}",
        )


# ===========================================================================
# TEST 2: Confidence baja + pequeñas sustituciones -> UNCERTAIN (no retry)
# ===========================================================================

def test_2_low_confidence_uncertain_no_retry():
    """Cuando OCR confidence < _OCR_UNCERTAIN_CONFIDENCE_THRESHOLD y hay sustituciones
    menores (TEXT_CORRUPTION), el resultado CRITICO debe degradarse a UNCERTAIN.
    UNCERTAIN nunca dispara retry."""
    expected = "pasamos anos sanando heridas que no fueron nuestras"
    # Simular lectura OCR con sustituciones tipicas de tipografia cursiva
    rendered = "pasainos afios sanando heridas que no fuerdn nuestras"

    fake_image = Path(tempfile.mktemp(suffix=".png"))
    try:
        # Crear archivo PNG minimo para que extract_ocr_confidence no crashee
        fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        # Mock de extract_ocr_confidence para devolver confidence 63 (< 75)
        with patch("text_qa.extract_ocr_confidence", return_value=63.0):
            with patch("text_qa.extract_text_from_image", return_value=rendered):
                result = run_text_qa(fake_image, expected)

        ok = result.approved and result.severity == "UNCERTAIN"
        report(
            "TEST 2",
            "Confidence 63 + sustituciones menores -> UNCERTAIN, aprobado sin retry",
            ok,
            f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
        )
    finally:
        if fake_image.exists():
            fake_image.unlink()


# ===========================================================================
# TEST 3: Texto duplicado -> CRITICAL_FAILURE (dispara 1 retry, no mas)
# ===========================================================================

def test_3_duplicated_text_critical():
    """Texto duplicado evidente => compare_text retorna CRITICAL (severity='CRITICAL').
    En el pipeline esto dispara exactamente 1 retry; si falla de nuevo => FAILED_FINAL.
    El duplicado debe aparecer DESPUES de un bloque de matching para que
    preceding_expected == inserted (ej. 'te te' tras 'el dolor que no')."""
    expected = "el dolor que no te pertenece"
    rendered = "el dolor que no te te pertenece"

    result = compare_text(expected, rendered)
    ok = (not result.approved and result.severity == "CRITICAL"
          and result.reason == REASON_DUPLICATED_TOKEN)
    report(
        "TEST 3",
        "Texto duplicado -> CRITICAL_FAILURE (approved=False, severity=CRITICAL, reason=DUPLICATED_TOKEN)",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


# ===========================================================================
# TEST 4: Frase faltante -> CRITICAL_FAILURE
# ===========================================================================

def test_4_missing_phrase_critical():
    """Cuando una frase completa esta ausente en el render, es MISSING_TOKEN / CRITICAL.
    Esto dispara exactamente 1 retry; FAILED_FINAL si persiste."""
    expected = "pero no tienes que seguir persiguiendo el amor que siempre tuviste que pedir"
    rendered = "pero no tienes que seguir"

    result = compare_text(expected, rendered)
    ok = (not result.approved and result.severity == "CRITICAL"
          and result.reason == REASON_MISSING_TOKEN)
    report(
        "TEST 4",
        "Frase faltante -> CRITICAL_FAILURE (approved=False, severity=CRITICAL, reason=MISSING_TOKEN)",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


# ===========================================================================
# TEST 5: Texto correcto pero OCR dificil (confidence bajo) -> UNCERTAIN
# ===========================================================================

def test_5_stylized_ocr_uncertain():
    """Con tipografia cursiva serif, Tesseract puede producir TEXT_CORRUPTION aunque
    el render este correcto. Cuando confidence < threshold, el CRITICAL se degrada
    a UNCERTAIN y se aprueba sin retry."""
    expected = "pasamos anos sanando heridas que no fueron nuestras"
    # OCR produce corrupciones tipicas de serif cursivo dorado
    rendered = "pasainos anos sanado heridas que no fuemn nuestras"

    fake_image = Path(tempfile.mktemp(suffix=".png"))
    try:
        fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        # confidence = 60, bien por debajo del umbral 75
        with patch("text_qa.extract_ocr_confidence", return_value=60.0):
            with patch("text_qa.extract_text_from_image", return_value=rendered):
                result = run_text_qa(fake_image, expected)

        ok = result.approved and result.severity == "UNCERTAIN"
        report(
            "TEST 5",
            "Texto correcto con OCR dificil (confidence 60) -> UNCERTAIN, sin retry infinito",
            ok,
            f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
        )
    finally:
        if fake_image.exists():
            fake_image.unlink()


# ===========================================================================
# TEST 6: Token numerico extra -> UNAUTHORIZED_TEXT_ELEMENT
# ===========================================================================

def test_6_unauthorized_numeric_element():
    """Un numero en circulo ('10') que aparece en la imagen pero no en el texto esperado
    debe clasificarse como UNAUTHORIZED_TEXT_ELEMENT (CRITICAL), no como EXTRA_TOKEN."""
    expected = "herida paterna el dolor que cargo sin saber de donde vino"
    rendered = "10 herida paterna el dolor que cargo sin saber de donde vino"

    result = compare_text(expected, rendered)
    ok = (not result.approved and result.reason == REASON_UNAUTHORIZED_TEXT_ELEMENT)
    report(
        "TEST 6",
        "Token numerico extra '10' -> UNAUTHORIZED_TEXT_ELEMENT (CRITICAL)",
        ok,
        f"approved={result.approved}, reason={result.reason}, severity={result.severity}",
    )


# ===========================================================================
# TEST 7: CRITICAL_FAILURE despues del retry -> FAILED_FINAL, pipeline continua
# ===========================================================================

def test_7_critical_after_retry_failed_final():
    """Simula el flujo de retry en el pipeline:
    - 1er intento: compare_text retorna CRITICAL
    - retry: compare_text SIGUE retornando CRITICAL
    - resultado final: FAILED_FINAL en cache; el pipeline NO vuelve a intentarlo
    Este test verifica la politica de retry sin llamar a Gemini — simula el estado
    de cache directamente despues de agotar el maximo de 1 retry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        carousel_dir = Path(tmpdir)
        cache = CacheManager(carousel_dir)
        fake_img = carousel_dir / "carousel-01.png"
        fake_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

        # Simular estado despues de 1 retry agotado: FAILED_FINAL
        rec = SlideCacheRecord(
            slide_number=1,
            prompt_hash="hash_slide1",
            model="gemini-3.1-flash-lite-image",
            resolution="1K",
            aspect_ratio="4:5",
            image_path="carousel-01.png",
            status="FAILED_FINAL",
            retry_count=1,
            last_error="TEXT_QA:MISSING_TOKEN — MISSING_TOKEN: ['pero', 'no', 'tienes']",
            text_qa_retry_count=1,
            text_qa_rejection_reason="MISSING_TOKEN",
        )
        cache.upsert(rec)

        # Verificar que FAILED_FINAL nunca se reutiliza (no bloquea regeneracion automatica)
        reuse_failed_final = cache.should_reuse(1, "hash_slide1", "gemini-3.1-flash-lite-image", "1K", "4:5")
        # Verificar que el estado se guardo correctamente
        loaded = cache.get(1)

        ok = (not reuse_failed_final and loaded is not None
              and loaded.status == "FAILED_FINAL" and loaded.retry_count == 1)
        report(
            "TEST 7",
            "CRITICAL_FAILURE tras retry -> FAILED_FINAL en cache, no se reutiliza, pipeline continua",
            ok,
            f"reuse={reuse_failed_final}, status={loaded.status if loaded else 'None'}, retries={loaded.retry_count if loaded else '?'}",
        )


# ===========================================================================
# TEST 8: UNCERTAIN -> pipeline no bloquea, slide sigue adelante
# ===========================================================================

def test_8_uncertain_does_not_block():
    """Cuando compare_text retorna UNCERTAIN (severity='UNCERTAIN', approved=True),
    el pipeline debe aprobar el slide sin disparar retry. Se verifica que:
    - approved=True (no bloquea)
    - severity='UNCERTAIN' (visible en cache, no silencioso)
    - reason=OCR_LIKELY_MISREAD o TEXT_CORRUPTION

    Caso 1: reemplazo individual (1 token -> 1 token) con alta similitud de caracteres
    => _looks_like_ocr_misread retorna True => OCR_LIKELY_MISREAD => UNCERTAIN.
    Nota: cuando TODOS los tokens son diferentes, SequenceMatcher produce un unico
    replace block de N tokens; la distancia editada sobre el string concatenado puede
    exceder el umbral aunque word-by-word seria OK. Por eso el caso 1 usa tokens
    "anclados" con palabras iguales intermedias que obligan splits individuales.

    Caso 2: confidence baja -> UNCERTAIN aunque haya CRITICAL inicial."""
    # Caso 1: tokens iguales como anclas permiten splits individuales de misreads
    # "biologicos" -> "biolegicos" (edit dist 1), "ovulo" -> "6vulo" (edit dist 1)
    # Las palabras ancla "la", "son" y "para" aseguran que SequenceMatcher hace
    # replace ops individuales, no un bloque unico de 2 tokens.
    expected = "la biologicos son ovulo para"
    rendered = "la biolegicos son 6vulo para"
    result = compare_text(expected, rendered)

    ok_uncertain = result.approved and result.severity == "UNCERTAIN"

    # Caso 2: confidence baja -> downgrade CRITICAL -> UNCERTAIN
    expected2 = "el amor que siempre tuviste que pedir"
    rendered2 = "el amx que siempr tuviste que pxdir"
    fake_image = Path(tempfile.mktemp(suffix=".png"))
    try:
        fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        with patch("text_qa.extract_ocr_confidence", return_value=62.0):
            with patch("text_qa.extract_text_from_image", return_value=rendered2):
                result2 = run_text_qa(fake_image, expected2)
        ok_confidence_downgrade = result2.approved and result2.severity == "UNCERTAIN"
    finally:
        if fake_image.exists():
            fake_image.unlink()

    ok = ok_uncertain and ok_confidence_downgrade
    report(
        "TEST 8",
        "UNCERTAIN (OCR misread / confidence baja) -> approved=True, severity=UNCERTAIN, sin bloqueo",
        ok,
        f"caso1=[approved={result.approved},sev={result.severity},reason={result.reason}] "
        f"caso2=[approved={result2.approved},sev={result2.severity}]",
    )


# ===========================================================================
# TEST A-F: Regla estructural TEXT_CORRUPTION -> UNCERTAIN
# ===========================================================================

def test_a_text_corruption_solo_es_uncertain():
    """TEXT_CORRUPTION con 5-7 diferencias y sin MISSING/DUPLICATE/EXTRA_TOKEN
    -> UNCERTAIN -> 0 retries. Replica el patron real de slides 2, 8, 10."""
    # Simula lectura OCR real de tipografia cursiva dorada sobre fotografia B&W:
    # sustituciones y deformaciones sin tokens faltantes ni sobrantes.
    expected = "a veces pasamos anos buscando personas que nos salven"
    rendered  = "a veces pasainos afios buscand personaz que no saalven"
    result = compare_text(expected, rendered)

    ok = result.approved and result.severity == "UNCERTAIN" and result.reason == REASON_TEXT_CORRUPTION
    report(
        "TEST A",
        "TEXT_CORRUPTION + 5-7 diferencias sin MISSING/DUPLICATE/EXTRA -> UNCERTAIN -> 0 retries",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


def test_b_text_corruption_low_confidence_uncertain():
    """TEXT_CORRUPTION + OCR confidence 68 -> UNCERTAIN -> 0 retries.
    Con la nueva regla, TEXT_CORRUPTION ya es UNCERTAIN antes de que intervenga la
    confianza -- pero el resultado sigue siendo UNCERTAIN en cualquier caso."""
    expected = "cuanto vales tu no lo determina la ausencia de papa"
    rendered  = "cudnto valest u no lo det ermina la ausen cia de papa"

    fake_image = Path(tempfile.mktemp(suffix=".png"))
    try:
        fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        with patch("text_qa.extract_ocr_confidence", return_value=68.0):
            with patch("text_qa.extract_text_from_image", return_value=rendered):
                result = run_text_qa(fake_image, expected)
        ok = result.approved and result.severity == "UNCERTAIN"
        report(
            "TEST B",
            "TEXT_CORRUPTION + confidence 68 -> UNCERTAIN -> 0 retries",
            ok,
            f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
        )
    finally:
        if fake_image.exists():
            fake_image.unlink()


def test_c_missing_token_critical():
    """MISSING_TOKEN es evidencia estructural -> CRITICAL_FAILURE -> max 1 retry."""
    expected = "pero no tienes que seguir persiguiendo el amor que siempre tuviste que pedir"
    rendered = "pero no tienes que seguir"

    result = compare_text(expected, rendered)
    ok = not result.approved and result.severity == "CRITICAL" and result.reason == REASON_MISSING_TOKEN
    report(
        "TEST C",
        "MISSING_TOKEN -> CRITICAL_FAILURE -> max 1 retry",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


def test_d_duplicated_token_critical():
    """DUPLICATED_TOKEN es evidencia estructural -> CRITICAL_FAILURE -> max 1 retry."""
    expected = "el dolor que no te pertenece"
    rendered = "el dolor que no te te pertenece"

    result = compare_text(expected, rendered)
    ok = not result.approved and result.severity == "CRITICAL" and result.reason == REASON_DUPLICATED_TOKEN
    report(
        "TEST D",
        "DUPLICATED_TOKEN -> CRITICAL_FAILURE -> max 1 retry",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


def test_e_unauthorized_element_critical():
    """UNAUTHORIZED_TEXT_ELEMENT (token numerico extra) -> CRITICAL_FAILURE -> max 1 retry."""
    expected = "herida paterna el dolor que cargo sin saber de donde vino"
    rendered = "10 herida paterna el dolor que cargo sin saber de donde vino"

    result = compare_text(expected, rendered)
    ok = not result.approved and result.severity == "CRITICAL" and result.reason == REASON_UNAUTHORIZED_TEXT_ELEMENT
    report(
        "TEST E",
        "UNAUTHORIZED_TEXT_ELEMENT (token numerico '10' extra) -> CRITICAL_FAILURE -> max 1 retry",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


def test_f_identical_text_approved():
    """Texto identico (tras normalizacion) -> APPROVED con severity PASS."""
    expected = "Cuanto vales tu no lo determina la ausencia de papa"
    result = compare_text(expected, expected)
    ok = result.approved and result.severity == "PASS" and result.reason is None
    report(
        "TEST F",
        "Texto identico -> APPROVED (severity=PASS)",
        ok,
        f"approved={result.approved}, severity={result.severity}",
    )


# ===========================================================================
# TESTS G-M: BUG 1 (OCR noise mixto), BUG 2 (mockup), BUG 3 (source_text)
# ===========================================================================

def test_g_mixed_ocr_noise_not_critical():
    """BUG 1: ['jia', '4', 's'] son artefactos mixtos de OCR sobre tipografia bold.
    Deben clasificarse como OCR_LIKELY_MISREAD (UNCERTAIN), NO como CRITICAL.
    Caso real: slide 3 del carrusel 2026-09-19-no-te-eligieron."""
    expected = "jamás escuchaste esas palabras"
    # OCR lee artefactos de kerning + dígito suelto además del texto
    rendered  = "jamás escuchaste esas palabras jia 4 s"

    result = compare_text(expected, rendered)
    ok = result.approved and result.severity == "UNCERTAIN"
    report(
        "TEST G",
        "OCR noise mixto ['jia', '4', 's'] -> UNCERTAIN, NO CRITICAL",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


def test_h_product_mockup_extra_text_not_critical():
    """BUG 2: uses_product_mockup=True + OCR lee titulo del libro como tokens extra.
    Deben clasificarse UNCERTAIN (no CRITICAL). Caso real: slide 10 con mockup del libro."""
    expected = "el dolor que no te pertenece"
    # OCR lee el titulo del libro + autora desde el mockup como tokens extra
    rendered  = "el dolor que no te pertenece EL DOLOR QUE NO TE PERTENECE ana barroso"

    fake_image = Path(tempfile.mktemp(suffix=".png"))
    try:
        fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        with patch("text_qa.extract_text_from_image", return_value=rendered):
            with patch("text_qa.extract_ocr_confidence", return_value=80.0):
                result = run_text_qa(fake_image, expected, uses_product_mockup=True)
        ok = result.approved and result.severity == "UNCERTAIN"
        report(
            "TEST H",
            "uses_product_mockup=True + texto del cover como tokens extra -> UNCERTAIN",
            ok,
            f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
        )
    finally:
        if fake_image.exists():
            fake_image.unlink()


def test_i_real_extra_word_still_critical():
    """BUG 2 (verificacion de no-regresion): uses_product_mockup=True NO excusa
    tokens faltantes. MISSING_TOKEN sigue siendo CRITICAL incluso en slides con mockup."""
    expected = "el dolor que heredamos sin saberlo"
    rendered  = "el dolor que heredamos"  # faltan tokens

    fake_image = Path(tempfile.mktemp(suffix=".png"))
    try:
        fake_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        with patch("text_qa.extract_text_from_image", return_value=rendered):
            with patch("text_qa.extract_ocr_confidence", return_value=85.0):
                result = run_text_qa(fake_image, expected, uses_product_mockup=True)
        ok = not result.approved and result.severity == "CRITICAL"
        report(
            "TEST I",
            "uses_product_mockup=True + MISSING_TOKEN -> sigue siendo CRITICAL",
            ok,
            f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
        )
    finally:
        if fake_image.exists():
            fake_image.unlink()


def test_j_source_text_fragment_matches_source():
    """BUG 3: source_text_fragment que SÍ existe en source_text -> 0 advertencias."""
    source_text = "esa herida, esa parte de ti que nunca fue elegida"
    slides = [
        {"number": 1, "source_text_fragment": "esa parte de ti que nunca fue elegida"},
    ]
    warnings = verify_source_text_fragments(source_text, slides)
    ok = len(warnings) == 0
    report(
        "TEST J",
        "source_text_fragment rastreable en source_text -> 0 advertencias",
        ok,
        f"warnings={warnings}",
    )


def test_k_source_text_fragment_typo_generates_warning():
    """BUG 3: source_text_fragment con typo ('asa' en vez de 'esa') no se localiza
    en source_text -> se genera advertencia. Caso real del carrusel 2026-09-19."""
    source_text = "esa herida, esa parte de ti que nunca fue elegida"
    slides = [
        {"number": 10, "source_text_fragment": "asa parte de ti"},  # typo
    ]
    warnings = verify_source_text_fragments(source_text, slides)
    ok = len(warnings) == 1 and "10" in warnings[0]
    report(
        "TEST K",
        "source_text_fragment con typo ('asa' vs 'esa') -> genera advertencia",
        ok,
        f"warnings={warnings}",
    )


def test_l_uncertain_means_zero_retries():
    """Politica: UNCERTAIN -> approved=True -> 0 retries (pipeline no bloquea)."""
    expected = "sanar no es olvidar es elegirte"
    rendered  = "sanar no es olvidar es elegitre"  # OCR transposicion

    result = compare_text(expected, rendered)
    # La transposicion menor produce TEXT_CORRUPTION -> UNCERTAIN
    ok = result.approved and result.severity == "UNCERTAIN"
    report(
        "TEST L",
        "UNCERTAIN -> approved=True -> 0 retries",
        ok,
        f"approved={result.approved}, severity={result.severity}",
    )


def test_m_critical_failure_triggers_max_one_retry():
    """Politica: CRITICAL_FAILURE -> approved=False, severity='CRITICAL' -> max 1 retry."""
    expected = "el amor que siempre tuviste que pedir no fue el que mereciste"
    rendered  = "el amor que siempre tuviste que pedir"  # MISSING_TOKEN evidente

    result = compare_text(expected, rendered)
    ok = not result.approved and result.severity == "CRITICAL"
    report(
        "TEST M",
        "CRITICAL_FAILURE -> approved=False, severity=CRITICAL -> max 1 retry",
        ok,
        f"approved={result.approved}, severity={result.severity}, reason={result.reason}",
    )


# ===========================================================================
# Runner
# ===========================================================================

def main():
    print("=" * 65)
    print("test_qa_classification.py — Politica QA + Cache Bypass")
    print("=" * 65)

    test_1_force_regenerate_bypasses_cache()
    test_2_low_confidence_uncertain_no_retry()
    test_3_duplicated_text_critical()
    test_4_missing_phrase_critical()
    test_5_stylized_ocr_uncertain()
    test_6_unauthorized_numeric_element()
    test_7_critical_after_retry_failed_final()
    test_8_uncertain_does_not_block()

    print()
    print("--- Regla estructural TEXT_CORRUPTION -> UNCERTAIN ---")
    test_a_text_corruption_solo_es_uncertain()
    test_b_text_corruption_low_confidence_uncertain()
    test_c_missing_token_critical()
    test_d_duplicated_token_critical()
    test_e_unauthorized_element_critical()
    test_f_identical_text_approved()

    print()
    print("--- BUG 1-3: OCR noise mixto, mockup, source_text fidelity ---")
    test_g_mixed_ocr_noise_not_critical()
    test_h_product_mockup_extra_text_not_critical()
    test_i_real_extra_word_still_critical()
    test_j_source_text_fragment_matches_source()
    test_k_source_text_fragment_typo_generates_warning()
    test_l_uncertain_means_zero_retries()
    test_m_critical_failure_triggers_max_one_retry()

    passed = sum(1 for r in results_log if r["status"] == PASS_S)
    failed = sum(1 for r in results_log if r["status"] == FAIL_S)
    print("=" * 65)
    print(f"RESULTADO: {passed}/{passed+failed} PASS" + (f" — {failed} FAIL" if failed else ""))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
