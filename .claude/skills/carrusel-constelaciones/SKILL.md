---
name: carrusel-constelaciones
description: Draft a multi-slide organic Instagram/Facebook carousel for Constelaciones Familiares in one of 5 structures (narrativo problema-explicación-Para asentar-CTA, lista de comportamientos, antes/después, autodiagnóstico, mini-historia con giro), following the brand voice in scripts/references/constelaciones_brand_voice.md. Writes slide-by-slide on-image text (second-to-last slide is always "Para asentar", last slide is always the book CTA) plus a separate caption with the CTA link and 2 fixed + 3 topic hashtags. Keeps one consistent protagonist (gender/age presentation) across all photo slides of the same carousel, and gives the hook slide and CTA slide a flat brand-color "quote card" background instead of a photo. On approval, saves each slide as .docx in Desktop/Posts Constelaciones and generates each slide's background by running scripts/generate_post_image.py once per slide, saved to Desktop/Imagenes Posts. Use for "hazme un carrusel de [tema]", "necesito un carrusel sobre [tema]". Not for single-image posts (use post-constelaciones) or paid ads (future ads-constelaciones).
---

# Carrusel Constelaciones (multi-slide)

Redacta un carrusel orgánico para Constelaciones Familiares: elige
estructura, escribe el texto de cada slide más una caption separada, lo
aprueba el usuario, guarda cada slide como `.docx`, y genera el fondo de
cada slide reutilizando `scripts/generate_post_image.py` una vez por slide
(foto para el contenido, color plano para el hook y el CTA).

## Cuándo se activa

- "hazme un carrusel de [tema]"
- "necesito un carrusel sobre [tema]"
- "arma un carrusel de Constelaciones sobre [tema]"

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
3. **Elegir un protagonista fijo para todo el carrusel.** A partir del copy
   (género gramatical del "tú"/"ella" del tema, o el que mejor encaje),
   definir una descripción corta en inglés (ej. `"a woman in her early-to-mid
   30s"`) que se va a usar en **todas** las slides con foto de este carrusel,
   para que no cambie de persona entre una slide y otra.
4. **Redactar las slides** según la forma que define la estructura elegida
   (ver conteo y orden exacto en `CAROUSEL_STRUCTURES`, que ahora siempre
   termina en: [...contenido de la estructura...] → "Para asentar"
   (penúltima) → CTA del libro (última). El CTA de la última slide debe
   incluir la frase-puente obligatoria (ver regla "Bridge required before the
   CTA" en `constelaciones_brand_voice.md`) + mención del libro — el link
   plano NO va en la slide, solo en la caption.
5. **Redactar la caption por separado** (no va en ninguna slide): mención del
   CTA hacia *El dolor que no te pertenece* + `https://eldolorquenotepertenece.com`
   sin UTM, luego los hashtags al final (2 fijos + 3 de tema). Para los 3 de
   tema, aplicar la lógica de tamaño (niche/mid/broad) de la skill pública
   `ig-hashtag-strategist` sobre el tema de este carrusel.
6. **Mostrar todo para aprobación** antes de generar ninguna imagen: estructura
   usada, protagonista elegido, texto de cada slide numerada (marcando cuáles
   son "sin foto"), y la caption completa. Esperar aprobación o ajustes — no
   gastar generación de imagen en un borrador sin aprobar.
7. **Guardar cada slide aprobada** como
   `Desktop/Posts Constelaciones/<hook> - Slide N.docx` (título/texto de esa
   slide en negrita en el primer párrafo), y la caption como
   `Desktop/Posts Constelaciones/<hook> - Caption.docx`.
8. **Elegir 2 colores distintos de `BRAND_COLORS`** (uno para el hook, otro
   para el CTA, nunca el mismo dentro del mismo carrusel) evitando repetir
   cualquiera de los últimos 2 usados: leer/actualizar
   `testing/copy_gen_state.json`, clave `"flat_color"`, mismo mecanismo de
   rotación que las demás categorías.
9. **Generar el fondo de cada slide** por la tool de Bash, desde la raíz del
   repo:
   - **Slide 1 (hook) y última slide (CTA):**
     `python scripts/generate_post_image.py "<ruta a esa slide>" --flat-color "<color elegido>"`
     — sin foto, sin llamar a Gemini, instantáneo.
   - **Todas las slides intermedias (incluida "Para asentar"):**
     `python scripts/generate_post_image.py "<ruta a esa slide>" --protagonist "<descripción del paso 3>"`
     — foto generada, con la misma persona consistente en todas.
   - No generar imagen para el archivo de caption.
10. **Mostrar el resultado**: las N imágenes generadas (tool de Read) en
    orden de slide, la caption final, y el recordatorio de que el texto de
    cada slide se agrega después a mano en Canva sobre su fondo.

## Reglas duras

- Nunca preguntar qué estructura usar antes de escribir — elegir (nombrada o
  rotada) y avisar cuál se usó al mostrar el resultado.
- "Para asentar" va exclusivamente en la penúltima slide; el CTA visual
  (bridge + mención del libro) va exclusivamente en la última slide. Ninguna
  se salta, ninguna se combina con otra. El link plano + hashtags van
  exclusivamente en la caption, nunca en una slide.
- El hook (slide 1) y la última slide (CTA) siempre usan `--flat-color`
  (sin foto); todas las demás siempre usan foto con `--protagonist`. Esta
  mezcla se repite en cada carrusel, no es aleatoria ni opcional.
- El protagonista elegido en el paso 3 debe pasarse igual en todas las
  llamadas con foto de un mismo carrusel — nunca generar una slide con foto
  sin `--protagonist`.
- Nunca pedir la API key de Gemini ni el comando de Python al usuario.
- No generar ninguna imagen antes de que el usuario apruebe el texto completo
  (todas las slides + caption).
- Las reglas de voz, cierre, CTA y hashtags viven únicamente en
  `constelaciones_brand_voice.md`; el estilo visual y `BRAND_COLORS`
  únicamente en `image_prompt_style.md`.

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` — voz, cierre,
  bridge, CTA, hashtags, y las 5 estructuras de carrusel (con su orden fijo
  de Para-asentar + CTA y el mix de diseño foto/color).
- `../../scripts/references/image_prompt_style.md` — estilo visual de cada
  foto de fondo y la paleta `BRAND_COLORS` (los usa `generate_post_image.py`,
  no esta skill directamente).
- `../../scripts/generate_post_image.py` — genera cada fondo; `--protagonist`
  para consistencia de persona, `--flat-color` para las slides sin foto.
- `testing/copy_gen_state.json` — estado de rotación de estructura y de
  color plano (claves `"carousel_structure"` y `"flat_color"`; se autogenera).

## Related skills

- `post-constelaciones` — para posts de una sola imagen.
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano.
- `ig-hashtag-strategist` (bundle público) — sizing de los 3 hashtags de tema.
