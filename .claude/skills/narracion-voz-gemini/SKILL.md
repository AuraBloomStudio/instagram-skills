---
name: narracion-voz-gemini
description: Given the full voice-over script (guion) of a Constelaciones Familiares reel, generate its narration audio with Gemini TTS, always using the fixed brand voice "Sulafat" (warm, mid tone) at a brisk, natural conversational pace -- never asks which voice or pacing to use, both are locked-in brand decisions. Splits scripts longer than ~500 words into ~350-word sentence-boundary chunks before generating (Gemini TTS quality degrades on long single calls), generates each chunk, then joins them with ffmpeg into one final MP3. Saves to scripts/output_audio/<reel_slug>/narracion.mp3. Use for "genera la narracion en voz para el reel de [tema]", "necesito el audio de este guion", "convierte este guion a voz". Not for writing the reel script itself (write it first, then paste it here), not for B-roll/video clips (use seleccion-clips-pexels), and not for still cover photos or feed copy (use imagen-post-constelaciones, post-constelaciones, carrusel-constelaciones, historias-constelaciones).
---

# Narracion en voz (Gemini TTS)

Toma el guion completo ya escrito de un reel de Constelaciones Familiares y
genera el audio de narracion con la voz oficial de marca, dividiendo el
guion en fragmentos si hace falta para evitar la degradacion de calidad de
Gemini en audios largos, y uniendo todo en un solo archivo final.

## Cuando se activa

- "genera la narracion en voz para el reel de [tema]"
- "necesito el audio de este guion"
- "convierte este guion a voz"
- "dame la narracion de este reel: [guion pegado]"

No se activa para escribir el guion en si (eso se escribe antes, a mano o en
otra conversacion), ni para seleccionar clips/B-roll (`seleccion-clips-
pexels`), ni para fotos de portada o copy de feed/carrusel/historia
(`imagen-post-constelaciones`, `post-constelaciones`, `carrusel-
constelaciones`, `historias-constelaciones`).

## Voz de marca (regla dura, no preguntar)

La voz oficial es **"Sulafat"** (calida, tono medio, la voz Gemini TTS que
mejor calza con el tono cercano/reflexivo de la marca) -- **siempre**, en
todas las narraciones. No preguntar al usuario que voz usar ni ofrecer
alternativas; esta decision ya esta tomada y vive hard-codeada en
`scripts/generate_reel_narration.py` (`BRAND_VOICE`). Si algun dia se quiere
cambiar la voz de marca, se edita esa constante, no se decide por
conversacion.

## Ritmo de narracion (regla dura, no preguntar)

El ritmo aprobado y definitivo es **calido pero agil, el de una
conversacion cercana normal** -- ni acelerado ni arrastrado, sin la cadencia
lenta y solemne de una meditacion guiada. Esta es la version final,
validada de oido por el usuario contra el audio real (reel
"crei-que-solo-tenia-mal-caracter", 189 palabras): una primera version que
pedia explicitamente "pausado" salio demasiado lenta (189 palabras en
90.8s, ~125 palabras/min); una segunda version mas neutra ("ritmo natural de
conversacion normal") seguia sintiendose lenta (71.4s, ~159 palabras/min);
la version actual, que pide un ritmo "vivo y agil, un poco mas rapido que
una conversacion pausada", quedo aprobada (66.73s medido con `ffprobe` sobre
el `narracion.mp3` real, ~170 palabras/min). **No preguntar al usuario por
el ritmo en futuras narraciones** -- esta decision ya esta tomada y vive
hard-codeada en `scripts/generate_reel_narration.py` (`STYLE_INSTRUCTION`).
Si algun dia se quiere volver a ajustar el ritmo, se edita esa constante, no
se decide por conversacion.

Este mismo ritmo (170 palabras/min) es la base del rango de longitud del
guion -- ver `REEL_SCRIPT_LENGTH` en
`../../scripts/references/constelaciones_brand_voice.md` (108-136 palabras,
para que el video completo quede en 40-50s) -- y del chequeo del paso 2
del Flujo, abajo.

## Flujo

1. **Recibir el guion.** El usuario pega el texto narrado completo del reel
   en el chat. Si no da un nombre para el reel, derivar un slug corto del
   tema/hook del guion (mismo criterio que `seleccion-clips-pexels`) y
   avisar cual se uso -- no preguntar antes de trabajar.

2. **Chequear la duracion ANTES de guardar o generar nada.** Contar las
   palabras del guion pegado y calcular los segundos estimados de narracion
   a razon de 170 palabras/min (2.833 palabras/seg -- ver "Ritmo de
   narracion" arriba y `REEL_SCRIPT_LENGTH` en
   `constelaciones_brand_voice.md`). El objetivo es que el video final
   (narracion + los 2s fijos del gancho, se use gancho o no en este reel en
   particular) quede en 40-50s -- eso equivale a **108-136 palabras**.
   Avisar siempre, sea cual sea el resultado:
   - Cuantas palabras tiene el guion.
   - Cuantos segundos estimados de narracion da (`palabras / 2.833`).
   - Si cae dentro de 108-136 palabras (en rango) o fuera (por arriba o por
     abajo).
   - Si esta fuera de rango, decir aproximadamente cuantas palabras hay que
     agregar o cortar para volver a entrar (`palabras_actuales - 136` si se
     paso, `108 - palabras_actuales` si le falta).
   Este chequeo es informativo, no bloqueante -- avisar y seguir el flujo
   igual si el usuario decide continuar con el guion tal cual esta.

3. **Guardar el guion** tal cual, sin reescribirlo ni resumirlo, en
   `testing/reel_scripts/<reel_slug>.txt` (crear la carpeta si no existe).
   Esta skill nunca corrige ni reescribe el texto del guion -- solo lo narra.

4. **Ejecutar el script** por la tool de Bash, desde la raiz del repo:
   ```
   python scripts/generate_reel_narration.py "testing/reel_scripts/<reel_slug>.txt" <reel_slug>
   ```
   El script:
   - Carga `GEMINI_API_KEY` de `.env` (si falta, la pide de forma
     interactiva y la guarda -- nunca pedir esta key al usuario desde la
     skill misma; mismo patron que `generate_post_image.py`).
   - Cuenta las palabras del guion. Si supera ~500 palabras (~3 min a un
     ritmo conversacional de 150-160 palabras/min), lo divide en fragmentos
     de ~350 palabras cada uno, cortando siempre en limite de oracion (nunca
     a mitad de una frase).
   - Genera el audio de cada fragmento con `gemini-2.5-flash-preview-tts` y
     la voz `Sulafat`, anteponiendo la instruccion de estilo fija (tono
     calido, ritmo agil de conversacion normal -- ver "Ritmo de narracion"
     arriba) -- la unica forma de controlar ritmo en Gemini TTS es via
     instruccion en lenguaje natural, no hay SSML.
   - Envuelve cada respuesta PCM en un `.wav` y **recorta el silencio final
     anomalo** de cada fragmento -- Gemini TTS puede devolver un colchon de
     silencio de varios minutos despues de terminar de narrar (visto en
     pruebas reales: 189 palabras narradas en ~103s dentro de un buffer de
     4:28). El recorte solo dispara cuando detecta un tramo de silencio de al
     menos 2.5s que llega hasta el final real del archivo (asi nunca confunde
     una pausa natural entre frases, siempre mas corta, con el colchon de la
     API), y aun asi deja 0.6s de margen despues del ultimo sonido detectado
     antes de cortar -- una version anterior cortaba justo en el borde
     detectado y se comio la ultima palabra del guion cuando esta terminaba
     en voz baja. Si aun con el margen el recorte quitaria mas del 85% del
     audio, se descarta el recorte y se conserva el fragmento original
     completo.
   - Une todos los fragmentos ya recortados con `ffmpeg` (con un breve
     silencio fijo entre cada uno para que el corte no suene abrupto) y
     codifica el resultado final directo a MP3.
   - Guarda el resultado en
     `scripts/output_audio/<reel_slug>/narracion.mp3` y limpia los
     archivos temporales de fragmentos.

5. **Confirmar al usuario**: ruta final del archivo, cuantos fragmentos se
   generaron (si el guion era largo), y recordar que el audio queda listo
   para importarse directo en el editor de video junto con los clips de
   `seleccion-clips-pexels`.

## Reglas duras

- Voz **siempre** "Sulafat" -- ver seccion de arriba. Nunca preguntar.
- Ritmo **siempre** calido y agil, de conversacion normal -- ver seccion
  "Ritmo de narracion" arriba. Version final aprobada, nunca preguntar por
  ritmo.
- **Nunca reescribir ni resumir el guion.** Esta skill solo convierte a voz
  el texto que el usuario ya trae escrito, palabra por palabra.
- **Nunca generar un audio largo en una sola llamada** cuando el guion
  supera el umbral de ~500 palabras -- siempre fragmentar primero. Es la
  mitigacion conocida a la degradacion de calidad de Gemini TTS en textos
  largos.
- Fragmentar siempre en limite de oracion, nunca a mitad de frase --
  cortar a mitad de una idea suena antinatural incluso despues de unir los
  audios.
- Nunca pedir la API key de Gemini al usuario directamente -- el script la
  maneja con el mismo patron que `generate_post_image.py`.
- El archivo final siempre es `.mp3` en
  `scripts/output_audio/<reel_slug>/narracion.mp3` -- no cambiar el nombre
  ni la extension sin que el usuario lo pida explicitamente.
- **El chequeo de duracion (paso 2 del Flujo) corre siempre, para todo
  guion recibido, nunca en silencio y nunca salteado** -- avisar palabras,
  segundos estimados, y si esta dentro o fuera de 108-136 palabras, antes de
  guardar el guion o generar audio. No bloquea el flujo si el usuario decide
  seguir igual, pero el aviso en si no es opcional.

## Recursos

- `../../scripts/generate_reel_narration.py` -- fragmenta el guion, llama a
  Gemini TTS por fragmento, une con `ffmpeg` y codifica el MP3 final.
  Acepta `--out-dir` para cambiar la carpeta base de salida.
- `../../scripts/references/constelaciones_brand_voice.md` -- voz de marca
  ("tu", tono calido/reflexivo) que informa la instruccion de estilo enviada
  a Gemini TTS, y `REEL_SCRIPT_LENGTH` -- el rango objetivo de 108-136
  palabras y el calculo detras (base del chequeo del paso 2 del Flujo).
- `testing/reel_scripts/` -- guiones pegados por el usuario, uno por reel
  (gitignored).
- `scripts/output_audio/` -- audios de narracion generados, uno por reel
  (gitignored, son binarios, no se suben al repo).

## Related skills

- `seleccion-clips-pexels` -- selecciona el B-roll de video del mismo
  guion; se usa junto con esta skill para armar el reel completo.
- `imagen-post-constelaciones` / `post-constelaciones` / `carrusel-
  constelaciones` / `historias-constelaciones` -- contenido estatico (foto o
  copy), no narracion de reel.
