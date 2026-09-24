---
name: carousel-gen
description: FABRICA RAPIDA Y AUTONOMA — transforma un post/copy viral de referencia (imagen OBLIGATORIA) en un carrusel Instagram de MAXIMO 10 slides (limite obligatorio para compatibilidad Facebook+Instagram), en uno de 7 formatos narrativos, usando Google Gemini (Nano Banana 2 Lite, generacion DIRECTA y PARALELA — Batch queda desactivado por defecto, ver "COST OPTIMIZATION") con Kie AI como generador legacy desactivado por defecto. El estilo visual se detecta automaticamente de la imagen de referencia en cada ejecucion (no hay biblioteca de estilos). De brief aprobado a paquete final (slides + COPY_FINAL.txt + COSTO_CARRUSEL.txt) en ~5 minutos en condiciones normales, sin ciclos de correccion sin limite. Genera imagenes verticales 4:5.
allowed-tools: Read, Write, Bash(python3:*), Bash(cd:*), Bash(curl:*), Bash(ls:*), Bash(mkdir:*), Bash(cp:*), Bash(export:*), Bash(pip3:*), Glob, Grep, AskUserQuestion, Edit
user-invocable: true
---

# Generador de Carruseles Instagram - Google Gemini (Nano Banana 2 Lite, economico)

Transforma un post viral (imagen de referencia OBLIGATORIA) en un carrusel de Instagram,
en uno de 7 formatos narrativos probados. El estilo visual NUNCA se elige manualmente:
se detecta automaticamente de la imagen de referencia, en cada ejecucion.

## Uso

```
/carousel-gen
```

No requiere parametros. El flujo pide todo lo necesario paso a paso, empezando siempre
por la imagen de referencia.

## FAST_PREP — Preparación express (PASO 0-8 en ≤ 60 segundos)

**FAST_PREP se activa automáticamente** cuando el mensaje inicial contiene TODO lo siguiente:
1. Imagen de referencia viral adjunta
2. `source_text` completo (texto pegado en el mismo mensaje)
3. Tipo de carrusel elegido (nombre del formato)
4. Número de slides (número exacto o la palabra "recomienda")
5. Producto (nombre o "ninguno")

Cuando FAST_PREP está activo, los PASOS 0-8 colapsan en **3 acciones y ≤ 4 tool calls**:

```
[1 Read]  products.json  →  URL del producto (si aplica)
          ↓
ANÁLISIS ÚNICO EN MEMORIA — sin outputs intermedios de texto:
  • ADN visual completo (image_treatment, paleta, tipografía, composición, accent_color)
  • Distribuir source_text en slides (exact_text + scene_description por slide)
  • word_count + text_density por slide (internos; van directo a los campos del JSON)
  • Validación fidelidad: interna y silenciosa — corregir en JSON antes de escribir;
    solo reportar al usuario si hay un problema real que no se puede auto-corregir
          ↓
[1 Write] outputs/bundles/[bundle_id]/claude_decisions.json  ← TODO lo anterior, de una vez
          ↓
[1 Bash]  prepare_carousel.py  →  PREPARE_RESULT (si status == READY → PASO 9)
```

**Qué se elimina en FAST_PREP y por qué:**

| Eliminado | Causa de demora | Reemplazo |
|-----------|-----------------|-----------|
| `pip install` + API key check (PASO 0) | ~30 s de Bash innecesario | prepare_carousel.py falla claro si algo falta |
| `AskUserQuestion` de PASO 4 / 5 / 7 | Esperas de usuario; inputs ya están | Leer del mensaje inicial |
| Tabla de 13 columnas antes del Write (PASO 8) | 5-10 min para 10 slides | El JSON escrito ES el plan |
| 8 preguntas fidelidad como texto visible (PASO 6.5) | 2-3 min de generación | Validación interna; sin texto visible |
| Tabla densidad palabras por slide (PASO 6.6) | 1-2 min de generación | word_count directo en cada slide del JSON |

**Regla de atomicidad FAST_PREP:** el análisis visual y la escritura del JSON son un único
acto mental. Claude NO produce outputs de texto entre el análisis y el Write — ninguna tabla,
ninguna pregunta de fidelidad numerada, ningún resumen del ADN visual en chat. Si hay un error
de fidelidad, se corrige directamente dentro del JSON antes de escribirlo, nunca como paso
previo de texto visible al usuario.

**El análisis visual NO se elimina.** Solo se elimina su PRESENTACIÓN como texto visible antes
del JSON. El `visual_dna` completo, el `reference_analysis` y los 16 campos por slide aparecen
dentro de `claude_decisions.json`.

**Cuando FAST_PREP NO aplica** (flujo normal de 11 PASOS interactivos):
- El usuario no proporcionó alguno de los 5 inputs en el primer mensaje
- El usuario quiere ser guiado paso a paso (inició solo con `/carousel-gen`)

## FIDELIDAD DEL CONTENIDO ORIGINAL (regla obligatoria y permanente, prioridad maxima)

**carousel-gen transforma la presentacion del contenido, no el contenido.**

**El texto original proporcionado por el usuario es la fuente de verdad. Ningun fragmento
puede eliminarse, resumirse, parafrasearse o inventarse sin autorizacion explicita del
usuario.**

Esta regla tiene prioridad sobre cualquier otra consideracion de formato, narrativa o
cantidad de slides. Aplica a TODOS los carruseles futuros, sin excepcion.

### Que NO puede hacer nunca la skill con el contenido

- resumir el contenido
- eliminar parrafos, ideas, ejemplos o explicaciones
- cambiar el significado o reinterpretar el mensaje
- inventar frases, conclusiones, revelaciones o consejos
- agregar afirmaciones que no esten en el original
- sustituir palabras por otras "mas bonitas"
- convertir el contenido en una version generica
- introducir contenido psicologico, terapeutico o educativo que no este respaldado
  literalmente por el texto original

La transformacion es SIEMPRE estructural y visual, NUNCA semantica:

```
ORIGINAL -> MISMO CONTENIDO -> NUEVA DISTRIBUCION EN SLIDES     (correcto, siempre)
ORIGINAL -> RESUMEN/INTERPRETACION -> SLIDES                     (prohibido, siempre)
```

### No perder ninguna parte del original

Cuando el usuario entrega el texto completo del post viral, se conserva TODO su
contenido: cada oracion, parrafo, idea, explicacion, ejemplo, reflexion y CTA debe quedar
representado dentro del carrusel.

- Se PUEDE dividir una oracion o parrafo entre dos slides para mejorar la lectura.
- Se PUEDE unir fragmentos solo si eso no elimina ni modifica contenido.
- NO se puede decidir que una parte "no es necesaria" y omitirla.

La unica modificacion permitida sobre un fragmento original es: dividirlo entre slides,
reorganizar saltos de linea, ajustar mayusculas/minusculas solo si el usuario lo permite, y
adaptar puntuacion solo si el usuario lo solicita. Nunca cambiar palabras, parafrasear,
resumir o agregar palabras.

### Trazabilidad obligatoria en brief.json

Cada slide en `brief.json` debe tener, ademas de los campos visuales existentes:

- `source_text_fragment`: el fragmento LITERAL del texto original del que sale el
  contenido de este slide (copiado tal cual, no reescrito).
- `source_location`: donde vive ese fragmento dentro de `source_text` (ej. "parrafo 2",
  "frase sanadora", "CTA final", "linea 5-7").
- `exact_text`: el texto exacto que se enviara a Kie AI para aparecer en el slide (ya
  existia; ahora debe ser rastreable 1:1 a `source_text_fragment`, con como maximo las
  adaptaciones de formato permitidas arriba).

Ver el esquema completo en el PASO 8.

### Validacion obligatoria ANTES de generar

Antes de generar cualquier imagen, se responde explicitamente:

1. ¿Todo el contenido original esta representado?
2. ¿Hay alguna parte del original que desaparecio?
3. ¿Hay alguna frase que no exista en el original?
4. ¿Se agrego alguna interpretacion?
5. ¿Se invento algun CTA?
6. ¿Se invento alguna conclusion?
7. ¿Se cambio alguna palabra importante?
8. ¿El contenido de todos los slides puede rastrearse al texto original?

Si alguna respuesta indica un problema, NO se generan las imagenes — se corrige primero
el brief. Ver PASO 6.5.

### Si el texto viene de una imagen (OCR)

Cuando el usuario dice "usar texto de la imagen", se extrae mediante OCR **TODO** el texto
visible: hook, cuerpo del post, subtitulos, parrafos, CTA, firma y cualquier otro texto
relevante — nunca asumir que solo el hook es el contenido. Ver detalle en el PASO 3.

### El hook original es intocable

Cuando existe un hook viral original, se conserva EXACTAMENTE. Nunca sustituirlo por
frases genericas inventadas (ej. "¿Esta historia te suena?") ni cambiarlo para hacerlo
"mas viral". El hook es parte del contenido fuente.

### El formato no determina que contenido se elimina

El tipo de carrusel elegido (PASO 4) determina UNICAMENTE como se presenta el contenido,
nunca que contenido se elimina. Si el original es largo y el formato "sugiere" pocos
slides, la solucion NUNCA es resumir arbitrariamente — es aumentar la cantidad de slides
hasta cubrir el contenido completo. La cantidad de slides es siempre dinamica y se
subordina a la cobertura completa del contenido (ver PASO 5).

**Carrusel Interactivo — caso especial**: se pueden convertir partes del contenido
original en preguntas o elementos de interaccion SOLO cuando la transformacion conserve
exactamente el significado del contenido original. Nunca inventar preguntas psicologicas
nuevas porque "encajan mejor" — cada pregunta debe poder rastrearse al contenido fuente
via `source_text_fragment`.

### Diseño vs. contenido

La skill tiene libertad total para transformar composicion, fotografia, escena, encuadre,
jerarquia visual, distribucion, tratamiento fotografico, ADN visual, tipografia (dentro de
las reglas de diseño), colores y recursos graficos. NO tiene libertad para transformar el
significado del texto.

```
DISEÑO    = adaptable
CONTENIDO = fiel
```

### Nunca inventar contenido para completar una estructura

Si un formato "necesita" una revelacion, un CTA o una conclusion, pero el texto original
no la contiene explicitamente, NO se inventa una — se usa solamente lo que existe en la
fuente. Si un formato no puede aplicarse sin inventar contenido, se informa al usuario
ANTES de generar (ofrecer alternativas: otro formato, mas slides, o pedir el contenido
faltante), nunca se rellena el hueco con contenido inventado silenciosamente.

## LÍMITE OBLIGATORIO DE SLIDES (regla obligatoria y permanente, compatibilidad Facebook + Instagram)

**Ningún carrusel generado por `carousel-gen` puede tener más de 10 slides.** El maximo
tecnico es `MAX_SLIDES = 10`, definido una unica vez en `scripts/generate-carousel.py` (ver
esa constante) y reutilizado en todas las validaciones — nunca se duplica ese numero en
otro lugar.

**Motivo**: que TODOS los carruseles generados por este skill sean compatibles tanto con
Facebook como con Instagram. Instagram no acepta carruseles de mas de 10 slides, asi que
publicar el mismo paquete en ambas plataformas exige respetar ese limite desde el origen,
no solo recomendarlo.

### Regla numerica

- Maximo permitido: **10 slides**. Nunca 11, 12, 15, 20 ni ningun numero superior.
- Puede generar MENOS de 10 cuando el contenido no necesite 10 (el limite es un techo, no
  un piso ni un numero fijo obligatorio — ver PASO 5).
- Aplica a TODOS los carruseles futuros, sin excepcion, independientemente del tema,
  formato narrativo, producto asociado o cantidad de contenido fuente.

### Reducir el maximo de slides NO es resumir contenido (la fidelidad manda igual)

Este limite es una restriccion de PRESENTACION, nunca una autorizacion para perder
contenido. Sigue aplicando integramente la seccion "FIDELIDAD DEL CONTENIDO ORIGINAL" de
arriba. Cuando `source_text` necesitaria mas de 10 slides bajo la logica narrativa normal
del formato elegido:

1. Reorganizar el contenido completo dentro de un maximo de 10 slides — nunca reducir la
   cantidad de contenido para que "quepa".
2. Conservar la TOTALIDAD del contenido relevante de `source_text` (misma regla de
   trazabilidad via `source_text_fragment`/`source_location` del PASO 8).
3. No inventar informacion nueva para rellenar huecos que la reorganizacion deje.
4. No agregar frases que no esten sustentadas por `source_text`.
5. No eliminar partes importantes del original solamente para cumplir el limite de 10.
6. Usar slides con MAYOR DENSIDAD de contenido (agrupar varias unidades/fragmentos por
   slide, mas texto por slide, `exact_text` mas largo) en vez de recortar significado.
7. Mantener la narrativa, la progresion emocional y la estructura propia del tipo de
   carrusel elegido (PASO 4), adaptando la agrupacion, no el mensaje.
8. Mantener el texto exacto (`exact_text` = `source_text_fragment` literal) cuando la skill
   trabaje bajo la regla de fidelidad textual — este limite nunca autoriza parafrasear o
   resumir para ahorrar espacio.
9. **La regla de fidelidad de contenido tiene prioridad sobre este limite**: si en algun
   punto reorganizar dentro de 10 slides pareciera exigir perder contenido real, la
   solucion es aumentar la densidad por slide (punto 6), nunca eliminar contenido — jamas
   se resuelve el limite de slides sacrificando fidelidad.

### Aplicacion en el PASO 5 (cantidad de slides) y el PASO 8 (`brief.json`)

- `slide_count.recommended` nunca puede ser superior a 10 (ver PASO 5 actualizado abajo).
- `slide_count.confirmed` nunca puede ser superior a 10.
- Si el analisis inicial del PASO 5 sugeriria mas de 10 slides para cubrir todo el
  contenido, la reorganizacion (mayor densidad por slide, agrupacion de unidades) debe
  aplicarse ANTES de presentar la recomendacion al usuario — nunca se presenta ni se
  confirma un numero mayor a 10.
- El `brief.json` final de cualquier carrusel debe quedar siempre entre 1 y 10 slides.

### Compuerta tecnica (no solo una instruccion)

`generate-carousel.py` valida el limite en `load_brief()`, ANTES de cualquier otra
verificacion de campos, ANTES de `get_api_key()` y ANTES de cualquier llamada a Kie AI:

- Si `len(brief["slides"]) > MAX_SLIDES`, o `slide_count.recommended`/`slide_count.confirmed`
  superan `MAX_SLIDES`, `load_brief()` imprime un error explicito y devuelve `None`.
- `main()` termina el proceso (`sys.exit(1)`) inmediatamente cuando `load_brief()` devuelve
  `None` — nunca llega a mostrar el brief, nunca llama a `get_api_key()`, nunca crea tareas
  en Kie AI, nunca genera imagenes, nunca gasta creditos, nunca escribe un `manifest.json` o
  paquete final invalido.
- El mensaje de error sigue este formato:
  `ERROR: carousel-gen admite un maximo de 10 slides. El brief solicitado contiene X
  slides. Debe reorganizarse el contenido dentro del limite de 10.`

## FABRICA RAPIDA Y AUTONOMA (regla obligatoria y permanente, prioridad estructural)

**carousel-gen no es un proceso de desarrollo/debugging: es una fabrica de carruseles.**
Objetivo operativo permanente: un carrusel de hasta 10 slides debe poder pasar de brief
aprobado a paquete final en **~5 minutos en condiciones normales** (nunca se promete un
tiempo exacto si la API externa tarda mas, pero el pipeline se diseña para minimizar la
latencia al maximo). Esta seccion es el principio rector; las secciones "COST
OPTIMIZATION" y "TEXT QA" abajo contienen el detalle tecnico exacto de cada regla.

### Flujo obligatorio de una generacion real

```
INPUT -> [PASO 1: guardar viral-reference.png o STOP] -> analisis ADN -> brief
  -> auditoria de fidelidad (PASO 6.5) -> mostrar tabla -> [PASO 9: generacion automatica]
  -> generacion PARALELA (Slide 1 solo, luego slides 2-10 en una unica tanda paralela)
  -> QA rapido (estructural + Text QA local)
  -> maximo 1 regeneracion por slide, SOLO si el fallo es CRITICO
  -> exportacion -> COPY_FINAL.txt -> COSTO_CARRUSEL.txt -> informe final -> TERMINADO
```

Después del informe final (ver PASO 11), el trabajo se DETIENE. La fábrica nunca:
regenera repetidamente un slide que ya paso o ya agoto su presupuesto; corrige el mismo
slide varias veces; rehace slides porque "podrian verse mejor"; inicia una nueva
auditoria despues de cada correccion; pide aprobacion humana para decisiones normales del
pipeline (PASO 9-10, ya aprobadas implicitamente al aprobar el brief en el PASO 8);
regenera imagenes de bundles historicos; ni ejecuta ciclos de QA sin limite.

### Reglas duras (cada una tiene su seccion detallada mas abajo)

1. **Sin Batch por defecto**: el modo normal SIEMPRE es DIRECT, paralelo. Batch (que
   Google documenta con turnaround de hasta 24h) queda reservado para una futura
   modalidad explicita de produccion masiva, activada solo con `--force-batch`. Ver
   "COST OPTIMIZATION" › "DIRECT MODE vs BATCH MODE".
2. **Generacion paralela real**: los slides 2-10 se generan simultaneamente (nunca
   slide 2 → esperar → slide 3 → esperar...) salvo la dependencia real e inevitable: el
   Slide 1 debe existir primero porque es el ancla visual de los demas. Ver "Slide 1 =
   ancla visual maestra" arriba y "COST OPTIMIZATION" › "DIRECT MODE vs BATCH MODE".
3. **Maximo 2 intentos por slide** (`MAX_RETRIES=1` = 1 intento inicial + 1 regeneracion
   como maximo), y esa regeneracion SOLO por error CRITICO — nunca por diferencias
   esteticas, de composicion o dudas menores de OCR. Ver "COST OPTIMIZATION" › "Retries y
   QA" y "TEXT QA" › "Severidad".
4. **Definicion de CRITICO** (dispara la unica regeneracion permitida): texto omitido,
   texto inventado, palabra cambiada, frase duplicada, texto ilegible, slide corrupto,
   proporcion incorrecta, imagen incompatible con el brief, mockup incorrecto cuando el
   brief exige uno real, referencia visual obligatoria ignorada en el Slide 1.
   **Definicion de NO CRITICO** (nunca regenera): espaciado, salto de linea, alineacion,
   tamaño de letra, composicion "mejorable", diferencia estetica subjetiva, OCR dudoso
   (ver "TEXT QA" › "Severidad"), un detalle de renderizado que no cambia el contenido.
5. **OCR dudoso nunca bloquea**: si Tesseract no esta disponible, o si esta disponible
   pero su confianza sobre una imagen es baja, el pipeline NUNCA se detiene por eso — ver
   "TEXT QA" › "Severidad".
6. **Un unico archivo de copy** (`COPY_FINAL.txt`) y **un unico archivo de costo/tiempo**
   (`COSTO_CARRUSEL.txt`, ver seccion propia mas abajo) — nunca archivos fragmentados por
   slide ni por seccion.
7. **Sin aprobaciones intermedias dentro del flujo normal**: la orden del usuario de crear
   el carrusel autoriza TODO el pipeline (analizar → brief → validar → generar → QA →
   corregir maximo una vez → exportar → COPY_FINAL.txt → COSTO_CARRUSEL.txt → finalizar).
   Los unicos puntos que SI requieren respuesta del usuario son inputs reales que nadie
   mas puede decidir (imagen de referencia, texto fuente, formato, cantidad de slides,
   producto, aprobacion del brief — PASOS 1-8) — nunca una pregunta tipo "¿quieres que
   genere/revise/continue?" durante el PASO 9 o el PASO 10. **UNA SOLA EJECUCION**: desde
   la aprobacion del brief (PASO 8), generar/QA/copy/manifest/costo/exportacion salen de
   una UNICA invocacion de `run_carousel_pipeline.py` (via `--copy-json`, ver PASO 9) —
   nunca hace falta una segunda invocacion completa del script para completar el paquete.
8. **Bundles historicos intactos**: cada carrusel nuevo usa un `bundle_id` nuevo; nunca
   se modifica, regenera ni reescribe un bundle de una ejecucion anterior salvo que el
   usuario pida explicitamente regenerar ese bundle puntual (`--regenerate-slides`).
9. **Prioridad del sistema** (en este orden): (1) fidelidad del contenido, (2)
   correctitud, (3) velocidad, (4) costo, (5) perfeccionamiento estetico. La velocidad y
   el costo nunca se priorizan sobre la fidelidad — pero el perfeccionamiento estetico
   tampoco se prioriza sobre la velocidad.
10. **Paralelismo obligatorio en llamadas independientes** (`USE_PARALLEL_TOOL_CALLS =
    TRUE`): tanto a nivel de codigo (generacion de slides 2-10 via
    `ThreadPoolExecutor` en `direct_generator.py`, QA de slides distintos) como a nivel
    de las propias herramientas que Claude invoca durante el workflow (ej. varias
    lecturas/verificaciones independientes del PASO 0, o varias operaciones de archivo
    sin dependencia entre si): cuando dos o mas operaciones son independientes, se lanzan
    juntas en paralelo — nunca secuencialmente solo porque "es mas simple de leer".

### Regla de terminación (obligatoria)

Una vez que existen las imagenes, el paquete esta completo, `COPY_FINAL.txt` existe,
`COSTO_CARRUSEL.txt` existe, el QA termino y la exportacion termino: **el trabajo esta
terminado**. Presentar el informe final (PASO 11) y DETENERSE — no buscar errores
adicionales, no hacer "una ultima revision", no regenerar nada mas, no modificar ningun
archivo del bundle, no tocar bundles historicos, no sugerir mejoras adicionales sin que
el usuario las pida.

## Los 4 conceptos (NUNCA mezclar)

- **IMAGEN DE REFERENCIA**: el post/copy viral que el usuario adjunta. Obligatoria y
  distinta en cada ejecucion. Es un input, no una configuracion del skill.
- **TIPO DE CARRUSEL**: uno de los 7 formatos narrativos (ver PASO 3). Se elige una vez
  por ejecucion.
- **ESTILO VISUAL**: se detecta automaticamente analizando la imagen de referencia (el
  "ADN visual"). Nunca se pregunta ni se elige de una lista ni se guarda entre ejecuciones.
- **TEMATICA**: se infiere del contenido de la imagen de referencia. Si el post trata
  temas emocionales, relaciones, familia, sanacion, patrones o mirada sistemica, la
  transformacion DEBE preservar esa tematica. Nunca convertir el contenido en marketing
  o emprendimiento generico, salvo que el post original ya trate justamente de eso.
- **MOCKUP DE PRODUCTO ORIGINAL** (opcional, distinto de la imagen de referencia viral): si
  el usuario proporciona el mockup/portada real de un producto propio (libro, ebook, curso,
  workbook) que el carrusel promociona — tipicamente para el slide de CTA/cierre — ese mockup
  SIEMPRE debe usarse como referencia visual directa. Ver regla completa en el PASO 8.

## Regla general: mockup de producto proporcionado por el usuario

Cuando el usuario adjunta o referencia el mockup/portada ORIGINAL de un producto propio
(ej.: la portada real de su libro) para que aparezca en algun slide (normalmente el de
llamado a la accion), aplica SIEMPRE:

1. **Nunca inventar una portada o mockup generico** cuando el usuario ya proporciono uno
   real. Inventar una cubierta neutra/generica es SOLO el fallback cuando NO existe un
   mockup real disponible.
2. Copiar el archivo tal cual (sin modificar, sin recortar, sin re-comprimir) a
   `carousel/assets/{nombre-descriptivo}.png` dentro del bundle.
3. Agregar en `brief.json` un bloque de nivel raiz `product_mockup`:
   ```json
   {
     "product_mockup": {
       "local_path": "carousel/assets/{nombre-descriptivo}.png",
       "description": "Que es este mockup y por que se proporciono (producto, contexto)"
     }
   }
   ```
   `product_mockup` describe UNICAMENTE el asset visual (la imagen del mockup). El nombre
   del producto y su enlace de compra viven en el bloque `product` de nivel raiz, que se
   registra en el PASO 7 (pregunta obligatoria del libro/producto) — ver mas abajo. Cuando
   el producto elegido en el PASO 7 tiene ademas un mockup visual, `product.product_name`
   debe coincidir con el producto que representa este `product_mockup`.
4. En el/los slide(s) donde debe aparecer el producto real, marcar
   `"uses_product_mockup_directly": true` y escribir el `scene_description` indicando que
   la portada/cubierta debe reproducirse fielmente del mockup adjunto — nunca describir una
   cubierta "neutra" o "sin decoración" cuando hay mockup real disponible.
5. El script `generate-carousel.py` sube automaticamente ese asset a Kie AI y lo pasa como
   `image_input` en los slides marcados, con instrucciones explicitas de reproducir la
   portada real sin reinventarla (ver `uses_product_mockup_directly` en el script).
6. El producto puede integrarse en una escena y composicion NUEVA (cambiar posicion,
   escala, entorno, iluminacion ambiental) siempre que conserve su identidad visual real
   — nunca se reinterpreta ni se rediseña el producto en si.
7. Esta regla NO esta limitada a libros: aplica igual a ebooks, productos digitales,
   portadas, mockups o cualquier otro producto visual que el usuario proporcione como
   asset original propio.

## Reglas de diseño obligatorias (aplican a TODOS los carruseles, sin excepcion)

Estas reglas son un SISTEMA DE DISEÑO fijo del skill — se aplican SIEMPRE, en cada
ejecucion. Nunca se documentan ni se aplican como "una eleccion mas" — son restricciones
obligatorias del sistema. Pero dentro de ese sistema, el ADN visual real del Slide 1 (no
un default generico) es quien decide el tratamiento de imagen, color y luminosidad — ver
"Slide 1 = ancla visual maestra" abajo.

### Slide 1 = ancla visual maestra (cadena obligatoria)

El Slide 1 no es "un slide mas": es la referencia visual maestra de la que heredan y
adaptan su lenguaje visual TODOS los slides siguientes. La cadena es siempre:

```
REFERENCIA VIRAL
  -> ANALISIS DEL ADN VISUAL (PASO 2, source_reference_dna)
  -> SLIDE 1 (recreacion fiel de la referencia)
  -> SLIDE 1 SE CONVIERTE EN ANCLA VISUAL (slide_1_master_dna)
  -> SLIDES 2+ HEREDAN Y ADAPTAN ESE LENGUAJE VISUAL (nunca lo reinventan)
```

En la practica (ver tambien `scripts/generate-carousel.py`): el Slide 1 se genera PRIMERO
y en solitario; su imagen resultante se usa como `image_input` adicional (ancla visual
real, no solo texto) para generar todos los slides 2+ en paralelo. Los slides 2+ NUNCA se
diseñan de forma independiente — deben sentirse una evolucion natural del mismo carrusel.

**Que se hereda del Slide 1 (obligatorio):** tratamiento fotografico (B&N, color, o
ilustrado — ver siguiente seccion), temperatura de color, contraste, exposicion,
saturacion, profundidad de negros, luminosidad, grano/textura, tratamiento de piel y
sombras, realismo fotografico, y atmosfera emocional.

**Que NO se copia del Slide 1 (obligatorio variar):** la escena exacta, el sujeto, la
pose ni la composicion. Cada slide 2+ evoluciona la composicion segun su rol narrativo —
mismo lenguaje visual, escenas y composiciones nuevas. Nunca 9 variaciones identicas de
la misma foto.

### Tratamiento de imagen y color — lo determina el Slide 1, NUNCA un default

El sistema NO impone blanco y negro por defecto a todos los carruseles, ni fuerza color
si el Slide 1 es B&N. Tras analizar la referencia y construir el Slide 1, hay que
identificar cual de estos tratamientos usa realmente:

- fotografia B&N pura
- B&N con uno o varios acentos de color
- fotografia a color
- color desaturado
- color cinematografico (calido o frio)
- otra combinacion cromatica claramente identificable
- lenguaje ilustrado/grafico (solo si la referencia y el Slide 1 son ellos mismos
  ilustrados — en ese caso, los slides 2+ siguen ese lenguaje, no fotografia realista)

Los slides 2+ usan una ADAPTACION COHERENTE de ese mismo tratamiento — nunca uno
distinto. Ejemplo: si el Slide 1 es B&N + amarillo como acento, todos los slides 2+
mantienen B&N + amarillo. Si el Slide 1 es color calido, los slides 2+ usan color calido
compatible — nunca convertir a B&N "porque la referencia es editorial".

### Realismo fotografico

Cuando el Slide 1 esta construido a partir de fotografia realista, los slides 2+ deben
ser fotografia hiperrealista y de apariencia profesional: personas anatomicamente
correctas, piel y cabello naturales, iluminacion fotografica real, profundidad de campo
realista, texturas naturales, expresiones humanas creibles, composicion editorial.

NUNCA: ilustracion, pintura, render 3D, imagen de stock artificial, aspecto plastico o
arte digital evidente. Excepcion unica: que el Slide 1 y la referencia sean ellos mismos
claramente ilustrados o graficos — ahi los slides 2+ siguen ese lenguaje.

Regla general: **el tipo de imagen del Slide 1 determina el tipo de imagen de los slides
2+.**

### Continuidad real de tonos (no solo paleta nominal)

No basta con usar la misma paleta nominal. Debe existir continuidad real en: temperatura
de color, contraste, exposicion, saturacion, profundidad de negros, luminosidad, textura,
tratamiento de piel, tratamiento de sombras y luces, ambiente, grano y sensacion
fotografica general. Los slides 2+ deben parecer fotografias tomadas dentro de la MISMA
direccion artistica que el Slide 1 — nunca un slide B&N editorial seguido de un slide a
color tipo stock, ni un slide calido, otro frio, otro sepia y otro B&N sin una razon
visual que venga del propio Slide 1.

### Luminosidad — coherente con el Slide 1, nunca forzada

La luminosidad se adapta al Slide 1, no al reves. El sistema NO fuerza todas las imagenes
a ser claras artificialmente.

Formula: **luminosidad coherente con el Slide 1 + contraste suficiente para leer el texto
+ sin subexposicion innecesaria.**

- Si el Slide 1 es oscuro y dramatico (de forma deliberada, no por error), los slides 2+
  pueden conservar esa profundidad y dramatismo — pero deben seguir siendo legibles.
- Si el Slide 1 es luminoso, los slides 2+ NO deben volverse oscuros sin motivo.
- Evitar siempre, en cualquier caso: subexposicion accidental (no deliberada por el Slide
  1), exceso de vignette que el Slide 1 no tenga, y texto perdido en zonas oscuras.

### Paleta de texto — maximo 2 colores: blanco + color de acento del Slide 1

Todo texto superpuesto en el carrusel usa como maximo DOS colores:

1. **BLANCO** — desarrollo, explicaciones, texto secundario, informacion complementaria.
2. **COLOR DE ACENTO** — derivado del ADN visual del Slide 1 (no necesariamente amarillo;
   depende de la referencia). Uso estrategico en hooks, palabras emocionalmente
   importantes, conceptos clave, frases que necesiten enfasis.

Regla general: **color de acento = color derivado del ADN visual del Slide 1** (se fija
una sola vez, en `visual_dna.slide_1_master_dna.accent_color`, y se reutiliza igual en
todos los slides — nunca "amarillos" distintos entre slides).

**DISTRIBUCIÓN OBLIGATORIA (regla dura, sin excepción):**
- **~80% del texto en BLANCO** — texto de desarrollo, explicaciones, cuerpo, frases de
  contexto, todo texto que no sea un énfasis crítico.
- **Máximo 20% en COLOR DE ACENTO** — solo palabras o frases aisladas que realmente
  necesiten énfasis (hooks cortos, conceptos clave puntuales, 1-3 palabras por línea
  de énfasis como máximo).

**Lo que NUNCA puede ocurrir:**
- Párrafos completos en el color de acento.
- Más de 20% del total de texto del slide en color de acento.
- El color de acento como color dominante del slide.
- Usar el color de acento "por defecto" cuando no hay énfasis real que justifique.

**Si no hay énfasis realmente importante:** usar 100% BLANCO es correcto y preferible
a forzar acento innecesario.

Nunca un tercer color de texto. El color de elementos que pertenezcan a la fotografia real,
al producto/mockup o a la escena (ej. una flor amarilla) NO cuenta como color de texto y
no esta limitado por esta regla.

### Tipografia — maximo 2 familias, una obligatoriamente Poppins

Cada carrusel usa como maximo DOS familias tipograficas. Una de ellas DEBE ser **Poppins**
— y debe usarse realmente en los slides generados, no solo declararse en el brief. La
segunda familia es libre, elegida para armonizar con el ADN visual detectado en la
referencia (ej. una serif editorial o una script si la referencia lo sugiere).

Nunca tres o mas familias. Dentro de esas 2 familias se puede variar peso, tamaño,
mayusculas/minusculas, cursiva, composicion, tracking e interlineado.

### Jerarquia tipografica — obligatoria en cada slide

Nunca texto colocado simplemente encima de una imagen sin jerarquia. Cada slide define 3
niveles:

- **NIVEL 1 — Hook/idea principal**: mayor tamaño, mayor peso visual, maximo contraste.
  Debe detener el scroll y percibirse en menos de un segundo.
- **NIVEL 2 — Desarrollo**: tamaño intermedio, explica o desarrolla el Nivel 1.
- **NIVEL 3 — Apoyo**: tamaño menor, solo cuando el slide lo necesite.

Las palabras emocionalmente mas importantes reciben mayor peso visual combinando tamaño,
peso, posicion, espacio y color (dentro de blanco/color de acento). Nunca todos los
textos de un slide con el mismo tamaño/peso/importancia.

Diseñar siempre pensando en visualizacion desde telefono: tamaño suficiente, contraste
suficiente, margenes seguros, interlineado adecuado, no comprimir demasiado texto, no
generar bloques pequeños e ilegibles. El texto es prioritario: si hace falta recortar u
oscurecer parcialmente la fotografia para ganar contraste y espacio de lectura, se hace —
nunca se reduce el texto o su tamaño para "hacer caber" mas contenido.

**El Nivel 1 nunca autoriza mover ni duplicar texto (regla obligatoria, hallazgo real de
produccion 2026-09-18)**: marcar una frase como Nivel 1 significa UNICAMENTE darle mayor
tamaño/peso/contraste EN EL LUGAR donde esa frase ya aparece dentro de `exact_text` —
nunca reubicarla al principio del slide como si fuera un titular nuevo, y nunca repetirla
en otro punto de la imagen. Se confirmo en produccion que Gemini a veces malinterpreta
"Nivel 1 (cian)" como permiso para adelantar o duplicar esa frase, rompiendo el orden real
de `exact_text` (ver "FIDELIDAD DEL CONTENIDO ORIGINAL" arriba — el orden tambien es
contenido, no solo las palabras). `build_prompt_for_slide()` en `carousel_common.py`
incluye ahora una regla explicita en el prompt contra esto — ver "COST OPTIMIZATION" ›
"Prompt: nunca renderizar instrucciones, nunca mover/duplicar el Nivel 1".

### Composicion — coherencia sin repeticion

Los slides 2+ mantienen coherencia con el Slide 1 pero NO copian su composicion exacta:
mismo lenguaje visual + nuevas composiciones + nuevas escenas + mismo tratamiento
fotografico. Ejemplo: si el Slide 1 usa retrato cercano con profundidad de campo, grano
analogico, B&N y amarillo como acento, los slides 2+ pueden usar manos, detalles, planos
medios, objetos, espacios o distintas perspectivas — pero conservando B&N, tratamiento
fotografico, textura, contraste, grano, el mismo acento cromatico y la atmosfera
emocional.

### Prioridad del Slide 1

Cuando exista conflicto entre una instruccion generica de estilo y el ADN visual del
Slide 1, **gana el ADN visual del Slide 1**. Excepcion: las reglas ESTRUCTURALES
obligatorias de este sistema nunca se saltan, sin importar el ADN del Slide 1:
legibilidad del texto, maximo 2 familias tipograficas, Poppins obligatoria, maximo 2
colores de texto, jerarquia tipografica de 3 niveles, y uso directo (sin reinventar) de
cualquier mockup de producto proporcionado por el usuario.

**Slide 1 (recreacion de la referencia viral) — condicion especial:** el Slide 1 conserva
la identidad de la publicacion original: sujeto principal, expresion, elementos clave
(ej. una flor), esencia emocional, tratamiento fotografico y composicion esencial, y el
hook/texto exacto aprobado — nunca se sustituye, resume, reinterpreta o reemplaza ese
texto. Lo unico que se puede adaptar es el FONDO (mas luz, menos vignette, mayor rango
tonal) para armonizar con la luminosidad del resto del carrusel, siempre de forma sutil y
sin alterar al sujeto, la expresion, los elementos clave ni el hook.

## Workflow obligatorio (PASO 0 + 11 pasos, en orden — PASO 6.5 es una validacion intermedia bloqueante, no un paso numerado aparte)

**REGLA PRINCIPAL**: NUNCA saltar pasos. NUNCA generar imagenes sin `brief.json` aprobado
explicitamente por el usuario.

### PASO 0: Verificaciones tecnicas (INVISIBLE al usuario)

**IMPORTANTE**: Este skill esta instalado globalmente en `$HOME/.claude/skills/carousel-gen`.
Todas las rutas de este workflow son relativas a esa carpeta (el script y el `.env` viven
ahi), NO al directorio de trabajo actual del usuario.

**CRONOMETRO GLOBAL REAL (ver seccion propia mas abajo)**: antes de cualquier otra
operacion de este PASO 0, registrar internamente el timestamp actual (ISO 8601) como
`skill_started_at` — es el punto de partida real del pipeline completo, ANTES de pedir
la imagen de referencia (PASO 1). Este valor (y los siguientes de PASO 1/3/8) se escriben
juntos en el bloque `timing` de `brief.json` recien en el PASO 8 (cuando el archivo se
crea por primera vez) — no hace falta ningun archivo intermedio para llevar la cuenta,
basta recordar cada timestamp a medida que ese paso ocurre.

1. Verificar dependencias Python — **usar SIEMPRE el mismo interprete que ejecuta el
   script** (`python3 -m pip install`, nunca `pip3` a secas: en entornos con varias
   instalaciones de Python, `pip3` y `python3` pueden resolver a interpretes distintos y
   los paquetes quedarian invisibles para el script; ver caso real documentado en
   "Limitaciones conocidas" de la seccion COST OPTIMIZATION):
   ```bash
   python3 -m pip install requests python-dotenv Pillow google-genai pytesseract 2>/dev/null || true
   ```
   `pytesseract` es el wrapper de **Text QA** (ver seccion propia) — requiere ademas el
   binario de Tesseract-OCR instalado en el sistema (en Windows:
   https://github.com/UB-Mannheim/tesseract/wiki). Si falta el binario, Text QA se
   omite automaticamente (nunca bloquea la generacion), pero se pierde la verificacion
   de texto renderizado — instalarlo es fuertemente recomendado.
2. Verificar API key del generador PRINCIPAL (Gemini):
   ```bash
   ENV_FILE="$HOME/.claude/skills/carousel-gen/.env"
   if [ -f "$ENV_FILE" ] && grep -q "GEMINI_API_KEY=." "$ENV_FILE"; then
     echo "GEMINI_API_KEY configurada"
   else
     echo "FALTA: Crear/completar $ENV_FILE con GEMINI_API_KEY=tu-api-key (copia .env.example, obtener en https://aistudio.google.com/apikey)"
   fi
   ```
   Si NO existe, DETENER y pedir al usuario su API key de Gemini. (El generador legacy de
   Kie sigue existiendo pero esta desactivado por defecto — `KIE_AI_API_KEY` solo hace
   falta si el usuario reactiva `KIE_ENABLED=true` explicitamente, ver "COST
   OPTIMIZATION".)

**Si FAST_PREP está activo** (ver sección "FAST_PREP" arriba): omitir las dos
verificaciones de este PASO 0. Pasar directamente a la Acción A (1 Read de
`products.json`) y al análisis en memoria.

### PASO 1: Solicitar la imagen de referencia (BLOQUEANTE)

Lo primero que se le dice al usuario, siempre, es:

> "Adjunta la imagen del post/copy viral de Facebook (o Instagram) que quieres transformar
> en carrusel. No puedo continuar sin ella."

Esto NO es una pregunta de `AskUserQuestion` (no es una eleccion entre opciones), es una
solicitud de adjunto. Si el siguiente mensaje del usuario no trae una imagen, repetir la
solicitud y NO avanzar al Paso 2 bajo ninguna circunstancia.

**CRONOMETRO GLOBAL REAL**: en cuanto el usuario adjunta la imagen (justo antes de pasar
al PASO 2), registrar internamente el timestamp actual como `reference_received_at` (ver
PASO 0 y PASO 8).

#### REFERENCIA VISUAL — guardado DELEGADO a prepare_carousel.py (PASO 8)

**Arquitectura reingenieria 2026-09-19**: el guardado de `viral-reference.png` ya NO
ocurre en PASO 1. Claude NO crea carpetas, NO ejecuta `save_reference_image.py` aqui.

En PASO 1 ocurre SOLO:
1. El usuario adjunta la imagen → Claude la recibe y la ve en la conversacion.
2. Claude registra mentalmente el timestamp `reference_received_at` para el timing.

`prepare_carousel.py` (PASO 8) ejecuta internamente `save_reference_image.py` como parte
de su pipeline determinista — lee el transcript JSONL de esta sesion y extrae el ULTIMO
bloque image de usuario, que corresponde exactamente al attachment de este carrusel.

**Mecanismo oficial** (ejecutado por prepare_carousel.py, no por Claude):
  Claude Desktop attachment → transcript JSONL de CLAUDE_CODE_SESSION_ID → `viral-reference.png`

El script lee el transcript JSONL identificado por `CLAUDE_CODE_SESSION_ID` (disponible
como variable de entorno en toda sesion de Claude Code), recorre los mensajes en orden y
extrae el ULTIMO bloque `type:image` de usuario. Ese bloque contiene exactamente el
attachment que el usuario adjunto en esta ejecucion.

**Garantia de identidad**: la imagen extraida es la mas reciente en el transcript de ESTA
sesion. Si el usuario adjunto varias imagenes en la misma sesion, siempre se usa la
ultima — que es la que envio justo ahora para este carrusel.

**Registro de auditoria**: el script escribe `carousel/assets/reference_audit.json` con:
`session_id`, `message_timestamp`, `media_type`, `size_bytes`, `dimensions`, `sha256`,
`mechanism: "session_transcript_jsonl"`. Este registro permite verificar en cualquier
momento que imagen fue utilizada y de que mensaje provino.

**Validaciones que el script realiza antes de retornar OK**:
- El archivo existe en disco
- Tamano > 0 bytes
- PIL puede abrirlo y verificar su integridad (no es un PNG corrupto)
- Dimensiones validas (width > 0, height > 0)

**Mensaje de STOP si no hay imagen en el transcript de esta sesion** (sin hacer ninguna
otra operacion posterior):
"STOP: El transcript de esta sesion no contiene ningun attachment de imagen.
Adjunta la imagen de referencia y ejecuta el skill de nuevo."

**PROHIBIDO sin excepcion:**
- Usar clipboard (`ImageGrab.grabclipboard()`) como mecanismo alternativo
- Buscar en bundles anteriores para "completar" la referencia de esta ejecucion
- Reutilizar `viral-reference.png` de una ejecucion anterior aunque el ADN visual parezca
  similar — una referencia nueva nunca puede reemplazarse silenciosamente por una vieja
- Leer transcripts de sesiones distintas a `CLAUDE_CODE_SESSION_ID`
- Buscar con `find`, `Get-ChildItem` o recorridos de `AppData`/`Temp`/`Downloads`
- Esperar (sleep/polling) a que el archivo aparezca en algun directorio
- Fabricar una imagen sintetica o placeholder
- Continuar el flujo con cualquier referencia que no provenga del transcript de esta sesion

`generate-carousel-gemini.py` aplica esta regla como compuerta tecnica final: si
`carousel/assets/viral-reference.png` no existe en el bundle al momento de generar, el
script termina de inmediato (`sys.exit(1)`) con error explicito, antes de llamar a Gemini.

### PASO 2: Analizar el ADN visual de la referencia

Con la imagen ya visible en la conversacion, analizarla directamente (leerla con el tool
de lectura de imagenes) y construir dos objetos, que luego iran dentro de `brief.json`:

**a) `reference_image.analysis`** — resumen del post original:
- `tema_mensaje`: tema y mensaje central del post
- `copy_estructura`: como esta estructurado el copy (gancho, cuerpo, cierre)
- `emocion_predominante`: la emocion principal que transmite
- `elementos_impacto`: que elementos concretos generan el impacto visual ("detienen el scroll")

**b) `visual_dna`** — ADN visual estructurado, OBLIGATORIO, se usa en TODOS los slides.

**IMPORTANTE**: `visual_dna` no es una transcripcion literal de lo observado en la
referencia — es esa observacion YA ADAPTADA a las "Reglas de diseño obligatorias" de
arriba (luminosidad coherente con el Slide 1, paleta blanco + color de acento del Slide 1,
Poppins + 1 familia, jerarquia de 3 niveles). Por ejemplo: si la referencia usa 3 familias
tipograficas, `tipografia.tratamiento` debe describir el sistema adaptado de 2 familias
(Poppins + la familia complementaria mas afin); si la referencia es un negro casi total
pero eso es parte deliberada de su identidad, `paleta_colores.fondo` y
`slide_1_master_dna.luminosity_profile` deben describir esa oscuridad conservada pero con
contraste suficiente para leer el texto (nunca forzarla a clara artificialmente). El
objeto que se escribe en `brief.json` es siempre la version ya conforme a las reglas
obligatorias, nunca la version cruda sin adaptar.

`visual_dna` tiene DOS partes, que materializan la cadena "REFERENCE IMAGE -> VISUAL DNA
-> SLIDE 1 -> MASTER VISUAL DNA -> SLIDES 2+" (ver seccion "Slide 1 = ancla visual
maestra" arriba):

```json
{
  "source_reference_dna": {
    "resumen": "Resumen breve del ADN visual observado en la referencia viral CRUDA, antes de adaptarla al Slide 1 (tratamiento fotografico, paleta, composicion tal como aparecen en el post original)"
  },
  "slide_1_master_dna": {
    "image_treatment": "b&n_puro | b&n_con_acento | color | color_desaturado | color_calido | color_frio | ilustrado — la categoria real que tendra el Slide 1, nunca un default",
    "color_treatment": "Descripcion concreta del tratamiento cromatico que tendra el Slide 1 (ej. 'blanco y negro editorial con un unico acento amarillo dorado')",
    "dominant_tones": ["...", "..."],
    "accent_color": "Codigo hex o descripcion precisa del color de acento (blanco + este color son los UNICOS 2 colores de texto de todo el carrusel)",
    "accent_color_source": "De donde sale ese accent_color (normalmente: 'derivado del ADN visual del Slide 1'; solo se fija a un slide especifico si el usuario lo pide explicitamente para ese carrusel)",
    "contrast_profile": "...",
    "luminosity_profile": "Luminosidad coherente con el Slide 1 (ver regla de Luminosidad arriba) — nunca 'siempre claro' ni 'siempre oscuro' por defecto",
    "photographic_realism": "Si el Slide 1 es foto real: descripcion del nivel de realismo esperado (hiperrealista, profesional, anatomicamente correcto...). Si es ilustrado: describir ese lenguaje en su lugar",
    "texture_profile": "Grano/textura esperados, consistentes en todos los slides",
    "continuity_rules": "Recordatorio operativo de que TODO esto lo heredan los slides 2+ adaptando composicion/escena, nunca el tratamiento visual — y que el ADN del Slide 1 tiene prioridad sobre instrucciones genericas (excepto las reglas estructurales: legibilidad, 2 familias tipograficas, Poppins obligatoria, 2 colores de texto, jerarquia, mockups directos)"
  },
  "paleta_colores": { "dominantes": ["..."], "acentos": ["..."], "fondo": "..." },
  "tipografia": { "tratamiento": "...", "peso": "...", "estilo": "..." },
  "tipo_imagen": "foto real | ilustracion | texto plano | mixto",
  "composicion_base": "...",
  "jerarquia_visual": "...",
  "tratamiento_personajes_objetos": "...",
  "textura": "...",
  "iluminacion": "...",
  "margenes": "...",
  "recursos_graficos": ["...", "..."]
}
```

`source_reference_dna` se llena en este PASO 2, a partir de la imagen cruda. `slide_1_master_dna`
se llena tambien aqui como PLAN del tratamiento que tendra el Slide 1 (con la mejor
informacion disponible antes de generarlo) — el script de generacion (`generate-carousel.py`)
despues genera el Slide 1 primero en solitario y usa su imagen REAL resultante como ancla
visual adicional (`image_input`) para los slides 2+, reforzando operativamente lo que este
campo ya describe en texto. Las claves de `slide_1_master_dna` deben coincidir en espiritu
con lo que finalmente se vea en el Slide 1 generado — no es una casilla decorativa, es la
fuente de verdad que usan los slides 2+ para no tener que adivinar el estilo de nuevo.

El resto de campos (`paleta_colores`, `tipografia`, etc.) siguen siendo el analisis
detallado de respaldo — en caso de conflicto con `slide_1_master_dna`, este ultimo manda.

Cada campo debe llenarse con observaciones CONCRETAS de la imagen real, nunca genericas.
("beige calido con acentos terracota y un azul petroleo puntual" sirve; "colores bonitos"
no sirve).

### PASO 3: Validar y confirmar el source_text (BLOQUEANTE)

**REGLA ABSOLUTA DE PRODUCCION — source_text DEBE provenir del usuario.**

La imagen de referencia sirve EXCLUSIVAMENTE para: referencia visual, ADN visual,
composicion, analisis del hook. NUNCA como fuente de `source_text`.

**Comportamiento obligatorio segun el estado del mensaje del usuario:**

**A) El usuario proporciono source_text en su mensaje** (texto completo pegado, incluso
   si llego junto con otras instrucciones o junto con la imagen):
   → Guardarlo LITERALMENTE como `source_text` (sin editar, resumir ni parafrasear).
   → Registrar `source_text_confirmed_at` y avanzar directamente al PASO 4.

**B) El usuario NO proporciono source_text** (su mensaje no contiene texto del post
   aparte de instrucciones/contexto de uso del skill):
   → STOP INMEDIATO. Responder UNICAMENTE con:
   > "No recibi el source_text del carrusel. Pegalo completo para continuar."
   → NO continuar. NO extraer texto de la imagen como fallback silencioso. NO intentar
   inferir el contenido del carrusel. Esperar la respuesta explicita del usuario.

**C) El usuario dijo EXPLICITAMENTE "usar texto de la imagen"** (o equivalente exacto:
   "usa el texto de la imagen", "extrae el texto de la referencia", "el texto esta en
   la imagen", "usa texto de la imagen"):
   → SOLO en este caso, y solo cuando el usuario lo haya dicho con esas palabras o
   equivalente explicito, extraer mediante lectura visual/OCR TODO el texto visible:
   1. Leer la imagen completa — no solo el hook. Extraer: hook, cuerpo del post,
      subtitulos, parrafos, CTA, firma y cualquier otro texto relevante.
   2. Si alguna parte no se puede leer con seguridad (borrosa, cortada, muy pequena),
      NO inventar ni completar — marcarla como ilegible y pedirsela al usuario.
   3. Mostrar al usuario el texto extraido (organizado: hook / cuerpo / CTA / firma)
      y pedir confirmacion: *"Este es el texto que extraje de la imagen: [texto].
      ¿Esta completo o falta algo (caption, descripcion, texto fuera del encuadre)?
      Pega lo que falte antes de continuar."*
   4. No avanzar al PASO 4 hasta confirmacion del usuario.
   5. Usar el texto confirmado (extraido + lo que el usuario haya agregado) como
      `source_text`.

**PROHIBIDO sin excepcion:**
- Extraer texto de la imagen como fallback silencioso cuando el usuario no proporciono
  source_text y no dijo "usar texto de la imagen"
- Interpretar que "el texto esta en el adjunto" implica extraerlo automaticamente
- Inventar, inferir, resumir o parafrasear source_text
- Continuar el flujo parcialmente sin source_text confirmado
- Usar OCR o lectura visual como sustitucion de source_text del usuario

`source_text` guardado es SIEMPRE el texto completo y literal — fuente de verdad
absoluta del contenido (ver "FIDELIDAD DEL CONTENIDO ORIGINAL" arriba). La TEMATICA se
determina a partir de `source_text`, no de la imagen. En el PASO 6, `source_text` es la
UNICA fuente de contenido a redistribuir — nunca se resume, parafrasea ni recorta.

**CRONOMETRO GLOBAL REAL**: en cuanto `source_text` queda confirmado (justo antes de
pasar al PASO 4), registrar internamente el timestamp actual como
`source_text_confirmed_at` (ver PASO 0 y PASO 8).

### PASO 4: Elegir el tipo de carrusel

`AskUserQuestion` tiene un limite de 4 opciones por pregunta. Por eso se usan DOS preguntas
secuenciales para exponer los 7 formatos. "Ver los otros 4 formatos" es solo navegacion,
NO es un tipo de carrusel.

**Pregunta A** — mostrar siempre primero:

| Opcion | Descripcion |
|--------|-------------|
| La Gran Noticia | Actua como un titular de prensa/noticiero. Imagen impactante o controversial + titular fuerte y directo tipo prensa + al final, interpretacion personal. |
| Collage Visual | Estilo diario/scrapbook. Composicion mixta de imagenes reales + iconos + tipografia tipo handwriting/recorte de revista. |
| Meme Cartoon | Viñetas tipo comic/tira comica, humor basado en situaciones cotidianas relacionadas con el tema. |
| Ver los otros 4 formatos | Mostrar los formatos 4 al 7. |

Si el usuario elige cualquiera de los primeros 3, continuar directamente al PASO 5 con ese formato.

Si el usuario elige "Ver los otros 4 formatos", mostrar inmediatamente la **Pregunta B**:

| Opcion | Descripcion |
|--------|-------------|
| Recopilacion de Ideas (Listicle) | Titulo con numero + lista enumerada de items, cada uno explicado brevemente. |
| Versus / Pantalla Dividida | Comparacion clara, dividida vertical u horizontalmente, entre dos posturas o situaciones. |
| Carrusel Interactivo | Invita al usuario a autoevaluarse o participar activamente (ej. un mini-test o pregunta de autoobservacion). |
| Tipos de X | Titulo con la palabra "tipos" + presentacion de cada tipo con su propia ilustracion/foto. |

Tras la eleccion en la Pregunta B, continuar al PASO 5 con el formato seleccionado.

### PASO 5: Recomendar y confirmar la cantidad de slides

Calcular una cantidad RECOMENDADA en base a:
- El formato elegido en el Paso 3 (cada formato tiene una logica narrativa distinta)
- Cuantos slides hacen falta para representar el CONTENIDO COMPLETO de `source_text`
  (cada oracion/idea/parrafo/CTA debe caber en algun slide — ver "FIDELIDAD DEL CONTENIDO
  ORIGINAL" arriba)

**La cobertura completa del contenido manda sobre la "logica narrativa ideal" del
formato — PERO ambas estan siempre subordinadas al limite obligatorio de 10 slides** (ver
"LÍMITE OBLIGATORIO DE SLIDES" arriba). Si el contenido original es extenso, la cantidad de
slides sube DENTRO de ese techo — nunca se resume el contenido para que quepa en menos
slides; en vez de eso, se aumenta la densidad de contenido por slide (ver esa seccion,
punto 6). **NUNCA usar un numero fijo predeterminado** para el valor recomendado por debajo
de 10. Para Recopilacion de Ideas y Tipos de X, la cantidad recomendada nace del numero
natural de items/tipos que existen en el contenido original (no un numero "redondo"
arbitrario), pero si ese numero natural supera 10, se reagrupan items/tipos afines en el
mismo slide para volver a caber en el limite — nunca se descartan items. Para el resto, se
recomienda segun cuantos slides hacen falta para no perder ninguna parte del mensaje, sin
superar nunca 10.

**Calculo de `recommended` en dos pasos**: (a) calcular primero cuantos slides
"pedirian" el formato + el contenido completo sin pensar todavia en el limite; (b) si ese
numero es mayor a 10, reorganizar/agrupar unidades de contenido hasta que el numero final
propuesto al usuario sea `min(numero_calculado, 10)` — el numero que se presenta como
`recommended` YA debe respetar el limite de 10, nunca se le muestra al usuario un numero
mayor a 10 como "recomendado".

Presentar: *"Recomiendo N slides para este carrusel (formato: [formato], porque
[justificacion breve basada en cuanto contenido hay que cubrir]). ¿Confirmas N o prefieres
otra cantidad?"* (N siempre <= 10).

No avanzar sin la confirmacion explicita del usuario. El numero confirmado puede ser
distinto del recomendado — pero nunca puede superar 10 (si el usuario pide mas de 10,
explicarle el limite de compatibilidad Facebook/Instagram y pedir una cantidad <= 10). Si
el usuario pide MENOS slides de los necesarios para cubrir todo el contenido (dentro del
limite de 10), advertirle explicitamente que eso implica perder contenido original y pedir
su autorizacion explicita antes de proceder (ver regla de fidelidad). `generate-carousel.py`
rechaza tecnicamente cualquier brief con mas de 10 slides (ver PASO 9 y "LÍMITE OBLIGATORIO
DE SLIDES"), asi que jamas se debe confirmar ni escribir en `brief.json` un numero mayor.

### PASO 6: Distribuir el contenido en el formato elegido (NUNCA reescribir)

Usar `source_text` (capturado en el PASO 3) como UNICA fuente del contenido — completo,
literal, sin resumir ni parafrasear (ver "FIDELIDAD DEL CONTENIDO ORIGINAL" arriba). La
imagen de referencia aporta el ADN visual, nunca el texto a transformar.

Este paso es de **REDISTRIBUCION**, no de reescritura:

1. Segmentar `source_text` completo en unidades (oraciones/ideas/parrafos), sin omitir
   ninguna.
2. Asignar cada unidad a uno o mas slides, en el orden y agrupacion que mejor sirva al
   formato elegido (ver guias por formato abajo) — el formato decide la DISTRIBUCION,
   nunca decide que unidad se descarta.
3. El `exact_text` de cada slide sale literalmente de su `source_text_fragment`
   correspondiente, con como maximo: division entre slides, saltos de linea
   reorganizados, mayusculas/minusculas o puntuacion si el usuario lo autorizo. Nunca
   parafrasear, resumir, ni agregar palabras.
4. Si dos formatos narrativos "clasicos" (ej. gancho -> autoobservacion -> revelacion ->
   ejemplos -> insight -> CTA) no encajan 1:1 con la estructura real del original, se
   adapta la AGRUPACION de unidades a esos roles — pero cada rol solo existe si hay
   contenido real del original que lo sustente (ver PASO 6.5, pregunta 5-6-7). Nunca se
   inventa contenido para rellenar un rol narrativo vacio.
5. Mantener la tematica emocional/relaciones/familia/sanacion/mirada sistemica si el post
   original la tiene. Nunca "marketizar" el contenido ni convertirlo en lenguaje de
   emprendimiento generico — esto tambien es una forma de alterar el significado.

**Guias breves por formato** (como se DISTRIBUYE el contenido completo en cada uno — no
son licencia para resumir):

- *La Gran Noticia*: slide 1 = titular (hook original) + imagen impactante; slides
  intermedios = el resto del contenido distribuido tipo desarrollo de noticia; penultimo =
  la reflexion/conclusion SI existe en el original; ultimo = el CTA SI existe en el
  original
- *Collage Visual*: cada slide es un "fragmento de diario" — un fragmento real del
  original por slide (nunca una frase inventada), coherentes entre si como paginas del
  mismo cuaderno
- *Meme Cartoon*: cada slide es una viñeta secuencial que dramatiza un fragmento real del
  original, con humor en el tratamiento visual, no en el contenido inventado
- *Recopilacion de Ideas*: slide 1 = titulo con numero; cada slide siguiente = un item que
  existe literalmente en el original, explicado con su propio texto; ultimo = cierre +
  CTA SI existen en el original
- *Versus*: slide 1 = plantea la comparacion tal como esta en el original; slides
  intermedios = cada lado de la comparacion con su texto real; cierre = la
  reflexion/CTA SI existen en el original
- *Carrusel Interactivo*: slide 1 = plantea el ejercicio/pregunta (si existe en el
  original) o presenta el hook; intermedios = el contenido real convertido en pasos de
  autoevaluacion SOLO si conserva el significado exacto (ver regla especial arriba);
  cierre = revelacion + CTA SI existen en el original
- *Tipos de X*: slide 1 = titulo "tipos de..."; cada slide siguiente = un tipo que existe
  literalmente en el original, con su descripcion real; cierre = insight + CTA SI existen
  en el original

### PASO 6.6: Distribución equilibrada del texto (regla obligatoria y permanente — NARRATIVA + DENSIDAD + LEGIBILIDAD + COMPOSICIÓN + ESPACIO)

**En FAST_PREP:** calcular word_count de cada slide internamente e incluirlo directamente
en el campo `word_count` de cada slide en `claude_decisions.json`. No mostrar la tabla de
palabras/densidad como texto separado — el JSON es la única salida de este cálculo.

**Regla obligatoria, corrige un problema real detectado en produccion (2026-09-16,
carrusel "El Dolor Que No Te Pertenece"): un brief tecnicamente fiel (100% de cobertura,
0% inventado) puede seguir siendo un MAL brief si la distribucion de palabras entre
slides es muy desigual — un caso real tuvo un slide con 112 palabras (4.3x el promedio)
mientras otros tenian 25.** La narrativa NUNCA es el UNICO criterio para decidir donde
cortar — narrativa y composicion visual se diseñan JUNTAS, en este orden de prioridad:

```
1. Distribución correcta del contenido (fidelidad + narrativa)
2. Composición
3. Legibilidad
4. Tamaño tipográfico
```

**Nunca** se resuelve un exceso de texto reduciendo el tamaño de letra hasta que "quepa" —
eso viola la prioridad de arriba. La solucion correcta a un slide sobrecargado es
SIEMPRE redistribuir el corte hacia un slide adyacente con espacio disponible, nunca
encoger la tipografia por debajo del minimo legible.

#### Calculo obligatorio: palabras por slide

Al proponer la distribucion de contenido (justo despues del PASO 6, antes del PASO 6.5),
calcular el conteo de palabras de `exact_text` de cada slide propuesto y construir una
tabla interna:

```
Slide | palabras | densidad | área texto (estimada) | balance
1     | 26       | LOW      | ~24% (estructural)     | balanced
2     | 34       | LOW      | ~31% (estructural)     | balanced
...
```

**NO se busca que todos los slides tengan la misma cantidad de palabras** — eso rompe la
narrativa y produce cortes artificiales. Se busca evitar EXTREMOS innecesarios:

- Si un slide propuesto tiene una cantidad de texto significativamente superior al resto
  (regla practica: mas del doble del promedio de esa tanda) Y el contenido puede dividirse
  en un punto de corte natural (ver "Regla de corte" abajo): **dividirlo** entre ese slide
  y un slide adyacente con menos texto.
- Si un slide propuesto tiene muy poco texto y existe contenido inmediatamente adyacente
  que puede integrarse sin romper la secuencia narrativa: **evaluar mover el corte** para
  equilibrar, nunca reordenar el contenido fuera de secuencia.
- El total de slides sigue limitado a `MAX_SLIDES=10` — la redistribucion mueve
  FRONTERAS entre slides existentes, nunca agrega un slide extra solo para aliviar
  densidad (si hiciera falta un slide 11, la solucion sigue siendo reagrupar dentro de
  los 10, nunca inventar/quitar contenido para evitarlo).

#### Clasificacion de densidad: LOW / MEDIUM / HIGH

La densidad es una categoria ESTRUCTURAL relativa a esa ejecucion especifica (no un
umbral universal fijo) — se calibra con el rango real de palabras/slide de ESE carrusel.
Como referencia orientativa (ajustable segun el rango real observado):

- **LOW**: notablemente por debajo del promedio de esa tanda de slides.
- **MEDIUM**: cercano al promedio.
- **HIGH**: notablemente por encima del promedio.

**Evitar `HIGH, HIGH, HIGH` en slides consecutivos.** Si la redistribucion inicial
produce 3 o mas HIGH seguidos, volver a mover fronteras (nunca contenido) hasta romper
esa secuencia — normalmente basta con adelantar o atrasar un corte en un slide vecino.
Si el contenido real de esa seccion es genuinamente denso y no es posible evitar 2 HIGH
consecutivos sin fragmentar una idea a mitad de frase, 2 HIGH consecutivos SI es
aceptable — la regla dura es evitar 3+, no eliminar toda variacion.

**Que hacer segun la densidad de cada slide (composicion, ver tambien Visual DNA):**

- **HIGH**: usar composicion que soporte mas texto (mas altura util de texto), aumentar
  el area segura de texto, usar bloques bien separados con respiracion entre parrafos,
  evitar texto pegado a los bordes, reducir elementos visuales secundarios que compitan
  con la lectura, mantener el tamaño tipografico legible (nunca encogerlo para compensar).
- **LOW**: NUNCA agregar contenido inexistente para "llenar" el slide. En su lugar:
  aprovechar mejor el espacio visual disponible, usar una composicion mas protagonista
  (la imagen/escena gana presencia), permitir mayor tamaño tipografico cuando corresponda,
  y usar espacio negativo deliberado — el espacio vacio intencional es una herramienta de
  diseño valida, no un defecto, cuando favorece la composicion.
- **MEDIUM**: tratamiento estandar segun las reglas de diseño ya establecidas (ver Visual
  DNA, jerarquia de 3 niveles).

#### Regla de espacio (diseñar la composicion ANTES del texto, no despues)

La escena/composicion de cada slide se diseña PENSANDO en cuanto texto va a llevar — no
se genera primero una escena generica y despues se intenta "meter" el texto encima. Antes
de escribir `scene_description`, ya debe saberse: cuanto texto tiene el slide, donde
estara ubicado, cuanto espacio ocupara aproximadamente, si necesita una columna, una
composicion central, o bloques separados. El texto debe ocupar una proporcion visual
razonable del slide — ni un area vacia sin intencion cuando el contenido podria
distribuirse mejor, ni un area sobrecargada solo para "aprovechar el espacio".

#### Regla de corte: donde SI y donde NO cortar

**Preferir cortes, en este orden:**
1. Despues de una oracion completa (punto final).
2. Despues de un parrafo completo del original.
3. Despues de una idea completa (aunque el original no la separe con parrafo aparte).
4. Despues de una frase independiente dentro de una lista/enumeracion.

**Evitar cortar:**
- Una oracion a mitad de idea (nunca partir una oracion en dos slides con palabras
  distintas a cada lado — si una oracion continua al siguiente slide, debe conservarse
  COMPLETA y literal, solo su UBICACION cambia de slide, nunca su redaccion).
- Una frase que dependa visualmente/semanticamente del fragmento siguiente para tener
  sentido.
- Listas de forma arbitraria (si una enumeracion tiene 4 items, no partirla dejando 3 en
  un slide y 1 solo en el siguiente sin razon narrativa).
- Conceptos relacionados que pierden fuerza si se separan sin necesidad real de espacio.

Si una oracion o bloque es demasiado largo para el slide sin producir densidad visual
excesiva, PUEDE continuar en el siguiente slide — pero manteniendo exactamente las mismas
palabras, nunca resumiendo ni reescribiendo para que "quepa" mejor en uno de los dos.

Cada slide debe registrar `text_break_reason`: por que se corto ahi (ej.
`"natural_sentence_boundary"`, `"paragraph_boundary"`, `"density_rebalance"` cuando el
corte se movio especificamente para equilibrar densidad respecto a la agrupacion
narrativa "por defecto").

### PASO 6.5: Validacion obligatoria de fidelidad (BLOQUEANTE, antes de construir el brief)

**En FAST_PREP:** esta validación ocurre silenciosamente dentro del mismo análisis de
PASO 6. No se muestran las 8 preguntas ni sus respuestas como texto visible. Si se detecta
un problema (contenido perdido o fragmento inventado), se corrige directamente en el JSON
antes de escribirlo. Solo reportar al usuario si hay un problema que no se puede auto-corregir.

Antes de escribir `brief.json` (PASO 7), responder explicitamente las 8 preguntas de
"Validacion obligatoria ANTES de generar" (ver seccion FIDELIDAD DEL CONTENIDO ORIGINAL
arriba), comparando `source_text` completo contra el conjunto de `exact_text` de todos los
slides propuestos:

1. ¿Todo el contenido original esta representado?
2. ¿Hay alguna parte del original que desaparecio?
3. ¿Hay alguna frase que no exista en el original?
4. ¿Se agrego alguna interpretacion?
5. ¿Se invento algun CTA?
6. ¿Se invento alguna conclusion?
7. ¿Se cambio alguna palabra importante?
8. ¿El contenido de todos los slides puede rastrearse a `source_text_fragment`?

Si CUALQUIER respuesta senala un problema (contenido perdido, frase inventada,
interpretacion agregada, CTA/conclusion inventados, palabra importante cambiada, o un
slide sin fragmento fuente rastreable): **NO avanzar al PASO 7 tal cual** — corregir la
distribucion de contenido primero (agregar los slides que hagan falta, ajustar
`exact_text` a su fragmento literal, o eliminar contenido inventado) y volver a validar.

Si un formato no puede aplicarse sin inventar contenido (PASO 6, punto 4), informar esto
al usuario ANTES de continuar y ofrecer alternativas (mas slides, otro formato, o pedir el
contenido faltante) — nunca generar con el hueco relleno de contenido inventado.

### PASO 7: Preguntar que libro/producto se va a promocionar (OBLIGATORIO, sin excepcion)

**Regla maestra — permanente, para TODOS los carruseles futuros**: antes de construir
`brief.json` (PASO 8), Claude SIEMPRE pregunta:

> "¿Qué libro o producto vamos a promocionar en este carrusel?"

Esta pregunta es OBLIGATORIA en cada carrusel nuevo, sin ninguna excepcion. NO se salta ni
se asume automaticamente aunque:
- la tematica del carrusel ya sugiera un libro obvio
- exista un unico producto registrado en `products.json`
- el carrusel anterior haya usado el mismo producto
- el producto parezca "el mismo de siempre" para este tipo de contenido

La tematica NUNCA determina el producto por si sola — el producto lo determina UNICAMENTE
la eleccion explicita del usuario, en cada ejecucion.

**Como preguntar**: usar `AskUserQuestion` mostrando los productos ya existentes en
`products.json` como opciones seleccionables (hasta 3 + la opcion "Otro" incorporada del
tool para escribir uno nuevo). Si hay mas de 3 productos registrados, usar el mismo patron
de preguntas secuenciales del PASO 4 (Pregunta A con los primeros 3 + "Ver mas", Pregunta B
con el resto) en vez de recortar la lista arbitrariamente.

**Si el usuario selecciona un producto ya registrado en `products.json`**:
- usar EXACTAMENTE el nombre registrado (`product_name`)
- usar EXACTAMENTE su `purchase_url` registrado
- usar cualquier otra informacion ya disponible de ese producto (`notes`, etc.)
- nunca modificarlo ni "mejorarlo" al reutilizarlo

**Si el usuario indica un producto que NO existe todavia en `products.json`**:
- pedir unicamente la informacion minima necesaria para registrarlo: nombre exacto del
  producto y enlace de compra
- agregarlo a `products.json` (mismo archivo y esquema que ya existe — ver PASO 10.1)
- dejarlo disponible para cualquier carrusel futuro que lo vuelva a elegir

**Nunca inventar** un producto que el usuario no menciono, ni un enlace que el usuario no
proporciono, ni sustituir el enlace de un producto por el de otro solo porque el dominio o
el nombre se parezcan (ver el caso real documentado en `products.json` sobre
"Sanando con Mamá" vs. el dominio `constelacionesfamiliaresoficial.com`).

**Registrar la eleccion en `brief.json`**: agregar (o completar) el bloque de nivel raiz
`product`:
```json
{
  "product": {
    "product_name": "Nombre exacto elegido por el usuario en este PASO",
    "purchase_url": "URL de compra real (del registro existente o recien proporcionada), o null si el usuario aun no la tiene"
  }
}
```
Este bloque queda asociado UNICAMENTE a este carrusel — nunca se hereda automaticamente de
un `brief.json` anterior sin volver a pasar por esta pregunta.

Si el usuario responde que este carrusel no promociona ningun producto, registrar
`"product": {"product_name": null, "purchase_url": null}` (el bloque debe existir siempre,
aunque estos dos campos internos puedan ser `null`) y continuar — el PASO 10 (entregables)
generara la descripcion igual, pero el CTA sera de reflexion/reconocimiento sin dirigir a
ninguna compra.

### PASO 8: Entregar decisiones + prepare_carousel.py (arquitectura reingenieria 2026-09-19)

**Principio:** Claude es inteligencia visual y narrativa. Python es el ejecutor determinista.
Claude NO crea carpetas, NO extrae referencias, NO valida JSON manualmente, NO escribe
`brief.json` a mano. Todo eso lo hace `prepare_carousel.py` en una sola invocacion.

**Tool calls para PASO 8 completo:** 1 Write + 1 Bash (antes: 28+ tool calls).

#### Qué decide Claude (11 campos por slide)

Python calcula automaticamente 5 campos de cada slide a partir de los datos que Claude
entrega (`word_count`, `text_density`, `estimated_text_area`, `text_area_percentage`,
`visual_balance`). Claude proporciona los otros 11:

**Campos que Claude entrega por slide:**

- `number`, `role`
- `source_text_fragment` — fragmento LITERAL de source_text (nunca reescrito)
- `exact_text` — texto exacto para generacion, rastreable 1:1 a source_text_fragment
- `scene_description` — **máximo 25 palabras**, solo lo visual esencial para la imagen
- `composition` — **máximo 12 palabras**, encuadre + posición + fondo
- `visual_hierarchy` — **máximo 10 palabras**, solo los niveles de énfasis necesarios
- `text_placement` — descriptor de posicion (ej. "lower_third_centered")
- `key_visual_elements` — array de strings (elementos clave, sin prosa)
- `uses_reference_image_directly` — true SOLO en slide 1
- `uses_product_mockup_directly` — true SOLO en slide de CTA si hay mockup

**Campos eliminados del esquema (optimización tokens T0→T1, 2026-09-19):**
`narrative_objective`, `message`, `visual_dna_connection`, `source_location`,
`text_break_reason` — no son requeridos por el pipeline Python ni por el generador.
Si están presentes, el generador los usa; si faltan, el brief sigue siendo válido.

#### Esquema de claude_decisions.json

Claude construye este objeto en un bloque de codigo y luego lo escribe en UNA operacion Write:

```json
{
  "bundle_id": "YYYY-MM-DD-slug",
  "source_text": "Texto completo del post viral tal como lo entrego el usuario",
  "carousel_type": "revelacion_progresiva",
  "visual_dna": {
    "slide_1_master_dna": {
      "fotografia": "BW alto contraste...",
      "composicion": "full bleed, tercio inferior...",
      "tipografia": "sans-serif blanca, texto centrado..."
    }
  },
  "product": {
    "product_name": "Nombre exacto del producto o null",
    "purchase_url": null
  },
  "copy": {
    "description": "Descripcion del post (ver PASO 10.1-10.4)",
    "cta": "CTA de publicacion",
    "hashtags": ["#hashtag1", "#hashtag2", "..."]
  },
  "slides": [
    {
      "number": 1,
      "role": "portada",
      "source_text_fragment": "Umbral del dolor: la linea invisible...",
      "exact_text": "Umbral del dolor",
      "scene_description": "Nina de espaldas en contraluz, BW, silueta en tercio derecho",
      "composition": "Full bleed BW, figura derecha, texto inferior izquierdo",
      "visual_hierarchy": "1. Silueta. 2. Texto ámbar inferior.",
      "text_placement": "lower_third_centered",
      "key_visual_elements": ["nina", "contraluz", "silueta"],
      "uses_reference_image_directly": true,
      "uses_product_mockup_directly": false
    }
  ]
}
```

**Nota**: `product.purchase_url` puede ser `null` — `prepare_carousel.py` lo resuelve
automaticamente desde `products.json` si el nombre coincide. Si el producto es nuevo, el
usuario ya proporcionó la URL en el PASO 7 y Claude la pone directamente aqui.

#### Mostrar tabla de slides ANTES de ejecutar

**En FAST_PREP: omitir esta tabla por completo.** Proceder directamente a las 2 tool calls
(Write `claude_decisions.json` + Bash `prepare_carousel.py`). La tabla es informativa y no
es un gate de aprobación — en FAST_PREP, el JSON escrito es la única representación del plan.

Antes de escribir `claude_decisions.json`, Claude muestra al usuario la tabla de 13 columnas
(ver descripcion original del PASO 8) para que vea el plan. La tabla es INFORMATIVA — no
es un gate de aprobacion. Tambien ejecutar el checklist de fidelidad (PASO 6.5) en este
momento si no se hizo antes.

#### Ejecutar (2 tool calls)

**Paso 1 — Write:** escribir el objeto completo a:
`outputs/bundles/[bundle_id]/claude_decisions.json`

**Paso 2 — Bash:** ejecutar `prepare_carousel.py`:

```bash
PYTHONUNBUFFERED=1 python3 "$HOME/.claude/skills/carousel-gen/scripts/prepare_carousel.py" "$HOME/.claude/skills/carousel-gen/outputs/bundles/[bundle_id]/claude_decisions.json" --fake-reference "[ruta_a_fake_png_si_es_test]"
```

En produccion real (con imagen real adjunta en la sesion):

```bash
PYTHONUNBUFFERED=1 python3 "$HOME/.claude/skills/carousel-gen/scripts/prepare_carousel.py" "$HOME/.claude/skills/carousel-gen/outputs/bundles/[bundle_id]/claude_decisions.json"
```

`prepare_carousel.py` ejecuta autonomamente:
- Crea `outputs/bundles/[bundle_id]/carousel/assets/`
- Extrae `viral-reference.png` del transcript JSONL (via `save_reference_image.py`)
- Resuelve la URL del producto desde `products.json` si es necesario
- Copia el mockup del producto si algun slide lo usa
- Calcula los 5 campos computados por slide (`word_count`, `text_density`, etc.)
- Valida los 21 REQUIRED_SLIDE_FIELDS de todos los slides
- Escribe `brief.json` (una sola vez, ya validado)
- Escribe `copy.json`
- Escribe `pipeline_input.json` con el comando exacto para el siguiente paso
- Imprime `PREPARE_RESULT:<json>` al final de stdout

Si el script termina con `PREPARE_RESULT.status == "READY"`, proceder al PASO 9.
Si termina con `STOP:`, hay un problema que requiere intervencion de Claude antes de continuar.

**El brief.json NO se escribe manualmente.** La estructura completa a continuacion es
referencia historica/documentacion — `prepare_carousel.py` la construye automaticamente:

```json
{
  "bundle_id": "...",
  "reference_image": {
    "local_path": "carousel/assets/viral-reference.png",
    "analysis": {
      "tema_mensaje": "...",
      "copy_estructura": "...",
      "emocion_predominante": "...",
      "elementos_impacto": "..."
    }
  },
  "source_text": "texto completo del post viral (pegado por el usuario o extraido de la imagen)",
  "product": {
    "product_name": "Nombre exacto elegido por el usuario en el PASO 7 (OBLIGATORIO en todo brief, puede ser null si el usuario indico que este carrusel no promociona nada)",
    "purchase_url": "URL de compra real asociada a ese producto (del registro en products.json o recien proporcionada por el usuario), o null"
  },
  "product_mockup": {
    "local_path": "carousel/assets/{nombre-descriptivo}.png",
    "description": "SOLO si el usuario proporciono el mockup/portada real de un producto propio (ver regla general arriba). Omitir este bloque por completo si no aplica — es independiente de `product` (ese es el asset visual; `product` es el nombre/enlace elegido en el PASO 7)."
  },
  "visual_dna": { "...": "... (del Paso 2)" },
  "timing": {
    "skill_started_at": "ISO 8601 registrado en el PASO 0, antes de pedir la imagen",
    "reference_received_at": "ISO 8601 registrado en el PASO 1, cuando llego el adjunto",
    "source_text_confirmed_at": "ISO 8601 registrado en el PASO 3, cuando source_text quedo confirmado",
    "brief_approved_at": "ISO 8601 registrado automaticamente al finalizar la construccion del brief en PASO 8 (justo despues de mostrar la tabla, sin esperar aprobacion del usuario), antes de invocar el PASO 9"
  },
  "carousel_type": "la-gran-noticia | collage-visual | meme-cartoon | recopilacion-ideas | versus | interactivo | tipos-de-x",
  "slide_count": {
    "recommended": "<numero calculado en el Paso 5, especifico de este carrusel, SIEMPRE <= 10>",
    "confirmed": "<numero confirmado por el usuario en el Paso 5, SIEMPRE <= 10>"
  },
  "slides": [
    {
      "number": 1,
      "role": "...",
      "narrative_objective": "...",
      "message": "...",
      "source_text_fragment": "Fragmento LITERAL de source_text del que sale este slide — copiado tal cual, nunca reescrito. Ver FIDELIDAD DEL CONTENIDO ORIGINAL.",
      "source_location": "Donde vive ese fragmento dentro de source_text (ej. 'parrafo 2', 'frase sanadora', 'CTA final', 'linea 5-7')",
      "exact_text": "Texto exacto para Kie AI — rastreable 1:1 a source_text_fragment, con a lo sumo division entre slides / saltos de linea / mayusculas-puntuacion si el usuario lo autorizo",
      "scene_description": "...",
      "composition": "...",
      "visual_hierarchy": "...",
      "text_placement": "...",
      "key_visual_elements": ["...", "..."],
      "visual_dna_connection": "...",
      "connects_prev": null,
      "connects_next": "...",
      "uses_reference_image_directly": true,
      "uses_product_mockup_directly": false,
      "word_count": "<numero entero de palabras de exact_text — ver PASO 6.6>",
      "text_density": "LOW | MEDIUM | HIGH — relativo al rango real de esa tanda de slides, ver PASO 6.6",
      "estimated_text_area": "descriptor estructural de donde vive el texto (ej. 'upper_third_centered', 'centered_stacked_blocks', 'full_height_stacked_paragraphs') — nunca una medicion real en pixeles",
      "text_area_percentage": "<numero entero 0-100, ESTIMACION estructural de cuanto del frame ocupa el texto — nunca presentar como medicion exacta>",
      "visual_balance": "balanced | text_heavy | underutilized — resultado de comparar este slide contra el resto de la tanda",
      "text_break_reason": "por que el corte quedo aqui: 'natural_sentence_boundary' | 'paragraph_boundary' | 'density_rebalance' (cuando el corte se movio especificamente para equilibrar densidad)"
    }
  ]
}
```

**IMPORTANTE — OBLIGATORIO (ver PASO 6.6)**: `word_count`, `text_density`,
`estimated_text_area`, `text_area_percentage`, `visual_balance` y `text_break_reason` son
campos OBLIGATORIOS en TODOS los slides desde esta version — `generate-carousel-gemini.py`
y `generate-carousel.py` (legacy) rechazan un brief que no los tenga, igual que ya hacen
con `source_text_fragment`/`source_location` (ver `REQUIRED_SLIDE_FIELDS` en
`carousel_common.py`). Existen para que la distribucion de texto se planifique
DELIBERADAMENTE (narrativa + densidad + legibilidad + composicion + espacio) en vez de
solo dividir el contenido en partes narrativas sin considerar el equilibrio visual — ver
PASO 6.6 para el metodo completo. `text_area_percentage` y `estimated_text_area` son
SIEMPRE estimaciones estructurales (nunca mediciones reales de pixeles) — deben
presentarse como tales, nunca como datos medidos.

**IMPORTANTE**: `uses_reference_image_directly` debe ser `true` UNICAMENTE en el slide 1.
En todos los demas slides debe ser `false` — heredan el ADN visual en texto (Paso 2), no
la imagen bruta de la referencia.

**IMPORTANTE**: `uses_product_mockup_directly` es un campo OPCIONAL (se puede omitir por
completo si no hay mockup de producto). Cuando existe un `product_mockup` a nivel raiz,
debe ser `true` UNICAMENTE en el/los slide(s) donde el producto real debe aparecer
(tipicamente el slide de CTA), y `false`/ausente en el resto. Nunca coincide con
`uses_reference_image_directly: true` en el mismo slide — son dos imagenes de entrada
distintas (la referencia viral vs. el mockup del producto propio).

**IMPORTANTE**: ni `slide_count.recommended` ni `slide_count.confirmed` tienen un valor
por defecto fijo. Se calculan y confirman de nuevo en cada ejecucion segun el formato y
el contenido de esa referencia especifica.

**IMPORTANTE — OBLIGATORIO (ver "LÍMITE OBLIGATORIO DE SLIDES" arriba)**: ni
`slide_count.recommended`, ni `slide_count.confirmed`, ni la cantidad real de elementos en
`slides[]` pueden superar 10 en ningun `brief.json`. Esto es ademas una compuerta tecnica:
`generate-carousel.py` (`load_brief()`, constante `MAX_SLIDES`) rechaza cargar cualquier
brief que supere ese numero, ANTES de llamar a Kie AI — ver PASO 9.

**IMPORTANTE — OBLIGATORIO**: `source_text_fragment` y `source_location` son campos
OBLIGATORIOS en TODOS los slides (no opcionales, a diferencia de `uses_product_mockup_directly`).
`generate-carousel.py` rechaza generar si faltan en cualquier slide (ver `REQUIRED_SLIDE_FIELDS`
en el script) — esto es una compuerta tecnica, no solo una instruccion. Existen para que
cualquier persona pueda auditar, fragmento por fragmento, que `exact_text` viene
literalmente de `source_text` y que ninguna parte del original quedo fuera del carrusel
completo (recorrer todos los `source_text_fragment` de todos los slides debe reconstruir
~todo `source_text`, sin huecos no explicados).

**IMPORTANTE — OBLIGATORIO**: el bloque `product` a nivel raiz es OBLIGATORIO en todo
`brief.json` (ver `REQUIRED_BRIEF_TOP_FIELDS` en el script — compuerta tecnica, no solo
instruccion). Debe existir siempre, resultado directo de la pregunta del PASO 7 — aunque
sus dos campos internos (`product_name`, `purchase_url`) puedan ser `null` cuando el
usuario indico que no hay producto para este carrusel. Nunca se omite el bloque completo.

5. Mostrar al usuario una tabla con estas 13 columnas por cada slide:
   Numero, Objetivo narrativo, Mensaje, Fragmento fuente (`source_text_fragment`),
   Ubicacion en el original (`source_location`), Texto exacto, Descripcion de escena,
   Composicion, Jerarquia visual, Ubicacion del texto, Elementos visuales importantes,
   Como mantiene el ADN visual, Conexion con el slide anterior/siguiente.

6. Confirmar que el PASO 6.5 (validacion de fidelidad) ya se corrio y las 8 preguntas
   no señalaron problemas — si quedo pendiente, hacerlo ahora antes de mostrar la tabla.

7. **CRONOMETRO GLOBAL REAL**: inmediatamente despues de mostrar la tabla del brief
   (sin esperar aprobacion del usuario), registrar el timestamp actual como
   `brief_approved_at` y actualizar el bloque `timing` de `brief.json` (ya escrito en
   el paso 4) con los 4 timestamps acumulados desde el PASO 0/1/3 — este bloque es lo
   que `generate-carousel-gemini.py` lee para calcular `preparation`/`reference`/`brief`
   en `COSTO_CARRUSEL.txt` (ver seccion propia). Si algun timestamp anterior no se
   registro (ej. brief de un flujo antiguo), omitir esa clave del bloque — nunca
   inventar un valor.

8. Proceder automaticamente al PASO 9 (generacion). No pedir aprobacion del usuario —
   la tabla es informativa, no un gate de aprobacion. La orden de crear el carrusel
   (entregada al invocar el skill) ya autoriza todo el pipeline hasta la exportacion.

### PASO 9: Generar

**Generador PRINCIPAL desde la migracion economica: Google Gemini (Nano Banana 2 Lite).**

**UNA SOLA EJECUCION (regla obligatoria y permanente, ver "FABRICA RAPIDA"): el copy
final (descripcion/CTA/enlace/hashtags) NUNCA depende de ver los pixeles ya generados —
sale de `source_text`, `brief.json` y el producto ya elegido en el PASO 7 (ver PASO 10.1-
10.4 para el contenido exacto), toda esa informacion ya existe ANTES de generar ninguna
imagen.** Por eso, antes de ejecutar el comando de abajo, Claude ya construyo internamente
el JSON de copy (mismo contenido/reglas que PASO 10.1-10.4) y lo escribio en un archivo
temporal dentro del bundle (ej. `outputs/bundles/[bundle_id]/copy.json`) — y lo pasa en la
MISMA llamada via `--copy-json`, para que imagenes + QA + copy + manifest + costo +
exportacion salgan de una unica invocacion del script. `--add-copy` (ver PASO 10.5) sigue
existiendo aparte SOLO para corregir el copy de un bundle YA generado, sin volver a tocar
imagenes — nunca es el camino normal de un carrusel nuevo.

Ejecutar via `run_carousel_pipeline.py` (controlador autonomo — delega a
`generate-carousel-gemini.py`, captura tiempos T0-T5 y escribe `pipeline_result.json`):

```bash
PYTHONUNBUFFERED=1 python3 "$HOME/.claude/skills/carousel-gen/scripts/run_carousel_pipeline.py" "[bundle_id]" --copy-json "$HOME/.claude/skills/carousel-gen/outputs/bundles/[bundle_id]/copy.json"
```

Al terminar, Claude lee `pipeline_result.json` de la raiz del bundle con una sola
operacion `Read` para obtener el resumen estructurado (status, slides, costo, tiempos,
rutas). Alternativa de bajo nivel (cuando se necesita acceso directo al generador):

```bash
PYTHONUNBUFFERED=1 python3 "$HOME/.claude/skills/carousel-gen/scripts/generate-carousel-gemini.py" "[bundle_id]" --skip-interactive --copy-json "$HOME/.claude/skills/carousel-gen/outputs/bundles/[bundle_id]/copy.json"
```

- El script lee `brief.json` como unica fuente de verdad (no depende de ningun otro
  archivo de contenido)
- Antes de nada, `load_brief()` valida el limite obligatorio de `MAX_SLIDES = 10` (ver
  "LÍMITE OBLIGATORIO DE SLIDES" arriba). Si el brief tiene mas de 10 slides, o
  `slide_count.recommended`/`slide_count.confirmed` superan 10, el script imprime el error
  y termina (`sys.exit(1)`) sin llamar a Gemini, sin crear tareas Batch, sin generar
  imagenes y sin gastar creditos — esto no deberia ocurrir nunca si el PASO 5 se siguio
  correctamente, pero es la compuerta tecnica final.
- Antes de generar cualquier slide, revisa la cache local del bundle
  (`carousel/.generation_cache.json`) y **reutiliza** (`REUSED`, costo cero) cualquier
  slide cuyo `prompt_hash` no haya cambiado — nunca regenera lo que ya esta aprobado.
- El Slide 1 (ancla visual maestra) se genera SIEMPRE primero y en solitario, en DIRECT
  MODE; su imagen resultante se usa como referencia real para los slides 2+.
- Los slides 2-10 que SI necesiten generarse (no reutilizables) se generan TODOS EN
  PARALELO en DIRECT MODE (FABRICA RAPIDA — ver "COST OPTIMIZATION" abajo); Batch queda
  reservado para una futura modalidad masiva explicita (`--force-batch`), nunca el
  comportamiento por defecto.
- Cada imagen generada pasa por QA automatico (archivo valido, dimensiones, relacion
  4:5) y Text QA (texto renderizado). Si falla por un motivo CRITICO, se reintenta SOLO
  ese slide, como maximo 1 vez (`MAX_RETRIES=1`) — nunca se regenera el carrusel completo
  por el fallo de un slide, y nunca hay un tercer intento.
- El generador LEGACY de Kie AI (`generate-carousel.py`) sigue existiendo pero esta
  DESACTIVADO por defecto (`KIE_ENABLED=false`) — nunca se invoca automaticamente. Ver
  "COST OPTIMIZATION" para la migracion completa y cuando reactivarlo.

**Regenerar slides especificos** (mantiene coherencia porque relee `brief.json` completo
y reutiliza cache para los que no cambiaron):
```bash
PYTHONUNBUFFERED=1 python3 "$HOME/.claude/skills/carousel-gen/scripts/generate-carousel-gemini.py" "[bundle_id]" --skip-interactive --regenerate-slides "2,4"
```

### Copia automatica a Descargas (regla general y permanente)

`export_final_slides_to_downloads()` copia automaticamente el PAQUETE FINAL completo a:

```
C:\Users\USUARIO\Downloads\Carruseles Carousel-Gen\[bundle_id]\
```

En el camino normal (UNA SOLA EJECUCION, ver PASO 9 con `--copy-json`) se invoca DOS
veces DENTRO de esa misma corrida (nunca hay que llamarla a mano ni lanzar el script una
segunda vez):
1. Justo despues de generar/exportar los slides — en ese punto copia los
   `carousel-NN.png` y el `manifest.json` (sin copy todavia).
2. Justo despues de aplicar el `--copy-json` de esa misma corrida — en ese punto ya
   existe `COPY_FINAL.txt`, asi que esta segunda copia (todavia dentro de la MISMA
   invocacion del script) es la que completa el paquete en Descargas.

Si en cambio se usa `--add-copy` (correccion sobre un bundle ya generado, ver PASO 10.5),
esa invocacion aparte tambien copia a Descargas al final, con el mismo efecto que el paso
2 de arriba.

El paquete final en Descargas siempre debe contener:
- `carousel-01.png` ... `carousel-NN.png` (la cantidad real de slides del carrusel,
  nunca un numero fijo)
- `COPY_FINAL.txt` — UNICO archivo de copy de publicacion (descripcion + CTA + enlace de
  compra + hashtags, ver "COPY_FINAL.txt — archivo unico de copy de publicacion" abajo).
  **Ya NO se generan `description.txt`, `cta.txt` ni `hashtags.txt` como archivos
  independientes** — esa fragmentacion quedo eliminada de forma permanente.
- `COSTO_CARRUSEL.txt` — UNICO archivo de resumen de costo/tiempo (ver "COSTO_CARRUSEL.txt
  — archivo obligatorio de costo y tiempo" abajo).
- `manifest.json` (el de `carousel/manifest.json`, copiado a la raiz de la subcarpeta)
- `brief.json` (copia exacta, nunca modificada al copiarla)
- `pipeline_result.json` — resultado estructurado del pipeline (generado por
  `run_carousel_pipeline.py`; contiene status, slides, costo, tiempos T0-T5). Si el
  PASO 9 se ejecuto con el controlador autonomo, este archivo esta disponible para una
  sola operacion `Read` — ver PASO 11.

**ELIMINADO definitivamente (ya no se genera):** `PARA FACEBOOK/` — subcarpeta que
anteriormente contenia copias renombradas de cada slide. El fix de `mtime` sintetico
creciente se aplico directamente sobre los `carousel-NN.png` en la raiz de Descargas
(via `os.utime()`) — la subcarpeta separada ya no es necesaria.

#### Subcarpeta `PARA FACEBOOK/` — ELIMINADA (referencia historica)

**Esta subcarpeta ya no se genera.** `build_para_facebook_folder()` fue eliminada de
`carousel_common.py`. El fix de `mtime` sintetico creciente se aplica directamente sobre
los `carousel-NN.png` copiados a la raiz de Descargas — no se necesita subcarpeta
separada. Contexto historico:

- Motivo original: `carousel-NN.png` generados en paralelo por Kie AI tenian `mtime`
  no-determinista (reflejaba el orden de finalizacion de cada descarga, no narrativo).
  Caso real 2026-09-15: `carousel-03.png` tenia `mtime` anterior a `carousel-02.png`.
- Fix aplicado: `export_final_slides_to_downloads()` usa `shutil.copy` + `os.utime()`
  para fijar fechas sinteticas estrictamente crecientes por indice narrativo.
- **Limite honesto:** esto solo controla los metadatos que carousel-gen
  genera. El selector de archivos del sistema operativo, el navegador y el propio Meta
  Business Suite son capas fuera del control de carousel-gen — Meta puede, por ejemplo,
  mostrar las miniaturas en el orden en que termina cada subida individual (que depende
  de la red), no en el orden de seleccion. **NUNCA afirmar que este fix garantiza el
  orden final en Meta.** Recomendacion permanente: verificar/reordenar manualmente las
  miniaturas dentro de Meta Business Suite (arrastrando, si el editor lo permite) antes
  de publicar cualquier carrusel — es la unica verificacion 100% fiable.
- Se genera automaticamente para CUALQUIER carrusel futuro, sin importar la cantidad de
  slides (6, 7, 9, 20, 30...) — la numeracion usa siempre al menos dos digitos con ceros
  a la izquierda (`01`, `02`, ..., `09`, `10`...), y mas digitos si el carrusel tuviera
  mas de 99 slides.
- Cada `NN_SLIDE.png` tiene el mismo contenido EXACTO (bytes identicos) que el
  `carousel-NN.png` correspondiente — nunca se recomprime, redimensiona, recorta, edita
  ni regenera ninguna imagen; solo se normaliza el metadato de fecha del archivo copiado.
- Se refresca en cada exportacion: si una corrida anterior dejo una cantidad distinta de
  slides (por ejemplo tras `--regenerate-slides`), los `NN_SLIDE.png` sobrantes se
  eliminan primero para que la carpeta siempre refleje unicamente el conteo actual.
- Nunca se crean/modifican los `carousel-NN.png` originales, ni se cambia su ubicacion.

NUNCA copia `carousel-assets-needed.md`, la carpeta `assets/` (referencias, mockups) ni
ningun otro archivo interno/temporal de generacion — solo los archivos finales listos
para publicar. Si `COPY_FINAL.txt`/`manifest.json` aun no existen (por ejemplo, justo
despues de generar imagenes pero antes de `--add-copy`), la funcion copia lo que sí exista
y avisa cuales faltan todavia — no es un error, se completa solo en la siguiente llamada.
`brief.json` en cambio siempre deberia existir ya (se crea en PASO 8, antes de generar),
asi que normalmente se copia desde la primera llamada.

- La carpeta `Carruseles Carousel-Gen` y la subcarpeta `[bundle_id]` se crean solas si no
  existen — nunca hay que crearlas a mano.
- `[bundle_id]` ya es un slug limpio (minusculas, sin acentos, con guiones — PASO 8), asi
  que se reutiliza tal cual como nombre de subcarpeta, sin transformarlo.
- Es SIEMPRE una copia (`shutil.copy2`, preserva metadata): el bundle original en
  `outputs/bundles/[bundle_id]/` nunca se mueve, se renombra ni se reemplaza.
- En una regeneracion parcial (`--regenerate-slides`), vuelve a copiar el estado COMPLETO
  actual de `carousel/` (todos los `carousel-NN.png` presentes en ese momento, no solo los
  regenerados en esa corrida) — Descargas siempre refleja el carrusel completo y vigente.
- Esta regla aplica a TODOS los carruseles futuros sin excepcion, sin importar tematica,
  formato, cantidad de slides, referencia visual o estilo — no es especifica de ningun
  carrusel.
- El resumen final del script imprime `Carrusel guardado en: [ruta completa]` cuando la
  copia se realizo con exito.

### PASO 10: Generar el paquete completo (slides + COPY_FINAL.txt + COSTO_CARRUSEL.txt) — OBLIGATORIO

**Regla general y permanente**: para CUALQUIER carrusel, Claude SIEMPRE redacta
descripcion, CTA y hashtags, y los guarda UNIFICADOS en un unico archivo de publicacion:
`COPY_FINAL.txt` (ver "COPY_FINAL.txt — archivo unico de copy de publicacion" mas abajo).

**UNA SOLA EJECUCION (ver PASO 9)**: 10.1-10.4 (que redactar) se resuelven ANTES de
llamar al script — el contenido no depende de las imagenes ya generadas — y 10.5 (como
guardarlo) ya no es una segunda invocacion separada del script: es el mismo `--copy-json`
que viaja en la llamada de generacion del PASO 9. El script, en esa misma corrida, genera
tambien automaticamente `COSTO_CARRUSEL.txt` (ver seccion propia) — Claude no necesita
pedirlo ni redactarlo, solo verificar que existe antes del informe final (PASO 11). Esto
aplica a todos los carruseles futuros, sin importar tematica, formato o producto asociado
— nunca es una excepcion puntual de un carrusel.

**Regla de no finalizar incompleto**: un carrusel NO se considera terminado si falta
cualquiera de estos 6 elementos: (a) algun slide, (b) descripcion, (c) CTA, (d) enlace de
compra (cuando el producto elegido en el PASO 7 tiene uno), (e) hashtags, (f)
`COSTO_CARRUSEL.txt`. Si el producto elegido no tiene `purchase_url` en ningun lado (ni
en `brief.json.product`, ni en `products.json`), Claude se DETIENE aqui y pide el enlace
al usuario — nunca inventa uno ni entrega el paquete como "completo" sin el.

Estos entregables son contenido de PUBLICACION, no de los slides: la redaccion aqui
descrita NUNCA modifica `exact_text` ni ningun campo de `brief.json`. La regla de
fidelidad del carrusel (ver arriba) sigue teniendo prioridad absoluta sobre los slides;
este paso solo agrega texto nuevo, separado, para el pie de foto del post.

**Quien hace el trabajo de redaccion**: Claude, no el script — `generate-carousel.py` no
tiene ni debe tener logica de generacion de texto (solo llama a Kie AI para imagenes). El
script unicamente GUARDA lo que Claude redacta, via `--add-copy` (ver mas abajo), y ese
mismo modo RECHAZA guardar el paquete si hay `product` sin `purchase_url` — compuerta
tecnica que refuerza la regla de no finalizar incompleto.

#### 10.1 — Resolver el producto ya elegido en el PASO 7 (nunca volver a preguntar aqui)

El producto de este carrusel YA quedo decidido por el usuario en el PASO 7 y registrado en
`brief.json.product`. Este paso NO vuelve a preguntar ni a inferir el producto — solo
resuelve su `purchase_url` si todavia no estaba fijado:

- Leer `brief.json.product.product_name` y `brief.json.product.purchase_url`.
- Si `product_name` es `null` (el usuario eligio no promocionar nada en este carrusel):
  generar igualmente la descripcion (10.2), pero el CTA (10.3) se limita a una invitacion
  a la reflexion/reconocimiento SIN dirigir a ninguna compra — no hace falta enlace.
- Si `product_name` existe pero `purchase_url` es `null`: buscarlo en `products.json` (ver
  esquema abajo) por coincidencia EXACTA de nombre. Si aparece ahi, usarlo. Si tampoco
  aparece ahi, DETENERSE (ver "Regla de no finalizar incompleto" arriba) y pedir el enlace
  al usuario — nunca inventarlo, nunca usar el de otro producto aunque el dominio se
  parezca.

**Registro persistente de enlaces de compra — `$HOME/.claude/skills/carousel-gen/products.json`**:

Este archivo (a nivel de INSTALACION del skill, no por bundle) es la fuente de verdad
reutilizable de `purchase_url` por producto, para que el usuario nunca tenga que repetir
un enlace ya proporcionado en un carrusel anterior. Esquema:

```json
{
  "products": {
    "Nombre exacto del producto": {
      "purchase_url": "https://...",
      "added_at": "ISO timestamp",
      "notes": "contexto opcional"
    }
  }
}
```

Orden de resolucion de `purchase_url` (resumen — ver tambien PASO 10.1 arriba):

1. Si `brief.json.product.purchase_url` de ESTE carrusel ya tiene un valor (porque el
   usuario lo proporciono al responder la pregunta del PASO 7), usarlo — es mas especifico
   que el registro global.
2. Si no, buscar `brief.json.product.product_name` en `products.json` (coincidencia EXACTA
   de nombre, nunca aproximada ni por similitud de dominio/URL). Si existe, usar ese
   `purchase_url`.
3. Si no aparece en ninguno de los dos lugares, DETENERSE y pedir el enlace al usuario (ver
   "Regla de no finalizar incompleto") — nunca inventarlo ni reutilizar el enlace de un
   producto distinto solo porque el dominio se parece.

Cuando el usuario proporcione un enlace de compra nuevo para un producto (en cualquier
momento, no solo durante la construccion de un brief), agregarlo/actualizarlo en
`products.json` bajo el nombre EXACTO de ese producto — nunca asociarlo a otro producto,
aunque el carrusel activo en ese momento promocione algo distinto. Esta actualizacion NO
toca `brief.json` de ningun carrusel existente ni regenera imagenes.

`purchase_url` final: usar EXACTAMENTE el valor resuelto arriba. Si es `null`, el CTA no
lleva enlace — nunca inventar uno ni usar un enlace generico o de otro producto.

#### 10.2 — Descripcion del carrusel

Se construye a partir de `source_text` completo, el `brief.json` validado, los
`exact_text` de los slides, la tematica real y el producto asociado (si existe) — nunca
solamente del titulo/hook.

Debe:
- explicar de que trata el carrusel
- desarrollar brevemente la idea central
- conectar con la emocion o conflicto que plantea
- mantener el tono humano, emocional y reflexivo del contenido original
- despertar identificacion en quien lo lee
- invitar a reflexionar
- sonar natural para redes sociales (no como ficha tecnica)
- mantener el enfoque de emociones/relaciones/familia/heridas/patrones/vinculos/sanacion
  cuando el carrusel lo tenga

NUNCA debe:
- inventar informacion o agregar afirmaciones no respaldadas por el contenido
- cambiar el significado del carrusel
- resumir de forma superficial al punto de perder la esencia
- copiar los slides completos
- convertir el contenido en marketing generico
- usar frases vacias tipo "en este carrusel descubriras..."
- inventar testimonios o resultados garantizados
- hacer afirmaciones medicas o psicologicas que no esten en la fuente

#### 10.3 — CTA emocional hacia el producto (regla CRITICA)

Antes de escribir el CTA, responder internamente (no hace falta mostrarlo, pero SI
razonarlo explicitamente):

1. ¿Cual es el dolor principal del carrusel?
2. ¿Que herida, conflicto, patron o necesidad esta mostrando?
3. ¿Que transformacion o proceso propone el contenido?
4. ¿Que producto/libro corresponde a esa problematica (ver 9.1)?
5. ¿Por que ese producto es una continuacion natural del carrusel?

El CTA sigue esta transicion, nunca un anuncio generico pegado al final:

```
DOLOR DEL CARRUSEL -> CONCIENCIA -> NECESIDAD DE SANACION/PROFUNDIZACION -> PRODUCTO COMO SIGUIENTE PASO
```

Debe sentirse como "si esto te toco, hay un siguiente paso" — nunca como un anuncio
escrito por separado y pegado al final.

PROHIBIDO usar CTAs genericos: "Conoce nuestro libro.", "Compra ahora.", "Haz clic en el
enlace.", "Descubre este maravilloso libro.", "Si te gusto este contenido, compra...",
"Te invito a conocer...".

**Intensidad emocional**: puede usar identificacion, dolor, reflexion, reconocimiento,
esperanza, posibilidad de cambio, invitacion a sanar, responsabilidad personal. NUNCA
miedo exagerado, culpa, amenazas, presion artificial, falsas urgencias, promesas de
curacion, "si no compras seguiras sufriendo", "este libro cambiara tu vida garantizado",
ni afirmaciones clinicas no respaldadas.

El enlace de compra se agrega al final del CTA UNICAMENTE si `purchase_url` existe (ver
9.1) — nunca inventarlo ni sustituirlo.

#### 10.4 — Hashtags

Generar entre 8 y 10 hashtags especificos a: tematica del carrusel, dolor/problema
tratado, nicho, relaciones, emociones, familia, sanacion, concepto especifico del
contenido. NUNCA hashtags genericos de marketing (#marketing, #emprendedores, #negocios,
#ventas, #dinero) salvo que el contenido realmente trate de eso.

#### 10.5 — Guardar el copy unificado (via el script, nunca a mano)

Escribir un JSON temporal con los 5 campos:

```json
{
  "description": "...",
  "cta": "...",
  "hashtags": ["...", "...", "..."],
  "product": "nombre real o null",
  "purchase_url": "url real o null"
}
```

**Camino normal (UNA SOLA EJECUCION, ver PASO 9)**: este JSON se escribe ANTES de llamar
al script y se pasa como `--copy-json "/ruta/al/copy.json"` en la MISMA llamada que
genera las imagenes (PASO 9) — nunca hace falta una segunda invocacion completa del
script solo para el copy.

**Camino de correccion/historico (`--add-copy`)**: para corregir o completar el copy de
un bundle que YA se genero (por ejemplo, un bundle antiguo, o si el copy inicial tenia un
error) — esto NUNCA llama a Kie AI ni a Gemini, ni toca imagenes ni `brief.json`:

```bash
python3 "$HOME/.claude/skills/carousel-gen/scripts/generate-carousel-gemini.py" "[bundle_id]" --add-copy "/ruta/al/copy.json"
```

(El generador legacy `generate-carousel.py` acepta el mismo flag `--add-copy` con
identico comportamiento, por si el bundle se genero con Kie AI.)

Cualquiera de los dos caminos crea, dentro de la raiz del bundle
(`outputs/bundles/[bundle_id]/`), UN UNICO archivo de copy de publicacion:

- `COPY_FINAL.txt`

**Ya NO se crean `description.txt`, `cta.txt` ni `hashtags.txt` como archivos
independientes** — esa fragmentacion quedo eliminada de forma permanente (ver
"COPY_FINAL.txt — archivo unico de copy de publicacion" mas abajo).

Y fusiona en `carousel/manifest.json` (sin tocar el resto del manifest ni la lista de
slides): `"description"`, `"cta"`, `"hashtags"`, `"product"`, `"purchase_url"` — con
`null`/`[]` cuando algun dato no existe, nunca inventado — y `"copy_final_file"`, que
registra que el archivo fisico de publicacion es `COPY_FINAL.txt`. Los campos
`description`/`cta`/`hashtags`/`product`/`purchase_url` del manifest se mantienen como
metadatos estructurados internos utiles (por ejemplo para reconstruir `COPY_FINAL.txt` si
hiciera falta) — el archivo de publicacion en si sigue siendo unicamente `COPY_FINAL.txt`.

**Compuerta tecnica (regla de no finalizar incompleto)**: si el JSON pasado a
`--copy-json` o a `--add-copy` trae `product` con un nombre pero `purchase_url`
vacio/`null`, el script RECHAZA guardar el copy (no crea `COPY_FINAL.txt` ni toca el
manifest) e indica que hay que resolver el enlace primero — nunca lo deja pasar en
silencio. Resolver el enlace (PASO 10.1) antes de construir ese JSON. Con `--copy-json`
esto NUNCA bloquea las imagenes ya generadas en esa misma corrida — solo el copy queda
sin guardar hasta corregir el enlace (con `--add-copy`, sobre el mismo bundle, una vez
resuelto).

#### 10.6 — Mostrar el resultado al usuario

Presentar siempre con este formato exacto (paquete completo — slides + copy unificado +
producto promocionado). El contenido mostrado es el mismo que queda escrito en
`COPY_FINAL.txt`:

```
========================================
CARRUSEL COMPLETO
========================================

SLIDES
- Cantidad total: XX/XX
- Todos los archivos generados y validados.
- Ruta de Descargas.

----------------------------------------
DESCRIPCIÓN
----------------------------------------

[description]

----------------------------------------
CTA
----------------------------------------

[CTA emocional]

----------------------------------------
ENLACE DE COMPRA
----------------------------------------

[purchase_url]

----------------------------------------
HASHTAGS
----------------------------------------

#...
#...
#...

----------------------------------------
PRODUCTO PROMOCIONADO
----------------------------------------

[Nombre exacto del libro/producto]

========================================
```

Un carrusel no se reporta como terminado hasta que los 6 componentes (slides,
descripcion, CTA, enlace, hashtags, `COSTO_CARRUSEL.txt`) esten disponibles — ver "Regla
de no finalizar incompleto" arriba. Los 4 del medio (descripcion, CTA, enlace, hashtags)
viven todos dentro de un unico archivo fisico, `COPY_FINAL.txt` — ver seccion siguiente.
Este bloque 10.6 es la presentacion detallada del COPY; el cierre real de la ejecucion es
el informe corto del PASO 11 (obligatorio, formato fijo) — despues de ese informe el
trabajo se detiene (ver "FABRICA RAPIDA" › "Regla de terminación").

### PASO 11: Informe final y regla de terminación (OBLIGATORIO, ultimo paso de toda ejecucion)

Una vez que `COSTO_CARRUSEL.txt` existe (PASO 10 completo), Claude entrega UN SOLO
informe final, corto, con este formato exacto — nunca el bloque largo de 10.6 como
cierre, y nunca ambos como si fueran mensajes separados de "aun sigo trabajando":

```
CARRUSEL TERMINADO

Bundle:
<bundle_id>

Slides:
X/X

Generados:
X

Reutilizados:
X

Regenerados:
X

Retries:
X

TEXT QA:
PASS / PARTIAL / FAIL

Cobertura:
100%

Inventado:
0%

Costo:
$X USD (o N/D si no hay precio configurado)

Orquestacion (Claude):
X min X sec

Generacion + QA + export (Python):
X min X sec

Wall-clock total:
X min X sec

COPY_FINAL:
<ruta>

COSTO_CARRUSEL:
<ruta>

Downloads:
<ruta>
```

Los valores de `Generados`/`Reutilizados`/`Regenerados`/`Retries`/`Costo` se leen
directamente de `COSTO_CARRUSEL.txt` (nunca se recalculan a mano ni se inventan).

**Alternativa estructurada (una sola operacion `Read`)**: cuando el PASO 9 se ejecuto con
`run_carousel_pipeline.py`, el archivo `pipeline_result.json` en la raiz del bundle
contiene todos esos valores ya parseados en JSON — `gemini_calls`, `retries`, `cost_usd`,
`slides_total`, `slides_pass`, `slides_failed`, `text_qa_status`, `timing` T0-T5. Usarlo
en lugar de parsear texto de `COSTO_CARRUSEL.txt` cuando este disponible.

**Como calcular los tres tiempos del informe:**

- **Orquestacion (Claude)**: tiempo desde que Claude inicio el skill hasta que el script
  Python arranco. Calcular como:
  `execution_started_at` (de `cost_log.json`) − `skill_started_at` (de `brief.json > timing`).
  Si `skill_started_at` no existe en el brief (brief antiguo), reportar "N/D".
  Este intervalo cubre TODO lo que Claude hizo antes de lanzar el script: guardar
  referencia, analizar ADN visual, esperar source_text, construir brief, escribir copy.

- **Generacion + QA + export (Python)**: el tiempo de ejecucion del script Python,
  ya reportado en `COSTO_CARRUSEL.txt` como "Duracion total". Cubre generacion de
  imagenes (Gemini), QA local (Tesseract) y exportacion a Descargas. Estos tres
  sub-intervalos no se rastrean por separado sin instrumentacion adicional del script
  — si el usuario necesita el desglose interno, requiere codigo.

- **Wall-clock total**: tiempo real desde el inicio del skill hasta el fin del script.
  Calcular como:
  `execution_finished_at` (de `cost_log.json`) − `skill_started_at` (de `brief.json > timing`).
  Si `skill_started_at` no existe, reportar "N/D".
`Cobertura` e `Inventado` los declara Claude a partir de su propia validacion de
fidelidad del PASO 6.5 (el script no puede medir esto — ver "COSTO_CARRUSEL.txt" ›
"Regla de nunca inventar datos"); si esa validacion detecto algun problema real que no se
corrigio, `Inventado` NUNCA se reporta como `0%` — se reporta el valor real y se explica.

**Después de este informe: DETENERSE.** No buscar errores adicionales, no hacer "una
ultima revision", no regenerar nada, no modificar ningun archivo del bundle ni tocar
bundles historicos, no sugerir mejoras o regeneraciones adicionales de forma proactiva.
Si el usuario pide un cambio despues de este informe, eso es una nueva solicitud
explicita — se trata como tal (puede implicar `--regenerate-slides` sobre el MISMO
bundle, nunca como continuacion automatica del mismo ciclo de correccion).

## COPY_FINAL.txt — archivo unico de copy de publicacion (regla obligatoria y permanente)

**Regla permanente de `carousel-gen`, aplica a TODOS los carruseles futuros, sin
excepcion.** El copy de publicacion (descripcion, CTA, enlace de compra y hashtags) NUNCA
se entrega como archivos separados. Se entrega SIEMPRE como un unico archivo:

```
COPY_FINAL.txt
```

`COPY_FINAL.txt` es el archivo principal que el usuario abre para copiar y pegar
directamente el contenido de publicacion — no debe ser necesario abrir varios archivos
para obtener el copy completo.

### Estructura obligatoria

```
========================================
DESCRIPCIÓN
========================================

[descripcion completa del carrusel]

========================================
CTA
========================================

[CTA completo]

========================================
ENLACE DE COMPRA
========================================

[URL exacta del producto, o "(sin producto asociado en este carrusel)" si el PASO 7 se
resolvio explicitamente sin producto — nunca una URL inventada]

========================================
HASHTAGS
========================================

[hashtags]
```

### Que archivos YA NO se generan

A partir de esta modificacion, `carousel-gen` **NO genera** como archivos independientes:

- `description.txt`
- `cta.txt`
- `hashtags.txt`

El copy de publicacion existe UNICAMENTE como `COPY_FINAL.txt`. No se mantienen
duplicados innecesarios del mismo contenido en archivos sueltos.

### Que NO cambia (metadatos internos)

Esta regla afecta UNICAMENTE a los archivos finales de copy/publicacion. NO significa
eliminar informacion del sistema — se mantienen sin cambios:

- `brief.json` (sigue siendo la fuente estructurada de verdad: `product`, `purchase_url`,
  y el resto de campos existentes, ver PASO 7 y PASO 8)
- `carousel/manifest.json` (sigue registrando `description`/`cta`/`hashtags`/`product`/
  `purchase_url` como metadatos estructurados utiles, ademas de `copy_final_file` que
  apunta a `COPY_FINAL.txt` — ver PASO 10.5)
- `products.json`
- `cost_log.json`
- logs tecnicos, archivos de QA, cache (`.generation_cache.json`, `.batch_state.json`) y
  cualquier otro archivo interno necesario para el funcionamiento de la skill

`COPY_FINAL.txt` es solamente la presentacion final unificada para el usuario — `brief.json`
sigue siendo la fuente estructurada de verdad de la que sale ese contenido.

### `PARA FACEBOOK/` no duplica `COPY_FINAL.txt`

La subcarpeta `PARA FACEBOOK/` (ver PASO 9, "Subcarpeta PARA FACEBOOK") sigue conteniendo
UNICAMENTE los `NN_SLIDE.png` necesarios para la seleccion/publicacion de imagenes — nunca
se copia `COPY_FINAL.txt` dentro de ella, para mantener esa carpeta limpia y dedicada
exclusivamente a los PNG.

### Reglas de contenido (sin cambios)

Esta modificacion es UNICAMENTE de empaquetado/archivo fisico — nunca cambia como se
REDACTA el copy. Siguen aplicando integramente las reglas ya existentes:

- La descripcion sigue basandose en `source_text`, el contenido real del carrusel,
  `brief.json` y el producto seleccionado (ver PASO 10.2).
- El CTA sigue conectado con el dolor/conflicto del carrusel, relacionado naturalmente con
  el producto, sin promesas inventadas, y usando la URL exacta proporcionada por el
  usuario (ver PASO 10.3).
- Los hashtags siguen siendo relevantes al tema y al producto (ver PASO 10.4).
- La pregunta obligatoria del PASO 7 (*"¿Qué libro o producto vamos a promocionar en este
  carrusel?"*) sigue haciendose para cada carrusel nuevo. Una vez elegido el producto: se
  registra `product` y `purchase_url`, se usa la URL exacta (nunca inventada), y se
  incluye en `COPY_FINAL.txt`. Si el producto no tiene URL valida, la entrega final queda
  BLOQUEADA (ver "Regla de no finalizar incompleto", PASO 10).

## COSTO_CARRUSEL.txt — archivo obligatorio de costo y tiempo (regla obligatoria y permanente)

**Regla permanente, aplica a TODOS los carruseles futuros, sin excepcion.** Cada vez que
`carousel-gen` termina un carrusel REAL (no `--dry-run`), se crea automaticamente —
**sin pedir permiso, sin preguntar** — el archivo:

```
outputs/bundles/<bundle_id>/COSTO_CARRUSEL.txt
```

y se copia tambien a la carpeta final de Descargas del carrusel (mismo mecanismo que
`COPY_FINAL.txt`, ver `export_final_slides_to_downloads()`). **No se crea un archivo
separado por slide** — es un unico resumen por carrusel, igual que `COPY_FINAL.txt`.

Lo construye `carousel_common.build_costo_carrusel_text()` / `save_costo_carrusel()`, a
partir de `cost_tracker.CostSummary` (nunca inventa un dato: cualquier campo sin
informacion real disponible se imprime como `N/D`). En el camino normal (UNA SOLA
EJECUCION, ver PASO 9) se escribe UNA sola vez, al final de esa misma invocacion de
`run_generation()`, ya con el copy incluido (`--copy-json`) — con los datos completos y
definitivos de todo el pipeline. Si en cambio se usa `--add-copy` por separado (bundle ya
generado, ver PASO 10.5), `run_add_copy()` vuelve a escribir este archivo con los datos
mas completos disponibles en ese momento.

### Estructura obligatoria

```
==================================================
RESUMEN DE COSTO DEL CARRUSEL
==================================================

Bundle:
<bundle_id>

Fecha:
<fecha>

Modelo:
<modelo>

Resolución:
<resolución>

Formato:
4:5

Slides:
<total>

==================================================
GENERACIÓN
==================================================

Slides generados:
X

Slides reutilizados:
X

Slides regenerados:
X

Total de generaciones reales:
X

Retries:
X

==================================================
TOKENS
==================================================

Input tokens:
X (o N/D si la API no los devolvio para ninguna llamada)

Output tokens:
X (o N/D)

Total tokens:
X (o N/D)

==================================================
COSTO
==================================================

Costo generación de imágenes:
$X USD (o N/D si GEMINI_IMAGE_PRICE_PER_IMAGE no esta configurado)

Costo input:
N/D (no facturado por separado del precio fijo por imagen — ver "COST OPTIMIZATION")

Costo output:
N/D (idem)

Costo regeneraciones:
$X USD (o N/D)

COSTO TOTAL:
$X USD (o N/D)

==================================================
EFICIENCIA
==================================================

Costo promedio por slide:
$X USD (o N/D)

Slides sin regeneración:
X

Slides regenerados:
X

Porcentaje de slides regenerados:
X% (o N/D)

==================================================
TIEMPO
==================================================

Inicio:
HH:MM:SS (o N/D)

Fin:
HH:MM:SS (o N/D)

Duración total:
X min X sec (o N/D)

Tiempo generación + QA:
X min X sec (o N/D — QA corre en linea con cada intento, no se mide como fase separada)

Tiempo QA:
incluido en "Tiempo generación + QA"

Tiempo exportación:
X min X sec (o N/D)

==================================================
CRONOMETRO GLOBAL REAL (extremo a extremo, ver SKILL.md)
==================================================

Tiempo total (wall-clock):
X min X sec (o N/D) — desde `run_started_at` hasta `run_finished_at`. `run_started_at`
puede fijarse ANTES de la primera llamada a Gemini (ver "CRONOMETRO GLOBAL REAL" abajo:
marca `timing.skill_started_at` de `brief.json`, capturada por Claude en el PASO 0/1,
antes de pedir la imagen) — asi este total cubre el pipeline completo, no solo el tiempo
dentro de Python.

  - Preparación (antes de recibir la referencia):
  X min X sec (o N/D)

  - Referencia visual (imagen -> texto confirmado):
  X min X sec (o N/D)

  - Brief (texto confirmado -> brief aprobado):
  X min X sec (o N/D)

  - Generación (llamadas a Gemini, ronda inicial):
  X min X sec (o N/D)

  - QA (estructural + Text QA, ronda inicial):
  X min X sec (o N/D)

  - Reintentos (generación + QA de rondas posteriores):
  X min X sec (o N/D)

  - Exportación:
  X min X sec (o N/D)

  - Finalización (manifest + copy + costo):
  X min X sec (o N/D)

==================================================
RESULTADO
==================================================

TEXT QA:
PASS / PARTIAL / FAIL / N/D

QA visual:
PASS / PARTIAL

Cobertura:
X% (o N/D)

Contenido inventado:
N/D (verificado manualmente en el PASO 6.5 antes de generar — no medible por el script;
el informe final de PASO 11 SI declara este valor, basado en esa validacion)

Bundle final:
<ruta>

==================================================
```

### Regla de "nunca inventar datos"

Cada campo sale de una fuente real y verificable:
- **Generación/tokens/costo**: de `cost_log.json` (entradas reales de `cost_tracker.py`
  para ESE `bundle_id`) — nunca un costo fijo inventado. Si
  `GEMINI_IMAGE_PRICE_PER_IMAGE` no esta configurado, todos los campos de costo son
  `N/D`, nunca `$0.00` ni un numero inventado.
- **Tiempo**: de timestamps reales capturados por el propio script
  (`cost_tracker.CostTracker.run_started_at`/`run_finished_at`/`phase_seconds`, via
  `time.time()`) MAS los timestamps que Claude registro durante el workflow, ANTES de
  que el script exista, en `brief.json["timing"]` (ver PASO 0/1/3/8) — de ahi salen
  `preparation`/`reference`/`brief` y el `run_started_at` real del cronometro global.
  Nunca un tiempo estimado a ojo, y nunca `0` para una fase que no se pudo medir (queda
  `N/D`).
- **Resultado (TEXT QA/QA visual/cobertura)**: del bloque `text_qa` de `manifest.json` y
  de los estados reales (`APPROVED`/`FAILED_FINAL`/etc.) registrados en `cost_log.json`.
- **Contenido inventado**: el script no puede medir fidelidad semantica — ese campo
  siempre queda `N/D` en el archivo fisico; el valor real (0% cuando el PASO 6.5 se sigue
  correctamente) lo declara Claude en el informe final de PASO 11, basado en su propia
  validacion de fidelidad, nunca inventado por el script.

## Logos de herramientas (opcional, independiente del flujo principal)

Si el contenido menciona herramientas conocidas (n8n, ChatGPT, Claude, etc.), el script
las detecta automaticamente y, si el usuario tiene logos oficiales, se pueden colocar en
`carousel/assets/{entidad}.png` para integrarlos via `nano-banana-edit`. Este mecanismo
es completamente opcional y NO afecta el ADN visual del carrusel (que viene siempre de la
imagen de referencia viral).

## Output

El bundle completo (fuente de verdad) vive dentro de la instalacion del skill:
`$HOME/.claude/skills/carousel-gen/`

```
outputs/bundles/[bundle_id]/
├── brief.json                       # Fuente de verdad: referencia, ADN visual, formato, slides
├── COPY_FINAL.txt                   # PASO 10: UNICO archivo de copy (descripcion+CTA+enlace+hashtags, OBLIGATORIO)
├── cost_log.json                    # Interno (COST OPTIMIZATION) — NUNCA se copia a Descargas
└── carousel/
    ├── carousel-01.png through carousel-NN.png
    ├── manifest.json                # incluye description/cta/hashtags/product/purchase_url/copy_final_file (PASO 10)
    ├── carousel-assets-needed.md    # Guia de logos opcionales
    ├── .generation_cache.json       # Interno (cache/reuso) — NUNCA se copia a Descargas
    ├── .batch_state.json            # Interno (estado del ultimo trabajo Batch) — NUNCA se copia
    └── assets/
        ├── viral-reference.png      # Imagen de referencia viral (OBLIGATORIA)
        ├── {mockup-producto}.png    # Mockup/portada real de producto (OPCIONAL, ver regla general)
        └── *.png                    # Logos opcionales de entidades detectadas
```

Ademas, al final de cada generacion se copian automaticamente los slides finales a
Descargas (ver "Copia automatica a Descargas" en el PASO 9) — una COPIA lista para
publicar, independiente del bundle original:

```
C:\Users\USUARIO\Downloads\Carruseles Carousel-Gen\[bundle_id]\
├── carousel-01.png
├── carousel-02.png
└── ... (los N slides finales del carrusel, sin manifest/assets/md)
```

## Tiempos y Costos

- Generador principal (desde la migracion economica): Google Gemini, modelo
  `GEMINI_IMAGE_MODEL` (por defecto `gemini-3.1-flash-lite-image`, "Nano Banana 2 Lite"),
  resolucion `IMAGE_SIZE=1K`, formato `IMAGE_ASPECT_RATIO=4:5`. Configuracion central
  unica en `scripts/gemini_config.py` — nunca hardcodeada en otro archivo.
- Generacion (FABRICA RAPIDA): Slide 1 primero y en solitario (DIRECT MODE, ancla visual
  maestra), luego TODOS los slides 2-10 que realmente necesiten generarse (no
  reutilizables desde cache) EN PARALELO, tambien en DIRECT MODE — nunca Batch por
  defecto (ver "COST OPTIMIZATION" abajo).
- Costo: se registra en `cost_log.json` por bundle (nunca se copia a Descargas tal cual,
  pero su resumen SI se copia como `COSTO_CARRUSEL.txt`, ver seccion propia). El costo
  ESTIMADO usa `GEMINI_IMAGE_PRICE_PER_IMAGE` (vacio por defecto — nunca se inventa un
  precio; el usuario debe confirmarlo en la documentacion oficial de Google y
  configurarlo en `.env`). El uso REAL que la API devuelve (tokens) se guarda por
  separado en `actual_usage` de cada entrada — nunca se presenta como si fuera el costo
  facturado real. Ver seccion "COST OPTIMIZATION" abajo para el detalle completo.
- Generador legacy (Kie AI, `nano-banana-2` @ 1K, ~$0.04/imagen publicado por Kie):
  sigue en `scripts/generate-carousel.py`, pero DESACTIVADO por defecto
  (`KIE_ENABLED=false`) — nunca se invoca automaticamente desde esta migracion.

## COST OPTIMIZATION (migracion economica: Google Gemini / Nano Banana 2 Lite)

Esta seccion documenta la arquitectura de generacion de imagenes MAS RECIENTE del skill,
diseñada para minimizar el costo por carrusel sin perder calidad, coherencia visual ni
fidelidad de contenido. Aplica UNICAMENTE a la generacion de imagenes de carruseles — ver
regla permanente "solo carruseles" al inicio de este documento; nada aqui agrega ni
prepara video, reels, shorts ni audio.

### Nuevo proveedor y modelo

- Proveedor: **Google Gemini** (API oficial `google-genai`), reemplaza a Kie AI como
  generador PRINCIPAL.
- Modelo: **Nano Banana 2 Lite**, identificador configurable `GEMINI_IMAGE_MODEL`
  (por defecto `gemini-3.1-flash-lite-image`). Nunca hardcodeado en mas de un lugar —
  toda la configuracion vive en `scripts/gemini_config.py` (`load_config()`), que
  `generate-carousel-gemini.py`, `direct_generator.py`, `batch_manager.py` y
  `gemini_client.py` importan siempre desde ahi.
- Resolucion y formato: `IMAGE_SIZE=1K`, `IMAGE_ASPECT_RATIO=4:5` — version economica,
  NUNCA sube automaticamente a 2K/4K. Si en el futuro se necesita mas calidad, requiere
  una configuracion separada y activacion explicita, nunca automatica.

### Arquitectura (11 responsabilidades separadas, sin logica duplicada)

| Responsabilidad | Archivo |
|---|---|
| Orquestador / planner del carrusel | `generate-carousel-gemini.py` |
| Prompt builder + Visual DNA + export + copy (compartido con Kie legacy) | `carousel_common.py` |
| Reference manager (decide que imagen(es) adjuntar por slide) | `reference_manager.py` |
| Cliente Gemini (Direct y Batch, real y `FakeGeminiClient` para pruebas) | `gemini_client.py` |
| Batch manager (Gemini Batch API) | `batch_manager.py` |
| Direct generator (generacion sincrona 1 a 1) | `direct_generator.py` |
| Reuse / cache manager | `cache_manager.py` |
| Hash de prompt (base de la reutilizacion) | `prompt_hash.py` |
| QA post-generacion | `qa.py` |
| Cost tracker | `cost_tracker.py` |
| Configuracion central | `gemini_config.py` |

### DIRECT MODE vs BATCH MODE (regla obligatoria y permanente: FABRICA RAPIDA nunca usa Batch por defecto)

**El modo NORMAL de produccion de carousel-gen SIEMPRE usa DIRECT MODE, para el Slide 1
Y para los slides 2-10** — nunca Batch, sin importar `ECONOMY_MODE`/`GEMINI_BATCH_ENABLED`
en `.env`. Motivo: Google documenta que la Gemini Batch API puede tardar hasta 24 horas
en completarse; eso es incompatible con el objetivo operativo de esta skill (carrusel de
hasta 10 slides, de brief aprobado a paquete final en ~5 minutos en condiciones
normales). `process_slides()` (`generate-carousel-gemini.py`) ya NO lee
`config.batch_enabled`/`config.economy_mode` para decidir el modo de una corrida normal.

- **DIRECT MODE**: generacion SINCRONA POR SLIDE pero PARALELA entre slides
  (`direct_generator.py`, `ThreadPoolExecutor` con hasta 9 workers — suficiente para
  generar TODOS los slides 2-10 pendientes en una unica tanda, nunca en 2-3 tandas
  secuenciales). Se usa siempre para el Slide 1 (ancla, generado en solitario, ya que los
  slides 2+ lo necesitan como referencia) y para el resto de slides en paralelo real. Ver
  regla "USE_PARALLEL_TOOL_CALLS" mas abajo.
- **BATCH MODE**: quedo reservado EXCLUSIVAMENTE para una futura modalidad explicita de
  produccion masiva/economica — NUNCA se activa automaticamente, ni siquiera con
  `GEMINI_BATCH_ENABLED=true` en `.env`. Se activa UNICAMENTE pasando `--force-batch` en
  esa corrida puntual. Agrupa los slides pendientes en un unico trabajo de la Gemini
  Batch API (`client.batches.create`), con un `InlinedRequest` por slide y
  `metadata={"bundle_id", "slide_number", "prompt_hash"}` para identificar EXACTAMENTE
  que slide corresponde a cada resultado. Si el trabajo termina
  `JOB_STATE_PARTIALLY_SUCCEEDED`, solo los slides que fallaron se reintentan.
- Flags de override para pruebas/diagnostico o para la futura modalidad masiva:
  `--force-direct` / `--force-batch`.
- `GEMINI_BATCH_ENABLED` en `.env` queda en `false` por defecto y ya no controla el modo
  normal — se conserva unicamente como valor informativo en `manifest.json` y por
  compatibilidad con instalaciones existentes del skill.

### Cuando genera, cuando reutiliza

1. Antes de generar CUALQUIER slide, se calcula su `prompt_hash` (ver `prompt_hash.py`):
   deriva del prompt visual completo, `exact_text`, numero de slide, Visual DNA completo,
   `carousel_type`, `aspect_ratio`, `image_size`, `model` y el identificador de la(s)
   imagen(es) de referencia usadas.
2. Se consulta `cache_manager.should_reuse()`: si existe un registro previo en
   `carousel/.generation_cache.json` con el MISMO `prompt_hash`/`model`/`resolution`/
   `aspect_ratio`, el archivo de imagen sigue existiendo en disco y su estado no es
   `FAILED`/`REJECTED`/`RETRYING`/`FAILED_FINAL`, el slide se marca `REUSED` y NO se
   genera — costo cero para ese slide.
3. Solo los slides que no pasan esa compuerta entran a la cola de generacion real
   (Direct o Batch, ver arriba).
4. Si `exact_text`, el Visual DNA, el formato o la referencia usada cambian, el
   `prompt_hash` cambia automaticamente y el slide se regenera — nunca se reutiliza una
   imagen desactualizada.

### Retries y QA (regla obligatoria y permanente: maximo 2 intentos, nunca ciclos sin limite)

**Presupuesto UNICO de reintentos**: `MAX_RETRIES` (por defecto **1**) aplica por igual a
fallos de generacion (error de la API), rechazos de QA estructural Y rechazos de Text
QA — un solo contador compartido, nunca dos presupuestos apilables. Esto significa,
para CUALQUIER slide: **1 intento inicial + como maximo 1 regeneracion = 2 intentos
totales**, y esa unica regeneracion solo se dispara por un motivo CRITICO real (ver "TEXT
QA" abajo para la clasificacion CRITICAL/UNCERTAIN). Tras el segundo intento, el sistema
**acepta el mejor resultado disponible** (queda `FAILED_FINAL`/`TEXT_QA_FAILED` si sigue
sin pasar QA) **y continua** — nunca hay un tercer intento automatico, nunca se vuelve a
intentar porque "podria verse mejor", nunca se regenera por una diferencia puramente
esteticas/subjetiva. El sistema reporta claramente: slide, error, numero de intentos y
costo estimado acumulado.
- QA (`qa.py`) valida automaticamente: el archivo existe, es una imagen valida (PIL puede
  abrirla), tiene dimensiones razonables y respeta la relacion de aspecto configurada
  (`IMAGE_ASPECT_RATIO`, con tolerancia del 3%). El QA NUNCA regenera por su cuenta —
  solo marca `REJECTED` y deja que el orquestador decida el retry, respetando
  `MAX_RETRIES`. Estos criterios (archivo corrupto, proporcion incorrecta) son siempre
  CRITICOS por definicion — nunca generan un rechazo "dudoso".
- Limitacion conocida (ver "Limitaciones" mas abajo): el QA automatico NO evalua
  coherencia visual real con el Slide 1 ni si el mockup de producto se reprodujo
  fielmente — eso sigue requiriendo revision humana antes de publicar, igual que con el
  generador legacy de Kie.

### Prompt: nunca renderizar instrucciones, nunca mover/duplicar el Nivel 1 (regla
obligatoria y permanente, hallazgo real de produccion 2026-09-18, retest "abuela-materna")

**Investigacion real**: en una corrida real, Gemini escribio literalmente `[Espacio
visual]` como texto legible dentro de la imagen del slide 2 — esa frase venia
textualmente del campo `composition`/`visual_hierarchy` del brief ("Los bloques estan
separados por **espacio visual** entre las dos oraciones"), una instruccion de diseño
que Gemini confundio con contenido a renderizar. En otra corrida, los slides 9 y 10
mostraron una frase marcada "Nivel 1 (cian)" **duplicada como titular** al inicio de la
imagen, aunque esa frase vive en medio del `exact_text` — Gemini interpreto el enfasis de
Nivel 1 como permiso para reubicar/repetir la frase en vez de solo cambiarle tamaño/color
en su lugar original.

**Fix aplicado (`build_prompt_for_slide()` en `carousel_common.py`)**: el prompt ahora
incluye, justo despues del bloque `TEXTO EXACTO`, una regla explicita de 3 puntos: (1) ese
es el UNICO texto que debe quedar legible, en ese orden, sin duplicar ninguna
palabra/frase; (2) las secciones DESCRIPCIÓN/COMPOSICIÓN/JERARQUÍA VISUAL/UBICACIÓN DEL
TEXTO son instrucciones para el generador, NUNCA texto a renderizar; (3) el Nivel 1 de la
jerarquia visual es enfasis EN EL LUGAR donde la frase ya esta, nunca una excusa para
moverla o repetirla (ver tambien "Jerarquía tipográfica" arriba). Estas 3 reglas son
refuerzos tecnicos de reglas de fidelidad YA existentes en este documento (nunca inventar
texto, nunca reordenar el contenido) — no son reglas creativas nuevas.

Verificado con una segunda corrida real (2026-09-18): 5 de 10 slides que antes fallaban
por ruido de OCR ahora aprueban en el primer intento o en el retry, sin necesitar mas
regeneraciones — ver tambien la tolerancia a confusion de OCR arriba en "TEXT QA".

### Referencias (nunca enviar mas de las necesarias)

`reference_manager.py` decide, por slide, su `REFERENCE_MODE` (`NONE`, `SLIDE_1`,
`SPECIFIC_REFERENCE`, `BOOK_MOCKUP`) y adjunta SOLO las imagenes estrictamente
necesarias — nunca 3, 4 o 5 referencias a la vez, porque Nano Banana 2 Lite no esta
optimizado para eso:

- El Slide 1 recibe la imagen de referencia viral original (`SPECIFIC_REFERENCE`).
- Los slides 2+ reciben el Slide 1 YA GENERADO como ancla real (`SLIDE_1`) — igual que en
  el generador legacy, pero sin necesitar subirlo a ninguna nube: Gemini recibe los bytes
  de la imagen directamente (`Part.from_bytes`), lo que ademas elimina el paso de "subir
  asset para obtener URL publica" que si necesitaba Kie AI.
- Solo el slide de CTA/portada (marcado `uses_product_mockup_directly`) recibe TAMBIEN el
  mockup real del producto (`BOOK_MOCKUP`) — la UNICA excepcion en la que un slide recibe
  2 referencias a la vez. Si el mockup no esta disponible, ese slide especifico se omite
  con un error claro — NUNCA se inventa una portada generica.

### Control de costos

- `cost_log.json` (raiz del bundle, nunca se copia a Descargas) registra, por cada
  intento de generacion: timestamp, bundle_id, slide_number, model, resolution,
  aspect_ratio, mode (batch/direct), status, reused, retry_count, prompt_hash,
  estimated_cost_usd, `billable` y actual_usage (uso real devuelto por la API, cuando
  esta disponible).
- **`billable`** (booleano por entrada): `true` UNICAMENTE cuando esa llamada real SI
  produjo una imagen (aunque el QA la rechazara despues) — `false` cuando la llamada
  nunca llego a producir una imagen (fallo de red/API antes de recibir bytes, o el slide
  se omitio sin llamar a Gemini por falta de un mockup obligatorio). Los agregados del
  resumen (`generated`, `retries`, `estimated_cost_usd`) se calculan SIEMPRE contando
  cada entrada `billable=True` (generacion inicial + cada retry/regeneracion real) —
  nunca las entradas sin imagen producida. **Regla obligatoria y permanente (corrige un
  bug real de produccion, 2026-09-17, "abuela-materna"): estos agregados se RECALCULAN
  desde `entries` cada vez que se carga o se escribe `cost_log.json` — nunca se cargan
  ni se acumulan por separado.** Antes, una segunda invocacion sobre el mismo bundle
  (tipicamente `--add-copy`, que reconstruye `CostTracker` desde disco) podia dejar
  `generated`/`estimated_cost_usd` en `0` en el archivo final aunque las 19 llamadas
  reales seguian intactas en `entries` — nunca debe volver a ocurrir, y el costo total
  siempre debe coincidir exactamente con `total_real_image_generations × price_per_image_usd`.
- `GEMINI_IMAGE_PRICE_PER_IMAGE` es configurable; **confirmado en
  https://ai.google.dev/gemini-api/docs/pricing (verificado 2026-09-16) = 0.0336**
  (`gemini-3.1-flash-lite-image`: $30.00 por 1M tokens de salida de imagen, ~1120 tokens
  por imagen 1K; la entrada cuesta $0.25 por 1M tokens, tipicamente <$0.001/slide y no
  incluida en este valor fijo). Verificado con una llamada real de produccion (1 slide,
  DIRECT MODE): `actual_usage` reporto 3243 tokens de entrada + 1277 de salida, costo real
  ≈ $0.039 para esa llamada especifica — cercano al valor fijo de $0.0336/imagen usado
  como estimacion rapida. Si el precio oficial cambia en el futuro, actualizar este valor
  en `.env` — el sistema NUNCA lo inventa por su cuenta, solo usa lo que el usuario
  confirme aqui.
- Si Google factura este modelo por tokens en vez de por imagen, `actual_usage` guarda el
  conteo de tokens crudo devuelto por `usage_metadata` de la API — nunca se convierte a
  USD con una tasa inventada. El sistema distingue siempre `estimated_cost_usd` (calculo
  local) de `actual_usage` (dato real de la API) — nunca se presenta el estimado como si
  fuera el costo real facturado.

### Variables de entorno (`.env`)

```
GEMINI_API_KEY=                          # obligatoria salvo con --fake-provider (pruebas)
GEMINI_IMAGE_MODEL=gemini-3.1-flash-lite-image
IMAGE_ASPECT_RATIO=4:5
IMAGE_SIZE=1K
ECONOMY_MODE=true
GEMINI_BATCH_ENABLED=false                # FABRICA RAPIDA: modo normal SIEMPRE direct; true
                                           # NUNCA activa Batch por si solo (ver --force-batch)
MAX_SLIDES=10                            # nunca configurable por encima del limite duro
MAX_RETRIES=1                            # 1 intento + 1 regeneracion maximo (solo por CRITICO)
GEMINI_IMAGE_PRICE_PER_IMAGE=            # vacio hasta confirmar el precio oficial

KIE_AI_API_KEY=                          # legacy
KIE_ENABLED=false                        # nunca se activa automaticamente
FLOW_ENABLED=false                       # reservado, NUNCA usado por carousel-gen (solo carruseles)
```

### Migracion desde Kie AI

- El generador legacy `generate-carousel.py` (Kie AI) sigue intacto y funcional, pero
  DESACTIVADO por defecto (`KIE_ENABLED=false`). No se borro ningun archivo ni bundle
  historico de Kie.
- Para reactivar Kie explicitamente (caso excepcional): poner `KIE_ENABLED=true` en
  `.env` y ejecutar `generate-carousel.py` directamente en vez de
  `generate-carousel-gemini.py`. El sistema nunca hace fallback automatico de Gemini a
  Kie ni viceversa.
- Los bundles ya generados con Kie (`outputs/bundles/[bundle_id]/`) no se ven afectados
  por esta migracion — sus imagenes, `brief.json` y entregables siguen intactos.

### Limitaciones conocidas

- Sin una `GEMINI_API_KEY` real, no es posible verificar el comportamiento exacto de la
  Gemini Batch API en produccion (formato de `inlined_responses`, tiempos reales de
  polling) — la implementacion se construyo introspeccionando el SDK oficial
  `google-genai` instalado, pero SOLO una ejecucion real con credenciales confirma el
  comportamiento end-to-end contra la API en vivo.
- El QA estructural (archivo/dimensiones/aspect ratio) NO verifica coherencia visual real
  ni reproduccion fiel del mockup — eso sigue requiriendo revision humana. ~~Tampoco
  verificaba el texto renderizado exacto~~ — RESUELTO 2026-09-16 con la capa **TEXT QA**
  (ver seccion propia mas abajo): ahora SI se verifica automaticamente, via OCR local,
  que el texto dentro de la imagen coincide con `exact_text`.
- ~~El precio real por imagen no estaba confirmado~~ — RESUELTO 2026-09-16: confirmado en
  https://ai.google.dev/gemini-api/docs/pricing y verificado con una llamada real de
  produccion (ver arriba). `GEMINI_IMAGE_PRICE_PER_IMAGE=0.0336` en `.env`. Si Google
  cambia el precio oficial en el futuro, hay que actualizar ese valor manualmente — el
  sistema nunca lo revisa ni lo actualiza solo.
- El mecanismo de logos opcionales (`nano-banana-edit` via Kie) no se migro a Gemini en
  esta fase — es una funcionalidad opcional e independiente del flujo principal (ver
  seccion "Logos de herramientas" abajo); si se necesita, requiere Kie reactivado
  explicitamente o una implementacion Gemini equivalente en una migracion futura.

## TEXT QA (verificacion local del texto realmente renderizado en cada imagen)

**Regla obligatoria y permanente, aplica automaticamente a TODOS los carruseles futuros.**
Nace de un bug real de produccion (2026-09-16, carrusel "El Dolor Que No Te Pertenece"):
el QA estructural (archivo/dimensiones/aspect ratio) aprobo imagenes cuyo texto estaba
corrupto — palabras duplicadas ("EL DOLOR QUE NO TE **TE** PERTENECE", "conoce mi
libro: conoce mi libro:") y palabras deformadas ("esi compartir dir" en vez de
"estabilidad compartida"). La validacion de `brief.json` NUNCA puede detectar esto
porque el error ocurre en el RENDERIZADO de Gemini, no en el contenido del brief.

### Flujo completo

```
SOURCE_TEXT
  -> DISTRIBUCIÓN DE TEXTO (PASO 6.6)
  -> FIDELITY QA (PASO 6.5)
  -> brief.json
  -> GEMINI (Direct/Batch)
  -> imagen generada
  -> QA ESTRUCTURAL (qa.py: archivo/dimensiones/4:5)
  -> TEXT QA (text_qa.py: OCR local + comparacion contra exact_text)
       |
       +-- OK -> TEXT_QA_APPROVED
       |
       +-- ERROR -> TEXT_QA_REJECTED
             -> regenerar SOLO ese slide (nunca el Batch completo, nunca los demas)
             -> Text QA de nuevo
             -> TEXT_QA_APPROVED  o  (tras MAX_TEXT_QA_RETRIES)  TEXT_QA_FAILED
  -> QA FINAL (seccion "24" — cobertura, MAX_SLIDES, producto, CTA, URL, mockup, export)
  -> exportacion
```

### Estrategia: 100% LOCAL, cero llamadas adicionales a Gemini

Text QA usa OCR local con **Tesseract** (via `pytesseract`) sobre el archivo PNG ya
descargado en disco — NUNCA hace una llamada adicional a Gemini para "revisar" una
imagen, así que no aumenta el costo. Si Tesseract/pytesseract no están disponibles en
el entorno (`TEXT_QA_ENABLED=false` o dependencia faltante), Text QA se OMITE
automaticamente (nunca bloquea la generación por falta de una dependencia local
opcional) y el manifest lo refleja honestamente como `"status": "SKIPPED"` — nunca se
reporta `APPROVED` sin haber verificado de verdad.

Requisitos para que funcione: binario de Tesseract-OCR instalado en el sistema +
`pip install pytesseract` (ambos ya confirmados disponibles en este entorno).

### Normalización y detección de errores (`scripts/text_qa.py`)

`normalize_text()` ignora ÚNICAMENTE diferencias irrelevantes: mayúsculas/minúsculas,
acentos (el OCR los pierde con frecuencia), espacios múltiples, saltos de línea y
espacios al inicio/final. `tokenize()` extrae palabras de ese texto normalizado.
**Nunca** ignora palabras duplicadas, faltantes, adicionales o deformadas.

`compare_text(expected, rendered)` alinea los tokens esperados contra los tokens
renderizados (via `difflib.SequenceMatcher`, a nivel de PALABRAS, nunca de líneas — un
mismo texto distribuido en líneas distintas sigue aprobándose) y clasifica cada
diferencia real:

- **DUPLICATED_TOKEN**: el bloque insertado en el renderizado es idéntico al bloque que
  lo precede inmediatamente en el texto esperado (repetición real) — cubre tanto una
  palabra repetida ("TE TE") como una frase/bloque repetido ("conoce mi libro: conoce
  mi libro:").
- **MISSING_TOKEN**: un bloque completo del texto esperado no aparece en el renderizado.
- **EXTRA_TOKEN**: contenido añadido que no coincide con nada esperado alrededor.
- **TEXT_CORRUPTION**: un bloque fue reemplazado por otro de contenido distinto
  (palabras deformadas/ilegibles).

`check_exact_phrase(phrase, rendered_text, label)` es la verificación reforzada para
**frases críticas** (nombre del producto/título del libro, CTA — ver PASO 19/21 abajo):
busca la secuencia EXACTA de la frase en el renderizado; si aparece **exactamente una
vez**, aprueba; si aparece **0 veces**, cae a `compare_text` (detecta deformación o
incompletitud) re-etiquetada como `PRODUCT_TITLE_MISMATCH`/`CTA_MISMATCH`; si aparece
**2+ veces**, rechaza directamente como duplicación de esa frase especifica.

### Distribución de texto (`analyze_distribution`)

Complementa el PASO 6.6: por slide calcula `word_count`, `character_count`,
`num_blocks` (bloques separados por línea en blanco) y `longest_block_chars`, clasifica
`text_density` (LOW/MEDIUM/HIGH, relativo al rango real de esa tanda — nunca un umbral
universal) y genera advertencias (no bloqueantes) ante diferencias extremas (>3x entre
el slide más denso y el más vacío) o 3+ slides HIGH consecutivos. Prioridad siempre:
**legibilidad + ritmo + narrativa** sobre igualdad matemática de palabras.

### Severidad: CRITICAL / UNCERTAIN / SKIPPED (regla obligatoria — "OCR dudoso NUNCA bloquea")

Cada `TextQAResult` tiene un campo `severity`: `PASS` (aprobado), `CRITICAL` (rechazo
real, dispara la unica regeneracion permitida), `UNCERTAIN` (posible falso positivo del
propio OCR — **aprueba igual, nunca bloquea**), o `SKIPPED` (OCR no disponible).

Un hallazgo (`DUPLICATED_TOKEN`/`MISSING_TOKEN`/`EXTRA_TOKEN`/`TEXT_CORRUPTION`) nace
como `CRITICAL`. Antes de rechazar el slide, `_apply_ocr_confidence_downgrade()` mide la
**confianza promedio real del OCR** sobre esa imagen (`extract_ocr_confidence()`, via
`pytesseract.image_to_data`, escala 0-100 nativa de Tesseract). Si esa confianza esta por
debajo de `_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD` (70), el hallazgo se reclasifica
`UNCERTAIN` y **se aprueba igual** — no podemos distinguir con seguridad "el render esta
mal" de "el OCR leyo mal un render correcto", y la duda nunca detiene la fabrica. Si la
confianza es alta (o no se pudo medir), el hallazgo se mantiene `CRITICAL` y SI bloquea
— corresponde a un error de contenido real (texto omitido/inventado/cambiado/duplicado),
no a una duda de lectura.

Esto es distinto de "Tesseract no instalado" (`OCR_UNAVAILABLE`/`skipped=True`, ver
arriba): ahi no hay NINGUNA medicion posible y el Text QA se omite por completo. Aqui SI
hubo una lectura, pero de baja confianza — la fabrica prefiere avanzar antes que gastar
una regeneracion en una duda que quizas ni siquiera es real.

**Resumen operativo por severidad (compuerta tecnica en `save_image_and_qa`,
`generate-carousel-gemini.py`)**:

| Severidad  | ¿Regenera? | ¿Se registra? |
|------------|------------|----------------|
| `PASS`     | No, continua | — |
| `CRITICAL` | Si, maximo 1 vez (`MAX_RETRIES`) | log de rechazo por slide |
| `UNCERTAIN`| **Nunca** | `[WARN]` explicito por slide ("OCR dudoso, NO se regenera") |
| `SKIPPED`  | No, continua | `[WARN]` explicito ("Text QA omitido") |

Nunca existe una tercera generacion: el presupuesto es siempre 1 intento inicial + 1
regeneracion como maximo, sin importar cuantos slides fallen en la misma tanda.

### Tolerancia a confusion tipica de OCR con acentos/ene-con-tilde (regla obligatoria,
hallazgo real de produccion 2026-09-18, retest "abuela-materna")

**Investigacion real**: en una corrida real (10 slides, Gemini real, sin `--fake-provider`),
8/10 slides fueron rechazados por Text QA. Al inspeccionar visualmente los PNG reales
generados, se confirmo que **la mayoria de esos "rechazos" eran imagenes perfectamente
correctas** — el texto renderizado por Gemini estaba bien escrito, pero **Tesseract lo leyo
mal**, con confianza ALTA (86-91/100 medido, muy por encima de
`_OCR_UNCERTAIN_CONFIDENCE_THRESHOLD`=70), asi que el degradado normal por confianza NUNCA
se activaba. Patron confirmado en produccion:

- **ó/ú confundidas**: "biológicos" -> "biolégicos"/"biolegicos", "óvulo" -> "6vulo"
  (la tilde a veces se lee como el digito "6").
- **ñ leida como DOS caracteres**: "años" -> "afios", "acompañar" -> "acompaiiar" (el
  glifo de la eñe se confunde con "fi"/"ii" en tipografias bold/condensadas).
- **Fusion de palabras por kerning apretado**: "de su" -> "desu", "por ella o" -> "porellao"
  (sin perdida real de contenido, solo un problema de segmentacion del OCR).

**Fix aplicado (`text_qa.py`)**: dentro de `compare_text()`, cualquier diferencia
clasificada como `TEXT_CORRUPTION` (reemplazo de bloque) se compara ADEMAS por distancia
de edicion de caracter (`_edit_distance`, Levenshtein simple) entre los bloques JUNTADOS
sin espacios. Si la distancia es lo bastante chica (`_looks_like_ocr_misread`, calibrado
contra los casos reales de arriba: minimo 2 ediciones siempre tolerado por la
confusion de eñe, proporcional para bloques largos, coincidencia exacta tras juntar
espacios siempre tolerada sin minimo de longitud), se reclasifica como
`OCR_LIKELY_MISREAD` en vez de `TEXT_CORRUPTION`:

- Si **todas** las diferencias de un slide son `OCR_LIKELY_MISREAD`: el slide **aprueba**
  (`approved=True`), pero queda trazado con `severity="UNCERTAIN"` (nunca "PASS" silencioso)
  — mismo tratamiento que el resto de casos UNCERTAIN (log `[WARN]` explicito, nunca
  regenera, ver tabla arriba).
- Si hay **al menos una** diferencia real (`MISSING_TOKEN`/`EXTRA_TOKEN`/`DUPLICATED_TOKEN`,
  o un `TEXT_CORRUPTION` que NO paso el filtro de similitud): el slide sigue rechazandose
  como `CRITICAL`, por esa diferencia real — el ruido de OCR tolerado NUNCA enmascara un
  error real (verificado explicitamente, ver `test_25_mezcla_de_error_real_y_ruido_ocr_prioriza_el_error_real`
  en `test_text_qa.py`).

**Palabras cortas (2-3 caracteres)** — ajuste posterior, mismo dia: una segunda corrida
real mostro imagenes 100% correctas rechazadas por pares como "la"/"ia" o "mas"/"mds"
(confirmado visualmente), donde el presupuesto general de 2 ediciones ya no distingue de
forma confiable una confusion de OCR de una palabra distinta. Para bloques de 2-3
caracteres el presupuesto se reduce a 1 sola edicion (`_OCR_MISREAD_MAX_EDITS_SHORT`) —
mas permisivo seria indistinguible del azar a esa longitud.

**Regla dura que NUNCA cambia**: esta tolerancia se aplica UNICAMENTE a reemplazos de
bloque (`TEXT_CORRUPTION`) — jamas a `MISSING_TOKEN` (palabra realmente ausente),
`EXTRA_TOKEN` (contenido inventado) ni `DUPLICATED_TOKEN` (repeticion real). Una palabra
que genuinamente falta, se inventa o se duplica sigue siendo SIEMPRE un error real, sin
importar cuan "parecida" sea a algo del texto esperado — la fidelidad de contenido
(ver "FIDELIDAD DEL CONTENIDO ORIGINAL") nunca se relaja por esta tolerancia.

### Paralelizacion del Text QA (regla obligatoria, ver "FABRICA RAPIDA")

El OCR de los slides de una misma tanda (misma ronda de generacion, ej. los slides 2-10
tras la Fase B) es completamente independiente slide a slide, asi que
`generate-carousel-gemini.py` lo ejecuta en PARALELO (mismo tope de workers que la
generacion de imagenes) — nunca slide-por-slide de forma secuencial. Solo el paso de
guardar resultados/costo/cache se hace despues, en el hilo principal, para evitar
escrituras concurrentes sobre el mismo `cost_log.json`/`.generation_cache.json`.

### Regeneración selectiva y presupuesto único de reintentos

Si un slide es rechazado por Text QA con severidad `CRITICAL`: se regenera **ÚNICAMENTE
ese slide** (nunca el resto del carrusel, nunca los slides ya aprobados), conservando
`exact_text`, `scene_description`, Visual DNA, composición, referencia/ancla, producto y
mockup sin cambios — solo se vuelve a pedir la generación de la imagen.

`MAX_RETRIES` (por defecto **1**) es el ÚNICO presupuesto de reintentos del sistema —
compartido con los fallos de generación/QA estructural (ver "COST OPTIMIZATION" ›
"Retries y QA"), nunca un presupuesto separado para Text QA. Tras agotar ese presupuesto
(1 intento inicial + 1 regeneración), el slide queda `TEXT_QA_FAILED` — el sistema
**acepta el mejor resultado disponible y continúa**, nunca sigue regenerando
indefinidamente ni inicia una "nueva auditoría" después de esa corrección. Ese estado
NUNCA se reutiliza silenciosamente en un rerun futuro (queda en `_NON_REUSABLE_STATUSES`
de `cache_manager.py`).

### Estados (`cache_manager.py`)

`TEXT_QA_PENDING`, `TEXT_QA_APPROVED`, `TEXT_QA_REJECTED`, `TEXT_QA_REGENERATING`,
`TEXT_QA_FAILED`. Un slide solo se considera finalizado cuando queda
`TEXT_QA_APPROVED` (o `APPROVED` simple si Text QA estuvo desactivado/omitido para esa
corrida — siempre trazable via el campo `text_qa_status` del registro de cache y del
manifest). `TEXT_QA_APPROVED` SÍ es reutilizable en un rerun (igual que `APPROVED`);
los demás estados TEXT_QA_* nunca se reutilizan silenciosamente.

### Cache

Un slide `TEXT_QA_APPROVED` con el mismo `prompt_hash`/modelo/resolución/aspect_ratio
produce `REUSE` en un rerun idéntico — 0 llamadas nuevas a Gemini, 0 costo adicional
(verificado con test de integración real, ver PRUEBAS abajo).

### Costos

Cada intento (inicial o de regeneración por Text QA) se registra por separado en
`cost_log.json` vía `cost_tracker.record()`, con `status` distinguiendo
`TEXT_QA_REGENERATING` (reintento en curso) de `TEXT_QA_FAILED` (agotado) de
`TEXT_QA_APPROVED` (éxito) — nunca se cuenta una regeneración selectiva como si fuera
un carrusel completo. Ejemplo: 10 slides iniciales + 1 rechazado + 1 regeneración =
**11 imágenes reales**, nunca 20.

### Manifest (`manifest.json`)

Bloque `"text_qa"` a nivel raíz:

```json
"text_qa": {
  "status": "APPROVED | FAILED | SKIPPED",
  "slides_checked": 10,
  "slides_rejected": 1,
  "slides_regenerated": 1,
  "retries": 1,
  "text_errors_detected": 1,
  "text_errors_fixed": 1
}
```

Y por slide (dentro de `"carousel"`): `expected_text_hash`, `rendered_text_hash`,
`text_qa_status`, `text_qa_retry_count`, `text_qa_rejection_reason`.

### Producto, título y CTA (atención especial)

Todo slide marcado `uses_product_mockup_directly: true` verifica automáticamente, con
`check_exact_phrase` y la etiqueta `PRODUCT_TITLE_MISMATCH`, que
`brief.json.product.product_name` aparece **exactamente una vez** y sin deformar en el
renderizado — detecta tanto duplicación ("EL DOLOR QUE NO TE PERTENECEEE" deformado, o
el título repetido) como palabras faltantes del título completo. La CTA se verifica con
la misma lógica general de `compare_text`/`check_exact_phrase` sobre el `exact_text`
del slide de cierre — el sistema NUNCA modifica el CTA o el título aprobados para que
coincidan con un error de renderizado; siempre se regenera la imagen.

### Mockup real (sin cambios de sistema)

Text QA NO reemplaza ni modifica el sistema de mockups ya existente (ver "Regla
general: mockup de producto proporcionado por el usuario" arriba) — sigue siendo
`product_mockup.local_path` en `brief.json`, nunca inventado. Text QA solo AÑADE una
verificación extra sobre el título visible cuando es legible por OCR.

### `--fake-provider` y Text QA

Text QA se **desactiva automáticamente** en modo `--fake-provider` (las imágenes
sintéticas de `FakeGeminiClient` son PNGs de 1x1 píxel sin texto real — hacerles OCR
solo produciría rechazos falsos). Ese modo sigue sirviendo para probar cache/retries/
batch-direct; la capa de Text QA en sí se prueba con su propia suite dedicada
(`scripts/test_text_qa.py`), que sí usa OCR real sobre imágenes locales generadas con
PIL — sin ninguna llamada a Gemini ni Kie.

La auditoria de FABRICA RAPIDA (paralelizacion real de generacion y de Text QA, fallo
rapido sin placeholder ante attachment ausente, UNCERTAIN nunca regenera, cronometro
global, cost_tracker/`billable` nunca en cero tras `--add-copy`, UNA SOLA EJECUCION con
`--copy-json`) tiene su propia suite dedicada, tambien sin llamadas a Gemini/Kie:
`scripts/test_execution_bottlenecks.py`.

### Limitación conocida

Si el texto tiene tipografía muy estilizada/artística (curvas, distorsión decorativa
extrema) o el contraste texto/fondo es muy bajo, el OCR puede fallar en leer el texto
correctamente aunque la imagen sea visualmente correcta — un falso rechazo posible.
Ante esto, Text QA solo puede confirmar o señalar duda; la decisión final de publicar
siempre puede revisarse humanamente.

## Herramientas Detectadas Automaticamente (para logos opcionales)

n8n, ChatGPT, Claude, Make, WhatsApp, Zapier, Anthropic, OpenAI, Gemini

## Troubleshooting

**"El script se queda colgado"**
-> SIEMPRE usar `--skip-interactive` y `PYTHONUNBUFFERED=1`

**"No encuentra brief.json"**
-> El PASO 8 lo crea. Si falta, no se puede generar — hay que completar el analisis de la
imagen (PASO 2), el texto (PASO 3), el formato (PASO 4), la cantidad de slides (PASO 5), la
distribucion de contenido (PASO 6), la validacion de fidelidad (PASO 6.5) y la pregunta del
libro/producto (PASO 7) antes de escribirlo.

**"GEMINI_API_KEY no configurada"**
-> Crear/completar `$HOME/.claude/skills/carousel-gen/.env` con: `GEMINI_API_KEY=tu-api-key`
(obtener en https://aistudio.google.com/apikey, copiar `.env.example` de esa misma carpeta
como base). Para probar el flujo completo SIN clave real (sin red, sin costo), usar
`--fake-provider` — ver "COST OPTIMIZATION".

**"No se encontro la imagen de referencia"**
-> El script falla rapido y a proposito (ver PASO 1, "REFERENCIA VISUAL — resolucion del
attachment"): nunca busca el archivo ni fabrica un placeholder. Verificar que se copio a
`carousel/assets/viral-reference.png` en el Paso 8 (paso 3, con `cp` directo sobre la ruta
real del adjunto), y que `brief.json` apunta a esa ruta en `reference_image.local_path`.
Si el adjunto original no esta disponible, hay que pedirselo de nuevo al usuario — nunca
continuar con una referencia distinta.

**"Timeout esperando resultado" / trabajo Batch atascado**
-> La API esta sobrecargada o el trabajo Batch tarda mas de lo esperado, usa
`--regenerate-slides` para reintentar solo los slides fallidos (nunca hace falta
regenerar el carrusel completo).

**"ModuleNotFoundError: No module named 'google'" (o 'requests'/'dotenv'/'PIL')**
-> Ejecutar con el MISMO interprete que corre el script (nunca solo `pip3` si hay varias
instalaciones de Python — ver PASO 0): `python3 -m pip install requests python-dotenv
Pillow google-genai`.

**"Credits insufficient" / cuota de Gemini agotada**
-> Verificar cuota/facturacion en https://aistudio.google.com/, luego usar
`--regenerate-slides "6,7,8"` para los que faltaron — el cache evita regenerar los que
ya estan aprobados.

**"El trabajo Batch termino en PARTIAL_FAILURE" / "no aparece en las respuestas del batch"**
-> Revisar `carousel/.batch_state.json` para ver el estado por slide, y
`--regenerate-slides "N,M"` con solo los numeros que fallaron. El sistema NUNCA regenera
el carrusel completo por un fallo parcial del batch.

**"Slide N queda TEXT_QA_FAILED" / palabras duplicadas o deformadas en la imagen**
-> Text QA detecto que el texto renderizado no coincide con `exact_text` y ya agoto
`MAX_TEXT_QA_RETRIES`. Usar `--regenerate-slides "N"` para reintentar SOLO ese slide
(el prompt/exact_text no cambian solos; si el problema persiste tras varios intentos,
puede ser un patron dificil para el modelo con ese texto especifico — considerar
acortar o reformular la composicion, nunca el contenido de `exact_text`).

**"Text QA omitido" / manifest.json muestra `"text_qa": {"status": "SKIPPED"}`**
-> `pytesseract` o el binario de Tesseract-OCR no estan instalados/disponibles (o
`TEXT_QA_ENABLED=false`). El carrusel se genera igual (nunca bloquea por esto), pero
sin la verificacion de texto renderizado. Instalar Tesseract-OCR y ejecutar
`python3 -m pip install pytesseract` para activarlo.

**"PRODUCT_TITLE_MISMATCH" / "CTA_MISMATCH"**
-> El titulo del producto o el CTA aparecen duplicados, incompletos o deformados en el
slide de cierre/CTA. Regenerar unicamente ese slide con `--regenerate-slides` — el
sistema nunca modifica el titulo/CTA aprobados para "hacer coincidir" un error de
renderizado.

**"El slide de portada/CTA se genero con una cubierta generica en vez de la real"**
-> Verificar que exista el bloque `product_mockup` en `brief.json` (nivel raiz), que el
archivo apunte a un asset real dentro de `carousel/assets/`, y que el slide correspondiente
tenga `"uses_product_mockup_directly": true`. Ver "Regla general: mockup de producto
proporcionado por el usuario" arriba.

**"ERROR: carousel-gen admite un maximo de 10 slides..."**
-> El brief.json tiene mas de 10 slides (o `slide_count.recommended`/`.confirmed` > 10). El
script se detuvo en `load_brief()` ANTES de llamar a Gemini (o a Kie, si estuviera
reactivado) — no se genero ninguna imagen ni se gasto ningun credito. Solucion: volver al
PASO 5/6 y reorganizar el contenido de
`source_text` dentro de 10 slides (mayor densidad por slide, agrupar unidades afines) —
nunca resumir ni eliminar contenido, ver "LÍMITE OBLIGATORIO DE SLIDES" arriba. Editar
`brief.json` para que `slides[]`, `slide_count.recommended` y `slide_count.confirmed` queden
todos en 10 o menos, y volver a ejecutar el PASO 9.

**"No aparece la copia en Descargas / no dice 'Carrusel guardado en:'"**
-> El script solo copia si encuentra al menos un `carousel-NN.png` en `carousel/` al
finalizar — si todos los slides fallaron no hay nada que copiar. Si los slides SI existen
pero la copia fallo igual, revisar el mensaje de advertencia impreso (permisos de escritura
en `C:\Users\<usuario>\Downloads\`, disco lleno, etc.) — el bundle original en
`outputs/bundles/` no se ve afectado en ningun caso, solo falla la copia hacia Descargas.
