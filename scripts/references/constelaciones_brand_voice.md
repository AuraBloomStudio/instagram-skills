# Constelaciones Familiares — Brand voice & post structures

Reference read by the `post-constelaciones`, `carrusel-constelaciones`, and
`historias-constelaciones` skills (and, later, `ads-constelaciones`) when
drafting organic copy. Extracted from the 9 real approved posts in
`Desktop/Posts Constelaciones/` — this is the first time it's written down, so
treat it as a living draft: edit freely as you approve or reject drafts and
the voice needs correcting.

This file governs COPY only. Background-photo style lives in
`image_prompt_style.md`; both are read for the same post.

## Voice fingerprint

- **Address: "tú".** The body speaks directly to the reader in second person
  throughout.
- **Exception: the contrast couplet shifts to third person.** Whenever the
  copy uses the "cree que X / en realidad Y" device, it switches to "Ella"
  (or "Él" if the post's protagonist is explicitly male) for those lines only
  — a deliberate distancing beat, found in all 3 of the existing posts that
  use this device, nowhere else in the same posts. Switch back to "tú"
  immediately after.
- **Short, declarative rhythm.** Single-sentence paragraphs are normal and
  used for emphasis, especially in parallel lists ("Alguien disponible a
  medias.").
- **Naming the hidden cause behind the surface symptom** is the recurring
  intellectual move: "no es mala suerte, es lealtad invisible"; "no es que
  ayudes, es que invades." Every structure below should land one version of
  this reframe.
- **No em dashes, no AI-vocabulary filler** ("leverage", "profundizar",
  "en definitiva"). Same global rules as the public bundle's voice rules,
  applied here too.

## Closer, CTA, and hashtags (hard rules -- feed content only)

These rules apply to `post-constelaciones` and `carrusel-constelaciones`
(feed content). **They do NOT apply to `historias-constelaciones`** — Stories
skip "Para asentar," the book CTA, and hashtags entirely; see
`STORY_STRUCTURES` below for what Stories use instead.

- **"Para asentar:" is the mandatory closer**, followed by one first-person
  affirmation paragraph that mirrors the post's core reframe. Every
  structure ends this way, no exceptions.
  - `post-constelaciones` (single image): the affirmation is the last part
    of the same on-image copy block.
  - `carrusel-constelaciones`: "Para asentar" + the affirmation is the
    on-image text of the **last slide only** — a visual closer meant to earn
    the save. It is never duplicated in the caption.
- **CTA:** one natural mention of the book *El dolor que no te pertenece*
  plus the plain URL `https://eldolorquenotepertenece.com` — no UTM
  parameters, no shortened link, no more than this one link.
  - `post-constelaciones`: CTA + link go at the end of the on-image copy
    block, right after "Para asentar."
  - `carrusel-constelaciones`: CTA + link go **only in the caption**, never
    on a slide.
  - If a post is about a topic the book doesn't directly cover, keep the
    same CTA anyway (it's the standing offer across this brand) unless the
    user says otherwise for that post.
- **Hashtags: always 5, in a 2 fixed + 3 topic shape** — never a single
  static set reused verbatim post to post.
  - Fixed, every time: `#ConstelacionesFamiliares` `#SanaciónFamiliar`
  - 3 topic tags: chosen per post by applying the `ig-hashtag-strategist`
    skill's sizing logic (niche/mid/broad mix) to this specific post's
    topic. Do not default to the same 3 across unrelated posts.
  - Placement: `post-constelaciones` -> end of the on-image copy block.
    `carrusel-constelaciones` -> end of the caption, after the CTA link.

## POST_STRUCTURES

`post-constelaciones` rotates through these, avoiding the last 2 used
(tracked in `testing/copy_gen_state.json`, key `post_structure`). If the user
names a structure, use that one instead and don't touch the rotation state.

1. **Carta directa.** Título contundente en mayúsculas, dirigido a "ti" (el
   formato de las "Carta TÚ" existentes). Cuerpo: 3-5 párrafos que insisten en
   una sola idea desde el "tú", sin listas, construyendo hacia el reencuadre.
   Cierre: Para asentar + CTA + hashtags.
2. **Contraste "cree que / en realidad."** Título breve en mayúsculas que
   plantea la creencia equivocada. Cuerpo: 1-2 párrafos de contexto, luego 1-2
   pares "Ella cree que X. / En realidad, Y." como núcleo central (aquí es
   donde ocurre el quiebre de voz a tercera persona), luego 1 párrafo de
   reencuadre de vuelta en "tú". Cierre: Para asentar + CTA + hashtags.
3. **Pregunta directa sin resolución.** Título = la pregunta, en mayúsculas.
   Cuerpo: 2-3 párrafos que profundizan la pregunta con situaciones concretas
   y sensación corporal, pero SIN entregar el reencuadre completo — la tensión
   queda abierta a propósito para generar comentarios. Distinto de una
   "pregunta directa" que sí resuelve (eso sería Carta directa). Para asentar
   aquí es más invitación a responder en comentarios que cierre resuelto, pero
   sigue siendo obligatorio, + CTA + hashtags.
4. **Confesión personal.** Título en mayúsculas y en primera persona ("DURANTE
   AÑOS PENSÉ QUE..."). Cuerpo enteramente en "yo", tono vulnerable, cuenta una
   experiencia propia y el momento de comprensión. Cierre: Para asentar (ya
   coherente en primera persona) + CTA + hashtags.
5. **Dato/afirmación tipo manifiesto.** Título = la afirmación central, en
   mayúsculas. Cuerpo corto: 1-2 párrafos máximo, sin desarrollo narrativo
   largo, tono de declaración. El más corto de las 5. Cierre: Para asentar
   (breve) + CTA + hashtags.

## CAROUSEL_STRUCTURES

`carrusel-constelaciones` rotates through these, avoiding the last 2 used
(tracked in `testing/copy_gen_state.json`, key `carousel_structure`). If the
user names a structure, use that one instead and don't touch the rotation
state. In every structure, the **final listed slide is the "Para asentar"
closer slide** — never an extra slide on top of the count below.

1. **Narrativo: problema → explicación → cierre.** 3 slides. Slide 1 plantea
   el problema (funciona como hook). Slide 2 explica la causa oculta. Slide 3
   es el cierre "Para asentar."
2. **Lista de comportamientos en paralelo.** 4-6 slides depending on how many
   behaviors fit the topic. Slide 1 is the hook ("Señales de que..."), each
   middle slide names one behavior, the last slide is "Para asentar."
3. **Antes / Después.** 2-3 slides. Slide 1 = "Antes" (el patrón viejo).
   Slide 2 = "Después" (el reencuadre). If a 3rd slide is used, it's the
   dedicated "Para asentar" closer; in the 2-slide version, fold the
   affirmation into slide 2.
4. **Preguntas de autodiagnóstico.** 5-7 slides depending on how many signs
   fit. Slide 1 is the hook ("¿Reconoces estas señales?"), each middle slide
   is one yes/no self-check question, the last slide is "Para asentar."
5. **Mini-historia con giro: situación → tensión → revelación → cierre.**
   4 slides. Slide 1 sets the situation, slide 2 the tension, slide 3 the
   revelation (the reframe), slide 4 is "Para asentar."

## STORY_STRUCTURES

`historias-constelaciones` rotates through these, avoiding the last 2 used
(tracked in `testing/copy_gen_state.json`, key `story_structure`). If the user
names a structure, use that one instead and don't touch the rotation state.

Stories are read in seconds: keep the "tú" voice fingerprint above, but drop
"Para asentar," the book CTA, and hashtags entirely — none of those apply
here. Text per structure:

1. **Frase destacada.** Una cita o gancho potente, 1-2 líneas, extraída o
   inspirada en el tema, pensada para reforzar/repostear un post del feed.
2. **Pregunta interactiva.** Una pregunta abierta corta sobre el tema. Deja
   espacio explícito para que el usuario agregue a mano el sticker nativo de
   pregunta/encuesta de Instagram después -- esta skill no genera el sticker,
   solo el texto y el fondo.
3. **Mini-consejo práctico.** Un tip corto y accionable, 3-4 líneas, directo,
   sin la estructura larga de un post de feed.
4. **Recordatorio con CTA.** Invita a ver un post nuevo, el libro, o agendar
   sesión con Diana, con una llamada a la acción directa y corta ("desliza
   hacia arriba", "link en bio"). Este CTA es libre por historia -- no es el
   CTA fijo del libro que usan `post-constelaciones`/`carrusel-constelaciones`.
5. **Detrás de cámaras / voz personal.** Mensaje en primera persona de Diana,
   tono íntimo y reflexivo, 2-3 líneas.

## Reference example (contrast-couplet device, for calibration)

From an existing approved post, showing the "tú" body with the third-person
couplet shift:

> Por eso, sin darse cuenta, vuelve a elegir el mismo patrón: [...]
>
> Ella cree que está eligiendo el amor.
> En realidad, está repitiendo la ausencia.
>
> Ella busca sentirse elegida.
> Elige a quien no puede elegirla del todo.
>
> No se trata de mala suerte ni de "no saber elegir". Es lealtad invisible...

## Changing the voice later

Edit this file directly — all three skills re-read it on every draft, so no
code change is needed. If a draft doesn't sound right, say so and point at the
paragraph; that correction is what should get folded back into this file, the
same way `image_prompt_style.md` evolved from real feedback.
