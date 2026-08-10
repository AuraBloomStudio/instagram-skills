---
name: post-constelaciones
description: Draft a single-image organic Instagram/Facebook post for Constelaciones Familiares in one of 5 structures (carta directa, contraste cree-que/en-realidad, pregunta sin resolver, confesión personal, dato-manifiesto), following the brand voice documented in scripts/references/constelaciones_brand_voice.md (tú address, "Para asentar" closer, plain-URL CTA, 2 fixed + 3 topic hashtags via ig-hashtag-strategist). On approval, saves the copy as .docx in Desktop/Posts Constelaciones and generates its background photo by running scripts/generate_post_image.py, saved to Desktop/Imagenes Posts. Use for "hazme un post de [tema]", "necesito un post sobre [tema]". Not for carousels (use carrusel-constelaciones), not for paid ads (future ads-constelaciones), and not for generating only the image of a copy already written by hand (use imagen-post-constelaciones).
---

# Post Constelaciones (imagen única)

Redacta un post orgánico de una sola imagen para Constelaciones Familiares,
de principio a fin: elige estructura, escribe el copy, lo aprueba el usuario,
lo guarda como `.docx`, y genera su foto de fondo reutilizando
`scripts/generate_post_image.py`.

## Cuándo se activa

- "hazme un post de [tema]"
- "necesito un post sobre [tema]"
- "escríbeme un post de Constelaciones sobre [tema]"

No se activa para carruseles (`carrusel-constelaciones`), para anuncios
pagados, ni para generar solo la imagen de un copy que el usuario ya escribió
a mano (`imagen-post-constelaciones`).

## Flujo

1. **Tema.** Tomar el tema/ángulo del pedido del usuario.
2. **Elegir estructura.**
   - Si el usuario nombra una de las 5 (ver `POST_STRUCTURES` en
     `../../scripts/references/constelaciones_brand_voice.md`), usar esa y no
     tocar la rotación.
   - Si no la nombra, elegirla automáticamente evitando repetir cualquiera de
     las últimas 2 usadas: leer `testing/copy_gen_state.json` (crear con `{}`
     si no existe), tomar la lista bajo la clave `"post_structure"` (últimas
     usadas, más reciente primero), elegir al azar entre las estructuras que
     no estén en esa lista, y actualizarla anteponiendo la elegida y
     recortando a 2 elementos.
   - **Nunca preguntar cuál usar antes de redactar** — elegir y avisar cuál se
     usó junto con el borrador.
3. **Redactar el copy** siguiendo esa estructura y las reglas de voz, cierre,
   CTA y hashtags de `constelaciones_brand_voice.md`. Para los 3 hashtags de
   tema, aplicar la lógica de tamaño (niche/mid/broad) de la skill pública
   `ig-hashtag-strategist` sobre el tema de este post; los 2 fijos
   (`#ConstelacionesFamiliares` `#SanaciónFamiliar`) van siempre.
4. **Mostrar el borrador** en el chat: estructura usada, título, cuerpo
   completo, cierre, CTA, hashtags. Esperar aprobación o ajustes.
5. **Guardar el copy aprobado** como `.docx` en
   `Desktop/Posts Constelaciones/<título o hook>.docx`, con el título en
   negrita en el primer párrafo (mismo formato que los posts existentes).
   Usar `python-docx` (ya es una dependencia del proyecto).
6. **Generar la imagen de fondo**: correr
   `python scripts/generate_post_image.py "<ruta al .docx recién guardado>"`
   por la tool de Bash, desde la raíz del repo. No reimplementar ese flujo a
   mano ni pedir la API key — ya vive en `.env`.
7. **Mostrar el resultado**: leer el PNG generado (tool de Read) y mostrarlo,
   junto con la ruta final, y el recordatorio de que el título se agrega
   después a mano en Canva siguiendo la tipografía fija de
   `scripts/references/canva_title_style.md` (titular cartel amarillo/naranja
   centrado + cierre en script dorado pálido centrado, con la posición
   vertical del bloque ajustada a mano según el encuadre de esta foto para no
   tapar la cara) — sin ninguna firma ni atribución de marca, eliminada por
   completo.

## Reglas duras

- Nunca preguntar qué estructura usar antes de escribir — elegir (nombrada o
  rotada) y avisar cuál se usó al mostrar el resultado, para que el usuario
  pueda pedir otra si no le convence.
- Nunca pedir la API key de Gemini ni el comando de Python al usuario — la
  skill los maneja internamente.
- No generar la imagen antes de que el usuario apruebe el texto del copy.
- Las reglas de voz, cierre, CTA y hashtags viven únicamente en
  `constelaciones_brand_voice.md`; el estilo visual únicamente en
  `image_prompt_style.md`. Esta skill no las duplica ni las reinterpreta.
- El título en Canva sigue siempre la tipografía fija de
  `canva_title_style.md`; la posición vertical del bloque no es un valor
  fijo — se ajusta a mano según el encuadre de cada foto para no tapar la
  cara de la protagonista. Nunca se agrega firma de marca (nombre de autor,
  @handle) a ningún post.

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` — voz, cierre, CTA,
  hashtags, y las 5 estructuras de post.
- `../../scripts/references/image_prompt_style.md` — estilo visual de la foto
  de fondo (lo usa `generate_post_image.py`, no esta skill directamente).
- `../../scripts/references/canva_title_style.md` — tipografía y color del
  título para el paso manual en Canva, y la regla de que no se agrega firma.
- `../../scripts/generate_post_image.py` — genera la imagen de fondo.
- `testing/copy_gen_state.json` — estado de rotación de estructura
  (se autogenera).

## Related skills

- `carrusel-constelaciones` — para carruseles multi-slide.
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano.
- `ig-hashtag-strategist` (bundle público) — sizing de los 3 hashtags de tema.
