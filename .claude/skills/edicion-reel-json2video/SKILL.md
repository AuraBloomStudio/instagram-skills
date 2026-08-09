---
name: edicion-reel-json2video
description: Arma el video final de un reel de Constelaciones Familiares con la API de JSON2Video, a partir de los clips de B-roll y el orden_edicion.txt de seleccion-clips-pexels mas la narracion.mp3 de narracion-voz-gemini, ya guardados con el mismo slug del reel. Ordena las escenas segun orden_edicion.txt (un clip por momento, prefiriendo video sobre foto entre los 1-3 candidatos de cada uno), reparte la duracion total de la narracion entre los momentos en proporcion a las palabras de cada linea del guion, sube todo a JSON2Video (clips, narracion y musica de fondo opcional) porque la API solo acepta URLs publicas, genera subtitulos automaticos nativos en espanol via Whisper con la palabra activa resaltada en el dorado de marca, mezcla una pista de musica de fondo en volumen bajo si el usuario pasa un archivo (no hay musica de stock integrada en JSON2Video), renderiza en vertical 9:16 (instagram-story, 1080x1920) y descarga el resultado a scripts/output_reels/<slug>/reel_final.mp4. Usar para "arma el reel final de [tema]", "edita el video con los clips y la narracion", "renderiza el reel". Not for writing the script (write it first), not for selecting B-roll clips (use seleccion-clips-pexels), and not for generating the narration audio (use narracion-voz-gemini) -- this skill only assembles what those two already produced.
---

# Edicion del reel final (JSON2Video)

Toma los clips de B-roll ya elegidos por `seleccion-clips-pexels` y la
narracion ya generada por `narracion-voz-gemini` para el mismo reel, y arma
el video final vertical con subtitulos automaticos usando la API de
JSON2Video.

## Cuando se activa

- "arma el reel final de [tema]"
- "edita el video con los clips y la narracion"
- "renderiza el reel de [tema]"
- "junta los clips y el audio del reel de [tema] en un video"

No se activa para escribir el guion (eso se escribe antes, a mano), ni para
seleccionar los clips de B-roll (`seleccion-clips-pexels`), ni para generar
la narracion en voz (`narracion-voz-gemini`) -- esta skill solo ensambla lo
que esas dos ya dejaron guardado en disco.

## Que hace exactamente (leer antes de tocar nada)

JSON2Video **no acepta rutas locales** -- todo elemento de un `movie` JSON
(clip, audio, imagen) tiene que ser una URL publica. Por eso el script sube
cada archivo local a la libreria de medios de JSON2Video primero (usa el
mismo patron get-upload-url + PUT a S3 que ya usa `lib/publora_client.py`
para Publora, solo que contra la API de JSON2Video en vez de Publora) y
borra esos assets subidos al terminar, para no agotar el storage gratuito de
la cuenta (~50MB en el plan de prueba).

**JSON2Video tampoco tiene musica de stock integrada.** Si el usuario no
pasa un archivo de musica con `--music`, el reel se renderiza solo con
narracion y subtitulos -- nunca se bloquea el render por falta de musica.

**Subtitulos:** son nativos de JSON2Video (`type: "subtitles"`), transcriben
automaticamente el audio de la narracion con el modelo Whisper en espanol --
no hace falta pasar un guion de texto por separado. Estilo confirmado por
prueba real: `classic-progressive` (linea completa en blanco, palabra activa
resaltada), con la palabra activa en `#B8985E` (Dorado de marca, de
`BRAND_COLORS` en `image_prompt_style.md`).

**Seleccion de clip por momento:** `orden_edicion.txt` normalmente trae 2-3
candidatos por momento (`_a`, `_b`, `_c`). El script toma automaticamente el
primer candidato de video; si el momento no tiene ningun video (solo fotos),
usa la primera foto y le aplica un efecto Ken Burns (zoom + pan) para que no
quede estatica. No pide confirmacion antes de elegir -- si el usuario quiere
otro candidato especifico, se le puede pasar aparte (ver Flujo, paso 4).

**Sincronizacion de duracion:** la duracion total de `narracion.mp3` se
reparte entre los momentos en proporcion al numero de palabras de la linea
de guion de cada uno (aproxima bien el ritmo real de una narracion a
velocidad mas o menos constante), con un piso de ~1.2s por momento para que
ningun beat corto quede ilegible. Si el clip elegido es mas corto que el
tiempo que le toca, se loopea (`loop`) las veces necesarias y se corta
(`duration`) exacto; si es mas largo, simplemente se recorta.

**Carpetas de origen con slugs distintos:** se ha visto en la practica que
`seleccion-clips-pexels` y `narracion-voz-gemini` a veces guardan el mismo
reel con separador distinto (`crei_que_solo...` vs `crei-que-solo...`). El
script prueba el slug exacto y ambas variantes (guion/guion bajo) para cada
carpeta por separado antes de fallar.

## Flujo

1. **Recibir el slug o nombre del reel.** Si el usuario da el tema en vez de
   un slug exacto, usar el mismo criterio de slug que las otras skills de
   reel (derivarlo del tema/hook) y avisar cual se uso.

2. **Confirmar que existen las dos carpetas de origen** antes de llamar al
   script: `scripts/output_clips/<slug>/orden_edicion.txt` (de
   `seleccion-clips-pexels`) y `scripts/output_audio/<slug>/narracion.mp3`
   (de `narracion-voz-gemini`). Si falta alguna, avisar al usuario cual
   skill correr primero -- esta skill nunca genera clips ni narracion por su
   cuenta.

3. **Preguntar una sola vez por la musica de fondo** si el usuario no la
   menciono ya: "¿Tienes un archivo de musica instrumental para el fondo, o
   sigo sin musica?". Si no tiene, seguir sin musica (regla dura, ver
   arriba) -- no bloquear el render por esto.

4. **Ejecutar el script** por la tool de Bash, desde la raiz del repo:
   ```
   python scripts/render_reel_json2video.py <reel_slug> [--music "ruta/al/archivo.mp3"] [--quality high]
   ```
   El script:
   - Carga `JSON2VIDEO_API_KEY` de `.env` (si falta, la pide de forma
     interactiva y la guarda -- nunca pedir esta key al usuario desde la
     skill misma, mismo patron que `generate_post_image.py`).
   - Resuelve las carpetas de clips y audio (con el fallback de slug
     descrito arriba), parsea `orden_edicion.txt`, elige un clip por
     momento, calcula la duracion de cada uno con `ffprobe`.
   - Reparte la duracion total de la narracion entre los momentos por
     proporcion de palabras.
   - Imprime la cuota de render restante de la cuenta de JSON2Video antes de
     enviar el render, con un aviso si la narracion es mas larga que la
     cuota disponible.
   - Sube narracion, clips elegidos y musica (si hay) a JSON2Video, arma el
     `movie` JSON (una escena por momento, narracion + musica opcional +
     subtitulos nativos como elementos a nivel de pelicula, resolucion
     `instagram-story` = 1080x1920), lo envia y hace poll cada ~7s hasta que
     termina.
   - Descarga el resultado final a
     `scripts/output_reels/<reel_slug>/reel_final.mp4`.
   - Borra los assets subidos a JSON2Video (narracion, clips, musica) al
     terminar, exito o error, para no agotar el storage gratuito de la
     cuenta.

5. **Mostrar el resultado**: ruta final del archivo, duracion y resolucion
   del render, creditos consumidos, y la lista de momentos que
   `orden_edicion.txt` ya traia marcados con advertencia (`⚠ protagonista
   distinta`, `ℹ imagen de apoyo`, etc.) para que el usuario los revise
   visualmente en el video terminado -- esas advertencias vienen heredadas
   de la seleccion de clips, esta skill no las resuelve, solo las hace
   visibles de nuevo en el resumen final.

## Reglas duras

- Nunca inventar ni regenerar clips o narracion -- si falta alguno de los
  dos archivos de origen, decirle al usuario que corra
  `seleccion-clips-pexels` o `narracion-voz-gemini` primero.
- Nunca pedir la API key de JSON2Video al usuario directamente -- el script
  la maneja con el mismo patron que `generate_post_image.py`.
- Nunca renderizar sin subtitulos -- son parte fija del formato de reel de
  la marca, no un opcional que se pregunta cada vez.
- Musica de fondo es siempre opcional (ver seccion de arriba) -- no bloquear
  el render por falta de un archivo de musica.
- El archivo final siempre es `.mp4` en
  `scripts/output_reels/<reel_slug>/reel_final.mp4` -- no cambiar el nombre
  ni la extension sin que el usuario lo pida explicitamente.
- Siempre mostrar al usuario las advertencias heredadas de
  `orden_edicion.txt` en el resumen final -- nunca ocultarlas solo porque el
  render en si haya salido bien.

## Recursos

- `../../scripts/render_reel_json2video.py` -- resuelve carpetas de origen,
  parsea `orden_edicion.txt`, calcula duraciones, sube assets a JSON2Video,
  arma y envia el `movie` JSON, hace poll del render, descarga el resultado
  y limpia los assets subidos. Acepta `--music`, `--quality`
  (`low`/`medium`/`high`, default `high` -- la calidad no cambia el costo en
  creditos, solo la fidelidad visual), `--clips-dir`, `--audio-dir` y
  `--out-dir` para override.
- `scripts/output_clips/` -- clips de B-roll + `orden_edicion.txt` por reel
  (gitignored, de `seleccion-clips-pexels`).
- `scripts/output_audio/` -- narracion por reel (gitignored, de
  `narracion-voz-gemini`).
- `scripts/output_reels/` -- reels finales renderizados (gitignored, son
  binarios, no se suben al repo).
- `../../scripts/references/image_prompt_style.md` -- `BRAND_COLORS`, de
  donde sale el Dorado (#B8985E) usado como color de palabra activa en los
  subtitulos.

## Related skills

- `seleccion-clips-pexels` -- elige el B-roll y escribe `orden_edicion.txt`
  que esta skill consume. Correr primero.
- `narracion-voz-gemini` -- genera `narracion.mp3` que esta skill consume.
  Correr primero.
- `imagen-post-constelaciones` / `post-constelaciones` / `carrusel-
  constelaciones` / `historias-constelaciones` -- contenido estatico (foto o
  copy), no reels.
