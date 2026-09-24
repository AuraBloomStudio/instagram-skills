"""
carousel_common.py - Logica compartida de carousel-gen, independiente del proveedor de
generacion de imagenes (Kie AI o Gemini).

Este modulo existe para que NO haya logica duplicada entre el generador legacy
(`generate-carousel.py`, Kie AI) y el generador economico (`generate-carousel-gemini.py`,
Google Gemini / Nano Banana 2 Lite). Contiene unicamente lo que es identico sin importar
que API genere las imagenes:

- Rutas del proyecto (PROJECT_ROOT, OUTPUTS_DIR, DOWNLOADS_EXPORT_DIR)
- Carga y validacion de brief.json (incluye la compuerta MAX_SLIDES=10, ver SKILL.md
  seccion "LIMITE OBLIGATORIO DE SLIDES")
- Deteccion de herramientas/entidades para logos opcionales
- Construccion de prompts a partir del Visual DNA (build_prompt_for_slide y todo lo que
  usa: GLOBAL_DESIGN_RULES, IMAGE_ROLE_INSTRUCTIONS, format_visual_dna_block)
- Generacion de manifest.json y de la guia de logos opcionales
- Exportacion del paquete final (PARA FACEBOOK/, copia a Descargas)
- Guardado del copy de publicacion unificado en COPY_FINAL.txt (description/cta/enlace/hashtags)

NUNCA modificar el comportamiento de estas funciones sin revisar antes ambos scripts que
las importan (Kie legacy y Gemini economico) — un cambio aqui afecta a los dos.
"""

import os
import json
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

# Configuración de rutas (identica sin importar el proveedor de generacion)
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "bundles"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Carpeta de Descargas de Windows donde se copian los slides finales de CADA carrusel
# generado (regla general y permanente del skill, ver export_final_slides_to_downloads).
# El bundle original en OUTPUTS_DIR nunca se mueve ni se reemplaza — esto es siempre una
# COPIA de los archivos finales listos para publicar.
DOWNLOADS_EXPORT_DIR = Path.home() / "Downloads" / "Carruseles Carousel-Gen"

# Nombre del archivo UNICO de copy de publicacion (regla permanente, ver SKILL.md seccion
# "COPY_FINAL.txt"). Reemplaza a los antiguos description.txt/cta.txt/hashtags.txt, que ya
# no se generan.
COPY_FINAL_FILENAME = "COPY_FINAL.txt"

# Nombre del archivo OBLIGATORIO de resumen de costo/tiempo de cada carrusel REAL (ver
# SKILL.md "FABRICA RAPIDA" / "COSTO_CARRUSEL.txt"). Se crea automaticamente, sin pedir
# permiso, al terminar cualquier carrusel.
COSTO_CARRUSEL_FILENAME = "COSTO_CARRUSEL.txt"

# LÍMITE OBLIGATORIO Y PERMANENTE DE SLIDES (ver SKILL.md, sección "LÍMITE OBLIGATORIO DE
# SLIDES"). Ningún carrusel generado por carousel-gen puede superar MAX_SLIDES, sin importar
# el proveedor de generación (Kie o Gemini), para que el paquete final sea compatible tanto
# con Facebook como con Instagram. Este es el ÚNICO lugar donde se define el límite — tanto
# el script legacy de Kie como el script económico de Gemini importan esta misma constante.
# Nunca duplicar este número en otro lugar del código; siempre referenciar esta constante.
MAX_SLIDES = 10

REQUIRED_BRIEF_TOP_FIELDS = ["reference_image", "visual_dna", "carousel_type", "slide_count", "slides", "product"]
# "product": bloque {"product_name": ..., "purchase_url": ...} — resultado obligatorio de
# la pregunta "¿Que libro o producto vamos a promocionar?" (SKILL.md PASO 7), que se hace
# SIEMPRE en cada carrusel nuevo, sin excepcion. Puede tener ambos campos en null cuando el
# usuario indico explicitamente que este carrusel no promociona nada — pero el bloque en si
# siempre debe existir. Sin el, load_brief() rechaza el brief.

REQUIRED_SLIDE_FIELDS = [
    "number", "role",
    "source_text_fragment", "exact_text",
    "scene_description", "composition", "visual_hierarchy", "text_placement",
    "key_visual_elements", "uses_reference_image_directly",
    "word_count", "text_density", "estimated_text_area", "text_area_percentage",
    "visual_balance",
]
# Campos eliminados de la lista requerida (optimización de tokens T0→T1, 2026-09-19):
#   narrative_objective, message, visual_dna_connection: eran opcionales para la calidad
#   del prompt; cuando están presentes se usan, cuando no, el prompt sigue siendo válido.
#   source_location, text_break_reason: metadatos de trazabilidad/planificación — útiles
#   como documentación pero no necesarios para la generación ni la validación del brief.
#
# source_text_fragment: garantiza que exact_text sea rastreable al texto original del post
# viral (fidelidad del contenido — ver SKILL.md, "FIDELIDAD DEL CONTENIDO ORIGINAL"). Sin
# este campo load_brief() rechaza el brief — es una compuerta técnica, no solo documental.
#
# word_count / text_density / estimated_text_area / text_area_percentage /
# visual_balance: garantizan que la distribucion de texto entre slides se haya planificado
# deliberadamente (narrativa + densidad + legibilidad + composicion + espacio). Nace de un
# caso real (2026-09-16, carrusel "El Dolor Que No Te Pertenece"): un brief 100% fiel tuvo
# un slide con 112 palabras (4.3x el promedio) mientras otros tenian 25 — tecnicamente
# fiel, pero visualmente desequilibrado. Un brief SIN estos campos queda rechazado —
# esto rompe briefs antiguos que no los tengan (ej. bundles generados antes de esta
# regla); es intencional: cualquier regeneracion futura de un bundle antiguo debe
# primero completar estos campos, nunca se genera "a ciegas" sin planificacion visual.

_VALID_TEXT_DENSITIES = {"LOW", "MEDIUM", "HIGH"}
_VALID_VISUAL_BALANCE = {"balanced", "text_heavy", "underutilized"}


def load_brief(bundle_path: Path) -> Optional[Dict[str, Any]]:
    """
    Carga y valida brief.json del bundle.

    brief.json es la fuente de verdad unica generada por el workflow de SKILL.md:
    contiene la referencia viral, el ADN visual, el formato elegido y los slides
    con sus campos narrativos/visuales. Esta validacion es identica sin importar el
    proveedor de generacion (Kie o Gemini) que use el script que la invoque.
    """
    brief_file = bundle_path / "brief.json"

    if not brief_file.exists():
        print(f"[ERROR] Error: No se encontró {brief_file}")
        print("   brief.json debe crearse desde el workflow de SKILL.md (Paso 6) antes de ejecutar este script.")
        return None

    with open(brief_file, "r", encoding="utf-8") as f:
        brief = json.load(f)

    missing_top = [k for k in REQUIRED_BRIEF_TOP_FIELDS if k not in brief]
    if missing_top:
        print(f"[ERROR] Error: brief.json incompleto, faltan campos: {missing_top}")
        return None

    slides = brief["slides"]
    if not slides:
        print("[ERROR] Error: brief.json no tiene slides")
        return None

    # COMPUERTA TÉCNICA OBLIGATORIA — LÍMITE DE MAX_SLIDES (ver SKILL.md, sección "LÍMITE
    # OBLIGATORIO DE SLIDES"). Se valida ANTES que cualquier otra cosa en este archivo:
    # antes de revisar campos por slide, antes de credenciales, antes de cualquier llamada
    # a la API de generacion (Kie o Gemini). Si el brief supera el límite, load_brief()
    # devuelve None y el script que la invoque debe terminar el proceso sin generar ninguna
    # imagen ni gastar ningún crédito. El motivo es que el paquete final debe poder usarse
    # tanto en Facebook como en Instagram, donde el límite real de slides por carrusel es 10.
    num_slides = len(slides)
    if num_slides > MAX_SLIDES:
        print(f"[ERROR] ERROR: carousel-gen admite un máximo de {MAX_SLIDES} slides. El brief "
              f"solicitado contiene {num_slides} slides. Debe reorganizarse el contenido "
              f"dentro del límite de {MAX_SLIDES}.")
        print(f"   Motivo: el paquete final debe ser compatible tanto con Facebook como con "
              f"Instagram (limite real de Instagram: {MAX_SLIDES} slides por carrusel).")
        print(f"   Esto NO significa resumir o eliminar contenido: hay que redistribuir el "
              f"mismo contenido fiel de source_text dentro de {MAX_SLIDES} slides (slides con "
              f"mayor densidad de texto), nunca perder fragmentos ni inventar nada — ver "
              f"SKILL.md, seccion 'FIDELIDAD DEL CONTENIDO ORIGINAL' y 'LÍMITE OBLIGATORIO DE "
              f"SLIDES'.")
        return None

    slide_count_block = brief.get("slide_count") or {}
    for count_key in ("recommended", "confirmed"):
        count_value = slide_count_block.get(count_key)
        if isinstance(count_value, (int, float)) and count_value > MAX_SLIDES:
            print(f"[ERROR] ERROR: carousel-gen admite un máximo de {MAX_SLIDES} slides. El brief "
                  f"solicitado tiene slide_count.{count_key} = {count_value}. Debe "
                  f"reorganizarse el contenido dentro del límite de {MAX_SLIDES}.")
            return None

    for slide in slides:
        missing_fields = [f for f in REQUIRED_SLIDE_FIELDS if f not in slide]
        if missing_fields:
            _FIELD_HINTS = {
                "word_count":            "entero positivo — contar palabras de exact_text (ej. 9)",
                "text_density":          '"LOW" | "MEDIUM" | "HIGH"  (mayusculas exactas)',
                "estimated_text_area":   'descriptor estructural (ej. "upper_third_centered", "centered_stacked_blocks")',
                "text_area_percentage":  "entero 0-100, estimacion estructural (ej. 25)",
                "visual_balance":        '"balanced" | "text_heavy" | "underutilized"  (no "image_heavy")',
                "text_break_reason":     '"natural_sentence_boundary" | "paragraph_boundary" | "density_rebalance"',
            }
            print(f"[ERROR] Error: slide {slide.get('number', '?')} incompleto, faltan campos: {missing_fields}")
            for fld in missing_fields:
                if fld in _FIELD_HINTS:
                    print(f"   {fld}: {_FIELD_HINTS[fld]}")
            return None

        # Compuerta tecnica de la planificacion visual del texto (ver SKILL.md PASO 6.6):
        # valida no solo que existan los campos, sino que sus valores sean los permitidos.
        density = slide.get("text_density")
        if density not in _VALID_TEXT_DENSITIES:
            print(f"[ERROR] Error: slide {slide.get('number', '?')} tiene 'text_density' invalido: "
                  f"recibido {density!r}. "
                  f"Valores permitidos: {sorted(_VALID_TEXT_DENSITIES)}. "
                  f"Ejemplo valido: \"LOW\"")
            return None
        balance = slide.get("visual_balance")
        if balance not in _VALID_VISUAL_BALANCE:
            print(f"[ERROR] Error: slide {slide.get('number', '?')} tiene 'visual_balance' invalido: "
                  f"recibido {balance!r}. "
                  f"Valores permitidos: {sorted(_VALID_VISUAL_BALANCE)}. "
                  f"Ejemplo valido: \"balanced\"  (NO usar 'image_heavy' ni 'full_image')")
            return None
        word_count = slide.get("word_count")
        if not isinstance(word_count, int) or word_count <= 0:
            print(f"[ERROR] Error: slide {slide.get('number', '?')} tiene 'word_count' invalido: "
                  f"recibido {word_count!r} (tipo: {type(word_count).__name__}). "
                  f"Debe ser un entero positivo. Ejemplo: 9  (contar palabras de exact_text)")
            return None

    densities = [s["text_density"] for s in slides]
    for i in range(len(densities) - 2):
        if densities[i] == densities[i + 1] == densities[i + 2] == "HIGH":
            slide_nums = [slides[i]["number"], slides[i + 1]["number"], slides[i + 2]["number"]]
            print(f"[WARN] Advertencia: los slides {slide_nums} son HIGH consecutivos (ver SKILL.md PASO 6.6, "
                  f"'Evitar HIGH, HIGH, HIGH en slides consecutivos'). No bloquea la generación, pero "
                  f"se recomienda redistribuir el corte antes de continuar.")

    first_slide_flags = [s["number"] for s in slides if s.get("uses_reference_image_directly")]
    if first_slide_flags != [1] and 1 in [s["number"] for s in slides]:
        print(f"[WARN] Advertencia: 'uses_reference_image_directly' debería ser true únicamente en el slide 1 "
              f"(actualmente: {first_slide_flags})")

    mockup_slide_flags = [s["number"] for s in slides if s.get("uses_product_mockup_directly")]
    if mockup_slide_flags and not brief.get("product_mockup"):
        print(f"[WARN] Advertencia: los slides {mockup_slide_flags} tienen 'uses_product_mockup_directly': true "
              f"pero brief.json no tiene un bloque 'product_mockup' de nivel raiz con la ruta del mockup.")

    product_block = brief.get("product") or {}
    if product_block.get("product_name") and not product_block.get("purchase_url"):
        print(f"[WARN] Advertencia: el producto '{product_block['product_name']}' no tiene 'purchase_url' "
              f"en brief.json. Esto NO bloquea la generacion de imagenes, pero el paquete final "
              f"(--add-copy) rechazara guardarse hasta resolver el enlace (products.json o preguntar "
              f"al usuario) — ver SKILL.md PASO 10.1.")

    print(f"   [OK] Brief cargado: {len(slides)} slides, formato '{brief['carousel_type']}'")
    return brief


def detect_tools_in_text(text: str) -> List[str]:
    """Detecta menciones de herramientas/apps en el texto."""
    tools_keywords = {
        "n8n": ["n8n", "n8n.io"],
        "chatgpt": ["chatgpt", "chat gpt", "gpt"],
        "claude": ["claude", "claude ai"],
        "make": ["make", "make.com", "integromat"],
        "whatsapp": ["whatsapp", "whatsapp business"],
        "zapier": ["zapier"],
        "anthropic": ["anthropic"],
        "openai": ["openai"],
    }

    found_tools = []
    text_lower = text.lower()

    for tool, keywords in tools_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                if tool not in found_tools:
                    found_tools.append(tool)
                break

    return found_tools


def detect_entities_in_slides(slides: List[Dict]) -> Dict[int, List[str]]:
    """
    Detecta entidades (herramientas, empresas, temas) en cada slide.
    Espera dicts con al menos 'number', 'title', 'content'.

    Returns:
        Dict mapping slide number to list of detected entities
    """
    entities_by_slide = {}

    KNOWN_ENTITIES = {
        'openclaw': ['openclaw', 'open claw', 'clawdbot', 'moltbot'],
        'peter-steinberger': ['peter steinberger', 'steipete', 'pspdfkit'],
        'seedance': ['seedance', 'bytedance', 'seed dance'],
        'tiktok': ['tiktok'],
        'disney': ['disney', 'hollywood'],
        'tom-cruise': ['tom cruise', 'brad pitt'],
        'chatgpt': ['chatgpt', 'gpt', 'openai'],
        'claude': ['claude', 'anthropic'],
        'gemini': ['gemini', 'google ai', 'bard'],
        'n8n': ['n8n'],
        'whatsapp': ['whatsapp'],
        'zapier': ['zapier'],
        'make': ['make', 'integromat'],
        'midjourney': ['midjourney'],
        'eu': ['eu ', 'european union', 'europa'],
        'ai act': ['ai act', 'regulatory'],
    }

    for slide in slides:
        slide_num = slide['number']
        slide_text = f"{slide.get('title', '')} {slide.get('content', '')}".lower()

        detected = []
        for entity, keywords in KNOWN_ENTITIES.items():
            if any(keyword in slide_text for keyword in keywords):
                detected.append(entity)

        if detected:
            entities_by_slide[slide_num] = detected

    return entities_by_slide


def format_visual_dna_block(visual_dna: Dict[str, Any]) -> str:
    """
    Renderiza el ADN visual estructurado como bloque de texto para el prompt.
    Este bloque se inyecta igual en TODOS los slides para garantizar coherencia real
    (no es una frase generica de estilo, es el analisis concreto de la referencia).

    Cuando el brief incluye 'slide_1_master_dna' (el ADN maestro fijado por el Slide 1
    ya generado), ese bloque se renderiza PRIMERO y con prioridad explicita: es la fuente
    de verdad operativa para los slides 2+. El resto de campos (paleta_colores, tipografia,
    etc.) son el analisis original de la referencia y siguen sirviendo de contexto/respaldo,
    pero el master DNA manda en caso de conflicto.
    """
    lines = []

    master = visual_dna.get("slide_1_master_dna")
    if master:
        lines.append(
            "ADN VISUAL MAESTRO (fijado por el Slide 1 YA GENERADO de este carrusel — "
            "TIENE PRIORIDAD sobre cualquier otro dato de estilo de mas abajo):"
        )
        lines.append(f"- Tipo de imagen/tratamiento: {master.get('image_treatment', '')}")
        lines.append(f"- Tratamiento de color: {master.get('color_treatment', '')}")
        dominant_tones = master.get('dominant_tones', []) or []
        lines.append(f"- Tonos dominantes: {', '.join(dominant_tones) if dominant_tones else ''}")
        accent = master.get('accent_color', '')
        accent_source = master.get('accent_color_source', '')
        lines.append(f"- Color de acento EXACTO: {accent}" + (f" ({accent_source})" if accent_source else ""))
        lines.append(f"- Perfil de contraste: {master.get('contrast_profile', '')}")
        lines.append(f"- Perfil de luminosidad: {master.get('luminosity_profile', '')}")
        lines.append(f"- Realismo fotográfico: {master.get('photographic_realism', '')}")
        lines.append(f"- Perfil de textura/grano: {master.get('texture_profile', '')}")
        lines.append(f"- Reglas de continuidad: {master.get('continuity_rules', '')}")
        lines.append("")

    source = visual_dna.get("source_reference_dna")
    if source:
        resumen = source.get("resumen", "") if isinstance(source, dict) else str(source)
        if resumen:
            lines.append(f"ADN ORIGINAL DE LA REFERENCIA (contexto, antes de convertirse en Slide 1): {resumen}")
            lines.append("")

    paleta = visual_dna.get("paleta_colores", {}) or {}
    tipografia = visual_dna.get("tipografia", {}) or {}
    recursos = visual_dna.get("recursos_graficos", []) or []

    lines += [
        "ADN VISUAL DETALLADO (analisis de respaldo; ante conflicto con el ADN MAESTRO de arriba, gana el maestro):",
        f"- Paleta de colores: dominantes {paleta.get('dominantes', [])}, "
        f"acentos {paleta.get('acentos', [])}, fondo '{paleta.get('fondo', '')}'",
        f"- Tratamiento tipográfico: {tipografia.get('tratamiento', '')} "
        f"(peso: {tipografia.get('peso', '')}, estilo: {tipografia.get('estilo', '')})",
        f"- Tipo de imagen/ilustración: {visual_dna.get('tipo_imagen', '')}",
        f"- Composición base: {visual_dna.get('composicion_base', '')}",
        f"- Jerarquía visual: {visual_dna.get('jerarquia_visual', '')}",
        f"- Tratamiento de personajes/objetos: {visual_dna.get('tratamiento_personajes_objetos', '')}",
        f"- Textura: {visual_dna.get('textura', '')}",
        f"- Iluminación: {visual_dna.get('iluminacion', '')}",
        f"- Márgenes: {visual_dna.get('margenes', '')}",
        f"- Recursos gráficos: {', '.join(recursos) if recursos else 'ninguno específico'}",
    ]
    return "\n".join(lines)


GLOBAL_DESIGN_RULES = """
REGLAS DE DISEÑO OBLIGATORIAS (aplican a TODOS los carruseles generados por este sistema):

ORDEN DE PRIORIDAD: cuando exista conflicto entre el ADN VISUAL MAESTRO del Slide 1 (arriba)
y una instrucción genérica de estas reglas, GANA el ADN del Slide 1 — es el que decide si el
carrusel es B&N, a color, cálido, frío, ilustrado, etc., y con qué tratamiento fotográfico.
La ÚNICA excepción son las reglas ESTRUCTURALES obligatorias de este bloque, que nunca se
saltan pase lo que pase: legibilidad del texto, máximo 2 familias tipográficas, Poppins
obligatoria, máximo 2 colores de texto, jerarquía tipográfica de 3 niveles, y uso directo
(sin reinventar) de cualquier mockup de producto proporcionado por el usuario.

1. LUMINOSIDAD (coherente con el Slide 1, no forzada): la imagen no debe quedar oscura o
   subexpuesta SIN RAZÓN visual. Si el ADN maestro del Slide 1 indica un tratamiento oscuro
   y dramático de forma deliberada, los slides 2+ pueden conservar esa profundidad y
   dramatismo — pero deben seguir siendo legibles (texto con contraste suficiente, sin
   perderse en zonas negras). Si el Slide 1 es luminoso, los slides 2+ NO deben volverse
   oscuros sin motivo. En cualquier caso, evita SIEMPRE: subexposición accidental, exceso de
   vignette no presente en el Slide 1, y texto perdido en zonas oscuras. El objetivo es
   luminosidad coherente con el Slide 1 + contraste suficiente para leer + sin subexposición
   innecesaria — nunca "aclarar todo" de forma artificial ni "oscurecer todo" por defecto.

2. TRATAMIENTO DE IMAGEN Y COLOR (lo determina el Slide 1, nunca un default): NO conviertas
   automáticamente el carrusel a blanco y negro solo porque la referencia sea editorial, ni
   fuerces color si el Slide 1 es B&N. El tipo de imagen de los slides 2+ (B&N puro, B&N con
   acento(s), color desaturado, color cinematográfico cálido/frío, color estándar, o
   ilustrado/gráfico) es SIEMPRE el mismo que determina el ADN maestro del Slide 1.

3. REALISMO FOTOGRÁFICO OBLIGATORIO: si la referencia es fotografía real, TODOS los slides
   deben tener apariencia de fotografía tomada con cámara real.
   OBLIGATORIO:
   ✓ Textura de piel natural visible (poros, imperfecciones sutiles — no piel suavizada)
   ✓ Asimetría facial humana natural (los rostros reales no son perfectamente simétricos)
   ✓ Cabello con hebras individuales visibles, no masa perfecta homogénea
   ✓ Ojos humanos sin brillo "glassy" ni reflejos perfectamente artificiales
   ✓ Manos anatómicamente correctas y naturales
   ✓ Iluminación con dirección física coherente (una fuente principal, sombras que la siguen)
   ✓ Profundidad de campo realista para el encuadre elegido
   ✓ Grano/textura fotográfica coherente con la referencia
   ✓ Sensación documental/editorial: parece una foto, no un render
   PROHIBIDO (si la referencia no es ilustración):
   ✗ Piel plástica, encerada o suavizada artificialmente
   ✗ Simetría facial perfecta (señal directa de generación IA)
   ✗ Ojos con reflejos perfectos o brillo "glassy" artificial
   ✗ Aspecto CGI, render 3D o arte digital evidente
   ✗ Ilustración, pintura o diseño gráfico
   ✗ HDR excesivo o post-proceso artificial
   ✗ Iluminación de estudio genérica no presente en la referencia
   ✗ Stock photography genérica sin personalidad visual
   La excepción: si la referencia viral es explícitamente ilustrada o gráfica, los slides
   siguen ese mismo lenguaje (ilustración coherente, no fotografía).

4. CONTINUIDAD REAL DE TONOS (no solo paleta nominal): busca continuidad real en temperatura
   de color, contraste, exposición, saturación, profundidad de negros, luminosidad, textura,
   tratamiento de piel, tratamiento de sombras y luces, ambiente, grano y sensación
   fotográfica general — los slides 2+ deben parecer fotografías tomadas dentro de la misma
   dirección artística que el Slide 1, nunca una mezcla de tratamientos (uno cálido, otro
   frío, otro sepia, otro B&N sin razón).

5. PALETA DE TEXTO (regla estructural, sin excepción): usa como máximo DOS colores de texto
   en todo el slide — BLANCO y el COLOR DE ACENTO fijado en el ADN maestro.
   DISTRIBUCIÓN OBLIGATORIA: ~80% del texto en BLANCO (desarrollo, cuerpo, explicaciones,
   texto secundario) y MÁXIMO 20% en COLOR DE ACENTO (solo palabras o frases aisladas de
   énfasis real: hooks cortos, conceptos clave puntuales, máximo 1-3 palabras por línea de
   énfasis). NUNCA párrafos completos en color de acento. NUNCA el color de acento como
   color dominante del slide. NUNCA más del 20% del texto total en acento. Si no hay énfasis
   realmente importante en el slide, usar 100% BLANCO es correcto y preferible. El color de
   elementos de la fotografía/escena/producto (ej. una flor amarilla) no es texto y no
   cuenta para este límite.

6. TIPOGRAFÍA (regla estructural, sin excepción): máximo DOS familias tipográficas en total.
   Una de ellas DEBE ser POPPINS y debe usarse realmente en el slide (nunca solo mencionarse).
   La segunda familia es la que mejor armonice con el ADN visual del Slide 1. Nunca tres o más
   familias. Varía peso, tamaño, mayúsculas/minúsculas, cursiva, tracking e interlineado
   dentro de esas 2 familias únicamente.

7. JERARQUÍA TIPOGRÁFICA (regla estructural, obligatoria, debe percibirse en menos de un
   segundo):
   - NIVEL 1 (hook/idea principal): mayor tamaño, mayor peso, máximo contraste.
   - NIVEL 2 (desarrollo): tamaño intermedio, explica o desarrolla el Nivel 1.
   - NIVEL 3 (apoyo): tamaño menor, solo si el slide lo necesita.
   Nunca todos los textos del slide con el mismo tamaño/peso/importancia. Diseña para móvil:
   tamaño y contraste suficientes, márgenes seguros, interlineado adecuado, sin comprimir
   texto en bloques pequeños e ilegibles. El texto es prioritario sobre el encuadre completo
   de la fotografía — si hace falta oscurecer o recortar parcialmente la imagen para ganar
   legibilidad, se hace; nunca se reduce el texto para que "quepa".
"""


IMAGE_ROLE_INSTRUCTIONS = {
    "reference": """
INSTRUCCIÓN CLAVE - IMAGEN ADJUNTA {tag}: REFERENCIA VIRAL ORIGINAL — MÁXIMA PRIORIDAD
(Slide 1 únicamente):
Esta imagen es la referencia visual definitiva del carrusel completo. El Slide 1 DEBE:
▸ REPRODUCIR FIELMENTE: sujeto principal, pose, expresión facial, tipo de encuadre,
  distancia cámara-sujeto, dirección y calidad de luz, temperatura de color, profundidad de
  campo, nivel de grano/textura fotográfica, tratamiento de piel, tratamiento de cabello,
  relación sujeto/fondo, atmósfera emocional y sensación general de cámara real.
▸ SER FOTOGRAFÍA REAL: textura de piel natural con poros e imperfecciones visibles
  (exactamente como en la referencia), asimetría facial humana natural, hebras de cabello
  individuales visibles, ojos sin brillo "glassy" artificial, manos anatómicamente
  naturales, iluminación físicamente coherente con una fuente de luz real, sombras que
  caigan según esa dirección de luz, profundidad de campo realista según el encuadre.
▸ PROHIBIDO si la referencia es fotografía real: piel plástica o suavizada artificialmente,
  simetría facial perfecta (señal de IA), ojos con reflejos perfectos artificiales, aspecto
  CGI, render 3D, ilustración o arte digital, post-proceso HDR excesivo, iluminación de
  estudio genérica sin presencia en la referencia, stock photography genérica.
El TEXTO EXACTO especificado arriba ES el texto — no lo sustituyas, parafrasees ni
reinterpretes. Reproduce el texto tal cual, sin crear otro.
La ÚNICA adaptación permitida es un ajuste MÍNIMO de luminosidad/contraste ambiental
(si es necesario para la legibilidad del texto) — nunca alterar la identidad, apariencia
física ni el tipo fotográfico del sujeto principal.
""",
    "anchor": """
INSTRUCCIÓN CLAVE - IMAGEN ADJUNTA {tag}: SLIDE 1 REAL DE ESTE CARRUSEL (ANCLA VISUAL
MAESTRA — no es una referencia externa, es el Slide 1 YA GENERADO de este mismo carrusel):
Reproduce su mismo tratamiento fotográfico REAL: temperatura de color, contraste,
exposición, saturación, profundidad de negros, luminosidad, grano/textura fotográfica,
tratamiento de piel y sombras, tipo de imagen (B&N/color/ilustración) y atmósfera
emocional — continuidad REAL, no solo una paleta nominal parecida. Este slide debe
sentirse fotografiado dentro de la MISMA dirección artística que esa imagen.
NO copies su escena, sujeto, pose ni composición exacta — crea una escena y composición
NUEVAS, adecuadas al rol narrativo de ESTE slide, dentro del mismo lenguaje visual.
Si esa imagen es fotografía realista, este slide TAMBIÉN debe ser fotografía hiperrealista:
piel y cabello naturales (sin suavizado artificial, con textura real visible), iluminación
físicamente plausible, asimetría facial natural, profundidad de campo realista, grano
fotográfico coherente — nunca piel plástica, aspecto CGI, render 3D, ilustración ni arte
digital evidente, salvo que el ancla sea explícitamente ilustrada/gráfica.
Ante cualquier conflicto entre esta ancla y una instrucción genérica de estilo, esta ancla
tiene PRIORIDAD — excepto sobre las reglas estructurales obligatorias (legibilidad, máximo
2 familias tipográficas, Poppins obligatoria, máximo 2 colores de texto, jerarquía
tipográfica, uso directo de mockups de producto), que nunca se saltan.
""",
    "viral_context": """
INSTRUCCIÓN CLAVE - IMAGEN ADJUNTA {tag}: REFERENCIA VIRAL ORIGINAL (contexto fotográfico
para continuidad — NO copies su escena):
Esta es la imagen viral original que define el ADN fotográfico de todo el carrusel.
ÚSALA para mantener el nivel de realismo fotográfico: mismo tipo de fotografía (real vs.
ilustrada), misma calidad de luz, mismo tratamiento de piel y cabello, misma sensación de
"cámara real" (grano, profundidad de campo, imperfecciones naturales), misma temperatura
emocional fotográfica.
NO copies su escena, sujeto ni composición — crea una escena nueva para el rol narrativo
de ESTE slide, pero dentro del mismo universo fotográfico real definido por esa imagen.
Si esa imagen es fotografía real, ESTE slide también debe ser fotografía real e hiperrealista.
""",
    "mockup": """
INSTRUCCIÓN CLAVE - IMAGEN ADJUNTA {tag}: MOCKUP DE PRODUCTO ORIGINAL (provisto por el
usuario):
Este slide debe mostrar el producto EXACTAMENTE como aparece en esta imagen. Reproduce
fielmente su diseño de portada/cubierta: tipografía, textos, colores, proporciones y
composición del mockup real. NO inventes una portada genérica, NO rediseñes la cubierta,
NO cambies ni ocultes su texto o arte original, NO sustituyas el mockup por una versión
propia. Intégralo dentro de una escena y composición nuevas, coherentes con el resto del
carrusel — el producto en sí es SIEMPRE el real del mockup adjunto, nunca una recreación.
""",
    "logo": """
INSTRUCCIÓN CLAVE - IMAGEN ADJUNTA {tag}: LOGO/ICONO REAL:
Coloca este logo tal cual, sin redibujarlo ni cambiar su forma o color, integrado de forma
natural en la composición del slide.
""",
}

_FALLBACK_NO_ANCHOR_INSTRUCTIONS = """
INSTRUCCIÓN CLAVE - SLIDE SIN IMAGEN DE ANCLAJE DISPONIBLE (caso excepcional):
No hay ninguna imagen de referencia ni ancla visual adjunta para este slide. Usa el ADN
visual descrito en texto abajo (especialmente 'ADN VISUAL MAESTRO' si está presente) con la
máxima fidelidad posible para que este slide se sienta parte del mismo carrusel. Crea una
escena y composición nuevas — no copies la escena del slide 1.
"""


def build_prompt_for_slide(
    slide: Dict[str, Any],
    visual_dna: Dict[str, Any],
    carousel_type: str,
    attached_images: Optional[List[str]] = None,
) -> str:
    """
    Construye el prompt de generacion para un slide a partir de sus campos narrativos
    (definidos en brief.json) y el ADN visual estructurado de la referencia.

    `attached_images` describe, EN ORDEN, el rol de cada imagen que se envia junto a este
    prompt (ej. ["anchor", "mockup"]). Cada rol tiene su propia instruccion (ver
    IMAGE_ROLE_INSTRUCTIONS) para que el modelo sepa que hacer con cada imagen adjunta
    especifica, en vez de una sola instruccion generica.

    Identico sin importar el proveedor (Kie o Gemini) — el prompt de texto no cambia, solo
    cambia el mecanismo de transporte de las imagenes adjuntas (URL publica para Kie, bytes
    inline para Gemini), que resuelve cada proveedor por separado.
    """
    attached_images = attached_images or []

    header = (
        f"Instagram carousel slide (1080x1350px, ratio 4:5).\n"
        f"Formato de carrusel: {carousel_type}.\n"
        f"Slide numero {slide.get('number')} de la secuencia.\n"
    )

    key_elements = slide.get("key_visual_elements", []) or []

    _narr_header = f"ROL NARRATIVO: {slide.get('role', '')}"
    if slide.get("narrative_objective"):
        _narr_header += f"\nOBJETIVO NARRATIVO: {slide['narrative_objective']}"
    if slide.get("message"):
        _narr_header += f"\nMENSAJE A COMUNICAR: {slide['message']}"

    narrative = f"""
{_narr_header}

TEXTO EXACTO QUE DEBE APARECER EN LA IMAGEN (escribirlo tal cual, sin parafrasear):
"{slide.get('exact_text', '')}"

REGLA CRITICA SOBRE ESE TEXTO (hallazgo real de produccion, 2026-09-18 — leer con
atencion, se ha visto fallar en imagenes reales):
1. Ese es el UNICO texto que debe quedar legible en la imagen, de principio a fin, en
   ese mismo orden, sin mover ninguna frase, sin repetirla en otro lugar y sin agregar
   un titular nuevo con una frase que ya esta en el medio o el final del texto. NUNCA
   dupliques ninguna palabra/frase (ej. nunca "suelen suelen", nunca un titular arriba
   que repite una frase que ya aparece mas abajo en el mismo texto).
2. Las secciones de mas abajo (DESCRIPCIÓN, COMPOSICIÓN, JERARQUÍA VISUAL, UBICACIÓN DEL
   TEXTO) son instrucciones internas para vos, el generador, sobre COMO construir la
   escena — jamas son texto a renderizar. Ninguna palabra o frase de esas secciones
   (ej. "espacio visual", "overlay oscuro", nombres de niveles) debe aparecer escrita,
   ni siquiera parcialmente o entre corchetes, dentro de la imagen final.
3. La JERARQUÍA VISUAL de abajo (Nivel 1/Nivel 2/Nivel 3) es UNICAMENTE una instruccion
   de enfasis (tamaño, peso, color) sobre una frase que YA esta en su posicion original
   dentro del texto exacto de arriba — aplica ese enfasis EN EL LUGAR donde esa frase ya
   aparece. Nunca uses el Nivel 1 como excusa para mover esa frase al principio de la
   imagen, ni para repetirla como si fuera un titular separado.

DESCRIPCIÓN CONCRETA DE LA ESCENA/IMAGEN (instruccion para vos, nunca texto a renderizar):
{slide.get('scene_description', '')}

COMPOSICIÓN (instruccion para vos, nunca texto a renderizar):
{slide.get('composition', '')}

JERARQUÍA VISUAL (instruccion de enfasis EN EL LUGAR, ver regla 3 arriba — nunca texto a renderizar):
{slide.get('visual_hierarchy', '')}

UBICACIÓN DEL TEXTO (instruccion para vos, nunca texto a renderizar):
{slide.get('text_placement', '')}

ELEMENTOS VISUALES IMPORTANTES:
{', '.join(key_elements) if key_elements else 'ninguno adicional especificado'}
"""

    connections = ""
    if slide.get("connects_prev"):
        connections += f"\nCONEXIÓN CON EL SLIDE ANTERIOR: {slide['connects_prev']}"
    if slide.get("connects_next"):
        connections += f"\nCONEXIÓN CON EL SLIDE SIGUIENTE: {slide['connects_next']}"

    dna_block = format_visual_dna_block(visual_dna)
    _vc = slide.get("visual_dna_connection", "")
    dna_connection = f"\nCÓMO ESTE SLIDE MANTIENE EL ADN VISUAL: {_vc}" if _vc else ""

    if attached_images:
        blocks = []
        for idx, role in enumerate(attached_images, start=1):
            template = IMAGE_ROLE_INSTRUCTIONS.get(role)
            if template:
                tag = f"#{idx} de {len(attached_images)}"
                blocks.append(template.format(tag=tag))
        reference_instructions = "\n".join(blocks) if blocks else _FALLBACK_NO_ANCHOR_INSTRUCTIONS
    else:
        reference_instructions = _FALLBACK_NO_ANCHOR_INSTRUCTIONS

    safety = "\nNO watermark, NO username, NO texto de branding genérico agregado por tu cuenta."

    return (
        header + narrative + connections + "\n\n" + dna_block + dna_connection + "\n"
        + reference_instructions + "\n" + GLOBAL_DESIGN_RULES + safety
    )


def generate_assets_needed_md(bundle_id: str, bundle_path: Path, slides_for_detection: List[Dict], tool_detections: Dict[int, List[str]]):
    """Genera archivo carousel-assets-needed.md con guía de logos opcionales (independiente del ADN visual)."""

    assets_file = bundle_path / "carousel" / "carousel-assets-needed.md"

    slides_with_opportunities = []

    for slide in slides_for_detection:
        slide_num = slide["number"]
        tools = tool_detections.get(slide_num, [])

        if tools:
            slides_with_opportunities.append({
                "slide": slide,
                "tools": tools
            })

    if not slides_with_opportunities:
        content = f"""# Guía de Logos Opcionales para Carrusel Instagram

**Bundle:** {bundle_id}
**Total slides:** {len(slides_for_detection)}
**Generado:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## [STATS] Resumen

No se detectaron menciones claras de herramientas específicas que requieran logos.
El carrusel usa el ADN visual detectado de la imagen de referencia, sin logos adicionales.

[OK] **Listo para publicar tal como se generó.**

Si en el futuro quieres agregar logos reales de herramientas específicas,
puedes usar la regeneración con el comando `--regenerate-slides`.
"""
    else:
        tool_list = ", ".join(sorted(set([t for item in slides_with_opportunities for t in item["tools"]])))

        content = f"""# Guía de Logos Opcionales para Carrusel Instagram

**Bundle:** {bundle_id}
**Total slides:** {len(slides_for_detection)}
**Herramientas detectadas:** {tool_list}
**Generado:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

## [STATS] Resumen

Se detectaron {len(slides_with_opportunities)} slides que mencionan herramientas específicas.
Esto es completamente OPCIONAL y no afecta el ADN visual del carrusel (que viene de la
imagen de referencia). Solo agrega logos si:

- Tienes logos oficiales de alta calidad
- Quieres reforzar el reconocimiento de una herramienta mencionada

---

## [TARGET] Workflow: Agregar Logos y Regenerar

### Paso 1: Conseguir Logos

"""
        unique_tools = sorted(set([t for item in slides_with_opportunities for t in item["tools"]]))
        for tool in unique_tools:
            content += f"""**{tool.title()}:**
- Formato: PNG con fondo transparente
- Tamaño: 512x512px o mayor
- Guardar como: `/carousel/assets/{tool}-logo.png`

"""

        content += f"""### Paso 2: Regenerar Slides

```bash
python3 scripts/generate-carousel-gemini.py "{bundle_id}" --regenerate-slides "NUMEROS"
```

## [TOOLS] Slides Sugeridos para Regenerar

"""

        for item in slides_with_opportunities:
            slide = item["slide"]
            tools = item["tools"]

            content += f"""**Slide {slide["number"]} - {slide["title"]}:**
- Herramienta: {", ".join(tools)}
- Asset sugerido: {tools[0]}-logo.png

"""

    with open(assets_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"   [OK] Guía de logos guardada: {assets_file.name}")


def generate_manifest(
    bundle_id: str,
    carousel_dir: Path,
    slides_generated: List[Dict],
    carousel_type: str,
    slide_count_confirmed: int,
    reference_image_filename: str,
    extra_fields: Optional[Dict[str, Any]] = None,
):
    """
    Genera manifest.json con metadata de la generación.

    `extra_fields` permite que un generador especifico (ej. Gemini economico) agregue
    campos adicionales (proveedor, modelo, modo, costo) sin duplicar esta funcion — se
    fusionan al nivel raiz del manifest, nunca pisan las claves ya definidas aqui.
    """
    manifest = {
        "success": True,
        "bundle_id": bundle_id,
        "generated_at": datetime.now().isoformat(),
        "carousel_type": carousel_type,
        "slide_count_confirmed": slide_count_confirmed,
        "reference_image": reference_image_filename,
        "total_slides": len(slides_generated),
        "carousel": slides_generated
    }
    if extra_fields:
        for key, value in extra_fields.items():
            manifest.setdefault(key, value)

    manifest_file = carousel_dir / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"   [OK] Manifest generado: manifest.json")


def build_para_facebook_folder(carousel_dir: Path) -> Optional[Path]:
    """
    Crea (o refresca) `carousel/PARA FACEBOOK/` con una COPIA de cada `carousel-NN.png`
    actual, renombrada como `NN_SLIDE.png` con ceros a la izquierda (01_SLIDE.png,
    02_SLIDE.png, ..., hasta la cantidad real de slides — nunca un numero fijo). Regla
    GENERAL y PERMANENTE del skill: se genera para CUALQUIER carrusel futuro, sin importar
    tematica, formato, cantidad de slides o proveedor de generacion (Kie o Gemini).

    Motivo: Windows Explorer respeta el orden `carousel-01.png ... carousel-NN.png` al
    ordenar por Nombre, pero al ordenar por Fecha de modificacion (vista tambien muy
    comun) el orden puede salir distinto — y ese mismo `mtime` es lo que un navegador o
    Meta Business Suite pueden terminar usando para decidir en que orden entregan/
    procesan los archivos seleccionados. Se confirmo el caso real: los `carousel-NN.png`
    se generan EN PARALELO, asi que su `mtime` original refleja el orden de finalizacion
    de cada descarga (no-determinista), NO el orden narrativo — por ejemplo
    `carousel-03.png` puede tener un `mtime` anterior al de `carousel-02.png`. Por eso
    esta funcion NUNCA hereda el `mtime` original: lo reemplaza por una marca de tiempo
    sintetica y estrictamente creciente (indice 1, 2, 3...) para que ordenar por Nombre
    O por Fecha de modificacion de siempre el mismo resultado narrativo correcto.

    Aun asi, esta carpeta NO garantiza el orden final con el que Facebook/Meta procesa o
    muestra la subida una vez que los archivos salen de este sistema de archivos (el
    selector del sistema operativo, el navegador y el propio Meta Business Suite son
    capas fuera del control de carousel-gen) — ver PASO de verificacion en SKILL.md.

    NUNCA modifica, recomprime, redimensiona, recorta ni regenera el CONTENIDO de ninguna
    imagen — el contenido de pixeles es una copia binaria exacta de `carousel-NN.png`;
    solo se normaliza el metadato de fecha del archivo copiado. La correspondencia de
    contenido es siempre exacta: carousel-01.png -> 01_SLIDE.png, etc.
    """
    slide_files = sorted(carousel_dir.glob("carousel-*.png"))
    if not slide_files:
        return None

    fb_dir = carousel_dir / "PARA FACEBOOK"
    fb_dir.mkdir(exist_ok=True)

    # Limpiar restos de una corrida anterior con una cantidad distinta de slides (p.ej.
    # tras --regenerate-slides que cambio el total), para que la carpeta siempre refleje
    # unicamente el estado actual del carrusel, sin sobrantes de un conteo previo.
    for old_file in fb_dir.glob("*_SLIDE.png"):
        old_file.unlink()

    width = max(2, len(str(len(slide_files))))
    # Base sintetica: "ahora" mas 1 segundo por indice narrativo, para que 01_SLIDE.png
    # siempre tenga el mtime mas antiguo y NN_SLIDE.png el mas reciente, sin importar el
    # mtime original (scrambleado por la generacion en paralelo) de los carousel-NN.png.
    base_ts = time.time()
    for idx, slide_file in enumerate(slide_files, start=1):
        dest_file = fb_dir / f"{idx:0{width}d}_SLIDE.png"
        shutil.copy(slide_file, dest_file)  # copia binaria exacta, SIN heredar metadata
        synthetic_ts = base_ts + idx
        os.utime(dest_file, (synthetic_ts, synthetic_ts))

    print(f"   [OK] {len(slide_files)} copias preparadas en 'PARA FACEBOOK/' con fecha "
          f"secuencial normalizada "
          f"({1:0{width}d}_SLIDE.png … {len(slide_files):0{width}d}_SLIDE.png)")
    return fb_dir


def export_final_slides_to_downloads(
    bundle_id: str, bundle_path: Path, carousel_dir: Path,
) -> Optional[Path]:
    """
    Copia (nunca mueve) el PAQUETE FINAL de un carrusel a la carpeta de Descargas de
    Windows, dentro de una subcarpeta propia nombrada con el bundle_id (ya es un slug
    limpio: minusculas, sin acentos, con guiones — ver generacion de bundle_id en
    SKILL.md PASO 7). Regla GENERAL y PERMANENTE del skill: se ejecuta al final de
    CUALQUIER generacion (o regeneracion parcial) de CUALQUIER carrusel futuro, sin
    importar el proveedor de generacion, y de nuevo al final de --add-copy.

    Paquete final = todos los `carousel-NN.png` presentes (cualquier cantidad, nunca un
    numero fijo) + `COPY_FINAL.txt` + `carousel/manifest.json` + `brief.json` +
    `COSTO_CARRUSEL.txt` — estos archivos sueltos se copian solo si ya existen en el
    bundle. REGLA PERMANENTE: ya NO se copian `description.txt`, `cta.txt` ni
    `hashtags.txt` ni se genera `PARA FACEBOOK/` — la carpeta PARA FACEBOOK quedo
    eliminada del paquete de produccion (PROHIBIDO recrearla aqui).

    NUNCA copia `carousel-assets-needed.md`, la carpeta `assets/` (referencias/mockups),
    archivos internos de cache/costos (`.generation_cache.json`, `.batch_state.json`,
    `cost_log.json`), ni ningun otro archivo interno o temporal de generacion. El bundle
    original en outputs/bundles/[bundle_id]/ nunca se mueve ni se reemplaza; Descargas es
    siempre una COPIA de los archivos listos para publicar (nunca se modifica `brief.json`
    al copiarlo — es copia binaria exacta, igual que el resto).
    """
    try:
        DOWNLOADS_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        dest_dir = DOWNLOADS_EXPORT_DIR / bundle_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Cualquier cantidad de slides finales presentes ahora mismo en el bundle (7, 9,
        # o los que sean) — nunca se asume un numero fijo.
        slide_files = sorted(carousel_dir.glob("carousel-*.png"))
        if not slide_files:
            print(f"   [WARN] No hay slides finales (carousel-NN.png) que copiar a Descargas todavia")
            return None

        # Igual que en build_para_facebook_folder: NO se hereda el mtime original
        # (scrambleado por la generacion en paralelo) — se normaliza a una marca de tiempo
        # sintetica y estrictamente creciente por orden narrativo, para que ordenar esta
        # carpeta por Nombre o por Fecha de modificacion de el mismo resultado. El
        # contenido sigue siendo una copia binaria exacta.
        base_ts = time.time()
        for idx, slide_file in enumerate(slide_files, start=1):
            dest_slide = dest_dir / slide_file.name
            shutil.copy(slide_file, dest_slide)
            synthetic_ts = base_ts + idx
            os.utime(dest_slide, (synthetic_ts, synthetic_ts))

        # Entregables adicionales del paquete final (lista fija, nunca archivos internos
        # como assets/ o carousel-assets-needed.md). El copy de publicacion es UNICAMENTE
        # COPY_FINAL.txt (regla permanente) — description.txt/cta.txt/hashtags.txt ya no
        # se generan ni se copian.
        extra_deliverables = (
            (COPY_FINAL_FILENAME, bundle_path / COPY_FINAL_FILENAME),
            (COSTO_CARRUSEL_FILENAME, bundle_path / COSTO_CARRUSEL_FILENAME),
            ("manifest.json", carousel_dir / "manifest.json"),
            ("brief.json", bundle_path / "brief.json"),
        )
        copied_extra = []
        for extra_name, extra_source in extra_deliverables:
            if extra_source.exists():
                shutil.copy2(extra_source, dest_dir / extra_name)
                copied_extra.append(extra_name)

        print(f"   [OK] {len(slide_files)} slides copiados a Descargas: {dest_dir}")
        if copied_extra:
            print(f"   [OK] Entregables adicionales copiados: {', '.join(copied_extra)}")
        missing_extra = [n for n, p in extra_deliverables if n not in copied_extra]
        if missing_extra:
            print(f"   [WARN] Aun no copiados a Descargas (no existen todavia en el bundle): "
                  f"{', '.join(missing_extra)}")

        return dest_dir

    except Exception as e:
        print(f"   [WARN] No se pudo copiar el carrusel a Descargas: {e}")
        return None


def build_copy_final_text(
    description: str,
    cta: str,
    purchase_url: Optional[str],
    hashtags: List[str],
) -> str:
    """
    Construye el contenido de COPY_FINAL.txt con la estructura obligatoria y permanente
    del skill (ver SKILL.md, seccion "COPY_FINAL.txt — archivo unico de copy de
    publicacion"): DESCRIPCION, CTA, ENLACE DE COMPRA, HASHTAGS, en ese orden, cada una
    bajo un separador de 40 signos "=". La seccion ENLACE DE COMPRA usa exactamente
    `purchase_url` (o la leyenda explicita de que no hay producto asociado cuando es
    None) — nunca inventa ni normaliza la URL.
    """
    enlace = purchase_url.strip() if purchase_url else "(sin producto asociado en este carrusel)"
    sep = "=" * 40
    return (
        f"{sep}\n"
        f"DESCRIPCIÓN\n"
        f"{sep}\n\n"
        f"{description.strip()}\n\n"
        f"{sep}\n"
        f"CTA\n"
        f"{sep}\n\n"
        f"{cta.strip()}\n\n"
        f"{sep}\n"
        f"ENLACE DE COMPRA\n"
        f"{sep}\n\n"
        f"{enlace}\n\n"
        f"{sep}\n"
        f"HASHTAGS\n"
        f"{sep}\n\n"
        f"{' '.join(hashtags)}\n"
    )


def save_copy_deliverables(
    bundle_path: Path,
    description: str,
    cta: str,
    hashtags: List[str],
    product: Optional[str] = None,
    purchase_url: Optional[str] = None,
) -> None:
    """
    Guarda el copy de publicacion (descripcion, CTA emocional, enlace de compra,
    hashtags) de un carrusel YA GENERADO. Bloque PERMANENTE del skill (ver SKILL.md
    PASO 10) — se ejecuta despues de que los slides finales existen, usando contenido
    que Claude redacta a partir de brief.json (source_text, exact_text, product_mockup).
    Esta funcion NUNCA llama a ninguna API de generacion de imagenes, NUNCA toca
    carousel-NN.png ni brief.json, y NUNCA inventa `product`/`purchase_url` — si no hay
    producto asociado en el brief, se pasan como None y quedan null.

    REGLA PERMANENTE (ver SKILL.md): el copy de publicacion existe UNICAMENTE como
    `COPY_FINAL.txt` en la raiz del bundle. Ya NO se generan `description.txt`,
    `cta.txt` ni `hashtags.txt` como archivos independientes — esos tres archivos
    quedaron eliminados de la generacion futura (no se crean ni se sobrescriben aqui).

    Escribe en la raiz del bundle:
      - COPY_FINAL.txt (DESCRIPCIÓN + CTA + ENLACE DE COMPRA + HASHTAGS, unificado)
    Y fusiona (sin pisar el resto del manifest) estos campos en carousel/manifest.json:
      "description", "cta", "hashtags", "product", "purchase_url" (metadatos
      estructurados internos, se mantienen por utilidad) y "copy_final_file" (registra
      que el archivo fisico de publicacion es COPY_FINAL.txt).
    """
    bundle_path.mkdir(parents=True, exist_ok=True)

    copy_final_text = build_copy_final_text(description, cta, purchase_url, hashtags)
    (bundle_path / COPY_FINAL_FILENAME).write_text(copy_final_text, encoding="utf-8")

    carousel_dir = bundle_path / "carousel"
    carousel_dir.mkdir(exist_ok=True)
    manifest_file = carousel_dir / "manifest.json"

    if manifest_file.exists():
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {}

    manifest["description"] = description.strip()
    manifest["cta"] = cta.strip()
    manifest["hashtags"] = hashtags or []
    manifest["product"] = product
    manifest["purchase_url"] = purchase_url
    manifest["copy_final_file"] = COPY_FINAL_FILENAME

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"   [OK] {COPY_FINAL_FILENAME} guardado en {bundle_path}")
    print(f"   [OK] manifest.json actualizado con description/cta/hashtags/product/purchase_url/copy_final_file")


def _fmt_clock(iso_ts: Optional[str]) -> str:
    if not iso_ts:
        return "N/D"
    try:
        return datetime.fromisoformat(iso_ts).strftime("%H:%M:%S")
    except ValueError:
        return "N/D"


def _fmt_duration_between(start_iso: Optional[str], end_iso: Optional[str]) -> str:
    if not start_iso or not end_iso:
        return "N/D"
    try:
        start, end = datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso)
    except ValueError:
        return "N/D"
    total_seconds = max(0, int((end - start).total_seconds()))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes} min {seconds} sec"


def _fmt_phase_seconds(phase_seconds: Dict[str, Any], key: str) -> str:
    value = phase_seconds.get(key)
    if value is None:
        return "N/D"
    minutes, seconds = divmod(int(round(value)), 60)
    return f"{minutes} min {seconds} sec"


def _seconds_between(start_iso: Optional[str], end_iso: Optional[str]) -> Optional[float]:
    """Segundos reales entre dos timestamps ISO 8601, o None si falta cualquiera de
    los dos o no se puede parsear — nunca 0 por defecto (ver SKILL.md "CRONOMETRO
    GLOBAL REAL")."""
    if not start_iso or not end_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except ValueError:
        return None
    # Normalize: if one is tz-aware and the other is naive (local time), strip the
    # timezone offset from the aware one so both are compared as local-time values.
    if (start.tzinfo is None) != (end.tzinfo is None):
        start = start.replace(tzinfo=None)
        end = end.replace(tzinfo=None)
    return max(0.0, (end - start).total_seconds())


def _fmt_raw_seconds(value: Optional[float]) -> str:
    """Igual que _fmt_phase_seconds pero recibe el valor directamente (no un dict) —
    para total_wall_clock_seconds, que no vive en `phase_seconds`."""
    if value is None:
        return "N/D"
    minutes, seconds = divmod(int(round(value)), 60)
    return f"{minutes} min {seconds} sec"


def build_costo_carrusel_text(
    bundle_id: str,
    cost_summary: Dict[str, Any],
    model: str,
    resolution: str,
    aspect_ratio: str,
    slides_total: int,
    text_qa_block: Optional[Dict[str, Any]],
    final_bundle_path: str,
) -> str:
    """
    Construye el contenido de COSTO_CARRUSEL.txt (ver SKILL.md "FABRICA RAPIDA" /
    "COSTO_CARRUSEL.txt"): resumen de generacion, tokens, costo, eficiencia, tiempo y
    resultado de UN carrusel real. Todos los datos salen de `cost_summary` (el
    `to_dict()` de `cost_tracker.CostSummary` para ESTE bundle — nunca inventa un
    precio ni un tiempo) y de `text_qa_block` (bloque "text_qa" de manifest.json).
    Cualquier campo sin dato real disponible se imprime como "N/D" — regla obligatoria,
    nunca se rellena con un valor inventado.
    """
    entries = [e for e in cost_summary.get("entries", []) if e.get("bundle_id") == bundle_id]
    non_reused = [e for e in entries if not e.get("reused")]
    reused_slide_numbers = {e["slide_number"] for e in entries if e.get("reused")}

    attempts_by_slide: Dict[int, int] = {}
    for e in non_reused:
        attempts_by_slide[e["slide_number"]] = attempts_by_slide.get(e["slide_number"], 0) + 1

    success_statuses = {"APPROVED", "TEXT_QA_APPROVED", "COMPLETED"}
    generated_slide_numbers = {e["slide_number"] for e in non_reused if e.get("status") in success_statuses}
    regenerated_slide_numbers = {num for num, count in attempts_by_slide.items() if count > 1}
    total_real_generations = len(non_reused)
    retries_count = sum(1 for e in non_reused if (e.get("retry_count") or 0) > 0)
    any_failed_final = any(e.get("status") in ("FAILED_FINAL", "TEXT_QA_FAILED") for e in entries)

    input_tokens = output_tokens = 0
    any_usage = False
    for e in entries:
        usage = e.get("actual_usage")
        if usage:
            any_usage = True
            input_tokens += usage.get("prompt_token_count") or 0
            output_tokens += usage.get("candidates_token_count") or 0

    price_per_image = cost_summary.get("price_per_image_usd") or 0.0
    total_cost = cost_summary.get("estimated_cost_usd")
    cost_available = price_per_image > 0 and total_cost is not None
    regen_cost = round(price_per_image * retries_count, 4) if cost_available else None
    avg_cost_per_slide = round(total_cost / slides_total, 4) if (cost_available and slides_total > 0) else None

    covered_slides = len(generated_slide_numbers) + len(reused_slide_numbers)
    coverage_pct = round(covered_slides / slides_total * 100) if slides_total > 0 else None
    regen_pct = round(len(regenerated_slide_numbers) / slides_total * 100) if slides_total > 0 else None

    if text_qa_block is None:
        text_qa_result = "N/D (Text QA no se ejecuto en esta corrida)"
    elif text_qa_block.get("status") == "SKIPPED":
        text_qa_result = "N/D (Text QA omitido — OCR no disponible en este entorno)"
    elif text_qa_block.get("status") == "FAILED":
        text_qa_result = "PARTIAL" if generated_slide_numbers else "FAIL"
    else:
        text_qa_result = "PASS"
    qa_visual = "PARTIAL" if any_failed_final else "PASS"

    started_at = cost_summary.get("run_started_at")
    finished_at = cost_summary.get("run_finished_at")
    phase_seconds = cost_summary.get("phase_seconds") or {}
    # execution_* = timestamps FRESCOS de esta invocacion concreta (ver cost_tracker.py).
    # Se usan para "Duracion total" e "Inicio/Fin" en el reporte — nunca el run_started_at
    # historico, que puede ser de una sesion anterior muy distante en el tiempo.
    exec_started_at = cost_summary.get("execution_started_at") or started_at
    exec_finished_at = cost_summary.get("execution_finished_at") or finished_at

    def money(value: Optional[float]) -> str:
        return f"${value:.4f} USD" if value is not None else "N/D"

    def pct(value: Optional[float]) -> str:
        return f"{value}%" if value is not None else "N/D"

    sep = "=" * 50
    lines = [
        sep, "RESUMEN DE COSTO DEL CARRUSEL", sep, "",
        "Bundle:", bundle_id, "",
        "Fecha:", datetime.now().strftime("%Y-%m-%d"), "",
        "Modelo:", model, "",
        "Resolución:", resolution, "",
        "Formato:", aspect_ratio, "",
        "Slides:", str(slides_total), "",
        sep, "GENERACIÓN", sep, "",
        "Slides generados:", str(len(generated_slide_numbers)), "",
        "Slides reutilizados:", str(len(reused_slide_numbers)), "",
        "Slides regenerados:", str(len(regenerated_slide_numbers)), "",
        "Total de generaciones reales:", str(total_real_generations), "",
        "Retries:", str(retries_count), "",
        sep, "TOKENS", sep, "",
        "Input tokens:", str(input_tokens) if any_usage else "N/D", "",
        "Output tokens:", str(output_tokens) if any_usage else "N/D", "",
        "Total tokens:", str(input_tokens + output_tokens) if any_usage else "N/D", "",
        sep, "COSTO", sep, "",
        "Costo generación de imágenes:", money(total_cost if cost_available else None), "",
        "Costo input:", "N/D (no facturado por separado del precio fijo por imagen)", "",
        "Costo output:", "N/D (no facturado por separado del precio fijo por imagen)", "",
        "Costo regeneraciones:", money(regen_cost), "",
        "COSTO TOTAL:", money(total_cost if cost_available else None), "",
        sep, "EFICIENCIA", sep, "",
        "Costo promedio por slide:", money(avg_cost_per_slide), "",
        "Slides sin regeneración:", str(max(0, slides_total - len(regenerated_slide_numbers))), "",
        "Slides regenerados:", str(len(regenerated_slide_numbers)), "",
        "Porcentaje de slides regenerados:", pct(regen_pct), "",
        sep, "TIEMPO", sep, "",
        "Inicio:", _fmt_clock(exec_started_at), "",
        "Fin:", _fmt_clock(exec_finished_at), "",
        "Duración total:", _fmt_duration_between(exec_started_at, exec_finished_at), "",
        "Tiempo generación + QA:", _fmt_phase_seconds(phase_seconds, "generation_qa"), "",
        "Tiempo QA:", "incluido en 'Tiempo generación + QA' (corre en línea con cada intento, no se mide por separado)", "",
        "Tiempo exportación:", _fmt_phase_seconds(phase_seconds, "export"), "",
        sep, "CRONOMETRO GLOBAL REAL (extremo a extremo, ver SKILL.md)", sep, "",
        "Tiempo total (wall-clock):", _fmt_raw_seconds(_seconds_between(started_at, finished_at)), "",
        "  - Preparación (antes de recibir la referencia):", _fmt_phase_seconds(phase_seconds, "preparation"), "",
        "  - Referencia visual (imagen -> texto confirmado):", _fmt_phase_seconds(phase_seconds, "reference"), "",
        "  - Brief (texto confirmado -> brief aprobado):", _fmt_phase_seconds(phase_seconds, "brief"), "",
        "  - Generación (llamadas a Gemini, ronda inicial):", _fmt_phase_seconds(phase_seconds, "generation"), "",
        "  - QA (estructural + Text QA, ronda inicial):", _fmt_phase_seconds(phase_seconds, "qa"), "",
        "  - Reintentos (generación + QA de rondas posteriores):", _fmt_phase_seconds(phase_seconds, "retry"), "",
        "  - Exportación:", _fmt_phase_seconds(phase_seconds, "export"), "",
        "  - Finalización (manifest + copy + costo):", _fmt_phase_seconds(phase_seconds, "finalization"), "",
        sep, "RESULTADO", sep, "",
        "TEXT QA:", text_qa_result, "",
        "QA visual:", qa_visual, "",
        "Cobertura:", pct(coverage_pct), "",
        "Contenido inventado:", "N/D (verificado manualmente en el PASO 6.5 antes de generar — no medible por este script)", "",
        "Bundle final:", final_bundle_path, "",
        sep,
    ]
    return "\n".join(lines) + "\n"


def save_costo_carrusel(
    bundle_path: Path,
    bundle_id: str,
    cost_summary: Dict[str, Any],
    model: str,
    resolution: str,
    aspect_ratio: str,
    slides_total: int,
    text_qa_block: Optional[Dict[str, Any]],
    final_bundle_path: str,
) -> None:
    """
    Escribe COSTO_CARRUSEL.txt en la raiz del bundle (regla obligatoria y permanente,
    ver SKILL.md "FABRICA RAPIDA"). Se llama automaticamente al final de CUALQUIER
    carrusel real — nunca pide permiso, nunca pregunta. Se sobrescribe en cada llamada
    (run_generation y run_add_copy) para reflejar siempre el estado mas reciente y real
    de costo/tiempo de este bundle.
    """
    bundle_path.mkdir(parents=True, exist_ok=True)
    text = build_costo_carrusel_text(
        bundle_id, cost_summary, model, resolution, aspect_ratio, slides_total,
        text_qa_block, final_bundle_path,
    )
    (bundle_path / COSTO_CARRUSEL_FILENAME).write_text(text, encoding="utf-8")
    print(f"   [OK] {COSTO_CARRUSEL_FILENAME} guardado en {bundle_path}")
