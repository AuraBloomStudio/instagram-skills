---
name: carrusel-constelaciones
description: Draft a multi-slide organic Instagram/Facebook carousel for Constelaciones Familiares in one of 5 structures (narrativo problema-explicación-Para asentar-CTA, lista de comportamientos, antes/después, autodiagnóstico, mini-historia con giro), following the brand voice in scripts/references/constelaciones_brand_voice.md (español neutro colombiano, no voseo), with the first content slide always carrying the carousel's strongest pain beat, never a generic opener, and every content slide/"Para asentar" written as a real 2-4 sentence paragraph naming one concrete microdolor, not a one-line headline. Sources every photo slide (hook + content + "Para asentar") from real Pexels stock photography via scripts/search_pexels_photo.py -- the same protagonist-consistency cascade seleccion-clips-pexels already uses for reels, reused by import -- never Gemini, and never any other skill's photo pipeline (post-constelaciones, imagen-post-constelaciones, historias-constelaciones keep generating with Gemini, unaffected). Bakes text directly onto every slide with Pillow (Poppins Bold + Playfair Display italic, same typography as reels): hook gets título + subtítulo + a third short line; content slides and "Para asentar" get título + subtítulo + the full microdolor paragraph in cyan #22D3EE over a dark gradient scrim; the CTA (flat-color quote card, last slide) gets título + subtítulo only, with a bridge sentence that explicitly names the specific pain the carousel just developed before mentioning the book. Placement always runs an OpenCV face check (needs opencv-python) since a real Pexels photo has no requested composition to trust blindly. Saves each carousel's finished images to its own Desktop/Imagenes Posts/<slug>/ subfolder instead of the shared root. Use for "hazme un carrusel de [tema]", "necesito un carrusel sobre [tema]", optionally with a visual style named ("...estilo minimalista/tipo libro/caricatura/storytelling/mezcla..."). Not for single-image posts (use post-constelaciones) or paid ads (future ads-constelaciones).
---

# Carrusel Constelaciones (multi-slide)

Redacta un carrusel orgánico para Constelaciones Familiares: elige
estructura, escribe el texto completo de cada slide (un párrafo real, no un
titular) más los bloques cortos que se queman en la imagen, más una caption
separada, lo aprueba el usuario, guarda cada slide como `.docx`, busca una
foto real de Pexels para cada slide con protagonista (hook + contenido +
"Para asentar"), y genera la imagen final de cada slide (foto + texto
quemado) reutilizando `scripts/generate_post_image.py`.

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

No se activa para posts de una sola imagen (`post-constelaciones`) ni para
anuncios pagados.

## Qué hace exactamente (leer antes de tocar nada)

**Toda foto de este carrusel sale de Pexels, nunca de Gemini.** El hook, cada
slide de contenido, y "Para asentar" llevan foto real de stock, buscada con
`scripts/search_pexels_photo.py` -- mismo mecanismo de protagonista único con
cascada de 4 niveles que ya usa `seleccion-clips-pexels` para reels,
reutilizado por import, no duplicado. Esto es así **solo para esta skill**:
`post-constelaciones`, `imagen-post-constelaciones`, y
`historias-constelaciones` siguen usando Gemini exactamente igual que
siempre, sin ningún cambio.

**Solo el CTA (última slide) sigue siendo quote card plana.** El hook dejó de
serlo -- es la slide más importante para detener el scroll, así que también
lleva foto real de fondo.

**Texto quemado, no editado a mano en Canva, con 3 niveles distintos según el
tipo de slide** (todo vía `render_headline` en `generate_post_image.py`,
Poppins Bold + Playfair Display italic, mismos colores que los reels):
- **Hook:** título (`--headline-main`, dorado `#F2A900`) + subtítulo
  (`--headline-accent`, dorado pálido `#FAE8A8`) + una tercera línea corta
  (`--headline-extra`, Poppins SemiBold, mismo dorado pálido).
- **Contenido + "Para asentar":** título + subtítulo, MÁS el párrafo
  completo del microdolor de esa slide quemado aparte como `--body-text` --
  Poppins Bold cian `#22D3EE`, con degradado oscuro de fondo
  (`apply_gradient_scrim`, mismos stops que `GRADIENT_HTML_TEMPLATE` de los
  reels) para que se lea encima de una foto real sin espacio negativo
  garantizado.
- **CTA:** título + subtítulo únicamente, sin bloque cian -- el peso de esta
  slide viene del bridge (ver regla reforzada en `constelaciones_brand_voice.md`),
  no de un tercer bloque de texto.
`--headline-extra` y `--body-text` son mutuamente excluyentes (nunca la misma
slide lleva los dos). La zona del texto **siempre** se resuelve con el veto
de OpenCV (nunca la tabla determinística de ángulos de cámara, que solo tiene
sentido cuando nosotros le pedimos la composición a Gemini -- acá la foto ya
existe, no la generamos).

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
   plano NO va en la slide, solo en la caption. La slide 2 (primera de
   contenido) tiene que ser el beat más fuerte del dolor central — ver regla
   "First content slide carries the strongest pain (mandatory)". **Todo el
   texto en español neutro colombiano, nunca voseo ni modismos de otro país**
   — ver regla de idioma en "Voice fingerprint" de `constelaciones_brand_voice.md`.
5. **Escribir los bloques cortos por slide (las 6-8), para quemar en la
   imagen** — distintos del párrafo completo del paso 4, que se sigue
   guardando entero en el `.docx`:
   - `headline_main` (todas las slides): 3-8 palabras, la frase de mayor
     impacto de esa slide.
   - `headline_accent` (opcional, todas las slides): línea de cierre más
     breve, cuando la slide tiene un reencuadre natural de dos partes.
   - `headline_extra` (**solo el hook**): una tercera línea corta adicional.
   - `body_text` (**solo contenido + "Para asentar"**): el párrafo completo
     del paso 4, tal cual, para quemar en cian. Nunca en el hook ni el CTA.
6. **Términos de búsqueda de Pexels por slide** (hook + contenido + "Para
   asentar", nunca el CTA que no lleva foto): 2-3 `search_terms` en inglés
   por slide más `cutaway_terms` opcionales, siguiendo las mismas reglas de
   vocabulario que ya usa `seleccion-clips-pexels` (ambientes domésticos
   cotidianos, tono cálido, sujeto explícito + acción concreta + ambiente,
   nunca objeto-símbolo, nunca pose de stock genérica tipo "business woman
   sonriendo a cámara") — ver esas reglas completas en el paso 3 del flujo de
   `../../seleccion-clips-pexels/SKILL.md`. Más `general_terms` (3-5, todo el
   carrusel) para elegir protagonista. **No hay `--protagonist` que redactar
   a mano** — el protagonista real lo elige `search_pexels_photo.py` en su
   Fase 0, a partir de estos términos.
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
11. **Elegir 1 color de `BRAND_COLORS`** para el CTA (único slide plano ahora)
    evitando repetir cualquiera de los últimos 2 usados: leer/actualizar
    `testing/copy_gen_state.json`, clave `"flat_color"`. Si el estilo es
    `mezcla` y hay slide de diagrama, elegir además un color aparte para esa
    (no participa de la rotación, ver `mixed_visual_style.md`).
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
    Si una candidata falla, volver a buscar solo ese slot con `--only N`
    (repitiendo la cascada completa desde "sola", nunca saltando directo a
    "protagonista distinta"). Si tras 2-3 rondas ninguna sirve, no forzar una
    foto débil -- dejar el slide marcado para búsqueda manual.
14. **Generar la imagen final de cada slide** por la tool de Bash, desde la
    raíz del repo, todas con `--out-dir "C:\Users\USUARIO\Desktop\Imagenes Posts\<slug>"`:
    - **Hook:**
      `python scripts/generate_post_image.py "<ruta a la slide 1>" --source-image "scripts/output_photos/<slug>/01_hook_<letra_elegida>.jpg" --headline-main "..." --headline-accent "..." --headline-extra "..." --out-dir "..."`
    - **Contenido y "Para asentar":**
      `python scripts/generate_post_image.py "<ruta a esa slide>" --source-image "scripts/output_photos/<slug>/NN_<label>_<letra>.jpg" --headline-main "..." --headline-accent "..." --body-text "<párrafo completo del paso 4>" --out-dir "..."`
    - **CTA:**
      `python scripts/generate_post_image.py "<ruta a la última slide>" --flat-color "<color del paso 11>" --headline-main "..." --headline-accent "..." --out-dir "..."`
    - Si el estilo es `mezcla`, las slides clasificadas `ilustración`/`diagrama`
      siguen su propio camino (ver Recursos) -- no llevan `--source-image`.
    - No generar imagen para el archivo de caption.
15. **Mostrar el resultado**: las imágenes generadas (tool de Read) en orden
    de slide, la ruta de la carpeta `Imagenes Posts/<slug>/`, la caption
    final, y cualquier advertencia heredada de `resumen_fotos.txt`
    (`⚠ protagonista distinta`, `⚠ match aproximado`, slides sin foto
    encontrada). Recordar que no se agrega firma de marca a ninguna slide.

## Reglas duras

- Nunca preguntar qué estructura usar antes de escribir — elegir (nombrada o
  rotada) y avisar cuál se usó al mostrar el resultado.
- "Para asentar" va exclusivamente en la penúltima slide; el CTA visual va
  exclusivamente en la última. Ninguna se salta, ninguna se combina. El link
  plano + hashtags van exclusivamente en la caption, nunca en una slide.
- **Toda foto de este carrusel viene de Pexels, nunca de Gemini** — regla
  dura, no una preferencia. Si `search_pexels_photo.py` no encuentra nada
  usable para un slide tras la cascada completa y la revisión visual, se dice
  explícitamente y se deja para búsqueda manual — nunca se cae a Gemini como
  fallback silencioso.
- **Solo el CTA sigue siendo `--flat-color`.** El hook, el contenido, y "Para
  asentar" siempre llevan `--source-image` con una foto real de Pexels.
- **Ninguna slide se genera sin `--headline-main`.** `--headline-extra` es
  exclusivo del hook; `--body-text` es exclusivo de contenido/"Para
  asentar"; nunca los dos en la misma slide.
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
  (Poppins Bold + Playfair Display italic + los 3 niveles según tipo de
  slide), distinta del spec manual de las otras 3 skills.
- `../../scripts/references/illustration_style.md` / `mixed_visual_style.md`
  — solo relevantes si se usa un estilo ilustrado o `mezcla`.
- `../../scripts/search_pexels_photo.py` — busca y descarga las fotos;
  reutiliza por import la cascada de protagonista de `search_pexels_clips.py`
  (Photos únicamente). Acepta `--only`, `--protagonist-id`/`--protagonist-name`.
- `../../scripts/generate_post_image.py` — genera la imagen final de cada
  slide. `--source-image` para usar la foto de Pexels ya descargada en vez de
  llamar a Gemini, `--flat-color` para el CTA, `--headline-main`/
  `--headline-accent`/`--headline-extra`/`--body-text` para el texto quemado.
- `../../scripts/generate_diagram_image.py` — solo si se usa `mezcla` y hay
  slide de diagrama.
- `requirements.txt` (raíz) — incluye `opencv-python` (veto de rostro al
  quemar texto) y `Pillow`.
- `testing/copy_gen_state.json` — rotación de estructura y color plano.
- `testing/pexels_carousels/` — JSON intermedio por carrusel (gitignored).
- `scripts/output_photos/` — fotos descargadas por carrusel (gitignored,
  binarios, no se suben al repo).
- `Desktop/Imagenes Posts/<slug>/` — imágenes finales de este carrusel, en su
  propia subcarpeta.

## Related skills

- `post-constelaciones` — para posts de una sola imagen (sigue con Gemini).
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano (sigue con Gemini).
- `seleccion-clips-pexels` — mismo mecanismo de protagonista/cascada, para
  B-roll de reels en vez de slides de carrusel.
- `ig-hashtag-strategist` (bundle público) — sizing de los 3 hashtags de tema.
