---
name: historias-constelaciones
description: Draft Instagram/Facebook Stories content for Constelaciones Familiares in one of 5 structures (frase destacada, pregunta interactiva, mini-consejo práctico, recordatorio con CTA, detrás de cámaras/voz personal), short-form copy (a few seconds of reading) following the tú voice from scripts/references/constelaciones_brand_voice.md but WITHOUT the "Para asentar" closer or hashtags -- Stories don't use either. On approval, saves the copy as .docx in Desktop/Posts Constelaciones/Historias and generates its 9:16 vertical background photo by running scripts/generate_post_image.py --aspect 9:16, saved to Desktop/Imagenes Posts/Historias. Use for "hazme una historia de [tema]", "necesito una story sobre [tema]". Not for feed posts (use post-constelaciones) or carousels (use carrusel-constelaciones).
---

# Historias Constelaciones (Stories 9:16)

Redacta contenido de Instagram/Facebook Stories para Constelaciones
Familiares: elige estructura, escribe el texto breve, lo aprueba el usuario,
lo guarda como `.docx`, y genera su foto de fondo vertical 9:16 reutilizando
`scripts/generate_post_image.py --aspect 9:16`.

## Cuándo se activa

- "hazme una historia de [tema]"
- "necesito una story sobre [tema]"
- "arma una historia de Constelaciones sobre [tema]"

No se activa para posts de feed (`post-constelaciones`) ni carruseles
(`carrusel-constelaciones`).

## Flujo

1. **Tema.** Tomar el tema/ángulo del pedido.
2. **Elegir estructura.**
   - Si el usuario nombra una de las 5 (ver `STORY_STRUCTURES` en
     `../../scripts/references/constelaciones_brand_voice.md`), usar esa y no
     tocar la rotación.
   - Si no la nombra, elegirla automáticamente evitando repetir cualquiera de
     las últimas 2 usadas: leer `testing/copy_gen_state.json` (crear con `{}`
     si no existe), clave `"story_structure"`, mismo mecanismo de rotación
     que las otras dos skills de copy.
   - **Nunca preguntar cuál usar antes de redactar** — elegir y avisar cuál se
     usó junto con el borrador.
3. **Redactar el texto**: breve (3-4 líneas máximo, se lee en segundos), tono
   "tú" de `constelaciones_brand_voice.md`, **sin** "Para asentar", sin el CTA
   fijo del libro, y **sin hashtags** — nada de eso aplica a Stories. Seguir
   la forma específica de la estructura elegida (frase destacada, pregunta
   interactiva, mini-consejo, recordatorio con CTA libre, o detrás de
   cámaras) según `STORY_STRUCTURES`.
4. **Mostrar el borrador** para aprobación (estructura usada + texto).
5. **Guardar el copy aprobado** como `.docx` en
   `Desktop/Posts Constelaciones/Historias/<resumen o hook>.docx`.
6. **Generar la imagen**: correr
   `python scripts/generate_post_image.py "<ruta>" --aspect 9:16 --out-dir "Desktop/Imagenes Posts/Historias"`
   por la tool de Bash, desde la raíz del repo. Reutiliza tal cual la misma
   rotación de composición/ubicación/ángulo y el mismo estilo visual
   (personas reales, escenas cotidianas, sin objetos literales) que las otras
   dos skills — solo cambia el formato de salida.
7. **Mostrar el resultado**: la imagen 9:16 generada (tool de Read) + la ruta
   final.

## Reglas duras

- Nunca preguntar qué estructura usar antes de escribir — elegir (nombrada o
  rotada) y avisar cuál se usó al mostrar el resultado.
- Nunca incluir "Para asentar", el CTA fijo del libro, ni hashtags.
- No generar la imagen antes de que el usuario apruebe el texto.
- Nunca pedir la API key de Gemini ni el comando de Python al usuario.

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` — voz y las 5
  estructuras de historia (bloque `STORY_STRUCTURES`).
- `../../scripts/references/image_prompt_style.md` — estilo visual de la foto
  de fondo (lo usa `generate_post_image.py`, no esta skill directamente).
- `../../scripts/generate_post_image.py` — genera la imagen, con `--aspect 9:16`.
- `testing/copy_gen_state.json` — rotación de estructura (clave
  `"story_structure"`).

## Related skills

- `post-constelaciones` — posts de feed, una imagen 4:5.
- `carrusel-constelaciones` — carruseles multi-slide 4:5.
- `imagen-post-constelaciones` — solo la imagen, cuando el copy ya está
  escrito a mano.
