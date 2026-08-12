---
name: post-viral-constelaciones
description: Draft one of two fixed viral Facebook text formats for Constelaciones Familiares, no image, pure copy-paste text. Variante 1 "USTED DEBERÍA SABER QUE:" (patrón sistémico + consecuencia, luego "Reconozca que.../Comprenda que..." con el reencuadre y una afirmación entre comillas, tono formal "usted", 900-1,300 caracteres). Variante 2 "GUARDA ESTE DECRETO EN TU CORAZÓN" (decreto/bendición en primera persona dirigido a los hijos, cierre fijo "Así es. Gracias, gracias, gracias." o "Hecho está. Gracias.", 700-1,000 caracteres). Both close with a short bridge CTA naming the book mapped by topic (Dolor, Dinero, Mamá, Papá, Regreso, same table as FACEBOOK_POST_STRUCTURE) and end literally with "El link está en la descripción." Alternates strictly between the two variants (tracked in testing/copy_gen_state.json, key post_viral_variant) instead of rotating a pool, since the goal is 2 pieces a day, one of each. After saving each piece's .docx, also builds one consolidated "PAQUETE - <hook>.docx" per piece (the copy + a new, differently-worded first-comment CTA + a publish checklist, no image section since this format never has one, per PACKAGING_STANDARD) via scripts/build_paquete_docx.py. Use for "hazme un post viral de [tema]", "dame el decreto de hoy", "necesito el par de posts virales de hoy". Not for the essay-style Facebook post (use post-constelaciones), not for carousels (use carrusel-constelaciones), and not for Stories (use historias-constelaciones).
---

# Post Viral Constelaciones (texto puro, Facebook)

Redacta una pieza de texto viral para Facebook siguiendo una de las dos
variantes fijas de `POST_VIRAL_STRUCTURE` en
`../../scripts/references/constelaciones_brand_voice.md`, la aprueba el
usuario, y la guarda como `.docx`. No genera imagen de ningún tipo -- es
contenido de texto puro pensado para copiar y pegar directo en Facebook.

## Cuándo se activa

- "hazme un post viral de [tema]"
- "dame el decreto de hoy" / "escríbeme el decreto sobre [tema]"
- "necesito el par de posts virales de hoy"

No se activa para el post ensayo largo de Facebook (`post-constelaciones`,
estructura `FACEBOOK_POST_STRUCTURE`), para carruseles
(`carrusel-constelaciones`), ni para Stories (`historias-constelaciones`).

## Flujo

1. **Tema.** Tomar el tema/ángulo del pedido del usuario.
2. **Elegir variante.**
   - Si el usuario nombra explícitamente una variante ("hazme el de USTED
     DEBERÍA SABER QUE" / "hazme el decreto"), usar esa y no tocar el
     estado de alternancia.
   - Si el usuario pide el par diario (2 piezas), producir una de cada
     variante en la misma respuesta, en cualquier orden, y actualizar el
     estado una sola vez al final con la última usada.
   - Si no se especifica nada, alternar automáticamente: leer
     `testing/copy_gen_state.json` (crear con `{}` si no existe), tomar el
     valor de la clave `"post_viral_variant"` ("1" o "2", puede no existir
     la primera vez), usar la variante que NO sea ese valor, y sobrescribir
     la clave con la elegida.
   - **Nunca preguntar cuál variante usar antes de redactar** -- elegir (o
     usar la nombrada) y avisar cuál se usó junto con el borrador.
3. **Redactar el texto** siguiendo exactamente la forma fija de la variante
   elegida (encabezado literal, estructura de párrafos, cierre literal) más
   el CTA obligatorio -- ver `POST_VIRAL_STRUCTURE` para el detalle
   completo de cada variante y la tabla de mapeo tema -> libro (compartida
   con `FACEBOOK_POST_STRUCTURE`, no se reinventa aquí). Respetar la
   excepción de tratamiento: Variante 1 en "usted", Variante 2 sin segunda
   persona directa -- ninguna de las dos usa "tú" ni "Para asentar".
4. **Mostrar el borrador** en el chat: variante usada, texto completo
   (encabezado + cuerpo + cierre + CTA), y el conteo de caracteres del
   cuerpo (sin el CTA) para confirmar que cae en el rango de la variante.
   Esperar aprobación o ajustes.
5. **Guardar el copy aprobado** como `.docx` en
   `Desktop/Posts Constelaciones/Virales/<hook o tema>.docx`, con el
   encabezado fijo de la variante en negrita en el primer párrafo (mismo
   formato que usan las demás skills de copy). Usar `python-docx` (ya es
   dependencia del proyecto). Si se generó el par diario, guardar dos
   archivos `.docx` separados.
6. **Confirmar el resultado**: ruta(s) final(es) del/los `.docx`, y
   recordar que esta pieza no lleva imagen -- se publica como texto puro.
7. **Armar el paquete consolidado** (ver `PACKAGING_STANDARD` en
   `constelaciones_brand_voice.md` para el detalle completo) -- uno por
   cada pieza generada; si se produjo el par diario, dos paquetes
   separados. El libro ya se decidió en el paso 3 (tabla tema -> libro
   compartida con `FACEBOOK_POST_STRUCTURE`); redactar el primer
   comentario con ESE MISMO libro pero en una redacción nueva y corta (2-3
   líneas), distinta de la frase de CTA que ya cierra la pieza -- mismo
   criterio de tono por variante que ya rige el CTA principal (directo en
   Variante 1, suave/decreto en Variante 2). Luego correr, por cada pieza:
   ```
   python scripts/build_paquete_docx.py "<hook o tema>" --copy-docx "<ruta al .docx del paso 5>" --primer-comentario "<texto del primer comentario>" --out-dir "Desktop/Posts Constelaciones/Virales"
   ```
   Sin `--image` -- esta pieza nunca lleva imagen. Esto genera
   `Desktop/Posts Constelaciones/Virales/PAQUETE - <hook>.docx` -- no
   reemplaza el `.docx` del paso 5, lo complementa. Mostrar la(s) ruta(s)
   final(es) junto con el resto del resultado.

## Reglas duras

- Nunca preguntar qué variante usar antes de escribir -- elegir (nombrada,
  alternada, o el par completo) y avisar cuál se usó al mostrar el
  resultado.
- Nunca mezclar las dos variantes dentro de una misma pieza -- cada pieza
  es una variante completa y fija, no un remix.
- Nunca omitir el CTA, y nunca poner el link inline -- el cierre de CTA
  siempre termina literal en "El link está en la descripción."
- Nunca usar "tú" en la Variante 1 (es "usted") ni agregar "Para asentar" o
  hashtags a ninguna de las dos variantes -- ver la excepción de
  tratamiento en `POST_VIRAL_STRUCTURE`.
- Nunca generar ni pedir generar una imagen para esta pieza -- es
  exclusivamente texto. Si el usuario también quiere una foto para
  acompañarla, redirigir a `imagen-post-constelaciones` sobre el `.docx`
  ya guardado.
- Nunca agregar firma de marca (nombre de autor, @handle) -- ninguna de las
  dos variantes lleva firma.
- El paquete consolidado (paso 7) es siempre el último paso, nunca antes de
  que exista el `.docx` de la pieza, y nunca lleva `--image` -- ver
  `PACKAGING_STANDARD` en `constelaciones_brand_voice.md`. El primer
  comentario es un texto nuevo, nunca una copia literal del CTA que ya
  cierra la pieza.

## Recursos

- `../../scripts/references/constelaciones_brand_voice.md` -- sección
  `POST_VIRAL_STRUCTURE` (las dos variantes, el CTA obligatorio, la regla
  de alternancia), `FACEBOOK_POST_STRUCTURE` (tabla de mapeo tema -> libro,
  reutilizada tal cual), y `PACKAGING_STANDARD` (el paquete consolidado del
  paso 7).
- `../../scripts/build_paquete_docx.py` -- arma el paquete consolidado del
  paso 7.
- `testing/copy_gen_state.json` -- estado de alternancia (clave
  `"post_viral_variant"`, se autogenera).

## Related skills

- `post-constelaciones` -- post ensayo largo de Facebook/Instagram con
  imagen de fondo.
- `carrusel-constelaciones` -- carruseles multi-slide.
- `historias-constelaciones` -- Stories 9:16.
- `imagen-post-constelaciones` -- si el usuario quiere una foto para
  acompañar una pieza viral ya guardada.
