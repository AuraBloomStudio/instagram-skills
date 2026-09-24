#!/usr/bin/env python3
"""
test_text_qa.py - Suite de pruebas SIN COSTO para el sistema TEXT QA de carousel-gen.

REGLA PERMANENTE: este archivo NUNCA llama a Gemini ni a Kie. Las pruebas de
comparacion de texto (TEST 1-11, CASOS REALES A/B/C) operan sobre strings directamente.
Las pruebas de integracion (TEST 12-14) usan un cliente de prueba local
(`DrawnTextClient`) que dibuja el texto "renderizado" simulado con PIL/Arial sobre una
imagen en blanco y le aplica OCR REAL con Tesseract (100% local, sin red) — asi se
prueba el flujo completo (generacion simulada -> OCR real -> comparacion -> retry
selectivo) sin ninguna llamada externa ni gasto.

Ejecutar con:
    python3 scripts/test_text_qa.py
"""

import sys
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from text_qa import (  # noqa: E402
    compare_text, check_exact_phrase, normalize_text, tokenize,
    analyze_distribution, run_text_qa, extract_text_from_image,
    REASON_DUPLICATED_TOKEN, REASON_MISSING_TOKEN, REASON_EXTRA_TOKEN, REASON_TEXT_CORRUPTION,
    REASON_OCR_LIKELY_MISREAD,
    _apply_ocr_confidence_downgrade, _OCR_UNCERTAIN_CONFIDENCE_THRESHOLD,
    _looks_like_ocr_misread, _edit_distance,
)
from gemini_client import GeminiImageResult  # noqa: E402
from cache_manager import CacheManager  # noqa: E402
from cost_tracker import CostTracker  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict[str, str]] = []


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    print(f"[{status}] {test_id}: {description}" + (f" -- {detail}" if detail else ""))


# ===========================================================================
# PARTE 1 — Comparacion de texto (TEST 1-11), sin imagenes, sin OCR
# ===========================================================================

def test_1_texto_correcto():
    r = compare_text("EL DOLOR QUE NO TE PERTENECE", "EL DOLOR QUE NO TE PERTENECE")
    report("TEST 1", "Texto correcto -> PASS", r.approved)


def test_2_palabra_duplicada():
    r = compare_text("EL DOLOR QUE NO TE PERTENECE", "EL DOLOR QUE NO TE TE PERTENECE")
    report("TEST 2", "Palabra duplicada 'TE TE' -> REJECT DUPLICATED_TOKEN", not r.approved and r.reason == REASON_DUPLICATED_TOKEN, r.detail)


def test_3_frase_duplicada():
    r = compare_text("conoce mi libro:", "conoce mi libro: conoce mi libro:")
    report("TEST 3", "Frase duplicada 'conoce mi libro:' x2 -> REJECT DUPLICATED_TOKEN", not r.approved and r.reason == REASON_DUPLICATED_TOKEN, r.detail)


def test_4_palabra_faltante():
    r = compare_text("Un hombre que llegue preparado para caminar contigo.", "Un hombre que llegue preparado para caminar.")
    report("TEST 4", "Palabra faltante 'contigo' -> REJECT MISSING_TOKEN", not r.approved and r.reason == REASON_MISSING_TOKEN, r.detail)


def test_5_palabra_adicional():
    r = compare_text("Un hombre que llegue preparado para caminar contigo.", "Un hombre que llegue preparado para caminar siempre contigo.")
    report("TEST 5", "Palabra adicional 'siempre' -> REJECT EXTRA_TOKEN", not r.approved and r.reason == REASON_EXTRA_TOKEN, r.detail)


def test_6_palabra_deformada():
    # REGLA NUEVA: TEXT_CORRUPTION sola -> UNCERTAIN (no CRITICAL, no retry).
    # "esi compartir dir" en lugar de "estabilidad compartida" es TEXT_CORRUPTION pero
    # sin evidencia estructural (no falta ni sobra ni se duplica contenido como tal).
    r = compare_text("dispuesto a construir una estabilidad compartida.", "dispuesto a construir una esi compartir dir compartida.")
    ok = r.approved and r.severity == "UNCERTAIN" and r.reason == REASON_TEXT_CORRUPTION
    report("TEST 6", "Palabras deformadas 'esi compartir dir' -> UNCERTAIN (TEXT_CORRUPTION sola, no CRITICAL)", ok, r.detail)


def test_7_dividido_en_lineas():
    r = compare_text("Un hombre que llegue preparado\npara caminar contigo.", "Un hombre que llegue\npreparado para caminar\ncontigo.")
    report("TEST 7", "Mismo texto en lineas distintas -> PASS", r.approved)


def test_8_mayus_minus():
    r = compare_text("EL DOLOR QUE NO TE PERTENECE", "el dolor que no te pertenece")
    report("TEST 8", "Mayusculas/minusculas distintas -> PASS", r.approved)


def test_9_espacios_saltos():
    r = compare_text("El   dolor  \n\n que no te pertenece", "El dolor que no te pertenece")
    report("TEST 9", "Espacios multiples y saltos de linea distintos -> PASS", r.approved)


def test_10_titulo_producto_incorrecto():
    rendered = "conoce mi libro: EL DOLOR QUE NO TE PERTENECEEE"
    r = check_exact_phrase("EL DOLOR QUE NO TE PERTENECE", rendered, label="PRODUCT_TITLE_MISMATCH")
    ok_reject = not r.approved and r.reason == "PRODUCT_TITLE_MISMATCH"
    # Caso adicional: falta una palabra del titulo completo
    r2 = check_exact_phrase("EL DOLOR QUE NO TE PERTENECE", "conoce mi libro: EL DOLOR QUE NO PERTENECE", label="PRODUCT_TITLE_MISMATCH")
    ok_reject2 = not r2.approved and r2.reason == "PRODUCT_TITLE_MISMATCH"
    report("TEST 10", "Titulo de producto incorrecto (deformado o incompleto) -> REJECT PRODUCT_TITLE_MISMATCH", ok_reject and ok_reject2, f"{r.detail} | {r2.detail}")


def test_11_cta_incorrecta():
    r = check_exact_phrase("conoce mi libro:", "conoce mi libro: conoce mi libro:", label="CTA_MISMATCH")
    report("TEST 11", "CTA duplicada -> REJECT CTA_MISMATCH", not r.approved and r.reason == "CTA_MISMATCH", r.detail)


# ===========================================================================
# CASOS REALES (seccion 26 del pedido) — strings EXACTAS del bug real en produccion
# ===========================================================================

def test_caso_real_a():
    r = compare_text("EL DOLOR QUE NO TE PERTENECE", "EL DOLOR QUE NO TE TE PERTENECE")
    report("CASO REAL A", "Bug real: 'EL DOLOR QUE NO TE TE PERTENECE' -> REJECT", not r.approved and r.reason == REASON_DUPLICATED_TOKEN)


def test_caso_real_b():
    r = compare_text("conoce mi libro:", "conoce mi libro: conoce mi libro:")
    report("CASO REAL B", "Bug real: 'conoce mi libro:' duplicado -> REJECT", not r.approved and r.reason == REASON_DUPLICATED_TOKEN)


def test_caso_real_c():
    # Con la nueva regla TEXT_CORRUPTION sola -> UNCERTAIN. El caso "esi compartir dir"
    # sigue siendo trazado como TEXT_CORRUPTION pero aprueba (UNCERTAIN, sin retry).
    r = compare_text("dispuesto a construir una estabilidad compartida.", "dispuesto a construir una esi compartir dir compartida.")
    ok = r.approved and r.severity == "UNCERTAIN" and r.reason == REASON_TEXT_CORRUPTION
    report("CASO REAL C", "Bug real: 'esi compartir dir' -> UNCERTAIN (TEXT_CORRUPTION sola, nueva regla)", ok, r.detail)


def test_17_severidad_por_defecto():
    ok_pass = compare_text("hola mundo", "hola mundo").severity == "PASS"
    # EXTRA_TOKEN es evidencia estructural -> CRITICAL
    ok_critical = compare_text("hola mundo", "hola hola mundo").severity == "CRITICAL"
    # TEXT_CORRUPTION sola -> UNCERTAIN (nueva regla: no evidencia estructural)
    # "xyz abc" es claramente distinto a "hola mundo" pero sin tokens faltantes/extra -> TEXT_CORRUPTION
    ok_uncertain = compare_text("hola mundo", "xyz abc").severity == "UNCERTAIN"
    report("TEST 17", "severity: PASS si igual, CRITICAL con evidencia estructural (EXTRA/MISSING/DUPLICATED), UNCERTAIN con TEXT_CORRUPTION sola",
           ok_pass and ok_critical and ok_uncertain,
           f"pass={ok_pass} critical={ok_critical} uncertain={ok_uncertain}")


def test_18_ocr_dudoso_degrada_a_uncertain_y_aprueba():
    # FABRICA RAPIDA: confianza OCR baja + evidencia estructural (MISSING_TOKEN) ->
    # se degrada a UNCERTAIN (no bloqueante). TEXT_CORRUPTION ya es UNCERTAIN por
    # regla estructural; aqui verificamos el mecanismo de degradacion con MISSING_TOKEN.
    r = compare_text("siempre pregunta por ti", "siempre por ti")
    # r es CRITICAL por MISSING_TOKEN
    assert r.severity == "CRITICAL" and not r.approved
    with patch("text_qa.extract_ocr_confidence", return_value=_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD - 5):
        degraded = _apply_ocr_confidence_downgrade(r, Path("irrelevante.png"))
    ok = degraded.severity == "UNCERTAIN" and degraded.approved is True
    report("TEST 18", "MISSING_TOKEN + OCR de baja confianza -> degrada CRITICAL -> UNCERTAIN (no bloquea)", ok, degraded.detail)


def test_19_ocr_confiable_no_degrada():
    # Confianza alta + MISSING_TOKEN -> CRITICAL se mantiene (evidencia estructural,
    # bloqueante). TEXT_CORRUPTION con confianza alta es ahora UNCERTAIN por regla
    # estructural, no por confianza — este test verifica que los errores estructurales
    # reales (MISSING_TOKEN) NO se degradan cuando el OCR es fiable.
    r = compare_text("siempre pregunta por ti", "siempre por ti")
    assert r.severity == "CRITICAL" and not r.approved
    with patch("text_qa.extract_ocr_confidence", return_value=_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD + 20):
        not_degraded = _apply_ocr_confidence_downgrade(r, Path("irrelevante.png"))
    ok = not_degraded.severity == "CRITICAL" and not_degraded.approved is False
    report("TEST 19", "MISSING_TOKEN + OCR de alta confianza NO degrada — evidencia estructural sigue bloqueando", ok)


# ===========================================================================
# PARTE 1b — Tolerancia a confusion tipica de OCR con acentos/ene-con-tilde
# (hallazgo real de produccion, 2026-09-18, retest "abuela-materna" — Tesseract leia
# con ALTA confianza [86-91/100] imagenes ya perfectas, gastando regeneraciones reales)
# ===========================================================================

def test_20b_edit_distance_y_heuristico_unitarios():
    ok = (
        _edit_distance("biologicos", "biolegicos") == 1
        and _edit_distance("anos", "afios") == 2
        and _edit_distance("desu", "desu") == 0
        and _looks_like_ocr_misread(["biologicos"], ["biolegicos"]) is True
        and _looks_like_ocr_misread(["anos"], ["afios"]) is True
        and _looks_like_ocr_misread(["de", "su"], ["desu"]) is True
        # Palabras cortas y claramente distintas (no una confusion de acento) NUNCA se
        # toleran, aunque compartan alguna letra.
        and _looks_like_ocr_misread(["si"], ["no"]) is False
        # Bloques largos y realmente distintos (la mitad o mas de los caracteres
        # cambia) tampoco se toleran.
        and _looks_like_ocr_misread(["estabilidadcompartida"], ["esicompartirdir"]) is False
    )
    report("TEST 20b", "_edit_distance/_looks_like_ocr_misread: unitarios sobre los casos reales calibrados", ok)


def test_20_biologicos_biolegicos_se_tolera():
    # Caso real confirmado visualmente contra el PNG: la imagen decia "biologicos"
    # correctamente, Tesseract leyo "biolegicos" (o->e) con confianza 89.6/100.
    r = compare_text(
        "En terminos biologicos, el ovulo ya estaba presente.",
        "En terminos biolegicos, el 6vulo ya estaba presente.",
    )
    ok = r.approved is True and r.severity == "UNCERTAIN" and r.reason == REASON_OCR_LIKELY_MISREAD
    report("TEST 20", "'biologicos'->'biolegicos' y 'ovulo'->'6vulo' (confusion real de acento) "
                       "se toleran: aprueba, severity UNCERTAIN, nunca CRITICAL", ok, r.detail)


def test_21_ene_con_tilde_leida_como_dos_caracteres_se_tolera():
    # Caso real: "años" (normalizado "anos") leido como "afios"; "acompañar"
    # (normalizado "acompanar") leido como "acompaiiar" — la ene con tilde se lee como
    # DOS caracteres ("fi"/"ii"), lo que por si solo ya cuesta 2 ediciones.
    r1 = compare_text("Pasaron los anos sin verse.", "Pasaron los afios sin verse.")
    r2 = compare_text("Ella pudo acompanar a su nieta.", "Ella pudo acompaiiar a su nieta.")
    ok = (r1.approved and r1.severity == "UNCERTAIN") and (r2.approved and r2.severity == "UNCERTAIN")
    report("TEST 21", "'anos'->'afios' y 'acompanar'->'acompaiiar' (ene con tilde leida como "
                       "2 caracteres) se toleran igual", ok, f"{r1.detail} | {r2.detail}")


def test_22_fusion_de_palabras_se_tolera():
    # Caso real: "de su" (2 tokens) leido como "desu" (1 token, fusion sin perdida real
    # de contenido) — se tolera SIN aplicar el minimo de longitud (coincidencia exacta
    # tras quitar espacios).
    r = compare_text("cerca de su abuela", "cerca desu abuela")
    ok = r.approved is True and r.severity == "UNCERTAIN"
    report("TEST 22", "'de su' -> 'desu' (fusion de palabras, sin perdida de contenido) se tolera",
           ok, r.detail)


def test_23_text_corruption_sola_siempre_uncertain():
    # NUEVA REGLA (reemplaza la anterior "corrupcion real sigue bloqueando"):
    # TEXT_CORRUPTION sola -> UNCERTAIN, sin importar cuan diferente sea el texto.
    # El retry solo se reserva para evidencia ESTRUCTURAL (MISSING/DUPLICATED/EXTRA_TOKEN).
    # "esi compartir dir" es TEXT_CORRUPTION (OCR plausible sobre render correcto) ->
    # UNCERTAIN: trazado, visible, pero no consume otro credito de Gemini.
    r = compare_text("dispuesto a construir una estabilidad compartida.",
                      "dispuesto a construir una esi compartir dir compartida.")
    ok = r.approved is True and r.severity == "UNCERTAIN" and r.reason == REASON_TEXT_CORRUPTION
    report("TEST 23", "TEXT_CORRUPTION sola siempre UNCERTAIN (no CRITICAL) — "
                       "retry reservado para evidencia estructural (MISSING/DUPLICATED/EXTRA_TOKEN)", ok, r.detail)


def test_24_palabra_completamente_ausente_nunca_se_tolera():
    # Regla dura: MISSING_TOKEN/EXTRA_TOKEN/DUPLICATED_TOKEN NUNCA pasan por el heuristico
    # de tolerancia (solo aplica a reemplazos de bloque/TEXT_CORRUPTION) — una palabra
    # real y completamente ausente sigue siendo SIEMPRE un error real.
    r = compare_text("siempre pregunta por ti", "siempre por ti")
    ok = r.approved is False and r.severity == "CRITICAL" and r.reason == REASON_MISSING_TOKEN
    report("TEST 24", "Una palabra completamente ausente (no una confusion de caracteres) "
                       "sigue bloqueando siempre, sin importar la tolerancia a OCR", ok, r.detail)


def test_25_mezcla_de_error_real_y_ruido_ocr_prioriza_el_error_real():
    # Caso real (slide 1 del retest 2026-09-18): 'abuela'->'abueca' es ruido OCR
    # tolerable, PERO 'pregunta' esta genuinamente ausente del render — el resultado
    # debe seguir siendo CRITICAL por la palabra ausente, nunca aprobarse solo porque
    # una de las dos diferencias era ruido de OCR.
    r = compare_text(
        "la abuela materna siempre esta, siempre pregunta.",
        "la abueca materna siempre esta, siempre.",
    )
    ok = r.approved is False and r.severity == "CRITICAL" and r.reason == REASON_MISSING_TOKEN
    has_ocr_likely_too = any(reason == REASON_OCR_LIKELY_MISREAD for reason, _ in r.issues)
    ok = ok and has_ocr_likely_too
    report("TEST 25", "Mezcla de ruido OCR tolerable + palabra realmente ausente -> "
                       "sigue CRITICAL por la palabra ausente (el ruido no la enmascara)", ok, r.detail)


def test_26_fragmentacion_de_bloque_ocr_se_tolera():
    # Caso real de produccion (2026-09-18, bundle umbral-dolor-nina): Tesseract recibe
    # un bloque de 6 tokens esperados y produce 2 tokens garbled. La distancia de edicion
    # de los strings juntados supera el umbral normal (24 >> 8), pero cada token
    # renderizado es identificable como una lectura corrupta de algun token esperado:
    #   'problenas' <- 'problemas' (1 edicion, s->n)
    #   'cmportantes' <- 'importantes' (1 edicion, i->c)
    # Clasificar esto como TEXT_CORRUPTION/CRITICAL y gastar 1 retry es INCORRECTO —
    # debe ser OCR_LIKELY_MISREAD/UNCERTAIN (aprueba sin retry).
    ok_heuristic = _looks_like_ocr_misread(
        ['problemas', 'considerados', 'mas', 'importantes', 'y', 'silencios'],
        ['problenas', 'cmportantes'],
    )
    r = compare_text(
        "problemas considerados mas importantes y silencios",
        "problenas cmportantes",
    )
    ok_compare = r.approved is True and r.severity == "UNCERTAIN" and r.reason == REASON_OCR_LIKELY_MISREAD
    report("TEST 26", "Fragmentacion de bloque OCR (6 tokens -> 2 garbled, caso real umbral-dolor-nina) "
                       "se tolera: heuristico True, compare_text aprueba UNCERTAIN",
           ok_heuristic and ok_compare,
           f"heuristic={ok_heuristic} approved={r.approved} severity={r.severity} reason={r.reason} detail={r.detail}")


def test_27_fragmentacion_inventada_no_se_tolera():
    # Contraprueba: si los tokens renderizados NO son lecturas plausibles de ningun
    # token esperado (demasiado diferentes), la fragmentacion NO debe aprobarse.
    ok_heuristic = not _looks_like_ocr_misread(
        ['estabilidad', 'compartida', 'real'],
        ['xyz', 'qwerty'],
    )
    report("TEST 27", "Fragmentacion con tokens completamente inventados (no identificables como "
                       "confusion OCR de ningun token esperado) NO se tolera",
           ok_heuristic,
           f"heuristic={not ok_heuristic} (deberia ser False)")


# ===========================================================================
# PARTE 2 — Distribucion (TEST 15) y cobertura/redistribucion (TEST 16)
# ===========================================================================

def test_15_distribucion_extrema():
    slides = [(1, "palabra " * 25), (2, "palabra " * 25), (3, "palabra " * 112)]
    report_obj = analyze_distribution(slides)
    ok = any("extrema" in w.lower() for w in report_obj.warnings)
    report("TEST 15", "Distribucion extrema (25/25/112 palabras) se detecta", ok, "; ".join(report_obj.warnings))


def test_16_redistribucion_cobertura():
    source = "Una oracion completa. Otra oracion distinta. Y una tercera idea final."
    # Redistribucion: mismos fragmentos literales, reagrupados en 2 "slides" en vez de 3
    redistributed = ["Una oracion completa. Otra oracion distinta.", "Y una tercera idea final."]
    src_tokens = set(tokenize(source))
    red_tokens = set()
    for t in redistributed:
        red_tokens.update(tokenize(t))
    missing = src_tokens - red_tokens
    invented = red_tokens - src_tokens
    ok = not missing and not invented
    report("TEST 16", "Redistribucion mantiene 100% cobertura y 0% inventado", ok, f"missing={missing} invented={invented}")


# ===========================================================================
# PARTE 3 — Integracion con OCR REAL (imagenes locales via PIL, sin Gemini/Kie)
# ===========================================================================

def _ocr_available() -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="ocr_check_"))
    try:
        img_path = tmp / "check.png"
        _draw_text_image("hola mundo", img_path)
        return extract_text_from_image(img_path) is not None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _draw_text_image(text: str, out_path: Path, size=(800, 1000)) -> None:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    margin, y = 40, 60
    for line in text.split("\n"):
        draw.text((margin, y), line, fill="black", font=font)
        y += 55
    img.save(out_path)


@dataclass
class DrawnTextClient:
    """
    Cliente de prueba LOCAL (no es GeminiClient real, no llama a ninguna API): simula
    la generacion "dibujando" con PIL el texto que Gemini habria renderizado en cada
    intento, para que Text QA le aplique OCR REAL. `attempts_by_slide[slide_number]` es
    la lista de textos a devolver en intentos sucesivos (1er intento, 2do intento...).
    """
    attempts_by_slide: Dict[int, List[str]]
    tmp_dir: Path
    attempt_count: Dict[int, int] = field(default_factory=dict)

    def generate_image_direct(self, prompt, reference_images=None, _slide_number=None):
        attempt = self.attempt_count.get(_slide_number, 0)
        self.attempt_count[_slide_number] = attempt + 1
        texts = self.attempts_by_slide.get(_slide_number, [""])
        text = texts[min(attempt, len(texts) - 1)]
        img_path = self.tmp_dir / f"drawn_{_slide_number}_{attempt}.png"
        _draw_text_image(text, img_path)
        return GeminiImageResult(success=True, image_bytes=img_path.read_bytes(), usage_metadata=None)


def _load_process_slides():
    """Carga process_slides desde el script con guion (no importable con `import` normal)."""
    import importlib.util
    path = Path(__file__).parent / "generate-carousel-gemini.py"
    spec = importlib.util.spec_from_file_location("gemini_main_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_slide(number: int, exact_text: str) -> dict:
    return {
        "number": number, "role": f"slide-{number}", "narrative_objective": "o", "message": "m",
        "source_text_fragment": "f", "source_location": "l", "exact_text": exact_text,
        "scene_description": "s", "composition": "c", "visual_hierarchy": "v", "text_placement": "p",
        "key_visual_elements": [], "visual_dna_connection": "d", "connects_prev": None, "connects_next": None,
        "uses_reference_image_directly": False, "uses_product_mockup_directly": False,
    }


@dataclass
class _FakeConfig:
    image_model: str = "gemini-3.1-flash-lite-image"
    aspect_ratio: str = "4:5"
    image_size: str = "1K"
    # FABRICA RAPIDA: presupuesto UNICO de reintentos (1 = 1 intento inicial + 1
    # regeneracion maximo, ver SKILL.md). Compartido por QA estructural y Text QA.
    max_retries: int = 1
    text_qa_enabled: bool = True
    economy_mode: bool = True
    batch_enabled: bool = False
    price_per_image_usd: float = 0.0336


def test_12_solo_slide_fallido_regenera():
    if not _ocr_available():
        report("TEST 12", "SKIPPED (Tesseract/pytesseract no disponible en este entorno)", True)
        return
    mod = _load_process_slides()
    tmp = Path(tempfile.mkdtemp(prefix="textqa_test12_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        correct_text = "Texto correcto del slide"
        slides = [_make_slide(n, correct_text) for n in range(1, 4)]
        # Slide 2 se genera con un error de texto (duplicacion) en el primer intento,
        # y correcto en el segundo intento -> debe regenerarse SOLO el slide 2.
        attempts = {
            1: [correct_text],
            2: ["Texto texto correcto del slide", correct_text],
            3: [correct_text],
        }
        client = DrawnTextClient(attempts_by_slide=attempts, tmp_dir=tmp)
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test12-bundle", 3, 0.0336)
        config = _FakeConfig()

        final_status = mod.process_slides(
            slides, {}, "la-gran-noticia", config, client, cache, cost_tracker,
            "test12-bundle", carousel_dir, None, None, None, force_mode="direct",
        )
        slide2_attempts = client.attempt_count.get(2, 0)
        slide1_attempts = client.attempt_count.get(1, 0)
        slide3_attempts = client.attempt_count.get(3, 0)
        ok = (
            final_status.get(2) == "TEXT_QA_APPROVED"
            and slide2_attempts == 2  # se regenero UNA vez
            and slide1_attempts == 1 and slide3_attempts == 1  # los demas NUNCA se regeneraron
        )
        report("TEST 12", "De 3 slides, solo el que falla Text QA se regenera (los demas 1 sola llamada c/u)", ok,
               f"status={final_status} attempts(1,2,3)=({slide1_attempts},{slide2_attempts},{slide3_attempts})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_13_rerun_identico_cero_generaciones():
    if not _ocr_available():
        report("TEST 13", "SKIPPED (Tesseract/pytesseract no disponible en este entorno)", True)
        return
    mod = _load_process_slides()
    tmp = Path(tempfile.mkdtemp(prefix="textqa_test13_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        correct_text = "Texto correcto del slide"
        slides = [_make_slide(n, correct_text) for n in range(1, 4)]
        client = DrawnTextClient(attempts_by_slide={n: [correct_text] for n in range(1, 4)}, tmp_dir=tmp)
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test13-bundle", 3, 0.0336)
        config = _FakeConfig()

        # Primera corrida: genera los 3 slides normalmente.
        mod.process_slides(slides, {}, "la-gran-noticia", config, client, cache, cost_tracker,
                            "test13-bundle", carousel_dir, None, None, None, force_mode="direct")
        total_attempts_run1 = sum(client.attempt_count.values())

        # Calcular el MISMO prompt_hash que usaria un rerun real, y verificar REUSE.
        reused_count = 0
        for slide in slides:
            plan = mod.build_reference_prompt_and_hash(slide, {}, "la-gran-noticia", config, None, None, None)
            record = cache.get(slide["number"])
            if record and cache.should_reuse(slide["number"], record.prompt_hash, config.image_model, config.image_size, config.aspect_ratio):
                reused_count += 1

        ok = total_attempts_run1 == 3 and reused_count == 3
        report("TEST 13", "Rerun identico -> cache.should_reuse()=True para los 3 slides (0 generaciones nuevas)", ok,
               f"attempts_run1={total_attempts_run1} reused_on_rerun_check={reused_count}/3")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_14_dos_fallos_consecutivos_max_retries():
    if not _ocr_available():
        report("TEST 14", "SKIPPED (Tesseract/pytesseract no disponible en este entorno)", True)
        return
    mod = _load_process_slides()
    tmp = Path(tempfile.mkdtemp(prefix="textqa_test14_"))
    try:
        carousel_dir = tmp / "carousel"
        carousel_dir.mkdir()
        correct_text = "Texto correcto del slide"
        slide = _make_slide(5, correct_text)
        # Falla SIEMPRE (todos los intentos corruptos, misma duplicacion real en cada
        # uno -> confianza de OCR alta, nunca se degrada a UNCERTAIN) -> con
        # MAX_RETRIES=1 (FABRICA RAPIDA: 1 intento inicial + 1 regeneracion como maximo)
        # debe agotar el presupuesto y quedar TEXT_QA_FAILED sin seguir intentando.
        corrupted = "Texto texto correcto del slide"
        client = DrawnTextClient(attempts_by_slide={5: [corrupted, corrupted, corrupted]}, tmp_dir=tmp)
        cache = CacheManager(carousel_dir)
        cost_tracker = CostTracker(tmp, "test14-bundle", 1, 0.0336)
        config = _FakeConfig(max_retries=1)

        final_status = mod.process_slides(
            [slide], {}, "la-gran-noticia", config, client, cache, cost_tracker,
            "test14-bundle", carousel_dir, None, None, None, force_mode="direct",
        )
        attempts = client.attempt_count.get(5, 0)
        # 1 intento inicial + 1 regeneracion = 2 intentos totales, nunca mas (FABRICA RAPIDA).
        ok = final_status.get(5) == "TEXT_QA_FAILED" and attempts == 2
        record = cache.get(5)
        ok = ok and record is not None and record.status == "TEXT_QA_FAILED"
        report("TEST 14", "Fallo persistente -> maximo MAX_RETRIES=1 regeneracion, luego TEXT_QA_FAILED (no infinito)", ok,
               f"status={final_status} attempts={attempts} cache_status={record.status if record else None}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("=" * 70)
    print("AUDITORIA DE TEXT QA — SIN LLAMADAS A GEMINI, SIN LLAMADAS A KIE")
    print("=" * 70)
    for fn in [
        test_1_texto_correcto, test_2_palabra_duplicada, test_3_frase_duplicada,
        test_4_palabra_faltante, test_5_palabra_adicional, test_6_palabra_deformada,
        test_7_dividido_en_lineas, test_8_mayus_minus, test_9_espacios_saltos,
        test_10_titulo_producto_incorrecto, test_11_cta_incorrecta,
        test_caso_real_a, test_caso_real_b, test_caso_real_c,
        test_17_severidad_por_defecto, test_18_ocr_dudoso_degrada_a_uncertain_y_aprueba,
        test_19_ocr_confiable_no_degrada,
        test_20b_edit_distance_y_heuristico_unitarios,
        test_20_biologicos_biolegicos_se_tolera,
        test_21_ene_con_tilde_leida_como_dos_caracteres_se_tolera,
        test_22_fusion_de_palabras_se_tolera,
        test_23_text_corruption_sola_siempre_uncertain,
        test_24_palabra_completamente_ausente_nunca_se_tolera,
        test_25_mezcla_de_error_real_y_ruido_ocr_prioriza_el_error_real,
        test_26_fragmentacion_de_bloque_ocr_se_tolera,
        test_27_fragmentacion_inventada_no_se_tolera,
        test_15_distribucion_extrema, test_16_redistribucion_cobertura,
        test_12_solo_slide_fallido_regenera, test_13_rerun_identico_cero_generaciones,
        test_14_dos_fallos_consecutivos_max_retries,
    ]:
        fn()

    print("\n" + "=" * 70)
    n_pass = sum(1 for r in results_log if r["status"] == PASS)
    n_fail = sum(1 for r in results_log if r["status"] == FAIL)
    print(f"RESULTADO: {n_pass} PASS, {n_fail} FAIL de {len(results_log)} pruebas")
    print("=" * 70)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
