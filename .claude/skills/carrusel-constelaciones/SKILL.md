---
name: carrusel-constelaciones
description: Draft a multi-slide organic Instagram/Facebook carousel for Constelaciones Familiares in one of 5 structures (narrativo problema-explicación-cierre, lista de comportamientos, antes/después, autodiagnóstico, mini-historia con giro), following the brand voice in scripts/references/constelaciones_brand_voice.md. Writes slide-by-slide on-image text (last slide is always the "Para asentar" closer) plus a separate caption with the CTA link and 2 fixed + 3 topic hashtags. On approval, saves each slide as .docx in Desktop/Posts Constelaciones and generates each slide's background photo by running scripts/generate_post_image.py once per slide, saved to Desktop/Imagenes Posts. Use for "hazme un carrusel de [tema]", "necesito un carrusel sobre [tema]". Not for single-image posts (use post-constelaciones) or paid ads (future ads-constelaciones).
---

# Carrusel Constelaciones (multi-slide)

Redacta un carrusel orgánico para Constelaciones Familiares: elige
estructura, escribe el texto de cada slide más una caption separada, lo
aprueba el usuario, guarda cada slide como `.docx`, y genera la foto de
fondo de cada slide reutilizando `scripts/generate_post_image.py` una vez
por slide.

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
3. **Redactar las slides.** Texto on-image por cada slide según la forma que
   define la estructura elegida (ver conteo de slides en
   `CAROUSEL_STRUCTURES`). La **última slide es siempre el cierre "Para
   asentar"** con su afirmación en primera persona — nunca una slide extra
   además del conteo.
4. **Redactar la caption por separado** (no va en ninguna slide): mención del
   CTA hacia *El dolor que no te pertenece* + `https://eldolorquenotepertenece.com`
   sin UTM, luego los hashtags al final (2 fijos + 3 de tema). Para los 3 de
   tema, aplicar la lógica de tamaño (niche/mid/broad) de la skill pública
   `ig-hashtag-strategist` sobre el tema de este carrusel.
5. **Mostrar todo para aprobación** antes de generar ninguna imagen: estructura
   usada, texto de cada slide numerada, y la caption completa. Esperar
   aprobación o ajustes — no gastar generación de imagen en un borrador sin
   aprobar.
6. **Guardar cada slide aprobada** como
   `Desktop/Posts Constelaciones/<hook> - Slide N.docx` (título/texto de esa
   slide en negrita en el primer párrafo), y la caption como
   `Desktop/Posts Constelaciones/<hook> - Caption.docx`.
7. **Generar la imagen de cada slide**: por cada archivo de slide, correr
   `python scripts/generate_post_image.py "<ruta a esa slide>"` por la tool de
   Bash. Cada llamada usa su propia rotación de composición/ubicación/ángulo
   (mismo mecanismo que ya existe), así que las imágenes del carrusel no se
   repiten entre sí tampoco. No generar imagen para el archivo de caption.
8. **Mostrar el resultado**: las N imágenes generadas (tool de Read) en orden
   de slide, la caption final, y el recordatorio de que el texto de cada
   slide se agrega después a mano en Canva sobre su imagen de fondo.

## Reglas duras

- Nunca preguntar qué estructura usar antes de escribir — elegir (nombrada o
  rotada) y avisar cuál se usó al mostrar el resultado.
- "Para asentar" va exclusivamente en la última slide, nunca en la caption.
  El CTA + link + hashtags van exclusivamente en la caption, nunca en una
  slide.
- Nunca pedir la API key de Gemini ni el comando de Python al usuario.
- No generar ninguna imagen antes de que el usuario apruebe el texto completo
  (todas las slides + caption).
- Las reglas de voz, cierre, CTA y hashtags viven únicamente en
  `constelaciones_brand_voice.md`; el estilo visual únicamente en
  `image_prompt_style.md`.

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` — voz, cierre, CTA,
  hashtags, y las 5 estructuras de carrusel.
- `../../scripts/references/image_prompt_style.md` — estilo visual de cada
  foto de fondo (lo usa `generate_post_image.py`, no esta skill directamente).
- `../../scripts/generate_post_image.py` — genera la imagen de fondo, una
  llamada por slide.
- `testing/copy_gen_state.json` — estado de rotación de estructura
  (se autogenera).

## Related skills

- `post-constelaciones` — para posts de una sola imagen.
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano.
- `ig-hashtag-strategist` (bundle público) — sizing de los 3 hashtags de tema.
