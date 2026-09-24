"""
text_qa.py - TEXT QA: verifica que el texto REALMENTE renderizado dentro de una imagen
generada coincide con el `exact_text` aprobado en brief.json.

Nace de errores reales detectados en produccion (2026-09-16, carrusel "El Dolor Que No
Te Pertenece"): el QA estructural (qa.py: archivo/dimensiones/aspect ratio) aprobaba
imagenes cuyo texto SI estaba corrupto — palabras duplicadas ("TE TE", "conoce mi
libro: conoce mi libro:") y palabras deformadas ("esi compartir dir" en vez de
"estabilidad compartida"). La validacion de brief.json NUNCA puede detectar esto porque
el error ocurre en el RENDERIZADO de Gemini, no en el contenido del brief.

Estrategia ECONOMICA (regla obligatoria, ver SKILL.md "TEXT QA"): esta verificacion es
100% LOCAL — OCR con Tesseract (via pytesseract) sobre el archivo ya descargado en
disco. NUNCA hace una llamada adicional a Gemini para "revisar" una imagen; el costo de
esta verificacion es cero.

Si Tesseract/pytesseract no estan disponibles en el entorno, `extract_text_from_image`
devuelve None y `run_text_qa` marca el resultado como OCR_UNAVAILABLE (aprueba con una
advertencia explicita, nunca bloquea la generacion por falta de una dependencia local
opcional) — esto se refleja siempre en el manifest, nunca se oculta.

FABRICA RAPIDA (ver SKILL.md): cada `TextQAResult` tiene `severity` en
PASS/CRITICAL/UNCERTAIN/SKIPPED. Solo CRITICAL bloquea (dispara la unica regeneracion
permitida). Cuando la confianza del OCR sobre la imagen es baja, un hallazgo que
normalmente seria CRITICAL se reclasifica UNCERTAIN y se aprueba igual — "OCR dudoso"
nunca detiene la fabrica (ver `_apply_ocr_confidence_downgrade`).
"""

import hashlib
import re
import unicodedata
import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# Motivos de rechazo (ver SKILL.md "TEXT QA"). DUPLICATED_TOKEN cubre tanto una palabra
# repetida como una frase/bloque repetido (misma logica de deteccion).
REASON_DUPLICATED_TOKEN = "DUPLICATED_TOKEN"
REASON_MISSING_TOKEN = "MISSING_TOKEN"
REASON_EXTRA_TOKEN = "EXTRA_TOKEN"
REASON_TEXT_CORRUPTION = "TEXT_CORRUPTION"
REASON_PRODUCT_TITLE_MISMATCH = "PRODUCT_TITLE_MISMATCH"
REASON_CTA_MISMATCH = "CTA_MISMATCH"
REASON_OCR_UNAVAILABLE = "OCR_UNAVAILABLE"
# Texto detectado en la imagen que no pertenece al exact_text ni a ningún elemento
# autorizado (firma, handle, CTA, producto) — indica un elemento gráfico no autorizado
# como un número de slide en círculo, marca de agua, o texto de plantilla.
REASON_UNAUTHORIZED_TEXT_ELEMENT = "UNAUTHORIZED_TEXT_ELEMENT"
# Hallazgo real de produccion (2026-09-18, retest "abuela-materna"): Tesseract confunde
# sistematicamente acentos/ene-con-tilde en las tipografias bold/condensadas tipicas de
# un carrusel, con confianza ALTA (86-91/100 medido sobre 8 slides reales) — muy por
# encima de `_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD` (70), asi que el degradado por
# confianza (`_apply_ocr_confidence_downgrade`) nunca se activaba para estos casos y se
# gastaban regeneraciones reales en imagenes que ya estaban perfectas (verificado
# visualmente contra el PNG real). Ver `_looks_like_ocr_misread`.
REASON_OCR_LIKELY_MISREAD = "OCR_LIKELY_MISREAD"

# Tokens extra de longitud <= este umbral son considerados ruido de OCR (artefactos de
# tipografías decorativas) y se reclasifican como UNCERTAIN en lugar de EXTRA_TOKEN.
# Se aplica a tokens alfabéticos puros Y a dígitos aislados (ver _OCR_NOISE_NUMERIC_MAX_CHARS).
_OCR_NOISE_EXTRA_TOKEN_MAX_CHARS = 3

# Tokens NUMÉRICOS de longitud <= este umbral son dígitos aislados de ruido de imagen
# (ej. "4" producido por el kerning de una tipografía bold sobre fotografía oscura).
# Diferente de números reales como "10" o "42" (slide en círculo, marca de agua) que
# sí son UNAUTHORIZED_TEXT_ELEMENT cuando no pertenecen al texto autorizado.
_OCR_NOISE_NUMERIC_MAX_CHARS = 1

_TESSERACT_CANDIDATE_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

# FABRICA RAPIDA (ver SKILL.md "TEXT QA" y regla "OCR dudoso NUNCA bloquea"): cuando la
# confianza promedio del OCR sobre la imagen esta por debajo de este umbral (escala
# 0-100 de Tesseract), un hallazgo que de otro modo seria CRITICO se reclasifica
# UNCERTAIN y se aprueba igual — no podemos distinguir con seguridad "el render esta mal"
# de "el OCR leyo mal un render correcto", y la duda nunca detiene la fabrica.
_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD = 75.0

# Bloques de 0-1 caracter nunca se toleran (no hay informacion suficiente para juzgar
# similitud). Para bloques de 2-3 caracteres (ver caso real 2026-09-18: "la"->"ia",
# "mas"->"mds", ambos confirmados visualmente como imagenes 100% correctas, solo mal
# leidas por Tesseract) se tolera UNICAMENTE 1 edicion — mas que eso, a esa longitud,
# ya es indistinguible de una palabra genuinamente distinta.
_OCR_MISREAD_MIN_LENGTH_SHORT = 2
_OCR_MISREAD_MAX_EDITS_SHORT = 1
# Para bloques de 4+ caracteres: minimo de ediciones SIEMPRE tolerado, sin importar el
# largo de la palabra — calibrado especificamente contra la confusion mas frecuente
# encontrada en produccion (2026-09-18): Tesseract lee "ñ" como DOS caracteres ("fi",
# "ii"), lo que por si solo ya cuesta 2 ediciones (ej. "anos"/"afios",
# "acompanar"/"acompaiiar") aunque el resto de la palabra sea identico.
_OCR_MISREAD_MIN_LENGTH = 4
_OCR_MISREAD_MIN_ALLOWED_EDITS = 2
# Proporcion adicional de ediciones toleradas para bloques largos (ver
# `_looks_like_ocr_misread`) — nunca menor a `_OCR_MISREAD_MIN_ALLOWED_EDITS`.
_OCR_MISREAD_EDIT_RATIO = 0.18


def _edit_distance(a: str, b: str) -> int:
    """Distancia de Levenshtein simple (sustitucion/insercion/eliminacion, costo 1 cada
    una) — sin dependencias externas, solo se usa sobre palabras/bloques cortos."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def _looks_like_ocr_misread(expected_block: List[str], rendered_block: List[str]) -> bool:
    """
    Heuristica para distinguir "Tesseract leyo mal un render correcto" de "el render
    esta realmente corrupto/mal escrito" en un bloque reemplazado (ver
    `REASON_OCR_LIKELY_MISREAD` arriba). Compara los bloques JUNTADOS sin espacios (para
    cubrir tambien fusiones de palabras como "de su" -> "desu") por distancia de edicion
    de caracter, calibrada contra casos reales confirmados visualmente (2026-09-18):
    "biologicos"/"biolegicos" (1 edicion), "ovulo"/"6vulo" (1), "anos"/"afios" (2, ñ->fi),
    "acompanar"/"acompaiiar" (2, ñ->ii), "desu"/"desu" (0, fusion exacta).

    Palabras de 2-3 caracteres (ej. "la"/"ia", "mas"/"mds", tambien confirmados
    visualmente en produccion) se toleran aparte con un presupuesto mas chico (1 sola
    edicion) — a esa longitud, 2+ ediciones ya no distinguen de forma confiable una
    confusion de OCR de una palabra genuinamente distinta.

    Solo se aplica a reemplazos de bloque (TEXT_CORRUPTION) — NUNCA a palabras
    completamente ausentes (MISSING_TOKEN) ni a palabras/frases inventadas que no
    aparecen en el original (EXTRA_TOKEN), que siguen siendo SIEMPRE errores reales sin
    importar cuan "parecidas" sean a algo del texto esperado.
    """
    joined_expected = "".join(expected_block)
    joined_rendered = "".join(rendered_block)
    if not joined_expected or not joined_rendered:
        return False
    # Fusion/segmentacion EXACTA (ej. "de su" -> "desu"): coincide caracter a caracter
    # una vez quitados los espacios, sin ninguna perdida de contenido — se tolera SIN
    # aplicar ningun minimo de longitud (nunca hay duda real en este caso especifico).
    if joined_expected == joined_rendered:
        return True
    shortest = min(len(joined_expected), len(joined_rendered))
    if shortest < _OCR_MISREAD_MIN_LENGTH_SHORT:
        return False
    if shortest < _OCR_MISREAD_MIN_LENGTH:
        return _edit_distance(joined_expected, joined_rendered) <= _OCR_MISREAD_MAX_EDITS_SHORT
    allowed = max(_OCR_MISREAD_MIN_ALLOWED_EDITS, round(len(joined_expected) * _OCR_MISREAD_EDIT_RATIO))
    if _edit_distance(joined_expected, joined_rendered) <= allowed:
        return True
    # Fragmentacion de bloque OCR: cuando Tesseract recibe un bloque de N palabras y
    # produce M < N tokens con alto grado de corrupcion combinada, la distancia de edicion
    # de los strings JUNTADOS supera el umbral anterior — pero cada token renderizado
    # sigue siendo identificable como una lectura corrupta de algun token esperado. Caso
    # real (2026-09-18, carousel umbral-dolor-nina): ['problemas', 'considerados', 'mas',
    # 'importantes', 'y', 'silencios'] -> ['problenas', 'cmportantes'] — 6 tokens esperados,
    # 2 renderizados, edit distance juntados ~24 >> allowed 8. Sin embargo 'problenas' es
    # 'problemas' con 1 substitucion, y 'cmportantes' es 'importantes' con 1 substitucion.
    # Clasificar estos como TEXT_CORRUPTION/CRITICAL (y gastar 1 retry en imagenes que
    # posiblemente son correctas) es incorrecto — deben ser OCR_LIKELY_MISREAD/UNCERTAIN.
    # NUNCA se aplica a EXTRA_TOKEN (tokens inventados) ni MISSING_TOKEN (tokens ausentes),
    # solo a reemplazos de bloque (esta funcion solo se llama para "replace" en el diff).
    if len(rendered_block) < len(expected_block) and rendered_block:
        all_explainable = True
        for ren_tok in rendered_block:
            if len(ren_tok) < 2:
                continue  # token demasiado corto para juzgar similitud
            best_dist = min(_edit_distance(ren_tok, exp_tok) for exp_tok in expected_block)
            # Tolerancia por token: 35% de su longitud, minimo 2 ediciones — cubre
            # confusiones comunes (ñ->fi = 2 ediciones, acento perdido = 1 sustitucion,
            # digito confundido con letra = 1 sustitucion).
            allowed_tok = max(2, round(len(ren_tok) * 0.35))
            if best_dist > allowed_tok:
                all_explainable = False
                break
        if all_explainable:
            return True
    return False


def _is_numeric_token(token: str) -> bool:
    """True si el token es puramente numérico o un número con separadores (ej. "10", "3.5", "100%").
    Los tokens numéricos no son ruido de OCR en texto alfabético — si aparecen como extra
    y no están en el texto autorizado, son UNAUTHORIZED_TEXT_ELEMENT."""
    return bool(token) and all(c.isdigit() or c in ".,%-" for c in token)


def _all_short_alphabetic_noise(tokens: List[str]) -> bool:
    """True si TODOS los tokens son artefactos típicos de OCR sobre tipografías estilizadas:
    - alfabéticos cortos (≤ _OCR_NOISE_EXTRA_TOKEN_MAX_CHARS): kerning apretado en bold/serif
    - numéricos aislados (≤ _OCR_NOISE_NUMERIC_MAX_CHARS): dígito suelto de ruido de imagen
    Maneja listas MIXTAS (ej. ['jia', '4', 's']) — deja de asumir que cualquier token
    numérico en el grupo es necesariamente contenido real no autorizado."""
    if not tokens:
        return False
    return all(
        (len(t) <= _OCR_NOISE_EXTRA_TOKEN_MAX_CHARS and t.isalpha())
        or (len(t) <= _OCR_NOISE_NUMERIC_MAX_CHARS and _is_numeric_token(t))
        for t in tokens
    )


def _is_systematic_ocr_failure(issues: List[Tuple[str, list]], exp_tokens: List[str]) -> bool:
    """True cuando el patrón de TEXT_CORRUPTION a lo largo del slide sugiere fallo
    sistemático de OCR sobre tipografía estilizada (ej. serif cursivo dorado sobre
    fotografía B&W), no errores reales de renderizado.

    Criterio: ≥ 4 issues TEXT_CORRUPTION Y los tokens esperados afectados representan
    ≥ 8% del total de tokens esperados del slide.

    NUNCA se aplica cuando hay MISSING_TOKEN o DUPLICATED_TOKEN (errores estructurales
    reales que no pueden explicarse por fallo de OCR).
    """
    if not issues or not exp_tokens:
        return False
    corruption_issues = [(t, p) for t, p in issues if t == REASON_TEXT_CORRUPTION]
    if len(corruption_issues) < 4:
        return False
    corrupted_exp_tokens = sum(
        len(payload[0]) if len(payload) == 2 and isinstance(payload[0], list) else 1
        for _, payload in corruption_issues
    )
    return corrupted_exp_tokens / len(exp_tokens) >= 0.08


def normalize_text(text: str) -> str:
    """
    Normaliza texto para comparacion, ignorando UNICAMENTE diferencias irrelevantes:
    mayusculas/minusculas, acentos (el OCR frecuentemente los pierde), espacios
    multiples, saltos de linea y espacios al inicio/final. NUNCA ignora palabras en si
    (duplicadas, faltantes, adicionales o deformadas siguen siendo detectables despues
    de esta normalizacion).
    """
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    """Extrae tokens de palabra (letras/numeros/apostrofe) de un texto ya normalizado."""
    return re.findall(r"[a-z0-9']+", normalize_text(text))


def _hash_text(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:16]


@dataclass
class TextQAResult:
    approved: bool
    reason: Optional[str] = None
    detail: str = ""
    expected_text_hash: str = ""
    rendered_text_hash: str = ""
    rendered_text: Optional[str] = None
    skipped: bool = False
    issues: List[Tuple[str, list]] = field(default_factory=list)
    # "PASS" | "CRITICAL" | "UNCERTAIN" | "SKIPPED" (ver SKILL.md "TEXT QA" / "FABRICA
    # RAPIDA"). Solo CRITICAL bloquea el pipeline (approved=False); UNCERTAIN y SKIPPED
    # siempre aprueban. Se fija automaticamente en __post_init__ segun `approved`/
    # `skipped`; `run_text_qa` puede degradar CRITICAL -> UNCERTAIN via confianza de OCR.
    severity: str = "PASS"

    def __post_init__(self) -> None:
        if self.skipped:
            self.severity = "SKIPPED"
        elif not self.approved and self.severity == "PASS":
            self.severity = "CRITICAL"


def compare_text(expected: str, rendered: str) -> TextQAResult:
    """
    Compara el texto esperado (`exact_text` de brief.json) contra el texto realmente
    renderizado (salida de OCR), a nivel de TOKENS (palabras) — nunca a nivel de lineas,
    para que una misma frase distribuida en lineas distintas siga aprobandose (ver
    SKILL.md "TEXTO EN DIFERENTES LINEAS").

    Usa difflib.SequenceMatcher sobre las listas de tokens para clasificar cada
    diferencia real en una de 4 categorias:
      - DUPLICATED_TOKEN: el bloque insertado en el renderizado es identico al bloque
        de texto esperado que lo precede inmediatamente (repeticion real).
      - EXTRA_TOKEN: el bloque insertado NO coincide con nada esperado alrededor —
        contenido añadido que no existe en el original.
      - MISSING_TOKEN: un bloque completo del texto esperado no aparece en absoluto en
        el renderizado.
      - TEXT_CORRUPTION: un bloque fue reemplazado por otro de contenido distinto
        (palabras deformadas/ilegibles tipo "esi compartir dir").
      - OCR_LIKELY_MISREAD: un caso especial de reemplazo de bloque que, por su alta
        similitud de caracteres, es mas probable que sea Tesseract leyendo mal un
        render CORRECTO (confusion tipica de acentos/ene-con-tilde en tipografias bold)
        que una corrupcion real — ver `_looks_like_ocr_misread` y
        `REASON_OCR_LIKELY_MISREAD`. NUNCA se aplica a MISSING_TOKEN/EXTRA_TOKEN/
        DUPLICATED_TOKEN: una palabra realmente ausente, inventada o duplicada sigue
        siendo SIEMPRE un error real, sin importar la similitud de caracteres.
    """
    expected_hash = _hash_text(expected)
    rendered_hash = _hash_text(rendered)

    exp_tokens = tokenize(expected)
    ren_tokens = tokenize(rendered)

    if exp_tokens == ren_tokens:
        return TextQAResult(True, None, "Texto identico tras normalizacion", expected_hash, rendered_hash, rendered)

    matcher = difflib.SequenceMatcher(None, exp_tokens, ren_tokens, autojunk=False)
    issues: List[Tuple[str, list]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            inserted = ren_tokens[j1:j2]
            preceding_expected = exp_tokens[max(0, i1 - len(inserted)):i1]
            if preceding_expected == inserted:
                issues.append((REASON_DUPLICATED_TOKEN, inserted))
            elif _all_short_alphabetic_noise(inserted):
                # Tokens extra cortos y alfabéticos = artefacto de OCR sobre tipografía
                # decorativa (ver _OCR_NOISE_EXTRA_TOKEN_MAX_CHARS). Se clasifican igual
                # que OCR_LIKELY_MISREAD (no bloquean el pipeline).
                issues.append((REASON_OCR_LIKELY_MISREAD, inserted))
            elif any(_is_numeric_token(t) for t in inserted):
                # Token numérico no esperado = elemento gráfico no autorizado (ej. número
                # de slide en círculo, marca de agua numérica). UNAUTHORIZED_TEXT_ELEMENT.
                issues.append((REASON_UNAUTHORIZED_TEXT_ELEMENT, inserted))
            else:
                issues.append((REASON_EXTRA_TOKEN, inserted))
        elif tag == "delete":
            issues.append((REASON_MISSING_TOKEN, exp_tokens[i1:i2]))
        elif tag == "replace":
            exp_block = exp_tokens[i1:i2]
            ren_block = ren_tokens[j1:j2]
            if _looks_like_ocr_misread(exp_block, ren_block):
                issues.append((REASON_OCR_LIKELY_MISREAD, [exp_block, ren_block]))
            else:
                issues.append((REASON_TEXT_CORRUPTION, [exp_block, ren_block]))

    if not issues:
        return TextQAResult(True, None, "Sin diferencias relevantes", expected_hash, rendered_hash, rendered)

    real_issues = [item for item in issues if item[0] != REASON_OCR_LIKELY_MISREAD]

    if not real_issues:
        # TODAS las diferencias encontradas son del patron tipico de confusion OCR (ver
        # REASON_OCR_LIKELY_MISREAD arriba) — se aprueba, pero queda trazado como
        # UNCERTAIN (nunca PASS silencioso, nunca CRITICAL): no bloquea el pipeline, pero
        # el detalle de que se toleró sigue siendo visible en cache/manifest.
        tolerated = "; ".join(
            f"{' '.join(pair[0])!r} leido como {' '.join(pair[1])!r}" if isinstance(pair[0], list) else str(pair)
            for _, pair in issues
        )
        return TextQAResult(
            True, REASON_OCR_LIKELY_MISREAD,
            f"Diferencias toleradas por ser tipicas de confusion OCR en acentos/ene: {tolerated}",
            expected_hash, rendered_hash, rendered, severity="UNCERTAIN", issues=issues,
        )

    # REGLA: TEXT_CORRUPTION sola → UNCERTAIN (nunca CRITICAL, nunca retry).
    # El retry está reservado para evidencia ESTRUCTURAL de que falta, sobra o se duplicó
    # contenido: MISSING_TOKEN, DUPLICATED_TOKEN, EXTRA_TOKEN, UNAUTHORIZED_TEXT_ELEMENT.
    # TEXT_CORRUPTION es siempre compatible con "OCR leyó mal una imagen correcta" sobre
    # tipografías estilizadas (cursivo, serif dorado, bold condensado) — gastar un retry
    # por TEXT_CORRUPTION es desperdiciar crédito con muy baja probabilidad de mejora.
    only_text_corruption_real = all(t == REASON_TEXT_CORRUPTION for t, _ in real_issues)
    if only_text_corruption_real:
        primary_reason, primary_payload = real_issues[0]
        detail = (f"TEXT_CORRUPTION sin evidencia estructural — {primary_reason}: {primary_payload}"
                  + (f" (+{len(issues)-1} diferencia(s) mas)" if len(issues) > 1 else ""))
        return TextQAResult(
            True, primary_reason, detail,
            expected_hash, rendered_hash, rendered,
            severity="UNCERTAIN", issues=issues,
        )

    # CRITICAL solo con evidencia estructural: MISSING_TOKEN, DUPLICATED_TOKEN,
    # EXTRA_TOKEN, UNAUTHORIZED_TEXT_ELEMENT. Estas sí son prueba de que falta,
    # sobra o se duplicó contenido — no pueden explicarse por fallo de OCR.
    primary_reason, primary_payload = real_issues[0]
    detail = f"{primary_reason}: {primary_payload}" + (f" (+{len(issues)-1} diferencia(s) mas)" if len(issues) > 1 else "")
    return TextQAResult(False, primary_reason, detail, expected_hash, rendered_hash, rendered, issues=issues)


def check_exact_phrase(phrase: str, rendered_text: str, label: str = "CRITICAL_PHRASE") -> TextQAResult:
    """
    Verificacion reforzada para frases criticas (titulo de producto, CTA — ver SKILL.md
    seccion "PRODUCTOS" y "CTA"). Primero busca la secuencia EXACTA de tokens de
    `phrase` como sub-lista contigua en algun punto de `rendered_text`. Si no la
    encuentra exacta, ejecuta la comparacion completa y re-etiqueta el motivo con
    `label` (ej. PRODUCT_TITLE_MISMATCH, CTA_MISMATCH) para que quede claro que el
    fallo esta en una frase critica, no en un fragmento cualquiera del slide.
    """
    phrase_tokens = tokenize(phrase)
    rendered_tokens = tokenize(rendered_text)
    n = len(phrase_tokens)

    # Contar TODAS las apariciones exactas y no solapadas de la frase — no basta con
    # encontrar una: si aparece 2+ veces (ej. "conoce mi libro: conoce mi libro:"), es
    # una duplicacion real y debe rechazarse, aunque la primera aparicion sea exacta.
    occurrences = 0
    start = 0
    while start <= len(rendered_tokens) - n:
        if rendered_tokens[start:start + n] == phrase_tokens:
            occurrences += 1
            start += n  # avanzar mas alla de esta aparicion, sin solapar
        else:
            start += 1

    if occurrences == 1:
        return TextQAResult(True, None, f"'{phrase}' encontrada exacta (1 sola vez) en el renderizado", _hash_text(phrase), _hash_text(rendered_text), rendered_text)
    if occurrences >= 2:
        return TextQAResult(
            False, label, f"{label}: '{phrase}' aparece duplicada ({occurrences} veces) en el renderizado",
            _hash_text(phrase), _hash_text(rendered_text), rendered_text,
            issues=[(REASON_DUPLICATED_TOKEN, phrase_tokens)],
        )

    result = compare_text(phrase, rendered_text)
    if result.approved:
        return result
    return TextQAResult(False, label, f"{label}: {result.detail}", result.expected_text_hash, result.rendered_text_hash, rendered_text, issues=result.issues)


def extract_text_from_image(image_path: Path) -> Optional[str]:
    """
    OCR 100% LOCAL (Tesseract via pytesseract) — NUNCA llama a ninguna API externa,
    NUNCA gasta credito. Devuelve None si pytesseract o el binario de Tesseract no
    estan disponibles en el entorno (caso que `run_text_qa` maneja explicitamente como
    OCR_UNAVAILABLE, nunca como un fallo silencioso).
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None

    if not getattr(pytesseract.pytesseract, "tesseract_cmd", None) or pytesseract.pytesseract.tesseract_cmd == "tesseract":
        for candidate in _TESSERACT_CANDIDATE_PATHS:
            if Path(candidate).exists():
                pytesseract.pytesseract.tesseract_cmd = candidate
                break

    try:
        with Image.open(image_path) as img:
            return pytesseract.image_to_string(img, lang="spa+eng")
    except Exception:  # noqa: BLE001 - cualquier fallo de OCR se trata como no disponible, nunca bloquea
        return None


def extract_ocr_confidence(image_path: Path) -> Optional[float]:
    """
    Confianza promedio del OCR (0-100, escala nativa de Tesseract) sobre TODAS las
    palabras detectadas en la imagen. Devuelve None si pytesseract/Tesseract no estan
    disponibles o no se detecto ninguna palabra con confianza valida — en ese caso
    `run_text_qa` simplemente no aplica el degradado a UNCERTAIN (nunca inventa una
    confianza que no pudo medir).
    """
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None

    if not getattr(pytesseract.pytesseract, "tesseract_cmd", None) or pytesseract.pytesseract.tesseract_cmd == "tesseract":
        for candidate in _TESSERACT_CANDIDATE_PATHS:
            if Path(candidate).exists():
                pytesseract.pytesseract.tesseract_cmd = candidate
                break

    try:
        with Image.open(image_path) as img:
            data = pytesseract.image_to_data(img, lang="spa+eng", output_type=pytesseract.Output.DICT)
    except Exception:  # noqa: BLE001 - cualquier fallo de OCR se trata como "sin medicion"
        return None

    confidences = []
    for raw_conf in data.get("conf", []):
        try:
            conf = float(raw_conf)
        except (TypeError, ValueError):
            continue
        if conf >= 0:  # Tesseract usa -1 para cajas sin texto detectado
            confidences.append(conf)

    if not confidences:
        return None
    return sum(confidences) / len(confidences)


def _apply_ocr_confidence_downgrade(result: TextQAResult, image_path: Path) -> TextQAResult:
    """
    Regla "OCR dudoso NUNCA bloquea" (ver SKILL.md "FABRICA RAPIDA"): si la confianza
    promedio del OCR sobre esta imagen esta por debajo de
    `_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD`, un hallazgo CRITICAL se reclasifica UNCERTAIN
    y se aprueba igual (no dispara regeneracion) — la duda es del lector OCR, no
    necesariamente del render. Si no se pudo medir la confianza, el resultado CRITICAL
    original se mantiene sin cambios.
    """
    if result.severity != "CRITICAL":
        return result
    confidence = extract_ocr_confidence(image_path)
    if confidence is not None and confidence < _OCR_UNCERTAIN_CONFIDENCE_THRESHOLD:
        result.severity = "UNCERTAIN"
        result.approved = True
        result.detail = (
            f"{result.detail} [degradado a UNCERTAIN: confianza OCR {confidence:.0f}/100 "
            f"< {_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD:.0f} -> no bloqueante]"
        )
    return result


@dataclass
class SlideDistributionMetrics:
    number: int
    word_count: int
    character_count: int
    num_blocks: int
    longest_block_chars: int
    text_density: str  # LOW | MEDIUM | HIGH, relativo a la tanda


@dataclass
class DistributionReport:
    slides: List[SlideDistributionMetrics]
    warnings: List[str] = field(default_factory=list)


def analyze_distribution(slides_exact_text: List[Tuple[int, str]]) -> DistributionReport:
    """
    Analiza la distribucion de texto entre slides ANTES de generar (ver SKILL.md PASO
    6.6 y esta seccion "TEXT QA DE DISTRIBUCIÓN"). `slides_exact_text` es una lista de
    (slide_number, exact_text). Calcula, por slide: word_count, character_count,
    num_blocks (separados por linea en blanco '\\n\\n'), longest_block_chars, y clasifica
    text_density de forma RELATIVA al rango real de esa tanda (nunca un umbral
    universal fijo) — LOW/MEDIUM/HIGH segun terciles del propio conjunto.

    NO busca igualdad matematica de palabras entre slides — solo señala, via
    `warnings`, desequilibrios estructurales: diferencias extremas (bloque mas grande
    > 3x el mas chico) y 3+ slides HIGH consecutivos.
    """
    metrics = []
    for number, text in slides_exact_text:
        words = tokenize(text)
        blocks = [b for b in re.split(r"\n\s*\n", text) if b.strip()]
        longest_block = max((len(b) for b in blocks), default=len(text))
        metrics.append({
            "number": number,
            "word_count": len(words),
            "character_count": len(text),
            "num_blocks": max(1, len(blocks)),
            "longest_block_chars": longest_block,
        })

    counts = sorted(m["word_count"] for m in metrics)
    n = len(counts)
    low_cut = counts[n // 3] if n >= 3 else (min(counts) if counts else 0)
    high_cut = counts[(2 * n) // 3] if n >= 3 else (max(counts) if counts else 0)

    def classify(wc: int) -> str:
        if wc <= low_cut:
            return "LOW"
        if wc >= high_cut and high_cut > low_cut:
            return "HIGH"
        return "MEDIUM"

    result_slides = [
        SlideDistributionMetrics(
            number=m["number"], word_count=m["word_count"], character_count=m["character_count"],
            num_blocks=m["num_blocks"], longest_block_chars=m["longest_block_chars"],
            text_density=classify(m["word_count"]),
        )
        for m in metrics
    ]

    warnings: List[str] = []
    if counts and min(counts) > 0 and max(counts) / min(counts) > 3:
        warnings.append(
            f"Diferencia extrema de densidad: slide mas denso tiene {max(counts)} palabras, "
            f"el mas vacio {min(counts)} (ratio {max(counts)/min(counts):.1f}x). Considerar redistribuir."
        )
    densities = [s.text_density for s in result_slides]
    for i in range(len(densities) - 2):
        if densities[i] == densities[i + 1] == densities[i + 2] == "HIGH":
            nums = [result_slides[i].number, result_slides[i + 1].number, result_slides[i + 2].number]
            warnings.append(f"Slides {nums} son HIGH consecutivos — evitar 3+ seguidos si es posible redistribuir.")

    return DistributionReport(slides=result_slides, warnings=warnings)


def verify_source_text_fragments(source_text: str, slides: list) -> List[str]:
    """
    Verificacion NO BLOQUEANTE de fidelidad: detecta source_text_fragments de
    claude_decisions.json que no pueden rastrearse al source_text original.

    La fuente de verdad es siempre source_text (el usuario es su autor); exact_text
    debe derivarse de el sin modificaciones semanticas. Si un fragmento no se localiza
    en source_text (comparacion normalizada por tokens), hay un posible typo introducido
    al escribir claude_decisions.json.

    Devuelve lista de advertencias (lista vacia = todo OK). NUNCA bloquea el pipeline.
    """
    warnings: List[str] = []
    if not source_text:
        return warnings
    src_tokens = tokenize(source_text)
    src_joined = " ".join(src_tokens)
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        fragment = slide.get("source_text_fragment", "")
        if not fragment:
            continue
        frag_tokens = tokenize(fragment)
        frag_joined = " ".join(frag_tokens)
        if frag_joined and frag_joined not in src_joined:
            num = slide.get("number", "?")
            warnings.append(
                f"Slide {num}: source_text_fragment no rastreable en source_text "
                f"(posible typo en claude_decisions.json): {fragment[:60]!r}"
            )
    return warnings


def run_text_qa(
    image_path: Path,
    expected_text: str,
    critical_phrases: Optional[List[Tuple[str, str]]] = None,
    authorized_extra_tokens: Optional[List[str]] = None,
    uses_product_mockup: bool = False,
) -> TextQAResult:
    """
    Orquesta el TEXT QA completo de un slide: OCR local + comparacion + verificacion
    reforzada de frases criticas (producto/CTA). `critical_phrases` es una lista de
    tuplas (label, phrase), ej. [("PRODUCT_TITLE_MISMATCH", "EL DOLOR QUE NO TE
    PERTENECE")].

    `authorized_extra_tokens` es una lista de cadenas autorizadas fuera de exact_text
    (attribution, handle, CTA, product name, etc.). Tokens extra del OCR que pertenecen
    a este conjunto NO se clasifican como UNAUTHORIZED_TEXT_ELEMENT — son contenido
    propio del diseño que no forma parte del exact_text del slide.

    `uses_product_mockup` (True cuando el slide muestra un mockup fisico del producto):
    el OCR leerá el texto impreso en la portada del libro/producto (título, subtítulo,
    firma de autora) como tokens adicionales. Sin bounding boxes no podemos separar
    "texto del slide" de "texto impreso dentro del mockup". Política: los tokens
    extra/no-autorizados que queden después de resolver authorized_extra_tokens se
    downgrada a UNCERTAIN — solo MISSING_TOKEN y DUPLICATED_TOKEN siguen siendo CRITICAL
    en slides con mockup (son errores estructurales del slide, no del cover del producto).
    """
    rendered = extract_text_from_image(image_path)
    if rendered is None:
        return TextQAResult(
            approved=True, reason=REASON_OCR_UNAVAILABLE,
            detail="pytesseract/Tesseract no disponibles en este entorno — Text QA omitido, no bloqueante",
            expected_text_hash=_hash_text(expected_text), rendered_text_hash="", skipped=True,
        )

    result = compare_text(expected_text, rendered)

    # Post-proceso: si hay tokens extra (EXTRA_TOKEN / UNAUTHORIZED_TEXT_ELEMENT) que
    # coinciden con contenido autorizado (attribution, handle, CTA, producto), no son
    # violaciones reales — se reclasifican a UNCERTAIN para no bloquear el pipeline.
    if not result.approved and authorized_extra_tokens:
        auth_token_set: set = set()
        for auth_text in authorized_extra_tokens:
            auth_token_set.update(tokenize(auth_text))
        blocking_issues = [
            item for item in result.issues
            if not (item[0] in (REASON_EXTRA_TOKEN, REASON_UNAUTHORIZED_TEXT_ELEMENT)
                    and all(tok in auth_token_set for tok in item[1]))
        ]
        if not blocking_issues:
            result.approved = True
            result.severity = "UNCERTAIN"
            result.detail = f"Tokens extra de contenido autorizado (atribución/handle/producto): {result.detail}"
        elif len(blocking_issues) < len(result.issues):
            # Algunos issues eran autorizados; quitar los autorizados y re-evaluar
            result.issues = blocking_issues
            primary_reason, primary_payload = blocking_issues[0]
            result.reason = primary_reason
            result.detail = (f"{primary_reason}: {primary_payload}"
                             + (f" (+{len(blocking_issues)-1} diferencia(s) mas)" if len(blocking_issues) > 1 else ""))

    # MOCKUP: cuando uses_product_mockup=True y quedan issues no MISSING/DUPLICATED,
    # estos vienen probablemente del texto impreso en la portada del libro/producto.
    # Sin bounding boxes no podemos separar "texto del slide" de "texto del cover".
    # EXTRA_TOKEN/UNAUTHORIZED_TEXT_ELEMENT → UNCERTAIN (nunca CRITICAL en mockup).
    # MISSING_TOKEN y DUPLICATED_TOKEN siguen siendo CRITICAL (son errores del slide).
    if uses_product_mockup and not result.approved:
        structural = [i for i in result.issues
                      if i[0] in (REASON_MISSING_TOKEN, REASON_DUPLICATED_TOKEN)]
        if not structural:
            result.approved = True
            result.severity = "UNCERTAIN"
            result.detail = (f"TEXTO DEL MOCKUP (portada del producto en imagen, no del slide) — {result.detail}")

    if not result.approved:
        return _apply_ocr_confidence_downgrade(result, image_path)

    for label, phrase in critical_phrases or []:
        phrase_result = check_exact_phrase(phrase, rendered, label=label)
        if not phrase_result.approved:
            return _apply_ocr_confidence_downgrade(phrase_result, image_path)

    return result
