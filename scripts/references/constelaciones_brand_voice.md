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
    on-image text of the **second-to-last slide** — a visual closer meant to
    earn the save. The last slide is the CTA slide (see below). It is never
    duplicated in the caption.
- **Bridge required before the CTA.** Naming the pain is not enough: between
  the reframe and the link there must be an explicit sentence stating that a
  way out exists and that Diana's book/process is that way out. Don't just
  name the wound and then drop the link with no connective sentence. Example:
  "Esto no se queda así: hay un camino para soltar esta carga, y en mi libro
  te lo muestro paso a paso." Applies to both `post-constelaciones` (as a
  sentence right before the link) and `carrusel-constelaciones` (as the text
  of the dedicated CTA slide, see `CAROUSEL_STRUCTURES`).
- **CTA:** one natural mention of the book *El dolor que no te pertenece*
  plus the plain URL `https://eldolorquenotepertenece.com` — no UTM
  parameters, no shortened link, no more than this one link.
  - `post-constelaciones`: CTA + link go at the end of the on-image copy
    block, right after "Para asentar" and the bridge sentence.
  - `carrusel-constelaciones`: the CTA (bridge sentence + book mention) is
    the on-image text of the **last slide**; the plain link itself still goes
    **only in the caption**, never on a slide.
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
state.

**Every structure ends with the same last two slides, on top of its own
content count below:** second-to-last = "Para asentar" closer (the
affirmation), last = the CTA slide (bridge sentence + book mention, see
`CAROUSEL_STRUCTURES`'s parent rules for the exact bridge requirement). Never
skip either, never merge them into one slide.

**Minimum 6 slides, every structure, no exceptions.** A carousel that would
otherwise land on 4 or 5 slides gets more content development instead of
staying short -- split the middle content into more distinct beats (cause,
how it shows up, consequence, etc.) rather than compressing the closer.

**Slide-to-slide connective flow (mandatory).** Slides must read as one
continuous story advancing, never as a list of independent, disconnected
statements. Every slide except the first must open by picking up something
from the slide before it, using one of these techniques:
- **Repeat a keyword or image** from the end of the previous slide and carry
  it forward (e.g. previous slide ends on "el puente"; this slide opens "Ese
  puente no se queda en la infancia...").
- **Answer the implicit question** the previous slide left open (a slide that
  ends on tension or a claim without proof should be answered by the next).
- **Continue the same sentence or idea naturally**, as if the reader is
  turning a page mid-thought, not starting a new one.
Do this for every transition, including into "Para asentar" and into the CTA
slide -- the affirmation should echo a word or image from the body, and the
CTA should pick up from what "Para asentar" just resolved.

**Design mix (fixed, not random):** slide 1 (hook) and the last slide (CTA)
use the flat-color "quote card" treatment from `BRAND_COLORS` in
`image_prompt_style.md` -- no photo, no Gemini call, text is the whole
design. Every other slide, including "Para asentar," uses a generated photo
background. This mix repeats on every carousel; it is not optional or
randomized per slide.

1. **Narrativo: problema → causa/origen → cómo se manifiesta → consecuencia →
   Para asentar → CTA.** 6 slides, siempre. Slide 1 plantea el problema
   (hook, sin foto). Slide 2 explica la causa/origen oculto (foto). Slide 3
   muestra cómo se manifiesta en el día a día (foto). Slide 4 nombra la
   consecuencia de no verlo (foto). Slide 5 es "Para asentar" (foto).
   Slide 6 es el CTA (sin foto).
2. **Lista de comportamientos en paralelo.** 6-8 slides depending on how many
   behaviors fit the topic: hook (sin foto) + 3-5 behavior slides (foto) +
   "Para asentar" (foto) + CTA (sin foto). Mínimo 3 comportamientos para
   llegar a 6 slides.
3. **Antes / Después.** 6 slides, siempre (ya no hay variante corta): el
   contraste se desarrolla en dos beats por lado en vez de uno. Slide 1 =
   "Antes" -- cómo se ve/siente el patrón viejo (hook, sin foto). Slide 2 =
   "Antes" -- una consecuencia concreta de ese patrón (foto). Slide 3 =
   "Después" -- qué cambia al soltarlo (foto). Slide 4 = "Después" -- qué se
   gana (foto). Slide 5 = "Para asentar" (foto). Slide 6 = CTA (sin foto).
4. **Preguntas de autodiagnóstico.** 6-8 slides depending on how many signs
   fit: hook (sin foto) + 3-5 self-check question slides (foto) + "Para
   asentar" (foto) + CTA (sin foto). Mínimo 3 preguntas para llegar a 6
   slides.
5. **Mini-historia con giro: situación → tensión → punto de quiebre →
   revelación → Para asentar → CTA.** 6 slides, siempre. Slide 1 sets the
   situation (hook, sin foto). Slide 2 the tension building up (foto).
   Slide 3 the specific breaking point/momento crítico (foto). Slide 4 the
   revelation/reframe (foto). Slide 5 is "Para asentar" (foto). Slide 6 is
   CTA (sin foto).

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
