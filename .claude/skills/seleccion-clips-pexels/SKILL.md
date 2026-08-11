---
name: seleccion-clips-pexels
description: Given a full reel voice-over script (guion) for Constelaciones Familiares, split it into 6-8 key emotional moments and write specific brand-consistent English search terms per moment (warm domestic scenes, everyday women, no literal metaphor objects -- same vocabulary as scripts/references/image_prompt_style.md). Picks ONE protagonist author with the best Pexels coverage (Videos AND Photos APIs) across the whole reel, excluding studio/preset accounts by name, then searches every moment restricted to that author only. If she has nothing solo for a moment, tries her accompanied by others (still her, relaxed search terms), then a faceless cutaway detail shot (hands, a mug, a window, domestic texture), and only then falls back to a different author -- each tier labeled explicitly in the summary. If the user also gives the reel's rewritten on-screen hook text (distinct from the guion's literal first line), searches and downloads a SEPARATE dedicated clip for it -- own search terms, own tier cascade, own entry in orden_edicion.txt ("Momento gancho"), never mixed into moment 1. Downloads candidates, runs a mandatory ffmpeg frame-by-frame visual review (scene/emotion fit, brand setting, AND face/appearance consistency of the protagonist) before showing results, swapping or dropping weak candidates instead of forcing them. Saves to scripts/output_clips/<reel>/ plus an orden_edicion.txt. Optional opt-in "--visual-mix" / "con mezcla visual" mode mixes 60% Pexels / 30% flat conceptual illustration / 10% diagram across the 6-8 moments instead of 100% Pexels (see scripts/references/mixed_visual_style.md) -- generates the non-Pexels moments locally (Gemini for illustration, Pillow for diagrams, both faceless) and writes them into the same orden_edicion.txt format; default behavior without this flag is 100% unchanged. Use for "selecciona clips para el reel de [tema]", "busca B-roll para este guion". Not for writing the reel script itself (write it first, then paste it here), not for still cover photos (use imagen-post-constelaciones), and not for carousels/posts/stories (use carrusel-constelaciones, post-constelaciones, historias-constelaciones).
---

# Selección de clips Pexels (B-roll para reels)

Toma el guion completo de un reel ya escrito, lo divide en momentos
emocionales, redacta términos de búsqueda en inglés coherentes con la
estética de marca, elige UN SOLO autor de Pexels como protagonista con
cobertura real (fotos y videos) para todo el reel, busca candidatos de ese
autor momento por momento, descarga los mejores, los revisa visualmente
(incluyendo consistencia de rostro) y deja un resumen listo para armar en
Canva/CapCut.

## Cuándo se activa

- "selecciona clips para el reel de [tema]"
- "busca B-roll para este guion"
- "necesito video clips de Pexels para este reel: [guion pegado]"
- Puede incluir el modo mezcla visual: "...con mezcla visual", "...estilo
  60/30/10 para el reel de [tema]". Sin pedirlo, el comportamiento es 100%
  Pexels, igual que siempre. El modo mezcla es 100% opcional -- ver paso 3b
  del Flujo y `../../scripts/references/mixed_visual_style.md`.

No se activa para redactar el guion en sí (eso se escribe antes, a mano o en
otra conversación), ni para imágenes fijas de portada (`imagen-post-
constelaciones`), ni para carruseles/posts/historias (`carrusel-
constelaciones`, `post-constelaciones`, `historias-constelaciones`).

## Restricción de la API de Pexels (leer antes de tocar nada)

Pexels **no tiene un endpoint para buscar "todo lo de un autor X"** -- ni en
Videos ni en Photos. La única forma de restringir a un autor es correr la
búsqueda normal por palabras clave y filtrar los resultados del lado del
cliente, quedándose solo con los que coinciden con el `author_id` elegido.
Esto significa que la regla de "protagonista única" descrita abajo es
estricta en la SELECCIÓN (nunca se mezcla otro autor salvo el fallback
explícito del paso 3), pero la COBERTURA real depende de qué tan arriba
rankee el contenido de ese autor en los resultados de cada búsqueda -- no es
un lookup exhaustivo. `scripts/search_pexels_clips.py` ya maneja este
workaround (`gather_candidates(..., author_id=X)`); no hay que pedirle nada
distinto a la API, solo entender por qué algunos momentos igual van a
necesitar el fallback del paso 3.

También: muchos de los autores más prolíficos de Pexels son cuentas de
"estudio" (ej. "cottonbro studio") que suben contenido con modelos
distintos entre fotos/videos. Elegir un `author_id` único NO garantiza que
sea literalmente la misma persona física en todos los resultados -- por eso
el paso 6 (revisión visual) valida explícitamente consistencia de rostro,
no solo autoría.

## Flujo

1. **Recibir el guion.** El usuario pega el texto narrado completo del reel
   en el chat. Si no da un nombre para el reel, derivar un slug corto del
   tema/hook del guion y avisar cuál se usó (no preguntar antes de trabajar).
   **Input adicional opcional: el texto del gancho.** Si el usuario también
   pega el titular reescrito que va a usar como gancho inicial (el mismo que
   después se pasa a `edicion-reel-json2video` como `--hook-main`/
   `--hook-accent`), capturarlo aparte -- nunca reemplaza ni se mezcla con
   el guion narrado ni con sus 6-8 momentos. Si no lo da, todo el flujo
   sigue exactamente igual que antes (sin bloque de gancho en el JSON ni en
   `orden_edicion.txt`).

2. **Dividir el guion en 6-8 momentos emocionales clave.** Cada momento es
   un beat con una carga emocional distinta (p. ej. culpa, confrontación,
   alivio, ternura, resignación, esperanza) -- no una división mecánica por
   oración. Para cada uno anotar la línea o líneas exactas del guion que le
   corresponden. Si el guion es muy corto o muy largo para caer en 6-8
   momentos naturales, avisar al usuario y ajustar el rango en vez de forzarlo.

3. **Escribir los términos de búsqueda en inglés**, siguiendo las mismas
   reglas que `../../scripts/references/image_prompt_style.md` usa para las
   fotos de portada:
   - Ambientes domésticos y cotidianos (kitchen, living room, bedroom,
     porch, dining table, sidewalk, neighborhood park) -- nunca paisajes
     abiertos, montañas, playas o fondos genéricos "cinematográficos".
   - Tonos cálidos: "warm light", "golden hour", "soft window light".
   - Personas reales en escenas cotidianas, priorizando mujeres, nunca
     poses de stock genéricas tipo "business woman smiling at camera".
   - Traducción conceptual, no literal: la emoción se expresa en postura y
     gesto humano, nunca en un objeto símbolo (nada de "broken chains",
     "heavy stone", "closed door" como sujeto central de la búsqueda).
   - **Específicos, nunca solo adjetivo + "home".** Términos demasiado
     genéricos como "empty home room warm light" o "relief home" traen con
     frecuencia fotos de ambientes vacíos sin ninguna persona, o resultados
     de estudio/editorial/moda que no calzan con la marca -- visto en
     pruebas reales. Cada término debe combinar sujeto explícito (siempre
     "woman"/"women"/"two women", nunca solo el ambiente) + acción o postura
     concreta + ambiente, por ejemplo "woman standing alone doorway home"
     en vez de "quiet empty home".
   - **Dos niveles de términos:**
     - `general_terms` (3-5 términos): el tema/tono general de TODO el
       reel, sin especificidad de un momento puntual -- ej. "woman home
       emotional everyday", "woman domestic life reflective warm light",
       "woman alone home candid". Se usan solo para elegir protagonista
       (paso 5), no para buscar clips.
     - `search_terms` (2-3 por momento): específicos del beat emocional de
       ESE momento, como ya se hacía.
   - El primer término de cada momento (`search_terms[0]`) debe ser el más
     representativo/genérico de ese momento -- el script lo usa solo a él
     para probar cobertura de cada autor candidato en el paso 5, así que si
     es demasiado nicho puede subestimar la cobertura real de un buen
     candidato.
   - **`cutaway_terms` (1-3 por momento, opcional pero recomendado):**
     términos de una "imagen de apoyo" sin ninguna persona -- manos,
     objetos cotidianos, detalles del ambiente doméstico que refuerzan la
     emoción sin mostrar un rostro: una taza, una ventana, una puerta, luz
     entrando, una silla vacía. Estos SÍ pueden centrarse en un objeto o
     detalle (a diferencia de `search_terms`, donde un objeto nunca puede
     ser el sujeto principal) porque no están reemplazando a una persona
     como portador de la emoción -- son textura de edición, no el plano
     principal del momento. Ejemplos: "steam rising from mug close up warm
     light", "hand resting on windowsill warm light", "door ajar hallway
     warm light". Se usan solo como tercer intento (paso 5, nivel B) cuando
     la protagonista no tiene nada, ni sola ni acompañada.
   - **Si el usuario dio texto de gancho (paso 1):** escribir 2-3
     `search_terms` en inglés específicos para ESE texto (mismas reglas de
     vocabulario que arriba), igual que se hace para cualquier momento. El
     gancho suele ser un titular reescrito, no la línea 1 literal del guion
     -- los términos van sobre lo que el gancho realmente dice, no sobre la
     `guion_line` del momento 1. `cutaway_terms` para el gancho es opcional,
     igual que en los momentos.

3b. **Si el usuario pidió mezcla visual (`--visual-mix`):** clasificar cada
   uno de los 6-8 momentos (nunca el gancho, que siempre queda foto/video de
   Pexels igual que hoy) en `foto` / `ilustración` / `diagrama`, siguiendo la
   heurística y el reparto 60/30/10 exactos de
   `../../scripts/references/mixed_visual_style.md` (narrativo/emocional ->
   foto, conceptual explicativo -> ilustración, estructurado/enumerado ->
   diagrama; método de mayor resto con empate foto > ilustración > diagrama;
   no forzar un diagrama con pocos momentos). Guardar la clasificación de
   cada momento como `"visual_type"` en el JSON del paso 4 (ver ahí). Si no
   se pidió mezcla visual, este paso no existe -- se omite entero y ningún
   momento lleva `"visual_type"`.

4. **Guardar el análisis en JSON** en
   `testing/pexels_moments/<reel_slug>.json` (crear la carpeta si no
   existe) con esta forma exacta:
   ```json
   {
     "reel_name": "<nombre o slug del reel>",
     "general_terms": ["term one", "term two", "term three"],
     "hook": {
       "text": "texto exacto del gancho, ej. NO ERA mal carácter",
       "search_terms": ["term one", "term two"],
       "cutaway_terms": ["detail term one"]
     },
     "moments": [
       {
         "order": 1,
         "label": "culpa",
         "guion_line": "línea exacta del guion para este momento",
         "search_terms": ["term one", "term two", "term three"],
         "cutaway_terms": ["detail term one", "detail term two"],
         "visual_type": "photo"
       }
     ]
   }
   ```
   La clave `"hook"` es **opcional** -- solo va si el usuario dio texto de
   gancho en el paso 1. Sin ella, el comportamiento es idéntico al de antes
   de esta función (ningún clip de gancho se busca ni se descarga). La clave
   `"visual_type"` por momento (`"photo"` / `"illustration"` / `"diagram"`)
   es **igual de opcional** -- solo va si el paso 3b clasificó ese momento
   (modo mezcla visual). Sin ella (comportamiento normal), el momento es
   foto/video de Pexels como siempre; `search_pexels_clips.py` nunca lee esta
   clave, es solo una nota para esta misma skill en el paso 5.

5. **Ejecutar el script** por la tool de Bash, desde la raíz del repo. **Si
   NO hay mezcla visual (comportamiento normal):**
   ```
   python scripts/search_pexels_clips.py "testing/pexels_moments/<reel_slug>.json"
   ```
   **Si hay mezcla visual (paso 3b), restringir a solo los momentos
   clasificados `"photo"`** (el gancho, si existe, sigue procesándose siempre
   -- nunca entra en la clasificación):
   ```
   python scripts/search_pexels_clips.py "testing/pexels_moments/<reel_slug>.json" --only <ordenes de los momentos "photo", ej. 1,2,4,6>
   ```
   El script:
   - Carga `PEXELS_API_KEY` de `.env` (si falta, la pide de forma interactiva
     y la guarda -- nunca pedir esta key al usuario desde la skill misma).
   - **Fase 0 -- elige protagonista**: busca `general_terms` en Videos Y
     Photos con resultados amplios, arma un pool de autores frecuentes,
     descarta los que suenan a cuenta de estudio/preset (nombre contiene
     "studio", "production(s)", "crew", "team", "agency", "films", "media",
     "presets", "etsy.com" -- `STUDIO_NAME_BLOCKLIST` en el script; visto en
     pruebas reales que estas cuentas "ganan" la cobertura por volumen pero
     publican modelos distintos), toma los 3 más frecuentes del resto y les
     prueba cobertura (1 búsqueda por momento, usando `search_terms[0]`,
     filtrada a cada autor candidato). Se queda con el autor que cubre más
     momentos (empate: el más frecuente en el pool general). Imprime cuántos
     momentos cubrió antes de seguir.
     **Ese filtro de nombre reduce pero NO elimina el riesgo**: en pruebas
     reales, incluso una cuenta individual (nombre de persona, sin ninguna
     palabra de la lista negra) resultó tener 3 mujeres distintas
     recurrentes en su catálogo. Por eso el paso 6 (revisión visual) sigue
     siendo obligatorio y es la única verificación real de que se trata de
     la misma persona -- el nombre de cuenta es apenas una primera pasada.
   - **Fase 1 -- por momento, SOLO ese autor**: busca los `search_terms` de
     cada momento en Videos Y Photos, filtrado al `author_id` elegido.
     Siempre `orientation=portrait`. Prioriza video sobre foto (esto es
     B-roll); una foto solo se usa si el protagonista no tiene ningún video
     para ese momento -- se descarga como `.jpg` y queda marcada en el
     resumen para animar o usar como imagen fija.
   - **Fase 2 -- cascada de 4 niveles si la protagonista sola no tiene nada**,
     probando cada nivel solo si el anterior dio cero candidatos:
     1. **Acompañada** (`⚠ protagonista principal, acompañada`): re-busca
        los mismos `search_terms` pero con las palabras de soledad
        ("alone", "solo", "standing/sitting alone") quitadas
        (`strip_solitude_words`), siempre filtrado al mismo `author_id`. La
        protagonista puede aparecer con otras personas en cuadro -- sigue
        contando como ella siempre que sea claramente reconocible (el paso
        6 valida esto visualmente, el script no puede).
     2. **Imagen de apoyo / cutaway** (`ℹ imagen de apoyo (sin rostro)`):
        busca `cutaway_terms` de ese momento, sin restricción de autor (no
        hay rostro que mantener consistente). Manos, objetos, luz, detalles
        del ambiente -- nunca una persona identificable en cuadro.
     3. **Protagonista distinta** (`⚠ protagonista distinta`): recién acá
        busca los `search_terms` originales sin restricción de autor.
     4. **Match aproximado** (`⚠ match aproximado`): si ni eso da resultado,
        amplía con `GENERIC_FALLBACK_TERMS` sin restricción de autor.
     Cada nivel queda marcado en `orden_edicion.txt` con su etiqueta -- nunca
     se combinan ni se ocultan.
   - Nunca re-descarga el mismo video/foto ya usado en otro momento del
     mismo reel (dedup global).
   - Descarga 1-3 candidatos por momento a
     `scripts/output_clips/<reel_slug>/NN_<label>_<variante>.mp4` (o `.jpg`
     si es foto) -- ej. `01_culpa_a.mp4`, `01_culpa_b.jpg`.
   - Escribe `scripts/output_clips/<reel_slug>/orden_edicion.txt` con el
     protagonista elegido y su cobertura inicial, la línea del guion,
     términos usados, tipo de archivo, y autor/link de Pexels de cada clip,
     con las marcas `⚠ protagonista distinta` / `⚠ match aproximado` donde
     aplique.
   - **Si el JSON trae `"hook"`**: corre exactamente la misma cascada de 4
     niveles de la Fase 2 (sola -> acompañada -> imagen de apoyo ->
     protagonista distinta -> match aproximado) y el mismo dedup global,
     pero como una entrada aparte, nunca mezclada con el momento 1. Descarga
     a `00_gancho_<variante>.mp4` (o `.jpg`) y escribe un bloque propio
     **`Momento gancho -- texto: "..."`** en `orden_edicion.txt`, ubicado
     antes de "Momento 01". `--hook-only` reprocesa solo esa entrada (sin
     tocar los 6-8 momentos) haciendo merge en el archivo existente, igual
     que `--only` para momentos numéricos -- se pueden combinar.

5b. **Si hay mezcla visual, generar los momentos `"illustration"` y
   `"diagram"` que el paso 5 no cubrió** -- no vienen de Pexels, se generan
   localmente por la tool de Bash, desde la raíz del repo, para cada momento
   así clasificado:
   - **`"illustration"`**: escribir la `guion_line` de ese momento a un
     archivo temporal `.txt` (ej.
     `testing/pexels_moments/<reel_slug>_tmp_NN.txt`), luego:
     `python scripts/generate_post_image.py "<ese .txt>" --visual-style mezcla-ilustracion --aspect 9:16 --out-dir scripts/output_clips/<reel_slug>`
     -- **sin `--protagonist`**, esta pierna es deliberadamente sin personas
     (ver `mixed_visual_style.md`). Renombrar el `.png` resultante a
     `NN_<label>_a.png` dentro de la misma carpeta.
   - **`"diagram"`**: elegir un color de `BRAND_COLORS` distinto al usado por
     el protagonista/gancho de este reel (no hay slides tipo quote card en
     reel, así que no hay rotación previa que evitar -- cualquier color
     distinto sirve), y correr directo con el nombre final:
     `python scripts/generate_diagram_image.py "scripts/output_clips/<reel_slug>/NN_<label>_a.png" --items-json '["item 1", "item 2", ...]' --flat-color "<color elegido>" --aspect 9:16`
     -- extraer los items de la `guion_line` de ese momento (si ya enumera
     puntos, usar cada uno; si no, dividir la idea en 2-4 sub-puntos breves),
     2 a 6 items. No llama a Gemini.
   - **Agregar el bloque de cada momento generado a
     `scripts/output_clips/<reel_slug>/orden_edicion.txt`** (crear el
     archivo si el paso 5 no corrió para ningún momento `"photo"`), con el
     mismo formato exacto que escribe `search_pexels_clips.py` para que
     `render_reel_json2video.py` lo parsee igual -- el orden dentro del
     archivo no importa, el parser ordena por el número de `Momento NN`:
     ```
     Momento NN -- <label>
       Línea del guion: <guion_line de ese momento>
       Términos usados: N/A (generado, no buscado en Pexels)
       NN_<label>_a.png -- autor: Generado (ilustración de marca, sin protagonista)
     ```
     (para diagrama, cambiar la última línea a
     `-- autor: Generado (diagrama de marca)`). Dejar una línea en blanco
     entre bloques, igual que el resto del archivo.

6. **Revisión visual antes de mostrarle nada al usuario.** Para los momentos
   `"photo"` (y el gancho) el script solo filtra por metadata (orientación,
   duración, autor) -- no puede detectar si un clip realmente encaja ni si de
   verdad se ve la misma persona; esos SIEMPRE pasan por la revisión completa
   de 6 chequeos de abajo. Los momentos `"illustration"`/`"diagram"` del paso
   5b son generación determinística sin persona, así que no aplican los
   chequeos de rostro/consistencia -- alcanza con abrir la imagen (tool de
   Read) y confirmar que no haya texto cortado, mal renderizado, o un
   diagrama con items pisándose. El clip del gancho (`00_gancho_*`), si lo
   hay, pasa por esta misma revisión y los mismos 6 chequeos que cualquier
   momento -- no es un gate distinto ni más liviano. Con la tool de Bash y
   `ffmpeg` (ya disponible), extraer un frame de cada clip/foto descargado
   (para video:
   `ffmpeg -y -ss 1.5 -i
   archivo.mp4 -vframes 1 -vf scale=270:480:force_original_aspect_ratio=
   decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2:color=black salida.jpg`; para
   foto, copiar/redimensionar directo), armar una grilla por momento con
   `hstack` y revisar cada una (tool de Read) con estos 6 chequeos:
   - **Sin persona en cuadro** (living/habitación vacíos) -- rompe la regla
     "las personas son siempre el sujeto" de `image_prompt_style.md`.
   - **Emoción equivocada** (ej. una mujer sonriendo/comiendo tranquila para
     un momento de rabia o explosión).
   - **Ambiente fuera de marca**: fondo de estudio liso, foto editorial/moda,
     retrato corporativo, mirada fija directo a cámara tipo posado -- nunca
     un ambiente doméstico candid.
   - **Protagonista inconsistente en edad/tipo**: una adolescente o niña en
     vez de una mujer adulta, o un cambio brusco de tono/vestuario que no
     pega con el resto del reel.
   - **Consistencia de rostro/apariencia entre los clips elegidos** (nuevo):
     mismo autor de Pexels no garantiza la misma persona física (ver nota de
     "estudios" arriba). Comparar rasgos generales (contextura, tono de
     piel, color/largo de pelo aproximado) entre los clips de un mismo
     momento y contra los de otros momentos del mismo autor. Si dos clips
     del mismo autor muestran a alguien visiblemente distinto, tratarlo
     igual que un fallo de los otros 4 chequeos.
   - **Nivel correcto según la etiqueta del clip** (nuevo): si el resumen
     marca un clip como `protagonista principal, acompañada`, la
     protagonista tiene que ser clara y reconociblemente ella entre las
     demás personas de la escena -- si no se la distingue bien, tratarlo
     como un fallo y pasar ese slot al siguiente nivel (imagen de apoyo) en
     vez de dejarlo. Si lo marca como `imagen de apoyo (sin rostro)`,
     confirmar que efectivamente no hay ningún rostro identificable en
     cuadro -- si aparece uno (aunque sea de fondo, desenfocado), tratarlo
     como un fallo también.
   Si un candidato falla alguno de estos 6 chequeos, volver a buscar solo
   ese slot importando el módulo (`gather_candidates(terms, api_key,
   author_id=protagonist_id)`, sin correr todo el script de nuevo),
   excluyendo las keys ya usadas en todo el reel (parsear
   `orden_edicion.txt` con algo como `re.findall(r"-(\d+)/", texto)` para
   los IDs), afinando el término si hace falta, y descargando el mejor
   candidato nuevo sobre el mismo nombre de archivo -- **siempre repitiendo
   la cascada de 4 niveles del paso 5 desde el principio para ese slot**
   (protagonista sola -> acompañada -> imagen de apoyo -> protagonista
   distinta -> match aproximado), nunca saltando directo a "protagonista
   distinta". Repetir hasta 2-3 rondas por slot. Si después de eso ningún
   candidato nuevo pasa los 6 chequeos, **no forzar un clip débil**: dejar
   ese momento con menos candidatos (2 en vez de 3, o incluso 1) y anotarlo
   explícito en `orden_edicion.txt` con qué se probó y por qué no sirvió.
   Al terminar, reescribir `orden_edicion.txt` a mano para reflejar
   cualquier reemplazo.

7. **Mostrar el resultado**: protagonista elegido y su cobertura, ruta final
   de la carpeta, cuántos momentos se cubrieron con esa protagonista,
   cuántos quedaron como `⚠ protagonista distinta`, `⚠ match aproximado`, o
   con menos candidatos de lo normal (para que el usuario los busque a mano
   o grabe su propio footage si lo necesita). Si había gancho, mencionar por
   separado si su clip dedicado se resolvió bien o con qué advertencia (nivel
   de la cascada, o sin candidatos). Si hubo mezcla visual, mostrar además el
   reparto final foto/ilustración/diagrama por momento (paso 3b) junto al
   resto del resumen.

## Reglas duras

- Siempre `orientation=portrait` -- nunca clips horizontales, este es
  contenido para Reels 9:16.
- **El clip del gancho, cuando existe, es una entrada aparte -- nunca se
  mezcla con el momento 1.** Términos de búsqueda, tier de la cascada,
  nombre de archivo (`00_gancho_*`) y bloque en `orden_edicion.txt`
  (`Momento gancho --`) son siempre propios. `edicion-reel-json2video` cae
  de vuelta a reusar el clip de momento 1 solo si este bloque no existe.
- **Protagonista única, estricta, no best-effort.** Antes de aceptar un
  clip de otra persona, agotar la cascada completa: sola -> acompañada
  (misma protagonista, mismo `author_id`) -> imagen de apoyo sin rostro ->
  recién ahí protagonista distinta. No saltar niveles ni mezclar autores
  "porque el candidato es mejor" si la protagonista tiene una opción
  aceptable en un nivel anterior.
- Todo momento resuelto con un autor distinto al protagonista debe quedar
  marcado `⚠ protagonista distinta` en `orden_edicion.txt`, nunca oculto
  entre los demás.
- Nunca pedir la API key de Pexels al usuario directamente -- el script la
  maneja con el mismo patrón que `generate_post_image.py` usa para Gemini.
- Nunca traducir la emoción del guion en un objeto símbolo como término de
  búsqueda (nada de "chains", "stone", "closed door" como sujeto) -- misma
  regla conceptual que `image_prompt_style.md`.
- No escribir ni reescribir el guion del reel -- esta skill solo selecciona
  B-roll para un guion que el usuario ya trae escrito.
- No prometer que todos los momentos tendrán clips perfectos del mismo
  protagonista -- Pexels es stock genérico sin filtro nativo por autor (ver
  sección de arriba); los "protagonista distinta", "match aproximado" y los
  huecos sin cobertura son normales y deben quedar visibles en
  `orden_edicion.txt`, no ocultados.
- Nunca mostrarle al usuario el resultado del script sin haber hecho la
  revisión visual del paso 6 primero, incluyendo el chequeo de consistencia
  de rostro -- el filtrado del script es solo por metadata (orientación,
  duración, autor), no garantiza que el contenido ni la persona encajen.
- Nunca descargar un candidato de reemplazo débil solo para completar el
  cupo de 1-3 por momento -- si ninguna opción pasa los 5 chequeos visuales
  tras varias rondas, dejar el momento con menos candidatos y anotarlo, en
  vez de entregar un clip que no sirve.
- **La mezcla visual (`--visual-mix`) es un modo alternativo opt-in.** Sin
  pedirla explícitamente, el reel es 100% Pexels, exactamente igual que antes
  de que este modo existiera -- nunca se activa por inferencia.
- En mezcla visual, el reparto 60/30/10 aplica solo a los 6-8 momentos
  narrados (nunca al gancho, que siempre es Pexels) y sigue el método de
  mayor resto de `mixed_visual_style.md`, nunca una asignación al azar. Los
  momentos `illustration`/`diagram` nunca representan personas -- ver
  `mixed_visual_style.md` para el porqué (consistencia visual entre un
  protagonista real de Pexels y uno dibujado, más evitar cualquier riesgo de
  calidad de rostro con Gemini).

## Recursos

- `../../scripts/references/image_prompt_style.md` -- vocabulario visual de
  marca (ambientes, tono cálido, traducción conceptual de la emoción) que
  informa los términos de búsqueda.
- `../../scripts/references/mixed_visual_style.md` -- la regla completa del
  modo mezcla visual (60/30/10): alcance, heurística de clasificación,
  apportionment con empates, y por qué ilustración/diagrama van sin
  protagonista. Compartida con `carrusel-constelaciones`.
- `../../scripts/search_pexels_clips.py` -- elige protagonista (Videos +
  Photos), busca por momento restringido a ese autor con la cascada de 4
  niveles, filtra, descarga y genera `orden_edicion.txt`. Acepta `--only
  5,7,8` para re-testear solo esos momentos (hace merge en el
  `orden_edicion.txt` existente en vez de sobreescribirlo),
  `--protagonist-id ID --protagonist-name NOMBRE` para saltar la Fase 0 y
  reusar un protagonista ya elegido en una corrida anterior -- útil después
  de ajustar `cutaway_terms` o `search_terms` de un momento puntual -- y
  `--hook-only` para reprocesar solo el clip del gancho (requiere `"hook"`
  en el JSON), combinable con `--only`.
- `../../scripts/generate_post_image.py` -- genera los momentos
  `"illustration"` de la mezcla visual con `--visual-style
  mezcla-ilustracion` (sin `--protagonist`).
- `../../scripts/generate_diagram_image.py` -- genera los momentos
  `"diagram"` de la mezcla visual: lista numerada vertical con Pillow puro
  (sin Gemini, texto siempre legible).
- `testing/pexels_moments/` -- JSON intermedio por reel (gitignored).
- `scripts/output_clips/` -- clips/fotos descargados por reel (gitignored,
  son binarios, no se suben al repo).

## Related skills

- `imagen-post-constelaciones` -- imagen fija de portada, no B-roll de reel.
- `carrusel-constelaciones` / `post-constelaciones` / `historias-
  constelaciones` -- contenido estático, no video.
