---
name: edicion-reel-json2video
description: Arma el video final de un reel de Constelaciones Familiares con la API de JSON2Video, a partir de los clips de B-roll y el orden_edicion.txt de seleccion-clips-pexels mas la narracion.mp3 de narracion-voz-gemini, ya guardados con el mismo slug del reel. Ordena las escenas segun orden_edicion.txt (un clip por momento, prefiriendo video sobre foto entre los 1-3 candidatos de cada uno), reparte la duracion total de la narracion entre los momentos en proporcion a las palabras de cada linea del guion, sube todo a JSON2Video (clips, narracion y musica de fondo opcional) porque la API solo acepta URLs publicas, genera subtitulos automaticos nativos en espanol via Whisper en Poppins, posicionados en la zona media-baja del encuadre (no pegados al fondo), en un solo color cian vivo (sin contraste entre la palabra activa y el resto de la linea), con un degradado oscuro fuerte que cubre todo el cuadro de arriba a abajo (confirmado visible incluso en el frame mas claro del video), agrega una transicion de fundido cruzado de 0.4s entre cada momento (incluido el gancho, si lo hay) en vez de cortes secos, opcionalmente arma un gancho inicial de 2s antes de que empiece la narracion (titular grande a dos fuentes -- Poppins bold amarillo/naranja de marca + Playfair Display italic dorado palido, mismos colores que los titulos de los posts estaticos -- como dos elementos `text` nativos de JSON2Video, no un elemento `html`, sobre su propio clip de fondo si seleccion-clips-pexels genero uno dedicado para el texto del gancho, o reciclando el clip de momento 1 si no), mezcla una pista de musica de fondo en volumen bajo si el usuario pasa un archivo (no hay musica de stock integrada en JSON2Video), renderiza en vertical 9:16 (instagram-story, 1080x1920) y descarga el resultado a scripts/output_reels/<slug>/reel_final.mp4. Usar para "arma el reel final de [tema]", "edita el video con los clips y la narracion", "renderiza el reel". Not for writing the script (write it first), not for selecting B-roll clips (use seleccion-clips-pexels), and not for generating the narration audio (use narracion-voz-gemini) -- this skill only assembles what those two already produced.
---

# Edicion del reel final (JSON2Video)

Toma los clips de B-roll ya elegidos por `seleccion-clips-pexels` y la
narracion ya generada por `narracion-voz-gemini` para el mismo reel, y arma
el video final vertical con subtitulos automaticos y un gancho opcional
usando la API de JSON2Video.

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
prueba real: `classic-progressive` (revela palabra por palabra). Fuente
`Poppins` (`font-family` en `settings`; antes no se especificaba y caia al
default `Arial` de JSON2Video). Color **unico**, `#22D3EE` (cian vivo,
aprobado tras un mockup local -- reemplaza al dorado `#B8985E` que se usaba
antes), para `word-color` y `line-color` por igual -- una version anterior
usaba blanco para la linea y un color solo para la palabra activa, pero el
usuario pidio un solo color sin ese contraste; esa decision se mantiene, solo
cambio el color en si. La revelacion progresiva palabra por palabra se
mantiene, solo que no cambia de color al hacerlo.

**Posicion de subtitulos (regla dura, no preguntar):** `position: "custom"`
con `x=540, y=1150` sobre el canvas de 1080x1920 (`SUBTITLE_X`/`SUBTITLE_Y`
en el script) -- version final aprobada tras DOS rondas de ajuste: la
primera version (`bottom-center` implicito) quedaba tapada por la interfaz
de Instagram; la segunda (`mid-bottom-center`, ~25% desde abajo) seguia
sintiendose "pegada al fondo" segun el usuario. La version actual sube el
texto a ~60% del alto del canvas, claramente en la zona media-baja, lejos
tanto del tercio superior como del borde inferior. Confirmado visualmente
contra un render real.

**Degradado (regla dura, no preguntar):** cada escena lleva un elemento
`html` con un `linear-gradient` que cubre el canvas **completo, de arriba a
abajo** (`GRADIENT_HTML_TEMPLATE` en el script) -- mas oscuro en el primer
~25% (zona del gancho) y en el ultimo ~30% (zona de subtitulos), mas
transparente en el medio para no oscurecer el video donde no hay texto.
Confirmado por prueba real que este overlay **tiene que ir dentro de los
`elements` de cada escena** con una `duration` numerica explicita -- puesto
como elemento a nivel de pelicula (`duration: -2`) no se renderiza (se probo
y salio en blanco).

**Los valores de alpha se subieron DOS veces** antes de quedar aprobados.
Version 1 (piso 0) era matematicamente correcta (muestreo de pixeles: el
brillo caia de 140 a 2 dentro de la franja) pero invisible a simple vista.
Version 2 (piso 0.5 arriba / 0.9 abajo, cubriendo todo el canvas) seguia sin
notarse en el extremo superior: al revisar el frame del gancho (fondo de
ventana clara) la parte de arriba se veia practicamente sin filtrar. La
version actual (piso 0.75 arriba / 0.95 abajo, la zona oscura mas extendida
hacia el centro) se confirmo **extrayendo el frame objetivamente mas claro
de todo el render** (medido con `ffmpeg -vf signalstats`, no a ojo) y
verificando que incluso ese frame muestra oscurecimiento claro en ambos
extremos. Si se vuelve a tocar esta formula, repetir ese mismo metodo de
verificacion -- el muestreo de pixeles solo (sin mirar el frame real) ya dio
un falso positivo una vez.

**Transiciones (regla dura, no preguntar, con un limite duro de API):** cada
escena, salvo la primera del movie completo (el gancho si lo hay, si no el
momento 1), lleva `transition: {type: "xfade", style: "fade", duration:
0.4}`. La duracion nunca supera el 40% de la escena mas corta de las dos que
une (`MAX_TRANSITION_FRACTION_OF_SCENE`), para que un momento muy breve no
quede consumido por su propio fundido.

**`TRANSITION_DURATION_S` esta fijo en 0.4 y no se debe subir sin volver a
probar con un render real completo.** Se investigo a fondo (mas de 10
renders de prueba reales) un pedido de subir a 0.6-0.8s para que el corte se
notara mas, y el resultado fue que **JSON2Video solo aplica el solape de
duracion de forma confiable a exactamente 0.4s con estilo `fade`, cuando el
movie tiene audio + subtitulos a nivel de pelicula** (que es siempre nuestro
caso). Se probo subir a 0.5s, 0.6s y 0.7s (todos fallaron, revirtiendo a
corte seco sin avisar ni devolver error), se probo el estilo `circleopen` a
los mismos 0.4s seguros (tambien fallo), se probo con un `duration` de
escena explicito, con el degradado nuevo de cuadro completo, con posicion de
subtitulo custom en vez de preset, con `quality: "high"`, con 8 escenas
cortas en vez de 2, y con un render real de 26s de audio -- **todas esas
variantes fallaron igual**, siempre revirtiendo a un corte duro sin
transicion aunque el JSON se aceptara sin error. Solo el render completo de
produccion (8-9 escenas, ~67-69s de narracion real) mostro el solape
esperado, dos veces seguidas. La causa raiz exacta no se pudo aislar (no es
la cantidad de escenas sola, no es la duracion de audio sola, no es
`quality`) -- es un limite empirico de la API en esta configuracion, no un
error de nuestro JSON. Si en el futuro se quiere una transicion mas larga o
mas notoria, la unica ruta confiable es pre-renderizar el fundido con
`ffmpeg` localmente (filtro `xfade`) antes de subir el clip, en vez de
confiar en el `transition` nativo de JSON2Video por encima de 0.4s.

**Verificacion correcta de una transicion (no confiar solo en la duracion
del render):** la duracion total puede dar un falso positivo o negativo.
La forma confiable es extraer TODOS los frames alrededor de un corte real
(`ffmpeg -ss <inicio> -t 0.8 -vf fps=25` sobre el mp4 ya descargado, sin
gastar cuota de la API porque es el archivo local) y armar un contact sheet
(`tile=5x4`) para ver si hay fotogramas de mezcla real (doble exposicion de
las dos escenas) entre el corte, no solo dos escenas limpias una tras otra.
Asi se confirmo que el fundido de 0.4s/`fade` SI produce ~8-10 frames de
mezcla real -- es sutil en reproduccion normal (0.4s entre clips de tono
similar), pero es un efecto real, no una falla.

Lista de estilos de `transition.style` documentados por JSON2Video (no hay
una lista exhaustiva oficial, solo ejemplos): `fade` (default), `wipeleft`,
`slideup`, `circleopen`, `dissolve`, `pixelize`, y "...". El `type` siempre
es `"xfade"`, que coincide con el filtro `xfade` de ffmpeg -- es muy
probable que soporte el catalogo completo de ffmpeg (~50 estilos: wipe*,
slide*, smooth*, vert*/horz*open/close, diag*, etc.), pero **solo `fade` a
0.4s quedo confirmado funcionando** en pruebas reales; `circleopen` fallo en
la unica prueba que se le hizo. No asumir que otro estilo funciona sin
probarlo con un render real primero.

**Gancho inicial (opcional, se pregunta el texto pero no si usarlo o no):**
si el usuario pide un gancho, la skill dibuja/confirma el texto ANTES de
llamar al script (ver Flujo, paso 3) y lo pasa via `--hook-main` /
`--hook-accent`. El script arma una escena inicial de `HOOK_DURATION_S`
(2.0s, fijo), con el mismo degradado de cuadro completo detras, y el
titular encima:
- **Clip de fondo del gancho**: si `seleccion-clips-pexels` genero un clip
  dedicado para el gancho (bloque `Momento gancho` en `orden_edicion.txt`,
  buscado por el texto del gancho, no por la `guion_line` del momento 1),
  `parse_hook_clip()` lo usa -- distinto del clip de momento 1, subido aparte
  a JSON2Video. Si ese bloque no existe (reels procesados antes de esta
  funcion, o un gancho improvisado sin volver a correr la busqueda de
  clips), cae de vuelta a reusar el clip de momento 1 (mudo, reciclado --
  comportamiento identico al de antes de esta funcion). El script imprime
  explicitamente cual de los dos casos aplico y que archivo uso, antes de
  subir nada.
- `--hook-main`: frase principal, Poppins bold 88px, en `#F2A900` (amarillo/
  naranja vivo -- mismo color que el titular de los posts estaticos en
  `canva_title_style.md`). Lleva ademas un `-webkit-text-stroke` solido de
  3px en `#1C1208` (contorno duro, sin blur) para mantener contraste cuando
  el clip de fondo tiene una zona clara (ej. una ventana) detras del texto --
  confirmado con un mockup local Y con un frame real extraido de un render
  (proyecto `5mBgcXoQbvqO3LGB`).
- `--hook-accent`: frase de acento, Playfair Display italic 100px, dorado
  palido (`#FAE8A8` -- mismo color que la linea de cierre de los posts
  estaticos).
**Los dos son elementos `type: "text"` nativos de JSON2Video, NO un elemento
`html` con CSS inline.** Una version anterior usaba un solo elemento `html`
con `font-family` en un `<span>` y un comentario que decia "JSON2Video ya
resuelve Poppins/Playfair por nombre, sin @import" -- eso nunca se verifico
contra un render real y resulto ser falso: un frame extraido de un render
real mostro un sans generico, no Poppins. La resolucion automatica de Google
Fonts por nombre (sin @import) esta documentada por JSON2Video **solo para
el elemento `text`** (y, aparte, para `subtitles`) -- el elemento `html` no
la menciona en ningun lado de su documentacion. Por eso el gancho ahora usa
dos elementos `text` apilados via `y` custom (`HOOK_MAIN_Y=650` /
`HOOK_ACCENT_Y` justo debajo), en vez de un solo `html` con dos `<span>`.

**Segunda vuelta de este mismo problema:** el primer render real con los dos
elementos `text` confirmo Poppins + color + contorno del titular principal
correctos, pero mostro la frase de acento en Playfair Display **derecho, sin
italica** -- `"font-style": "italic"` en `settings` no se aplico. Cambiado a
apuntar `font-family` directo a la URL publica del archivo TTF italico de
Playfair Display (`HOOK_ACCENT_FONT_URL`, del repo `google/fonts` en
GitHub) en vez de depender de `font-family` por nombre + `font-style`.
**Confirmado con un render real** (proyecto `8d4ipJeC00fGtiuD`, frame
extraido con ffmpeg): la frase de acento sale genuinamente italica/inclinada.

El gancho se coloca lejos tanto del borde superior como de
`SUBTITLE_Y=1150`, asi que nunca se superpone con el subtitulo de la
narracion -- ademas nunca hay solape de *tiempo*: la narracion arranca
recien en `start: HOOK_DURATION_S` (el audio se corre, no se reproduce en
paralelo al gancho), y los subtitulos solo transcriben audio real, asi que
no aparece texto de narracion durante el gancho. Si el usuario no pide
gancho, no pasar `--hook-main`/`--hook-accent` y el reel arranca directo en
el momento 1, como antes.

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
(`duration`) exacto; si es mas largo, simplemente se recorta. Cuando hay
gancho, su duracion fija (2.0s) tambien entra en el calculo de compensacion
de transiciones, pero nunca se escala -- solo los momentos narrados se
inflan para absorber el solape de las transiciones.

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

   **Preguntar tambien, una sola vez, si quiere un gancho inicial** (si no
   lo pidio ya explicitamente). Si quiere uno, draftear junto al usuario un
   titular corto (4-8 palabras totales entre las dos frases) dividido en dos
   partes -- una frase principal de impacto y una frase de acento mas corta
   -- y confirmar el texto exacto antes de renderizar, nunca asumir un texto
   sin mostrarlo primero. No es obligatorio reusar la primera linea del
   guion tal cual; un titular escrito aparte para detener el scroll suele
   funcionar mejor que la linea narrada completa.

4. **Ejecutar el script** por la tool de Bash, desde la raiz del repo:
   ```
   python scripts/render_reel_json2video.py <reel_slug> [--music "ruta/al/archivo.mp3"] [--quality high] [--hook-main "FRASE PRINCIPAL" --hook-accent "frase de acento"]
   ```
   El script:
   - Carga `JSON2VIDEO_API_KEY` de `.env` (si falta, la pide de forma
     interactiva y la guarda -- nunca pedir esta key al usuario desde la
     skill misma, mismo patron que `generate_post_image.py`).
   - Resuelve las carpetas de clips y audio (con el fallback de slug
     descrito arriba), parsea `orden_edicion.txt`, elige un clip por
     momento, calcula la duracion de cada uno con `ffprobe`.
   - Reparte la duracion total de la narracion entre los momentos por
     proporcion de palabras, calcula la transicion entre cada par de
     escenas (tope del 40% de la escena mas corta, incluyendo el gancho si
     lo hay) e infla las duraciones narradas para compensar el solape que
     las transiciones le restan al total.
   - Imprime la cuota de render restante de la cuenta de JSON2Video antes de
     enviar el render, con un aviso si la duracion esperada (narracion +
     gancho) es mayor que la cuota disponible.
   - Sube narracion, clips elegidos y musica (si hay) a JSON2Video, arma el
     `movie` JSON (escena de gancho opcional + una escena por momento, cada
     una con su clip + el overlay de degradado de cuadro completo + su
     transicion de entrada; narracion con `start` corrido si hay gancho +
     musica opcional + subtitulos nativos posicionados en la zona segura
     como elementos a nivel de pelicula, resolucion `instagram-story` =
     1080x1920), lo envia y hace poll cada ~7s hasta que termina.
   - Descarga el resultado final a
     `scripts/output_reels/<reel_slug>/reel_final.mp4`.
   - Borra los assets subidos a JSON2Video (narracion, clips, musica) al
     terminar, exito o error, para no agotar el storage gratuito de la
     cuenta.

5. **Mostrar el resultado**: ruta final del archivo, duracion y resolucion
   del render, creditos consumidos, el texto del gancho usado (si hubo), y
   la lista de momentos que `orden_edicion.txt` ya traia marcados con
   advertencia (`⚠ protagonista distinta`, `ℹ imagen de apoyo`, etc.) para
   que el usuario los revise visualmente en el video terminado -- esas
   advertencias vienen heredadas de la seleccion de clips, esta skill no las
   resuelve, solo las hace visibles de nuevo en el resumen final.

## Reglas duras

- Nunca inventar ni regenerar clips o narracion -- si falta alguno de los
  dos archivos de origen, decirle al usuario que corra
  `seleccion-clips-pexels` o `narracion-voz-gemini` primero.
- Nunca pedir la API key de JSON2Video al usuario directamente -- el script
  la maneja con el mismo patron que `generate_post_image.py`.
- Nunca renderizar sin subtitulos -- son parte fija del formato de reel de
  la marca, no un opcional que se pregunta cada vez.
- Subtitulos **siempre** en `position: "custom"` con `x=540, y=1150` y el
  degradado de cuadro completo detras -- version final aprobada tras dos
  rondas de ajuste de posicion. Nunca preguntar por esto.
- Transiciones **siempre** activas entre escenas (`fade`, 0.4s, tope 40% de
  la escena mas corta) -- version final aprobada. **Nunca subir
  `TRANSITION_DURATION_S` por encima de 0.4 sin antes confirmar con un
  render real completo** (ver la seccion de arriba: todo lo probado por
  encima de 0.4s revirtio a corte seco silenciosamente).
- El gancho inicial es opcional -- preguntar una sola vez si lo quiere, y
  siempre draftear/confirmar el texto exacto con el usuario antes de
  renderizar, nunca inventarlo sin mostrarlo.
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
  parsea `orden_edicion.txt`, calcula duraciones (con compensacion de
  transiciones, incluyendo el gancho si lo hay), sube assets a JSON2Video,
  arma y envia el `movie` JSON (subtitulos con posicion segura, overlay de
  degradado por escena, transiciones entre escenas, gancho opcional), hace
  poll del render, descarga el resultado y limpia los assets subidos.
  Acepta `--music`, `--quality` (`low`/`medium`/`high`, default `high` -- la
  calidad no cambia el costo en creditos, solo la fidelidad visual),
  `--hook-main`/`--hook-accent` (opcionales, van juntos), `--clips-dir`,
  `--audio-dir` y `--out-dir` para override. Constantes ajustables sin tocar
  la logica: `SUBTITLE_X`/`SUBTITLE_Y`, `GRADIENT_HTML_TEMPLATE`,
  `TRANSITION_STYLE`, `TRANSITION_DURATION_S` (ver limite duro arriba),
  `HOOK_DURATION_S`, `HOOK_MAIN_FONT`/`HOOK_ACCENT_FONT` y sus tamanos/
  colores.
- `scripts/output_clips/` -- clips de B-roll + `orden_edicion.txt` por reel
  (gitignored, de `seleccion-clips-pexels`).
- `scripts/output_audio/` -- narracion por reel (gitignored, de
  `narracion-voz-gemini`).
- `scripts/output_reels/` -- reels finales renderizados (gitignored, son
  binarios, no se suben al repo).
- `../../scripts/references/image_prompt_style.md` -- `BRAND_COLORS`, la
  paleta general de marca (ya no la fuente de los colores del gancho/
  subtitulos, ver siguiente).
- `../../scripts/references/canva_title_style.md` -- fuente de verdad de los
  colores del titular del gancho (`#F2A900` / `#FAE8A8`), compartidos con el
  titulo de los posts estaticos. El color cian de los subtitulos (`#22D3EE`)
  es especifico de los reels y vive solo en `SUBTITLE_WORD_COLOR` en el
  script, no en este archivo.

## Related skills

- `seleccion-clips-pexels` -- elige el B-roll y escribe `orden_edicion.txt`
  que esta skill consume. Correr primero.
- `narracion-voz-gemini` -- genera `narracion.mp3` que esta skill consume.
  Correr primero.
- `imagen-post-constelaciones` / `post-constelaciones` / `carrusel-
  constelaciones` / `historias-constelaciones` -- contenido estatico (foto o
  copy), no reels.
