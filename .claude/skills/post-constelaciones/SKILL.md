---
name: post-constelaciones
description: Draft a single-image organic Instagram/Facebook post for Constelaciones Familiares in one of 5 structures (carta directa, contraste cree-que/en-realidad, pregunta sin resolver, confesión personal, dato-manifiesto), following the brand voice documented in scripts/references/constelaciones_brand_voice.md (tú address, "Para asentar" closer, plain-URL CTA, 2 fixed + 3 topic hashtags via ig-hashtag-strategist). On approval, saves the copy as .docx in Desktop/Posts Constelaciones, generates its background photo by running scripts/generate_post_image.py with ONLY título+subtítulo baked directly onto the image (never the CTA, which would clutter a single-image post -- the full CTA stays in the caption text only; saved to Desktop/Imagenes Posts), then builds one consolidated "PAQUETE - <hook>.docx" (image + copy + a new first-comment CTA + hashtags + a publish checklist, per PACKAGING_STANDARD) via scripts/build_paquete_docx.py, saved to Desktop/Constelaciones - Publicaciones/<fecha> <micronicho>/. Use for "hazme un post de [tema]", "necesito un post sobre [tema]". Not for carousels (use carrusel-constelaciones), not for paid ads (future ads-constelaciones), and not for generating only the image of a copy already written by hand (use imagen-post-constelaciones).
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
6. **Generar la imagen de fondo con el texto ya quemado**: solo título y
   subtítulo, **nunca CTA** (regla dura, distinta del carrusel -- ver
   "Paquete 1" en `constelaciones_brand_voice.md`). Correr
   ```
   python scripts/generate_post_image.py "<ruta al .docx recién guardado>" --headline-main "<título>" --headline-accent "<línea de "Para asentar", si la estructura tiene una>"
   ```
   por la tool de Bash, desde la raíz del repo -- ver `BAKED_TYPOGRAPHY` en
   `canva_title_style.md` para el mapeo exacto y los colores. Omitir
   `--headline-accent` si la estructura elegida no tiene una línea de "Para
   asentar" o reencuadre corto equivalente. Nunca pasar `--body-text` para
   esta skill -- el CTA completo (libro + link) vive únicamente en el copy/
   caption de texto, nunca quemado en la imagen. No reimplementar ese flujo
   a mano ni pedir la API key — ya vive en `.env`.
7. **Revisión visual obligatoria antes de mostrar el resultado**: leer el PNG
   generado (tool de Read) y chequear que el título/subtítulo no tapen la
   cara de la protagonista (el script ya corre el veto automático de OpenCV,
   pero la revisión manual es el respaldo real) y que ninguna cabeza/rostro
   quede cortado de forma abrupta por el borde del encuadre -- ver la regla
   `EDGE_CROP` en `constelaciones_brand_voice.md`; el script imprime un aviso
   de "posible cabeza cortada" cuando lo detecta, pero un chequeo que confía
   solo en ese aviso NO alcanza -- un incidente real (2026-08-13) mostró que
   el aviso automático no detecta un mentón/mandíbula sin ojos visibles.
   **Recortar/hacer zoom sobre cada borde del encuadre** (no solo mirar la
   imagen completa una vez) antes de aprobar, con atención extra cuando el
   texto horneado quede cerca de un borde (puede camuflar visualmente una
   franja delgada de piel, como pasó en ese incidente). Si falla cualquiera
   de los dos chequeos, regenerar antes de mostrarlo. Mostrar el resultado
   final junto con la ruta.
8. **Armar el paquete consolidado** (ver `PACKAGING_STANDARD` en
   `constelaciones_brand_voice.md` para el detalle completo, incluida la
   carpeta de salida). Determinar el libro correcto para el primer
   comentario aplicando la tabla tema -> libro de `FACEBOOK_POST_STRUCTURE`
   (Dolor, Dinero, Mamá, Papá, Regreso, mismo fallback a *El dolor que no te
   pertenece*) al tema de este post -- puede ser un libro distinto del que
   ya nombra el CTA principal del copy, que sigue siendo siempre *El dolor
   que no te pertenece* por la regla existente de este formato. Redactar un
   texto de primer comentario corto (2-3 líneas) con ese libro, en una
   redacción distinta a la del CTA que ya va dentro del copy. Determinar el
   slug del micronicho: si este post es parte de un paquete diario junto con
   otras piezas del mismo tema (carrusel/virales/historia pedidos en la
   misma conversación), reusar el MISMO slug ya usado para esas piezas
   hermanas -- nunca derivar uno distinto solo porque el hook de este post
   es distinto. Si es una pieza suelta, derivar un slug corto del tema
   (mismo criterio kebab-case que ya usan `carrusel-constelaciones`/
   `seleccion-clips-pexels`). Luego correr:
   ```
   python scripts/build_paquete_docx.py "<título o hook>" --copy-docx "<ruta al .docx del paso 5>" --image "<ruta al PNG del paso 6>" --primer-comentario "<texto del primer comentario>" --tipo-pieza imagen-texto --micronicho "<slug>"
   ```
   Esto genera
   `Desktop/Constelaciones - Publicaciones/<fecha de hoy> <slug>/Paquete 1 -
   Imagen y Texto Largo/PAQUETE - <título o hook>.docx` -- no reemplaza el
   `.docx` del paso 5 ni el PNG del paso 6 (esos siguen guardándose donde
   siempre, en `Desktop/Posts Constelaciones/` y `Desktop/Imagenes Posts/`),
   los complementa. Mostrar
   la ruta final al usuario junto con el resto del resultado.

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
- El título/subtítulo se hornean siempre con `generate_post_image.py` (ver
  `BAKED_TYPOGRAPHY` en `canva_title_style.md`) — ya no es un paso manual en
  Canva para esta skill. **La imagen NUNCA lleva el CTA horneado** (ni la
  mención al libro ni "el link está en la descripción") — regla dura,
  distinta del carrusel, donde el CTA sí va horneado en su propia slide
  dedicada; en un post de una sola imagen, el CTA satura y compite con el
  título. El CTA completo sigue existiendo, pero solo en el copy/caption de
  texto. Nunca se agrega firma de marca (nombre de autor, @handle) a ningún
  post.
- Ninguna imagen se muestra al usuario sin pasar por la revisión visual del
  paso 7 (cara no tapada + sin cabeza/rostro cortado por el borde, regla
  `EDGE_CROP`) — el aviso automático de `generate_post_image.py` es solo un
  apoyo, nunca sustituye mirar la imagen.
- El paquete consolidado (paso 8) es siempre el último paso, nunca antes de
  que exista el `.docx` del copy y el PNG de la imagen. El texto del primer
  comentario es nuevo (nunca copiar el CTA del copy tal cual) y su libro se
  decide con la tabla tema -> libro, no siempre el mismo de la copy
  principal — ver `PACKAGING_STANDARD` en `constelaciones_brand_voice.md`.

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` — voz, cierre, CTA,
  hashtags, las 5 estructuras de post, y `PACKAGING_STANDARD` (el paquete
  consolidado del paso 8).
- `../../scripts/references/image_prompt_style.md` — estilo visual de la foto
  de fondo (lo usa `generate_post_image.py`, no esta skill directamente).
- `../../scripts/references/canva_title_style.md` — sección
  `BAKED_TYPOGRAPHY`: mapeo exacto título/subtítulo/CTA y colores para esta
  skill (ya no manual), y la regla de que no se agrega firma.
- `../../scripts/generate_post_image.py` — genera la imagen de fondo y
  hornea el título/subtítulo/CTA.
- `../../scripts/build_paquete_docx.py` — arma el paquete consolidado del
  paso 8.
- `testing/copy_gen_state.json` — estado de rotación de estructura
  (se autogenera).

## Related skills

- `carrusel-constelaciones` — para carruseles multi-slide.
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano.
- `post-viral-constelaciones` — para los formatos virales de solo texto
  ("USTED DEBERÍA SABER QUE:" / "GUARDA ESTE DECRETO EN TU CORAZÓN"), no
  para el post ensayo largo que cubre esta skill.
- `ig-hashtag-strategist` (bundle público) — sizing de los 3 hashtags de tema.
