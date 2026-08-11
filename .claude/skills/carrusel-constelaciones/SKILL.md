---
name: carrusel-constelaciones
description: Draft a multi-slide organic Instagram/Facebook carousel for Constelaciones Familiares in one of 5 structures (narrativo problema-explicación-Para asentar-CTA, lista de comportamientos, antes/después, autodiagnóstico, mini-historia con giro), following the brand voice in scripts/references/constelaciones_brand_voice.md, with the first content slide always carrying the carousel's strongest pain beat, never a generic opener. Writes slide-by-slide on-image text (second-to-last slide is always "Para asentar", last slide is always the book CTA) plus a separate caption with the CTA link and 2 fixed + 3 topic hashtags. Keeps one consistent protagonist (gender/age presentation) AND one fixed setting/light source across all photo slides of the same carousel, and gives the hook slide and CTA slide a flat brand-color "quote card" background instead of a photo. Bakes a short headline (+ optional accent line) directly onto every generated slide with Pillow -- Anton poster-style main phrase + Playfair Display italic accent, same colors as canva_title_style.md -- placed in whichever third of the frame an OpenCV face check confirms is clear of the protagonist's face (needs opencv-python), so no slide ships without legible on-image text and no manual Canva pass is required for it. Supports 6 visual styles -- photo (default, cinematic realism), 4 illustrated styles (minimal line-art, storybook, cartoon, sequential-panel storytelling), or the opt-in "mezcla" style that mixes 60% photo / 30% flat conceptual illustration / 10% diagram across the content slides of the SAME carousel instead of one style for all of them (see scripts/references/mixed_visual_style.md) -- chosen explicitly by the user, never auto-rotated. On approval, saves each slide as .docx in Desktop/Posts Constelaciones and generates each slide's finished image (background + baked headline) by running scripts/generate_post_image.py (or scripts/generate_diagram_image.py for a diagram slide in "mezcla") once per slide, saved to Desktop/Imagenes Posts. Use for "hazme un carrusel de [tema]", "necesito un carrusel sobre [tema]", optionally with a visual style named ("...estilo minimalista/tipo libro/caricatura/storytelling/mezcla..."). Not for single-image posts (use post-constelaciones) or paid ads (future ads-constelaciones).
---

# Carrusel Constelaciones (multi-slide)

Redacta un carrusel orgánico para Constelaciones Familiares: elige
estructura, escribe el texto de cada slide (más un titular corto por slide
para quemar en la imagen) más una caption separada, lo aprueba el usuario,
guarda cada slide como `.docx`, y genera la imagen final de cada slide
(fondo + titular quemado) reutilizando `scripts/generate_post_image.py` una
vez por slide (foto para el contenido, color plano para el hook y el CTA).

## Cuándo se activa

- "hazme un carrusel de [tema]"
- "necesito un carrusel sobre [tema]"
- "arma un carrusel de Constelaciones sobre [tema]"
- Puede incluir el estilo visual: "...estilo minimalista/tipo libro/
  caricatura/storytelling/mezcla sobre [tema]". Sin especificarlo, el estilo
  es fotográfico (el de siempre, sin cambios). "Mezcla" es el estilo 60/30/10
  (ver `../../scripts/references/mixed_visual_style.md`) -- 100% opcional, no
  reemplaza nada del comportamiento default.

No se activa para posts de una sola imagen (`post-constelaciones`) ni para
anuncios pagados.

## Flujo

1. **Tema.** Tomar el tema/ángulo del pedido.
2. **Elegir estructura.**
   - Si el usuario nombra una de las 5 (ver `CAROUSEL_STRUCTURES` en
     `../../scripts/references/constelaciones_brand_voice.md`), usar esa y no
     tocar la rotación.
   - Si no la nombra, elegirla automáticamente evitando repetir cualquiera de
     las últimas 2 usadas: leer `testing/copy_gen_state.json` (crear con `{}`
     si no existe), clave `"carousel_structure"`, mismo mecanismo de rotación
     que `post-constelaciones` (y que la rotación de imágenes).
   - **Nunca preguntar cuál usar antes de redactar** — elegir y avisar cuál se
     usó junto con el borrador.
3. **Elegir estilo visual.** Si el usuario lo nombra ("estilo minimalista",
   "tipo libro", "caricatura", "storytelling", "mezcla"), usar ese. Si no lo
   nombra, usar `photo` (default, el comportamiento fotográfico de siempre). A
   diferencia de la estructura, el estilo visual **nunca se rota
   automáticamente** — es una preferencia explícita del usuario, no una
   variedad forzada. Si el usuario pide `storytelling`, avisarle brevemente
   (no como bloqueo) que es el estilo con más riesgo de que el personaje o el
   trazo varíen ligeramente entre slides, porque cada slide se genera con una
   llamada independiente a Gemini sin imagen de referencia compartida.
   - **`mezcla`** es el estilo 60/30/10 (ver
     `../../scripts/references/mixed_visual_style.md`): en vez de un único
     estilo para todas las slides de contenido, mezcla foto / ilustración
     plana / diagrama dentro del MISMO carrusel. Es un estilo alternativo
     100% opcional para comparar contra el comportamiento de siempre — nunca
     se activa sin que el usuario lo pida explícitamente.
4. **Elegir un protagonista fijo para todo el carrusel.** A partir del copy
   (género gramatical del "tú"/"ella" del tema, o el que mejor encaje),
   definir una descripción corta en inglés (ej. `"a woman in her early-to-mid
   30s"`) que se va a usar en **todas** las slides con foto/ilustración de
   este carrusel, para que no cambie de persona entre una slide y otra.
5. **Redactar las slides** según la forma que define la estructura elegida
   (ver conteo y orden exacto en `CAROUSEL_STRUCTURES`, que ahora siempre
   termina en: [...contenido de la estructura...] → "Para asentar"
   (penúltima) → CTA del libro (última). El CTA de la última slide debe
   incluir la frase-puente obligatoria (ver regla "Bridge required before the
   CTA" en `constelaciones_brand_voice.md`) + mención del libro — el link
   plano NO va en la slide, solo en la caption. La slide 2 (primera de
   contenido, justo después del hook) tiene que ser el beat más fuerte del
   dolor central del carrusel, nunca una pregunta o dato genérico de
   arranque — ver regla "First content slide carries the strongest pain
   (mandatory)" en `CAROUSEL_STRUCTURES`, con el detalle de qué significa
   para cada una de las 5 estructuras.
5a. **Escribir un titular corto por slide (las 8), para quemar en la
   imagen.** Distinto del texto completo de la slide del paso 5 (que se sigue
   guardando entero en el `.docx`): `headline_main` son 3-8 palabras, la
   frase de mayor impacto de esa slide, en mayúsculas cuando se muestre
   (el script ya lo mayusculiza) — nunca la frase completa del paso 5 tal
   cual si es larga, sino su versión más corta y directa. `headline_accent`
   es **opcional**, una línea de cierre más breve todavía, solo cuando la
   slide tiene un reencuadre natural de dos partes (el hook con su
   contraste, "Para asentar" con su afirmación, el CTA con la mención del
   libro después del bridge). Para el hook y el CTA, que ya son cortos por
   convención de voz, `headline_main`/`headline_accent` normalmente COINCIDEN
   con el texto del paso 5 o son un recorte mínimo — no hace falta
   reinventarlos. Para las slides de contenido/"Para asentar" (frases más
   largas), sí hace falta distilar de verdad.
5b. **Si el estilo visual es `mezcla`, clasificar cada slide de contenido**
   (todas menos el hook y el CTA, que siguen siendo quote card plana) en
   `foto` / `ilustración` / `diagrama`, siguiendo la heurística y el reparto
   60/30/10 exactos de `mixed_visual_style.md` (narrativo/emocional -> foto,
   conceptual explicativo -> ilustración, estructurado/enumerado -> diagrama;
   método de mayor resto con empate foto > ilustración > diagrama; no forzar
   un diagrama en carruseles con pocas slides de contenido). Anotar la
   clasificación de cada slide para mostrarla en el paso 7 y usarla en el
   paso 10 — este paso no existe (se omite entero) si el estilo no es
   `mezcla`.
6. **Redactar la caption por separado** (no va en ninguna slide): mención del
   CTA hacia *El dolor que no te pertenece* + `https://eldolorquenotepertenece.com`
   sin UTM, luego los hashtags al final (2 fijos + 3 de tema). Para los 3 de
   tema, aplicar la lógica de tamaño (niche/mid/broad) de la skill pública
   `ig-hashtag-strategist` sobre el tema de este carrusel.
7. **Mostrar todo para aprobación** antes de generar ninguna imagen: estructura
   usada, estilo visual, protagonista elegido, texto de cada slide numerada
   junto con su `headline_main`/`headline_accent` del paso 5a (marcando
   cuáles son "sin foto", y si el estilo es `mezcla`, marcando además la
   clasificación foto/ilustración/diagrama de cada slide del paso 5b), y la
   caption completa. El titular queda quemado en la imagen y no se edita
   después a mano, así que tiene que aprobarse en este paso igual que el
   resto del texto — nunca generar sin que el usuario haya visto ambos
   (texto completo + titular) de cada slide. Esperar aprobación o ajustes —
   no gastar generación de imagen en un borrador sin aprobar.
8. **Guardar cada slide aprobada** como
   `Desktop/Posts Constelaciones/<hook> - Slide N.docx` (título/texto de esa
   slide en negrita en el primer párrafo), y la caption como
   `Desktop/Posts Constelaciones/<hook> - Caption.docx`.
9. **Elegir 2 colores distintos de `BRAND_COLORS`** (uno para el hook, otro
   para el CTA, nunca el mismo dentro del mismo carrusel) evitando repetir
   cualquiera de los últimos 2 usados: leer/actualizar
   `testing/copy_gen_state.json`, clave `"flat_color"`, mismo mecanismo de
   rotación que las demás categorías. Esto aplica igual sin importar el
   estilo visual elegido en el paso 3. Si el estilo es `mezcla` y hay al
   menos una slide de diagrama (paso 5b), elegir además un 3er color de
   `BRAND_COLORS` para el fondo de esa(s) slide(s) de diagrama, distinto de
   los otros 2 ya elegidos para hook/CTA (no participa de la rotación de
   `testing/copy_gen_state.json`, se elige fresco cada vez que hace falta).
10. **Generar la imagen final de cada slide** (fondo + titular quemado) por
    la tool de Bash, desde la raíz del repo. **Todas** las llamadas llevan
    `--headline-main "<headline_main del paso 5a>"` y, si esa slide tiene
    accent, `--headline-accent "<headline_accent del paso 5a>"` — ninguna
    slide se genera sin su titular:
    - **Slide 1 (hook) y última slide (CTA):**
      `python scripts/generate_post_image.py "<ruta a esa slide>" --flat-color "<color elegido>" --headline-main "..." [--headline-accent "..."]`
      — sin foto/ilustración, sin llamar a Gemini para la imagen en sí,
      igual sin importar el estilo visual. El titular queda centrado en todo
      el canvas (es el diseño entero de la slide, como siempre).
    - **Todas las slides intermedias (incluida "Para asentar"), si el estilo
      NO es `mezcla`:**
      `python scripts/generate_post_image.py "<ruta a esa slide>" --protagonist "<descripción del paso 4>" --visual-style <estilo del paso 3> --headline-main "..." [--headline-accent "..."] [--setting "..."]`
      — omitir `--visual-style` por completo si el estilo es `photo`
      (comportamiento idéntico al de antes de esta función en cuanto al
      fondo). **Setting fijo entre slides de foto de un mismo carrusel:** en
      la PRIMERA slide de foto del carrusel, omitir `--setting` (deja que
      rote como siempre) y anotar el texto exacto que el script imprime como
      "Ubicación elegida: ..."; en TODAS las slides de foto siguientes del
      mismo carrusel, pasar `--setting "<ese mismo texto exacto>"` para que
      compartan ambiente/fuente de luz. Solo aplica a slides con
      `--visual-style photo` (o sin `--visual-style`, que es lo mismo) —
      los 4 estilos ilustrados no tienen `SETTINGS`, se ignora si se pasa.
    - **Si el estilo es `mezcla`, cada slide intermedia según su
      clasificación del paso 5b** (la regla de `--setting` fijo de arriba
      aplica igual a las slides clasificadas `foto` dentro de la mezcla):
      - `foto` → `python scripts/generate_post_image.py "<ruta a esa slide>" --protagonist "<descripción del paso 4>" --headline-main "..." [--headline-accent "..."] [--setting "..."]` (sin `--visual-style`, foto de siempre).
      - `ilustración` → `python scripts/generate_post_image.py "<ruta a esa slide>" --visual-style mezcla-ilustracion --headline-main "..." [--headline-accent "..."]` — **sin `--protagonist`**, esta pierna es deliberadamente sin personas (ver `mixed_visual_style.md`). El titular no necesita chequeo de rostro (no hay protagonista), va directo al margen superior.
      - `diagrama` → `python scripts/generate_diagram_image.py "<ruta de salida .png para esa slide>" --items-json '["item 1", "item 2", ...]' --flat-color "<3er color del paso 9>" --headline-main "..." [--headline-accent "..."]` — extraer los items del propio texto de la slide (si ya es una lista, usar cada punto; si no, dividir la idea central en 2-4 sub-puntos breves), 2 a 6 items. No llama a Gemini para nada de esto (ni fondo ni titular).
    - No generar imagen para el archivo de caption.
11. **Mostrar el resultado**: las N imágenes generadas (tool de Read) en
    orden de slide, ya con su titular quemado, y la caption final — sin
    ningún paso manual de Canva pendiente para el texto (el titular ya está
    en la imagen). Recordar igual que no se agrega firma de marca (nombre de
    autor, @handle) a ninguna slide, eliminada por completo. Si alguna slide
    de foto/ilustración con protagonista muestra el titular en una posición
    que igual se ve forzada (el chequeo de OpenCV evita tapar la cara, pero
    no garantiza la composición más elegante), avisar al usuario para que
    decida si la regenera con otro `headline_main` más corto o la ajusta a
    mano — no es un bloqueo, es una nota de calidad.

## Reglas duras

- Nunca preguntar qué estructura usar antes de escribir — elegir (nombrada o
  rotada) y avisar cuál se usó al mostrar el resultado.
- "Para asentar" va exclusivamente en la penúltima slide; el CTA visual
  (bridge + mención del libro) va exclusivamente en la última slide. Ninguna
  se salta, ninguna se combina con otra. El link plano + hashtags van
  exclusivamente en la caption, nunca en una slide.
- El hook (slide 1) y la última slide (CTA) siempre usan `--flat-color`
  (sin foto/ilustración); todas las demás siempre usan `--protagonist`, con
  o sin `--visual-style` según lo elegido. Esta mezcla se repite en cada
  carrusel, no es aleatoria ni opcional, y no depende del estilo visual.
- El protagonista elegido debe pasarse igual en todas las llamadas con
  foto/ilustración de un mismo carrusel — nunca generar esa slide sin
  `--protagonist`.
- El estilo visual (`photo`, uno de los 4 ilustrados, o `mezcla`) es siempre
  elección explícita del usuario, nunca automática ni rotada. Combina con
  cualquiera de las 5 estructuras narrativas — son ejes independientes.
- `mezcla` es un estilo alternativo opt-in: sin nombrarlo explícitamente, el
  carrusel se comporta exactamente igual que antes de que este estilo
  existiera. Nunca se activa por inferencia ni se sugiere como default.
- En `mezcla`, el reparto 60/30/10 aplica solo a las slides de contenido
  (nunca al hook ni al CTA, que siguen siendo quote card plana) y sigue el
  método de mayor resto de `mixed_visual_style.md`, nunca una asignación al
  azar. Las slides `ilustración` y `diagrama` nunca llevan `--protagonist` ni
  representan personas — ver `mixed_visual_style.md` para el porqué
  (consistencia visual + evitar cualquier riesgo de calidad de rostro con
  Gemini).
- Nunca pedir la API key de Gemini ni el comando de Python al usuario.
- No generar ninguna imagen antes de que el usuario apruebe el texto completo
  (todas las slides + caption + `headline_main`/`headline_accent` del paso 5a).
- Las reglas de voz, cierre, CTA y hashtags viven únicamente en
  `constelaciones_brand_voice.md`; el estilo visual fotográfico únicamente en
  `image_prompt_style.md` (incluye `BRAND_COLORS`, compartido por todos los
  estilos); los 4 estilos ilustrados únicamente en `illustration_style.md`.
- **Ninguna slide se genera sin `--headline-main`.** El titular queda
  quemado en la imagen misma (Pillow, Anton + Playfair Display italic,
  mismos colores que `canva_title_style.md`) — ya no es un paso manual de
  Canva. Nunca se agrega firma de marca (nombre de autor, @handle) a
  ninguna slide.
- **Todas las slides de foto de un mismo carrusel comparten `--setting`**
  (mismo ambiente/fuente de luz): la primera lo elige por rotación normal
  (sin pasar `--setting`), todas las siguientes lo fijan al texto exacto que
  esa primera llamada imprimió. Composición y ángulo de cámara siguen
  rotando libres por slide — solo el ambiente/luz queda fijo. Esto aplica
  igual dentro de `mezcla` para las slides clasificadas `foto`.
- Quemar titulares en slides con protagonista requiere `opencv-python`
  instalado (`pip install opencv-python`) — el chequeo de rostro es lo que
  evita tapar la cara al elegir la zona del texto. Sin la librería, la
  llamada falla con un error explícito en vez de arriesgarse a tapar una
  cara silenciosamente.

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` — voz, cierre,
  bridge, CTA, hashtags, y las 5 estructuras de carrusel (con su orden fijo
  de Para-asentar + CTA y el mix de diseño foto/color).
- `../../scripts/references/image_prompt_style.md` — estilo fotográfico
  (default) y la paleta `BRAND_COLORS` (los usa `generate_post_image.py`, no
  esta skill directamente).
- `../../scripts/references/canva_title_style.md` — fuente de verdad de la
  tipografía/color del titular (Anton amarillo/naranja + Playfair Display
  italic dorado pálido) que `render_headline` en `generate_post_image.py`
  ahora quema automáticamente; y la regla de que no se agrega firma.
- `../../scripts/references/illustration_style.md` — los 4 estilos
  ilustrados con protagonista (`minimal`, `book`, `cartoon`, `storytelling`)
  y su límite de consistencia entre slides conocido (ver ese archivo), más
  `mezcla-ilustracion` (la pierna de ilustración sin persona del estilo
  `mezcla`).
- `../../scripts/references/mixed_visual_style.md` — la regla completa del
  estilo `mezcla` (60/30/10): alcance, heurística de clasificación,
  apportionment con empates, y por qué ilustración/diagrama van sin
  protagonista. Compartida con `seleccion-clips-pexels`.
- `../../scripts/generate_post_image.py` — genera cada fondo y quema el
  titular; `--protagonist` para consistencia de persona, `--setting` para
  fijar el mismo ambiente/luz entre slides de foto de un carrusel,
  `--flat-color` para las slides sin foto, `--visual-style` para elegir
  entre fotográfico, uno de los 4 ilustrados, o `mezcla-ilustracion`,
  `--headline-main`/`--headline-accent` para el titular quemado (zona segura
  vía `CAMERA_ANGLE_SAFE_ZONES` + veto de OpenCV para ángulos ambiguos o
  estilos ilustrados con protagonista).
- `../../scripts/generate_diagram_image.py` — genera las slides de diagrama
  del estilo `mezcla`: lista numerada vertical con Pillow puro (sin Gemini,
  texto siempre legible), reutiliza `BRAND_COLORS`/`--flat-color`, y
  `--headline-main`/`--headline-accent` en el margen superior reservado (sin
  chequeo de OpenCV, no hay protagonista).
- `requirements.txt` (raíz) — incluye `opencv-python`, requerido solo para
  quemar titulares sobre slides con protagonista (foto o los 4 estilos
  ilustrados); flat-color, mezcla-ilustracion y diagrama nunca lo importan.
- `testing/copy_gen_state.json` — estado de rotación de estructura y de
  color plano (claves `"carousel_structure"` y `"flat_color"`; se autogenera).
- `testing/image_gen_state.json` — estado de rotación de composición/ángulo/
  setting fotográfico (usado por `generate_post_image.py`, no por esta
  skill directamente).
- `testing/fonts/` — caché local de las fuentes descargadas (Anton, Playfair
  Display Italic, Poppins) para quemar texto sin Gemini; se autogenera.

## Related skills

- `post-constelaciones` — para posts de una sola imagen.
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano.
- `ig-hashtag-strategist` (bundle público) — sizing de los 3 hashtags de tema.
