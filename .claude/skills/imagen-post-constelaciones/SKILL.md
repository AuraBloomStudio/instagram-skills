---
name: imagen-post-constelaciones
description: Generate the cover/background photo for an approved Constelaciones Familiares Instagram/Facebook post copy (.docx or .txt file from "Posts Constelaciones"). Reads the copy, has Gemini analyze its central emotion and theme, builds an image prompt following the house visual style in scripts/references/image_prompt_style.md (warm cinematic color, real people in everyday domestic scenes, no literal metaphor objects, rotated composition/setting/camera-angle so consecutive posts don't repeat the same framing, 4:5 vertical), generates the image via Gemini Flash Image with ONLY título+subtítulo baked directly onto it (never the CTA, which stays in the caption text only), and saves it to Desktop/Imagenes Posts using the same filename as the copy, then builds one consolidated "PAQUETE - <nombre>.docx" (that image + the existing copy + a new first-comment CTA + its hashtags if any + a publish checklist, per PACKAGING_STANDARD) via scripts/build_paquete_docx.py. Runs scripts/generate_post_image.py internally via Bash -- never asks the user to type the python command or paste the API key. Use when asked to generate/make the cover image, background photo, or "foto de portada" for a post or copy file. Not for writing the caption itself. No brand signature/attribution is ever added to any post.
---

# Imagen de Portada — Constelaciones Familiares

Genera la fotografía de fondo para un post ya aprobado de Constelaciones
Familiares, ejecutando internamente `scripts/generate_post_image.py`. El
usuario nunca necesita escribir el comando de Python ni pegar su API key en
el chat.

## Cuándo se activa

- "genera la imagen de este post"
- "hazme la imagen para [archivo]"
- "necesito la foto de portada para [tema/archivo]"
- "genera el fondo para [nombre del copy]"
- Cualquier variante que pida la imagen/foto/portada de un copy ya escrito.

No se activa para escribir o editar el copy en sí. Nunca se agrega firma de
marca (nombre de autor, @handle) a ningún post -- se eliminó por completo.

## Flujo

1. **Resolver el archivo.** Si el usuario da un nombre exacto o parcial,
   buscarlo en `Desktop/Posts Constelaciones/` (glob por coincidencia parcial
   si no es exacto). Si hay más de una coincidencia o ninguna, listar
   opciones y preguntar antes de continuar. Si el usuario ya da una ruta
   completa, usarla tal cual.
2. **Leer el copy y derivar título/subtítulo para quemar en la imagen**
   (ver `BAKED_TYPOGRAPHY` en `../../scripts/references/canva_title_style.md`):
   título = el primer párrafo en negrita del `.docx`; subtítulo = la línea de
   "Para asentar", si la tiene esa estructura (omitir si no). **Nunca CTA en
   la imagen** -- regla dura, distinta del carrusel (ver "Paquete 1" en
   `constelaciones_brand_voice.md`); el CTA completo del copy se queda
   únicamente en el caption de texto.
3. **Ejecutar el script.** Desde la raíz del repo:
   ```
   python scripts/generate_post_image.py "<ruta al .docx o .txt>" --headline-main "<título>" --headline-accent "<línea de Para asentar, si existe>"
   ```
   vía la tool de Bash -- nunca pasar `--body-text` para esta skill. No
   reimplementar el flujo a mano: el script ya hace lectura del copy,
   análisis de emoción con Gemini, construcción del prompt con rotación de
   composición/ubicación/ángulo de cámara, generación de imagen, horneado
   del texto, y guardado en 4:5 (1080x1350).
4. **API key.** `GEMINI_API_KEY` ya vive en `.env` (gitignored). No pedirla
   en el chat. Si el script la pide de forma interactiva (falta en `.env`),
   avisar al usuario que debe correrla él mismo en su terminal o agregarla a
   `.env` directamente — nunca solicitarla ni pegarla en la conversación.
5. **Revisión visual obligatoria, luego mostrar el resultado.** Leer el PNG
   generado con la tool de Read y chequear que el título/subtítulo no tapen
   la cara de la protagonista y que ninguna cabeza/rostro quede cortado de
   forma abrupta por el borde del encuadre (regla `EDGE_CROP` en
   `constelaciones_brand_voice.md`). El aviso automático del script es solo
   un apoyo y tiene un punto ciego confirmado (un incidente real, 2026-08-13,
   mostró que no detecta un mentón/mandíbula sin ojos visibles) --
   **recortar/hacer zoom sobre cada borde del encuadre**, no solo mirar la
   imagen completa una vez, con atención extra si el texto horneado queda
   cerca de un borde. Si falla, regenerar antes de mostrarlo. Mostrarlo
   inline junto con la ruta final en `Desktop/Imagenes Posts/`.
6. **Reintentos transitorios.** El script ya reintenta automáticamente
   errores 503/429/timeout de Gemini; si aun así falla, mostrar el error tal
   cual lo imprime el script (suele traer la causa: cuota, modelo no
   disponible, etc.) en vez de reinterpretarlo.
7. **Armar el paquete consolidado** (ver `PACKAGING_STANDARD` en
   `constelaciones_brand_voice.md` para el detalle completo, incluida la
   carpeta de salida). Leer el texto del copy ya aprobado (el mismo archivo
   del paso 1) para identificar su tema y aplicar la tabla tema -> libro de
   `FACEBOOK_POST_STRUCTURE` (Dolor, Dinero, Mamá, Papá, Regreso, mismo
   fallback a *El dolor que no te pertenece*) -- puede ser un libro distinto
   del que ya nombra el CTA dentro del copy. Redactar un texto de primer
   comentario corto (2-3 líneas) con ese libro, en una redacción distinta a
   la del CTA que ya trae el copy. Determinar el slug del micronicho: si
   esta imagen es parte de un paquete diario junto con otras piezas del
   mismo tema, reusar el MISMO slug ya usado para esas piezas hermanas; si
   es una pieza suelta, derivar un slug corto del tema del copy (mismo
   criterio kebab-case que ya usan `carrusel-constelaciones`/
   `seleccion-clips-pexels`). Luego correr:
   ```
   python scripts/build_paquete_docx.py "<nombre del archivo sin extensión>" --copy-docx "<ruta al copy del paso 1>" --image "<ruta al PNG del paso 3>" --primer-comentario "<texto del primer comentario>" --tipo-pieza imagen-texto --micronicho "<slug>"
   ```
   Esto genera
   `Desktop/Constelaciones - Publicaciones/<fecha de hoy> <slug>/Paquete 1 -
   Imagen y Texto Largo/PAQUETE - <nombre>.docx` -- no reemplaza ni el copy
   original ni el PNG generado (esos siguen guardándose donde siempre), los
   complementa. Mostrar la ruta final al usuario junto con el resto del
   resultado.

## Reglas duras

- Nunca pedirle al usuario que escriba o copie el comando de Python — la
  skill lo corre internamente.
- Nunca pedir la API key de Gemini en el chat, ni mostrarla si aparece en
  algún output.
- El estilo visual (personas reales, escenas cotidianas, sin objetos
  metafóricos literales, rotación de composición/ubicación/ángulo, sin
  texto, 4:5) vive únicamente en `scripts/references/image_prompt_style.md`.
  Esta skill no lo duplica ni lo reinterpreta — si el usuario pide un cambio
  de estilo, edita ese archivo de referencia, no esta skill.
- Un solo archivo de copy por invocación salvo que el usuario pida
  explícitamente correr varios en lote.
- El título/subtítulo se hornean siempre con `generate_post_image.py` (ver
  `BAKED_TYPOGRAPHY` en `scripts/references/canva_title_style.md`) — ya no
  es un paso manual en Canva. **La imagen NUNCA lleva el CTA horneado** —
  regla dura, distinta del carrusel; el CTA completo se queda solo en el
  copy/caption de texto. Nunca se agrega firma de marca (nombre de autor,
  @handle) a ninguna imagen.
- Ninguna imagen se muestra al usuario sin pasar por la revisión visual del
  paso 5 (cara no tapada + sin cabeza/rostro cortado por el borde, regla
  `EDGE_CROP` en `constelaciones_brand_voice.md`) — el aviso automático del
  script es solo un apoyo, nunca sustituye mirar la imagen.
- El paquete consolidado (paso 7) es siempre el último paso, nunca antes de
  que exista el PNG generado. El texto del primer comentario es nuevo
  (nunca copiar el CTA del copy tal cual) y su libro se decide con la tabla
  tema -> libro aplicada al contenido real del copy leído, no un libro fijo
  — ver `PACKAGING_STANDARD` en `constelaciones_brand_voice.md`.

## Recursos

- `scripts/generate_post_image.py` — el script que genera la imagen y
  hornea el título/subtítulo/CTA.
- `scripts/build_paquete_docx.py` — arma el paquete consolidado del paso 7.
- `scripts/references/image_prompt_style.md` — reglas de estilo visual,
  editable sin tocar código.
- `scripts/references/canva_title_style.md` — sección `BAKED_TYPOGRAPHY`:
  mapeo exacto título/subtítulo/CTA y colores, y la regla de que no se
  agrega firma.
- `scripts/references/constelaciones_brand_voice.md` — `FACEBOOK_POST_STRUCTURE`
  (tabla tema -> libro) y `PACKAGING_STANDARD` (el paquete consolidado del
  paso 6).
- `testing/image_gen_state.json` — estado de rotación (se autogenera, no
  tocar a mano salvo para resetear la rotación).
