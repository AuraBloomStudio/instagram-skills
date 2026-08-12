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

- **Language: español neutro colombiano, always.** Every text this pipeline
  produces -- títulos, subtítulos, copy de slide, CTA, captions -- is in
  neutral Colombian Spanish. **Never voseo** ("vos", "cargás", "sos", "tenés")
  and never modismos tied to another country (Mexican, Rioplatense, Chilean,
  etc.). This has been violated in practice (a real carousel draft mixed "tú"
  conjugations with voseo mid-piece -- "ves" next to "abrís/apagás/quedás" --
  an inconsistency that should never reach a draft). If a draft slips into
  voseo or another region's modismos, that is a defect to fix before
  approval, not a stylistic variant.
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
- **Bridge required before the CTA, with real weight and an explicit
  callback.** A single generic sentence ("hay un camino, en mi libro te lo
  muestro") is not enough on its own -- the bridge has to name the SPECIFIC
  pain this exact piece developed (echo a concrete image or phrase from the
  body, the same way "Para asentar" already has to echo the body per the
  slide-to-slide connective-flow rule in `CAROUSEL_STRUCTURES`), not a
  reusable formula that could sit at the bottom of any post. Give it real
  body -- 2-3 sentences building from that specific pain into the offer, not
  one thin clause -- before naming the book. Example shape: name the
  recurring pattern this piece just walked through -> state plainly that it
  doesn't have to keep repeating -> THEN mention the book as the way through
  it. Applies to both `post-constelaciones` (right before the link) and
  `carrusel-constelaciones` (the text of the dedicated CTA slide, see
  `CAROUSEL_STRUCTURES`).
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

**Design mix (fixed, not random):** only the last slide (CTA) uses the
flat-color "quote card" treatment from `BRAND_COLORS` in
`image_prompt_style.md` -- no photo, text is the whole design. **Every other
slide, including the hook and "Para asentar," carries a real Pexels photo**
background (see "Photo sourcing: Pexels, not Gemini" below) -- the hook
stopped being a bare quote card because it's the single most important slide
for stopping the scroll. This mix repeats on every carousel; it is not
optional or randomized per slide. Baked text per slide type (all via
`generate_post_image.py`'s `render_headline`, Poppins Bold `#F2A900` title +
Playfair Display italic `#FAE8A8` subtitle on every slide that has one):
- **Hook (slide 1):** título + subtítulo + a third short line
  (`--headline-extra`, Poppins SemiBold, same pale gold as the subtitle).
- **Content slides + "Para asentar"** (every slide between the hook and the
  CTA): título + subtítulo, PLUS the slide's full microdolor paragraph baked
  separately as `--body-text` -- Poppins Bold, cyan `#22D3EE` (same color as
  the reel narration subtitles), with a dark gradient scrim behind it for
  contrast (same stops as `render_reel_json2video.py`'s
  `GRADIENT_HTML_TEMPLATE`). This is new text on the image, not just a
  distilled headline -- the reader should be able to read the actual
  microdolor without opening the caption.
- **CTA (slide 6, flat-color):** título + subtítulo only, no cyan block --
  the bridge already gets its own longer, higher-weight text per the
  strengthened bridge rule above; a third text block there would compete
  with it.

**Photo sourcing: Pexels, not Gemini.** Every photo slide (hook + content +
Para asentar) is a real stock photo from Pexels, sourced with the exact same
protagonist-consistency cascade `seleccion-clips-pexels` already uses for
reels (solo -> accompanied -> cutaway -> different author -> approximate),
reused by import in `scripts/search_pexels_photo.py` rather than
duplicated. Gemini is not called at all for this skill's photos --
`post-constelaciones`, `imagen-post-constelaciones`, and
`historias-constelaciones` are unaffected and keep generating with Gemini as
before; this is scoped to `carrusel-constelaciones` only. Search-term writing
follows the same candid, non-posed vocabulary `seleccion-clips-pexels`
already uses (real domestic scenes, never "business woman smiling at
camera"), not `image_prompt_style.md`'s Gemini-specific
composition/anonymity rules, which don't apply to a real licensed stock
photo. A mandatory visual review (same discipline as `seleccion-clips-pexels`,
adapted for stills) happens before any slide is shown to the user -- see
`carrusel-constelaciones/SKILL.md`.

**First content slide carries the strongest pain (mandatory).** Slide 2 (the
first slide after the hook) is the first real swipe -- if it doesn't land
hard, the carousel loses the scroll right there. It must name the carousel's
central pain/feeling at its most concrete and intense, never open with a
neutral, generic question or a soft piece of context ("¿te ha pasado esto
alguna vez?" is a bad slide 2 -- too vague to be the strongest beat). Later
slides can open questions, add nuance, or build tension; slide 2 does not get
to be the warm-up. What this means per structure:
- **Narrativo** (1): the causa/origen slide must expose the hidden cause in
  its rawest, most recognizable form, not a soft lead-in to it.
- **Lista de comportamientos** (2): order the behaviors so the FIRST one
  listed is the most recognizable/painful, not the mildest or most generic --
  the rest can descend or vary from there, but never open on the weakest one.
- **Antes/Después** (3): the first "Antes" slide must be the sharpest,
  most concrete image of the old pattern, not a vague mood-setter.
- **Preguntas de autodiagnóstico** (4): order the questions so the FIRST one
  is the most piercing/revealing, not the easiest or most generic self-check
  -- later questions can be softer or more specific.
- **Mini-historia con giro** (5): the tension-building slide must open on a
  concrete, high-stakes detail of the situation, not a scene-setting
  generality.

**Content-slide copy must be a real paragraph, not a one-line headline
(mandatory).** Every content slide and "Para asentar" needs 2-4 concrete
sentences that build genuine identification with one specific microdolor --
a recognizable situation, not an abstract label for a feeling. "Sientes
culpa a veces" is too thin; "Cada vez que por fin ves una cifra que te hace
respirar, aparece una urgencia y te quedas otra vez en ceros" names the
actual pattern (español neutro, sin voseo -- ver la regla de idioma en
"Voice fingerprint"). This full paragraph is what gets baked as `--body-text` (see
"Design mix" above) -- it is real content the reader reads on the image
itself, not a caption-only detail. A single generic sentence that could sit
on any post about any topic is a defect, not a stylistic minimum.

1. **Narrativo: problema → causa/origen → cómo se manifiesta → consecuencia →
   Para asentar → CTA.** 6 slides, siempre. Slide 1 plantea el problema
   (hook, foto). Slide 2 explica la causa/origen oculto (foto + body-text).
   Slide 3 muestra cómo se manifiesta en el día a día (foto + body-text).
   Slide 4 nombra la consecuencia de no verlo (foto + body-text). Slide 5 es
   "Para asentar" (foto + body-text). Slide 6 es el CTA (sin foto,
   flat-color).
2. **Lista de comportamientos en paralelo.** 6-8 slides depending on how many
   behaviors fit the topic: hook (foto) + 3-5 behavior slides (foto +
   body-text) + "Para asentar" (foto + body-text) + CTA (sin foto,
   flat-color). Mínimo 3 comportamientos para llegar a 6 slides.
3. **Antes / Después.** 6 slides, siempre (ya no hay variante corta): el
   contraste se desarrolla en dos beats por lado en vez de uno. Slide 1 =
   "Antes" -- cómo se ve/siente el patrón viejo (hook, foto). Slide 2 =
   "Antes" -- una consecuencia concreta de ese patrón (foto + body-text).
   Slide 3 = "Después" -- qué cambia al soltarlo (foto + body-text). Slide 4
   = "Después" -- qué se gana (foto + body-text). Slide 5 = "Para asentar"
   (foto + body-text). Slide 6 = CTA (sin foto, flat-color).
4. **Preguntas de autodiagnóstico.** 6-8 slides depending on how many signs
   fit: hook (foto) + 3-5 self-check question slides (foto + body-text) +
   "Para asentar" (foto + body-text) + CTA (sin foto, flat-color). Mínimo 3
   preguntas para llegar a 6 slides.
5. **Mini-historia con giro: situación → tensión → punto de quiebre →
   revelación → Para asentar → CTA.** 6 slides, siempre. Slide 1 sets the
   situation (hook, foto). Slide 2 the tension building up (foto +
   body-text). Slide 3 the specific breaking point/momento crítico (foto +
   body-text). Slide 4 the revelation/reframe (foto + body-text). Slide 5 is
   "Para asentar" (foto + body-text). Slide 6 is CTA (sin foto, flat-color).

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

## REEL_SCRIPT_LENGTH

Target length for a reel's narrated guion, so the finished video lands at
40-50s TOTAL (narration + the optional 2s hook) instead of being cut down
after the fact. This is a hard structural limit on the guion itself, same
category as the other structure rules above -- not just a post-hoc warning.

**Target: 108-136 words.**

Math, from real measured data (not a generic words-per-minute estimate):
the approved brand narration pace -- voice "Sulafat," brisk/warm
conversational rhythm, see `narracion-voz-gemini`'s "Ritmo de narracion" --
is **170 words/min (2.833 words/sec)**, measured directly from the reel
"crei-que-solo-tenia-mal-caracter" (189 words narrated in 66.73s, verified
via `ffprobe` against the actual `narracion.mp3`, not the rounded figure
already in that skill's docs).

The 40-50s target is deliberately the TOTAL video duration, so the word
range reserves the hook's fixed 2s even for reels that end up without one --
one single range for every reel, hook or no hook, rather than two different
targets depending on a decision made later at render time:
- Narration budget: 40-2=38s to 50-2=48s.
- 38s × 2.833 words/sec ≈ 108 words (floor).
- 48s × 2.833 words/sec ≈ 136 words (ceiling).

Whoever drafts a reel's guion (by hand, in another conversation, or however
it happens -- there is no dedicated drafting skill in this bundle as of this
writing) should aim for 108-136 words. `narracion-voz-gemini` checks this
automatically the moment a guion is pasted in (see that skill's Flujo) and
reports the actual word count/estimated duration before generating any
audio -- but the target belongs here, next to the other structural rules,
not only as a downstream warning.

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

Edit this file directly — every skill that drafts copy or narration
re-reads it on every draft, so no code change is needed. If a draft doesn't sound right, say so and point at the
paragraph; that correction is what should get folded back into this file, the
same way `image_prompt_style.md` evolved from real feedback.
