---
name: carrusel-constelaciones
description: Draft a multi-slide organic Instagram/Facebook carousel for Constelaciones Familiares in one of 5 structures (narrativo problema-explicación-Para asentar-CTA, lista de comportamientos, antes/después, autodiagnóstico, mini-historia con giro), following the brand voice in scripts/references/constelaciones_brand_voice.md (español neutro colombiano, no voseo), with the first content slide always carrying the carousel's strongest pain beat, never a generic opener, and every content slide/"Para asentar"/CTA written as a real 2-4 sentence paragraph naming one concrete microdolor (or, for the CTA, the reinforced bridge), not a one-line headline. Sources every slide (hook + content + "Para asentar" + CTA -- the whole carousel) from real Pexels stock photography via scripts/search_pexels_photo.py -- the same protagonist-consistency cascade seleccion-clips-pexels already uses for reels, reused by import -- never Gemini, and never any other skill's photo pipeline (post-constelaciones, imagen-post-constelaciones, historias-constelaciones keep generating with Gemini, unaffected). Bakes text directly onto every slide with Pillow: the hook (slide 1) is the ONLY slide with a título + subtítulo + a third short line (Poppins Bold #F2A900 + Playfair Display italic #FAE8A8, same typography as reels), forced dead-centered on the frame regardless of whether it covers the protagonist's face (--force-center-zone, a deliberate exception limited to this one slide); every other slide including the CTA carries ONLY its full paragraph in warm white #F5F0E6 over a dark gradient scrim, no gold title or subtitle at all, placed via the normal OpenCV face veto (needs opencv-python, unchanged everywhere except the hook), the CTA's paragraph being a bridge sentence that explicitly names the specific pain the carousel just developed before mentioning the book and pointing the reader to the caption for the link (never baking the link itself onto a slide, since Instagram never makes on-image text clickable). Saves each carousel's finished images to its own Desktop/Imagenes Posts/<slug>/ subfolder instead of the shared root, then builds one consolidated "PAQUETE - <hook>.docx" (every slide image in order + the caption + a new first-comment CTA + hashtags + a publish checklist, per PACKAGING_STANDARD) via scripts/build_paquete_docx.py. Optionally also produces a 6-slide "Carrusel Historias" version (9:16, reusing the same hook + first 3 content slides + Para asentar + CTA from this same feed carousel, no new copy or photos, only the CTA's closing "en la descripción" swapped for "en mi bio") for the daily package, replacing the old standalone historias-constelaciones piece. Use for "hazme un carrusel de [tema]", "necesito un carrusel sobre [tema]", optionally with a visual style named ("...estilo minimalista/tipo libro/caricatura/storytelling/mezcla..."). Not for single-image posts (use post-constelaciones) or paid ads (future ads-constelaciones).
---

# Carrusel Constelaciones (multi-slide)

Redacta un carrusel orgánico para Constelaciones Familiares: elige
estructura, escribe el texto completo de cada slide (un párrafo real, no un
titular) más los bloques cortos que se queman en la imagen, más una caption
separada, lo aprueba el usuario, guarda cada slide como `.docx`, busca una
foto real de Pexels para cada slide con protagonista (las 6 -- hook +
contenido + "Para asentar" + CTA), y genera la imagen final de cada slide
(foto + texto quemado) reutilizando `scripts/generate_post_image.py`.

## Cuándo se activa

- "hazme un carrusel de [tema]"
- "necesito un carrusel sobre [tema]"
- "arma un carrusel de Constelaciones sobre [tema]"
- Puede incluir el estilo visual: "...estilo minimalista/tipo libro/
  caricatura/storytelling/mezcla sobre [tema]". Sin especificarlo, el estilo
  es fotográfico (el de siempre, sin cambios). "Mezcla" es el estilo 60/30/10
  (ver `../../scripts/references/mixed_visual_style.md`) -- 100% opcional, no
  reemplaza nada del comportamiento default. **Nota:** la pierna `foto` de
  `mezcla` todavía está escrita para el pipeline viejo de Gemini y no se
  actualizó en esta pasada (mezcla sigue sin usarse desde que se canceló la
  prueba) -- si se retoma `mezcla`, revisar primero si su pierna `foto` debe
  pasar a Pexels también antes de usarla.
- "...y también la versión historias" / "con su carrusel de historias" /
  pedida como parte de un paquete diario que incluye "Carrusel Historias" --
  activa el paso 17 (ver Flujo) además del carrusel de feed normal. Nunca
  se genera sola sin su carrusel de feed asociado del mismo día -- para una
  Story suelta sin carrusel, usar `historias-constelaciones`.

No se activa para posts de una sola imagen (`post-constelaciones`) ni para
anuncios pagados.

## Qué hace exactamente (leer antes de tocar nada)

**Toda foto de este carrusel sale de Pexels, nunca de Gemini.** El hook, cada
slide de contenido, "Para asentar", y el CTA llevan foto real de stock,
buscada con `scripts/search_pexels_photo.py` -- mismo mecanismo de
protagonista único con cascada de 4 niveles que ya usa
`seleccion-clips-pexels` para reels, reutilizado por import, no duplicado.
Esto es así **solo para esta skill**: `post-constelaciones`,
`imagen-post-constelaciones`, y `historias-constelaciones` siguen usando
Gemini exactamente igual que siempre, sin ningún cambio.

**Ninguna slide es ya quote card plana.** El CTA (última slide) dejó de
serlo -- antes era la única excepción de color sólido, pero en una prueba
real quedaba desconectado visualmente de las otras 5 slides que sí comparten
protagonista/ambiente. Ahora las 6 slides, hook a CTA, llevan foto real de
fondo con la misma coherencia visual.

**Texto quemado, no editado a mano en Canva. El hook es la única slide con
título -- todas las demás llevan solo el párrafo, sin título ni subtítulo**
(todo vía `render_headline` en `generate_post_image.py`):
- **Hook (slide 1) -- único con título/subtítulo:** título (`--headline-main`,
  Poppins Bold, dorado `#F2A900`) + subtítulo (`--headline-accent`, Playfair
  Display italic, dorado pálido `#FAE8A8`) + una tercera línea corta
  (`--headline-extra`, Poppins SemiBold, mismo dorado pálido).
  **Posición forzada, sin veto de rostro (excepción deliberada, ver
  `PACKAGING_STANDARD`/"Design mix" en `constelaciones_brand_voice.md`):**
  siempre lleva `--force-center-zone`, que centra el bloque en todo el
  cuadro sin correr el chequeo de OpenCV -- si eso tapa la cara de la
  protagonista, la tapa a propósito. Ninguna otra slide de esta skill (ni
  ningún otro skill) usa esta excepción.
- **Contenido, "Para asentar", y CTA** (toda slide después del hook): SOLO
  el párrafo completo de esa slide, quemado como `--body-text` -- Poppins
  Bold blanco cálido `#F5F0E6` (antes era cian `#22D3EE`, cambiado por
  feedback del usuario: el blanco se lee mejor y combina mejor con el tono
  cálido de las fotos que el cian), con degradado oscuro de fondo
  (`apply_gradient_scrim`, mismos stops que `GRADIENT_HTML_TEMPLATE` de los
  reels) para que se lea encima de una foto real sin espacio negativo
  garantizado. **Sin `--headline-main` ni `--headline-accent` -- el
  mini-título dorado por slide se eliminó** (cada slide de contenido ya no
  se ve como su propio hook chico; eso quedó exclusivo de la slide 1).
  `generate_post_image.py` acepta `--body-text` solo, sin exigir
  `--headline-main`, justo para este caso. Para el CTA, ese párrafo es el
  bridge reforzado (ver `constelaciones_brand_voice.md`).
  **Estas slides SIGUEN con el veto de OpenCV normal** (top/bottom según
  qué zona no tenga rostro) -- nunca `--force-center-zone`, esa excepción es
  exclusiva del hook.

**Carpeta propia por carrusel.** Las imágenes finales van a
`Desktop/Imagenes Posts/<slug>/`, no a la raíz de `Imagenes Posts` -- el slug
se deriva del tema/hook al principio del flujo, mismo criterio que
`seleccion-clips-pexels`/`narracion-voz-gemini` usan para sus reels.

## Flujo

1. **Tema y slug.** Tomar el tema/ángulo del pedido y derivar un slug corto
   (ej. `cuantas-veces-ahorros`) para nombrar la carpeta de imágenes del paso
   10 -- avisar cuál se usó, no preguntar.
2. **Elegir estructura.**
   - Si el usuario nombra una de las 5 (ver `CAROUSEL_STRUCTURES` en
     `../../scripts/references/constelaciones_brand_voice.md`), usar esa y no
     tocar la rotación.
   - Si no la nombra, elegirla automáticamente evitando repetir cualquiera de
     las últimas 2 usadas: leer `testing/copy_gen_state.json` (crear con `{}`
     si no existe), clave `"carousel_structure"`, mismo mecanismo de rotación
     que `post-constelaciones`.
   - Si el usuario da un texto fuente ya escrito para adaptar (en vez de
     pedir un tema libre), mapearlo a la estructura que mejor calce con su
     forma real -- no rotar en ese caso, el texto ya dicta la estructura.
   - **Nunca preguntar cuál usar antes de redactar** — elegir y avisar cuál se
     usó junto con el borrador.
3. **Elegir estilo visual.** Si el usuario lo nombra ("estilo minimalista",
   "tipo libro", "caricatura", "storytelling", "mezcla"), usar ese. Si no lo
   nombra, usar `photo` (default -- ahora Pexels, ver arriba). A diferencia de
   la estructura, el estilo visual **nunca se rota automáticamente**.
4. **Redactar las slides.** Cada slide de contenido y "Para asentar" necesita
   un párrafo real de 2-4 oraciones nombrando un microdolor concreto y
   reconocible -- ver regla "Content-slide copy must be a real paragraph" en
   `CAROUSEL_STRUCTURES`, nunca una frase de una línea. Ver conteo y orden
   exacto en `CAROUSEL_STRUCTURES`, que siempre termina en:
   [...contenido...] → "Para asentar" (penúltima) → CTA del libro (última).
   El CTA debe incluir el bridge reforzado (ver regla "Bridge required before
   the CTA" en `constelaciones_brand_voice.md`: nombra el dolor específico de
   esta pieza, 2-3 oraciones de peso antes de mencionar el libro) — el link
   plano NUNCA va en la slide (Instagram no lo hace clickeable), solo en la
   caption; el copy del CTA debe decir explícitamente que el link está en la
   descripción (ej. "el link está en la descripción"), nunca dar a entender
   que está ahí mismo. La slide 2 (primera de
   contenido) tiene que ser el beat más fuerte del dolor central — ver regla
   "First content slide carries the strongest pain (mandatory)". **Todo el
   texto en español neutro colombiano, nunca voseo ni modismos de otro país**
   — ver regla de idioma en "Voice fingerprint" de `constelaciones_brand_voice.md`.
5. **Escribir los bloques cortos SOLO para el hook, para quemar en la
   imagen** — distintos del párrafo completo del paso 4, que se sigue
   guardando entero en el `.docx`. Las demás slides no llevan bloques
   cortos, solo su párrafo completo (ver `body_text` abajo):
   - `headline_main` (**solo el hook**): 3-8 palabras, la frase de mayor
     impacto del hook.
   - `headline_accent` (opcional, **solo el hook**): línea de cierre más
     breve, cuando el hook tiene un reencuadre natural de dos partes.
   - `headline_extra` (**solo el hook**): una tercera línea corta adicional.
   - `body_text` (**toda slide después del hook, incluido el CTA**): el
     párrafo completo del paso 4 (para el CTA, el bridge reforzado), tal
     cual, para quemar en blanco cálido. Sin `headline_main` ni
     `headline_accent` en estas slides -- el mini-título dorado por slide
     de contenido ya no existe.
6. **Términos de búsqueda de Pexels por slide** (todas -- hook + contenido +
   "Para asentar" + CTA, el carrusel entero): 2-3 `search_terms` en inglés
   por slide más `cutaway_terms` opcionales, siguiendo las mismas reglas de
   vocabulario que ya usa `seleccion-clips-pexels` (ambientes domésticos
   cotidianos, tono cálido, sujeto explícito + acción concreta + ambiente,
   nunca objeto-símbolo, nunca pose de stock genérica tipo "business woman
   sonriendo a cámara") — ver esas reglas completas en el paso 3 del flujo de
   `../../seleccion-clips-pexels/SKILL.md`. Más `general_terms` (3-5, todo el
   carrusel) para elegir protagonista. **No hay `--protagonist` que redactar
   a mano** — el protagonista real lo elige `search_pexels_photo.py` en su
   Fase 0, a partir de estos términos.
   - **`cutaway_terms` deben ser estrictamente de objeto/mano, nunca de
     persona (regla dura).** Pexels no entiende "sin rostro" como una
     restricción real: si el término menciona "woman"/"man" o cualquier
     parte del cuerpo cercana a la cara (hombros, labios, cuello), el motor
     de búsqueda igual devuelve retratos editoriales con rostro nítido,
     etiquetados como si fueran de apoyo. Escribir siempre en torno a un
     objeto o una mano en la escena, sin sujeto humano nombrado — ej. "close
     up hands resting table warm light", "hands holding coffee mug kitchen
     counter", nunca "woman shoulders relaxed" ni "woman biting lip".
7. **Si el estilo visual es `mezcla`, clasificar cada slide de contenido**
   (ver nota de la sección "Cuándo se activa" sobre la pierna `foto` de
   `mezcla` desactualizada) en `foto` / `ilustración` / `diagrama`, heurística
   y reparto 60/30/10 de `mixed_visual_style.md`. Se omite entero si el
   estilo no es `mezcla`.
8. **Redactar la caption por separado** (no va en ninguna slide): mención del
   CTA hacia el libro correspondiente + el link (plano, sin UTM, salvo que el
   usuario pida explícitamente mantener parámetros de tracking para ese post
   puntual) + hashtags al final (2 fijos + 3 de tema, sizing de
   `ig-hashtag-strategist`). En español neutro colombiano, igual que el resto.
9. **Mostrar todo para aprobación** antes de buscar ninguna foto ni generar
   ninguna imagen: estructura, estilo visual, párrafo completo de cada slide
   (paso 4), bloques cortos del paso 5, términos de búsqueda del paso 6, y la
   caption completa. Esperar aprobación o ajustes.
10. **Guardar cada slide aprobada** como
    `Desktop/Posts Constelaciones/<hook> - Slide N.docx` (el párrafo completo
    del paso 4 en negrita en el primer párrafo), y la caption como
    `Desktop/Posts Constelaciones/<hook> - Caption.docx`.
11. **Ninguna slide necesita color plano ahora** (el CTA dejó de ser
    quote card, ver "Qué hace exactamente"). Este paso solo aplica si el
    estilo visual es `mezcla` y hay una slide clasificada `diagrama`: elegir
    para esa un color de `BRAND_COLORS` (no participa de la rotación de
    `"flat_color"` en `testing/copy_gen_state.json`, ver
    `mixed_visual_style.md`). Si no es `mezcla`, saltar este paso entero.
12. **Buscar las fotos de Pexels** por la tool de Bash, desde la raíz del
    repo. Armar el JSON en `testing/pexels_carousels/<slug>.json`:
    ```json
    {
      "carousel_name": "<slug o nombre del carrusel>",
      "general_terms": ["term one", "term two", "term three"],
      "slides": [
        {"order": 1, "label": "hook", "search_terms": ["..."], "cutaway_terms": ["..."]},
        {"order": 2, "label": "causa_origen", "search_terms": ["..."], "cutaway_terms": ["..."]}
      ]
    }
    ```
    Luego:
    ```
    python scripts/search_pexels_photo.py "testing/pexels_carousels/<slug>.json"
    ```
    El script elige protagonista (Fase 0, solo Photos), corre la cascada de 4
    niveles por slide, descarga 1-3 candidatos a
    `scripts/output_photos/<slug>/NN_<label>_<variante>.jpg`, y escribe
    `resumen_fotos.txt` con las mismas marcas `⚠ protagonista distinta` /
    `⚠ match aproximado` que ya usa `seleccion-clips-pexels`. Acepta `--only`
    y `--protagonist-id`/`--protagonist-name` igual que el script de reels,
    para re-testear un slide puntual sin rehacer todo el carrusel.
13. **Revisión visual obligatoria antes de elegir ninguna foto final.** El
    script solo filtra por metadata -- no sabe si la foto realmente encaja.
    Con la tool de Read, abrir cada candidata descargada y chequear:
    - Sin persona en cuadro (rompe la regla de que las personas son siempre
      el sujeto).
    - Emoción equivocada para ese momento del carrusel.
    - Ambiente fuera de marca (fondo de estudio liso, foto editorial/moda,
      posado mirando a cámara).
    - **Blanco y negro o desaturada** (regla dura de `image_prompt_style.md`:
      "Full color, never black-and-white or desaturated" -- visto en pruebas
      reales que Pexels sí devuelve resultados en B&N con estos términos).
    - Protagonista inconsistente en edad/tipo entre slides.
    - Consistencia de rostro/apariencia entre las fotos elegidas del mismo
      autor (mismo autor no garantiza misma persona física).
    - Nivel correcto según la etiqueta de `resumen_fotos.txt` (si dice
      "imagen de apoyo sin rostro", confirmar que no hay ningún rostro en
      cuadro; si dice "acompañada", confirmar que la protagonista se
      distingue bien).
    - **Cabeza/rostro cortado por el borde del encuadre** (regla `EDGE_CROP`
      en `constelaciones_brand_voice.md`): rechazar cualquier candidata
      donde la cabeza, el rostro, o el mentón quede cortado de forma abrupta
      por cualquier borde (ej. cabeza a la mitad, mentón justo en el borde
      superior) -- independiente del chequeo de rostro permitido/prohibido
      de arriba. Un plano medio, manos, hombros, espalda, o una toma
      deliberada "desde los hombros hacia abajo" con la cabeza enteramente
      fuera del cuadro siguen siendo válidos; lo que falla es un corte
      parcial que se ve como error de recorte. **Recortar/hacer zoom sobre
      cada borde de la candidata** antes de decidir, no solo mirarla entera
      una vez -- un incidente real (2026-08-13) mostró que un mentón sin
      ojos visibles pasa completamente desapercibido en un vistazo general
      (y tampoco lo detecta el aviso automático de `generate_post_image.py`,
      que solo corre para Gemini/`--source-image`, no para esta revisión de
      candidatas de Pexels).
    Si una candidata falla, volver a buscar solo ese slot con `--only N`
    (repitiendo la cascada completa desde "sola", nunca saltando directo a
    "protagonista distinta"). Si tras 2-3 rondas ninguna sirve, no forzar una
    foto débil -- dejar el slide marcado para búsqueda manual.
14. **Generar la imagen final de cada slide** por la tool de Bash, desde la
    raíz del repo, todas con `--out-dir "C:\Users\USUARIO\Desktop\Imagenes Posts\<slug>"`:
    - **Hook (único comando con `--headline-main`/`--headline-accent`/
      `--headline-extra`/`--force-center-zone`):**
      `python scripts/generate_post_image.py "<ruta a la slide 1>" --source-image "scripts/output_photos/<slug>/01_hook_<letra_elegida>.jpg" --headline-main "..." --headline-accent "..." --headline-extra "..." --force-center-zone --out-dir "..."`
      (`--force-center-zone` es exclusivo del hook -- fuerza el centrado sin
      chequear rostro. NUNCA va en el comando de contenido/"Para asentar"/CTA
      de abajo.)
    - **Contenido, "Para asentar", y CTA** (mismo comando para las tres, el
      CTA ya no lleva `--flat-color`; **sin `--headline-main` ni
      `--headline-accent`** -- solo el párrafo, y sí corre el veto de OpenCV
      normal, nunca `--force-center-zone`):
      `python scripts/generate_post_image.py "<ruta a esa slide>" --source-image "scripts/output_photos/<slug>/NN_<label>_<letra>.jpg" --body-text "<párrafo completo del paso 4>" --out-dir "..."`
    - Si el estilo es `mezcla`, las slides clasificadas `ilustración`/`diagrama`
      siguen su propio camino (ver Recursos) -- no llevan `--source-image`.
    - No generar imagen para el archivo de caption.
15. **Mostrar el resultado**: las imágenes generadas (tool de Read) en orden
    de slide, la ruta de la carpeta `Imagenes Posts/<slug>/`, la caption
    final, y cualquier advertencia heredada de `resumen_fotos.txt`
    (`⚠ protagonista distinta`, `⚠ match aproximado`, slides sin foto
    encontrada). Recordar que no se agrega firma de marca a ninguna slide.
16. **Armar el paquete consolidado** (ver `PACKAGING_STANDARD` en
    `constelaciones_brand_voice.md` para el detalle completo, incluida la
    carpeta de salida). Determinar el libro correcto para el primer
    comentario aplicando la tabla tema -> libro de `FACEBOOK_POST_STRUCTURE`
    (Dolor, Dinero, Mamá, Papá, Regreso, mismo fallback a *El dolor que no te
    pertenece*) al tema de este carrusel -- puede ser un libro distinto del
    que ya nombra el bridge del CTA de la última slide. Redactar un texto de
    primer comentario corto (2-3 líneas) con ese libro, en una redacción
    distinta a la del CTA que ya va en la slide/caption. Determinar el slug
    del micronicho para la carpeta -- **distinto del `<slug>` del paso 1**,
    que solo nombra la subcarpeta de `Imagenes Posts`: si este carrusel es
    parte de un paquete diario junto con otras piezas del mismo tema (post
    estático/virales/historia pedidos en la misma conversación), reusar el
    MISMO slug de micronicho ya usado para esas piezas hermanas. Si es una
    pieza suelta, puede coincidir con el `<slug>` del paso 1. Luego correr:
    ```
    python scripts/build_paquete_docx.py "<hook>" --copy-docx "<ruta a la Caption.docx del paso 10>" --image "<ruta slide 1>" --image "<ruta slide 2>" ... --image "<ruta última slide>" --primer-comentario "<texto del primer comentario>" --tipo-pieza carrusel --micronicho "<slug de micronicho>"
    ```
    `--image` se repite una vez por slide, en el mismo orden de publicación
    (hook primero, CTA al final) -- nunca la caption, que no tiene imagen
    propia. Esto genera
    `Desktop/Constelaciones - Publicaciones/<fecha de hoy> <slug de
    micronicho>/Paquete 2 - Carrusel/Carrusel Publicación/PAQUETE -
    <hook>.docx` -- no reemplaza los `.docx` de slide/caption del paso 10 ni
    las imágenes del paso 14 (esos siguen guardándose donde siempre, en
    `Desktop/Posts Constelaciones/` y
    `Desktop/Imagenes Posts/<slug>/`), los complementa. Mostrar la ruta
    final al usuario junto con el resto del resultado.
17. **Generar la versión Historias del mismo carrusel** (opcional -- solo
    cuando el pedido pide explícitamente la versión historias, o es parte de
    un paquete diario que la incluye; si no, terminar en el paso 16). Va a
    `Paquete 2 - Carrusel/Carrusel Historias/`, reemplazando la pieza suelta
    que generaba antes `historias-constelaciones` para el día. **Nunca
    redacta contenido nuevo ni busca fotos nuevas** -- reutiliza al 100% lo
    que este mismo carrusel ya produjo:
    - **6 slides:** el hook + los primeros 3 slides de contenido en el orden
      ya publicado (nunca elegidos por separado -- para estructuras
      narrativas/con giro esos primeros 3 son el arranque real de la
      historia, no serían coherentes sueltos de otro punto; para listas en
      paralelo, el orden ya viene de mayor a menor pain por la regla de
      "First content slide carries the strongest pain") + "Para asentar" +
      CTA. Si el carrusel de feed tuvo menos de 3 slides de contenido más
      allá del hook (no debería pasar, el mínimo es 6 slides = hook + 3
      contenido + Para asentar + CTA), usar los que haya.
    - **Mismas fotos, mismo texto quemado, re-encuadradas a 9:16** en vez de
      4:5 -- correr `generate_post_image.py` otra vez sobre el MISMO
      `--source-image` de cada slide elegida, con el MISMO
      `--headline-main`/`--headline-accent`/`--headline-extra`/
      `--force-center-zone` (hook) o el MISMO `--body-text` (las demás),
      cambiando solo `--aspect 9:16` y `--out-dir
      "Desktop\Imagenes Posts\<slug>\historia"` (subcarpeta del carrusel,
      no una carpeta nueva separada).
    - **Única adaptación de texto permitida:** en la slide de CTA, cambiar
      la frase final del bridge de "El link está en la descripción." a "El
      link está en mi bio." -- Stories no tiene campo de descripción/caption,
      así que esa instrucción sería literalmente falsa en ese formato. El
      resto del bridge (el libro, el reencuadre) queda idéntico.
    - **Armar el paquete** (mismo `build_paquete_docx.py`, sin
      `--primer-comentario` -- Stories no tiene mecánica de primer
      comentario, igual que no la tenía el formato viejo de
      `historias-constelaciones`):
      ```
      python scripts/build_paquete_docx.py "<hook>" --copy-docx "<misma Caption.docx del paso 10>" --image "<ruta hook 9:16>" --image "<ruta contenido 1 9:16>" --image "<ruta contenido 2 9:16>" --image "<ruta contenido 3 9:16>" --image "<ruta Para asentar 9:16>" --image "<ruta CTA 9:16>" --tipo-pieza carrusel-historia --micronicho "<slug de micronicho>"
      ```
      La caption reusada aquí es solo de referencia dentro del paquete (qué
      mensaje es este) -- Instagram/Facebook Stories no tiene un campo de
      caption real, así que nadie la pega en ningún lado; el CTA que
      importa ya está horneado en la última imagen.

## Reglas duras

- Nunca preguntar qué estructura usar antes de escribir — elegir (nombrada o
  rotada) y avisar cuál se usó al mostrar el resultado.
- "Para asentar" va exclusivamente en la penúltima slide; el CTA visual va
  exclusivamente en la última. Ninguna se salta, ninguna se combina. El link
  plano + hashtags van exclusivamente en la caption, nunca en una slide — y
  el copy del CTA debe decirlo explícitamente ("el link está en la
  descripción"), nunca solo nombrar el libro y quedarse ahí.
- **Toda foto de este carrusel viene de Pexels, nunca de Gemini** — regla
  dura, no una preferencia. Si `search_pexels_photo.py` no encuentra nada
  usable para un slide tras la cascada completa y la revisión visual, se dice
  explícitamente y se deja para búsqueda manual — nunca se cae a Gemini como
  fallback silencioso.
- **Ninguna slide usa `--flat-color`, incluido el CTA.** Las 6 slides
  siempre llevan `--source-image` con una foto real de Pexels y la misma
  coherencia de protagonista/ambiente que el resto del carrusel.
- **Ninguna slide se genera sin texto que quemar, pero solo el hook lleva
  `--headline-main`.** El hook siempre lleva `--headline-main` +
  `--headline-accent` + `--headline-extra` + `--force-center-zone`; toda
  slide después del hook (contenido, "Para asentar", CTA) lleva SOLO
  `--body-text`, nunca `--headline-main`/`--headline-accent`/
  `--headline-extra` -- el mini-título dorado por slide de contenido ya no
  existe. `--force-center-zone` es exclusivo del hook; ninguna otra slide
  lo usa, todas las demás siguen con el veto de OpenCV normal.
- El estilo visual (`photo`, uno de los 4 ilustrados, o `mezcla`) es siempre
  elección explícita del usuario, nunca automática ni rotada.
- `mezcla` es un estilo alternativo opt-in, actualmente sin usar desde que se
  canceló su prueba -- ver nota de "Cuándo se activa" sobre su pierna `foto`
  desactualizada antes de retomarlo.
- **Español neutro colombiano en todo el texto, nunca voseo ni modismos de
  otro país** — regla de `constelaciones_brand_voice.md`, aplica a títulos,
  subtítulos, párrafos de slide, CTA, y caption por igual.
- **Revisión visual obligatoria antes de mostrarle nada al usuario** — el
  filtrado del script es solo metadata, nunca sustituye mirar la foto.
  Incluye el chequeo de blanco y negro/desaturada, no solo los heredados de
  reels.
- No generar ninguna imagen antes de que el usuario apruebe el texto completo
  (párrafo + bloques cortos + términos de búsqueda + caption).
- Nunca pedir la API key de Pexels al usuario — el script la maneja igual que
  `generate_post_image.py` maneja la de Gemini para los otros estilos.
- Quemar texto con protagonista requiere `opencv-python` instalado. Sin la
  librería, la llamada falla con un error explícito en vez de arriesgarse a
  tapar una cara silenciosamente.
- Nunca se agrega firma de marca (nombre de autor, @handle) a ninguna slide.
- El paquete consolidado (paso 16) es siempre el último paso, nunca antes de
  que existan todas las imágenes finales y la caption. El texto del primer
  comentario es nuevo (nunca copiar el bridge del CTA tal cual) y su libro
  se decide con la tabla tema -> libro, no siempre el mismo del bridge de la
  última slide — ver `PACKAGING_STANDARD` en `constelaciones_brand_voice.md`.
- **La versión Historias (paso 17) nunca redacta copy nuevo ni busca fotos
  nuevas.** Siempre las mismas 6 fotos/textos ya usados en el carrusel de
  feed (hook + primeros 3 de contenido, en el orden ya publicado + Para
  asentar + CTA), solo re-encuadrados a `--aspect 9:16`. La única palabra
  que cambia en todo el paso es "descripción" -> "bio" en la última frase
  del CTA -- nunca más que eso. Sin `--primer-comentario` en su paquete
  (Stories no tiene esa mecánica).

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` — voz (incluye la
  regla de español neutro colombiano), cierre, bridge reforzado, CTA,
  hashtags, las 5 estructuras, y el "Design mix" completo (qué slide lleva
  qué combinación de foto/color/bloques de texto).
- `../../scripts/references/image_prompt_style.md` — vocabulario de marca
  (ambientes, tono cálido, traducción conceptual) que informa los términos de
  búsqueda del paso 6, y la regla de "siempre color, nunca blanco y negro"
  que valida el paso 13. Ya no gobierna la generación de fotos de esta skill
  (eso pasó a Pexels) — sigue gobernando `mezcla-ilustracion`/los 4 estilos
  ilustrados si se usan.
- `../../scripts/references/canva_title_style.md` — sección
  `CARROUSEL_BAKED_TYPOGRAPHY`: la tipografía automática de esta skill
  (título/subtítulo dorado exclusivo del hook, párrafo blanco cálido en
  todas las demás slides), distinta del spec manual de las otras 3 skills.
- `../../scripts/references/illustration_style.md` / `mixed_visual_style.md`
  — solo relevantes si se usa un estilo ilustrado o `mezcla`.
- `../../scripts/search_pexels_photo.py` — busca y descarga las fotos;
  reutiliza por import la cascada de protagonista de `search_pexels_clips.py`
  (Photos únicamente). Acepta `--only`, `--protagonist-id`/`--protagonist-name`.
- `../../scripts/generate_post_image.py` — genera la imagen final de cada
  slide. `--source-image` para usar la foto de Pexels ya descargada en vez de
  llamar a Gemini (las 6 slides, incluido el CTA). `--headline-main`/
  `--headline-accent`/`--headline-extra`/`--force-center-zone` solo para el
  hook; `--body-text` solo para las demás slides (nunca combinado con los
  anteriores).
  `--flat-color` ya no se usa en esta skill salvo para una slide de
  `diagrama` dentro de `mezcla`.
- `../../scripts/generate_diagram_image.py` — solo si se usa `mezcla` y hay
  slide de diagrama.
- `../../scripts/build_paquete_docx.py` — arma el paquete consolidado del
  paso 16.
- `requirements.txt` (raíz) — incluye `opencv-python` (veto de rostro al
  quemar texto) y `Pillow`.
- `testing/copy_gen_state.json` — rotación de estructura y color plano.
- `testing/pexels_carousels/` — JSON intermedio por carrusel (gitignored).
- `scripts/output_photos/` — fotos descargadas por carrusel (gitignored,
  binarios, no se suben al repo).
- `Desktop/Imagenes Posts/<slug>/` — imágenes finales de este carrusel, en su
  propia subcarpeta.
- `Desktop/Constelaciones - Publicaciones/<fecha> <slug de micronicho>/Paquete
  2 - Carrusel/Carrusel Publicación/PAQUETE - <hook>.docx` — el paquete
  consolidado del paso 16.
- `Desktop/Imagenes Posts/<slug>/historia/` — imágenes 9:16 de la versión
  Historias (paso 17), subcarpeta del carrusel de feed.
- `Desktop/Constelaciones - Publicaciones/<fecha> <slug de micronicho>/Paquete
  2 - Carrusel/Carrusel Historias/PAQUETE - <hook>.docx` — el paquete
  consolidado del paso 17.

## Related skills

- `post-constelaciones` — para posts de una sola imagen (sigue con Gemini).
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano (sigue con Gemini).
- `seleccion-clips-pexels` — mismo mecanismo de protagonista/cascada, para
  B-roll de reels en vez de slides de carrusel.
- `historias-constelaciones` — sigue existiendo para una Story suelta con su
  propio tema, sin carrusel de feed asociado; para el paquete diario, el
  paso 17 de esta skill (Carrusel Historias) la reemplaza.
- `ig-hashtag-strategist` (bundle público) — sizing de los 3 hashtags de tema.
