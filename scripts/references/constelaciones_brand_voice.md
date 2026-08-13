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
- **CTA:** one natural mention of the book *El dolor que no te pertenece*.
  The plain URL `https://eldolorquenotepertenece.com` — no UTM parameters, no
  shortened link, no more than this one link — goes **only in the caption**,
  never inside any slide's on-image text. Instagram doesn't make text inside
  an image clickable, so a link baked onto a slide is dead text, not a real
  CTA.
  - `post-constelaciones`: CTA + link go at the end of the on-image copy
    block, right after "Para asentar" and the bridge sentence (this is a
    caption-only post, so the "on-image copy block" IS the caption -- the
    link belongs there same as always).
  - `carrusel-constelaciones`: the CTA (bridge sentence + book mention) is
    the on-image text of the **last slide** -- but since that slide's link
    can't be clicked, its copy must say explicitly where the link actually
    is (e.g. "el link está en la descripción" / "link en la descripción"),
    never just trail off after naming the book as if the link were right
    there. The link itself still goes only in the caption.
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

## EDGE_CROP (composition rule, applies to every skill that selects or generates a photo)

**Never select or ship a photo where a person's head, face, or upper body is
abruptly cut off by a frame edge** (e.g. a head cropped mid-forehead, a chin
cut right at the top edge). This applies to every source: `search_pexels_photo.py`
(`carrusel-constelaciones`), `search_pexels_clips.py` (`seleccion-clips-pexels`),
and Gemini-generated photos (`post-constelaciones`, `imagen-post-constelaciones`,
`historias-constelaciones`). It is a composition/quality rule, completely
independent of the face-privacy rule (whether a face is *allowed* to be
identifiable or must stay hidden/turned away/backlit) -- a photo can pass the
privacy rule and still fail this one, and vice versa.

**What's still valid:** medium shots, hands, shoulders, backs, and a
deliberate full "framed from the shoulders/collarbone down" composition where
the head is entirely and cleanly outside the frame (see `CAMERA_ANGLES` option
5 in `image_prompt_style.md`). **What fails this rule:** a head that is
*partially* in frame and gets cut by the edge -- that reads as a cropping
mistake, not an intentional composition choice, whether or not the visible
part is recognizable.

**Detection is manual-first, same division of labor as every other visual
check in this pipeline** (see the documented Haar-cascade instability under
`_zone_has_face` in `generate_post_image.py` -- the same cascade can flip
between detecting and missing the same real face depending on a 1px crop
change): every mandatory visual review step (`seleccion-clips-pexels/SKILL.md`,
`carrusel-constelaciones/SKILL.md`, and the single-image skills' result step)
must explicitly check for this, by eye, before a photo ships. `generate_post_image.py`
also runs `detect_edge_cropped_head()`, an advisory-only frontal+profile
Haar-cascade pass over the whole frame that prints a warning when a detected
face's bounding box touches or nearly touches an edge -- it never blocks
generation or rejects a photo by itself, it only flags the frame for the
human doing the manual check.

**Real incident, confirmed 2026-08-13 (read before trusting either layer):**
"Ese Peso Que Cargas No Nació Contigo" regenerated with the "shoulders down"
composition (`CAMERA_ANGLES` option 5), and Gemini didn't cut the crop quite
as cleanly as the prompt asked -- a thin chin/jaw sliver ended up visible at
the top edge. `detect_edge_cropped_head()` found zero faces and printed no
warning (a chin alone has no eyes/nose to trigger either cascade -- a real,
confirmed blind spot, not a wiring bug). The manual review also missed it on
the first pass: the baked título/subtítulo text sat right over that exact
region and visually camouflaged the sliver against a glance at the whole
image. **The fix that actually matters: the manual check must physically
zoom/crop into each edge of the frame at full resolution, not just look at
the whole image once** -- especially the edge nearest wherever baked text
sits, and with extra scrutiny whenever the "shoulders down" archetype was
chosen (its very premise -- trusting Gemini to cut the frame exactly at the
neckline -- has now failed a real test).

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

## FACEBOOK_POST_STRUCTURE

Facebook posts are a separate format from the Instagram `POST_STRUCTURES`
rotation above -- extracted from analyzing the 10 highest-performing
Facebook posts, all of which converged on the same shape. Unlike Instagram
(5 rotating structures), Facebook uses **one single structure, no rotation,
no short-verse variant**: Estilo A, párrafo largo / ensayo reflexivo.

**Pattern (fixed order, every Facebook post):**

1. **Título en MAYÚSCULAS** -- una afirmación provocadora o una pregunta
   directa, nunca las dos combinadas.
2. **3-5 párrafos de desarrollo** que construyen hacia un reencuadre
   sistémico explícito (el mismo movimiento intelectual del "Voice
   fingerprint": nombrar la causa oculta detrás del síntoma visible, pero
   dicho sin rodeos, como una explicación, no solo insinuado).
3. **Cierre "Para asentar"** con una afirmación en primera persona **entre
   comillas** -- distinto del cierre de `post-constelaciones`/
   `carrusel-constelaciones`, que no usa comillas.
4. **CTA al libro correcto según el tema** (ver mapeo abajo) -- nunca el
   libro por defecto si el tema del post apunta claramente a otro.
5. **4-5 hashtags**: 2-3 genéricos de marca + 2-3 específicos del tema
   (distinto del esquema fijo 2+3 de Instagram; aquí el conteo total varía
   entre 4 y 5).
6. **Extensión del cuerpo del post: aproximadamente 1,500-2,200 caracteres.**

**No signature.** Never close with "por Diana Barreto" or any attribution
line -- the 10 reference posts never use one.

**No "comenta la palabra X" mechanic.** Do not ask readers to comment a
specific trigger word to unlock something. Instead invite open opinion in
the comments, then move straight into the book CTA -- e.g. "¿Qué opinan? Los
leo en los comentarios." followed by the CTA sentence for the mapped book.

**Book CTA mapping (by ecosystem/theme) -- Facebook only:**

| Tema / ecosistema del post | Libro del CTA |
|---|---|
| Dolor | *El dolor que no te pertenece* |
| Dinero | *El dinero y el lugar que ocupas* |
| Mamá | *Sanando con Mamá* |
| Papá | *Sanando con Papá* |
| Regreso | *El Regreso* |

If a post's theme doesn't map cleanly to one of these five, default to *El
dolor que no te pertenece* (the standing offer, same fallback logic as the
Instagram CTA rule above) unless the user says otherwise for that post.

## POST_VIRAL_STRUCTURE

`post-viral-constelaciones` reads this section, not `FACEBOOK_POST_STRUCTURE`
above -- a different pair of high-conversion viral Facebook formats, kept
separate because neither variant follows the essay-paragraph shape or the
"Para asentar" closer that `FACEBOOK_POST_STRUCTURE` requires. There is no
pool of choices here: exactly **two fixed variants**, each with its own
literal fixed header, that strictly **alternate** rather than rotate (see
"Alternation" below).

**Address exception (read before drafting either variant).** The Voice
fingerprint's "tú" rule does not apply to this section. Variante 1 uses
formal **"usted"** throughout -- a deliberate register shift for the
direct-address "you should know" viral format, not a mistake to correct
back to "tú." Variante 2 uses no second-person address at all (a first-person
decree spoken to "mis hijos"). Neither variant uses "Para asentar" -- the CTA
described below is each variant's only closer mechanic, replacing it
entirely.

**VARIANTE 1 -- "USTED DEBERÍA SABER QUE:"**

- Encabezado fijo, literal, siempre igual: `USTED DEBERÍA SABER QUE:`
- Párrafo 1: nombra un patrón sistémico concreto y su consecuencia (p. ej.
  intervenir en la vida de otros, sostener económicamente a los padres,
  silencio evitativo, salvar a otros), en tono directo de segunda persona
  formal ("Su... es...").
- Párrafo 2: abre con "Reconozca que..." o "Comprenda que...", da el
  reencuadre sistémico (qué hacer distinto), y cierra con una frase en
  primera persona **entre comillas** que reafirma una jerarquía familiar
  sana (ej. "Yo soy la grande y tú eres el pequeño...", "Respeto sus
  problemas y su destino tal como son...").
- Extensión total (sin contar el CTA): 900-1,300 caracteres.
- Sin hashtags, sin firma.

**VARIANTE 2 -- "GUARDA ESTE DECRETO EN TU CORAZÓN"**

- Encabezado fijo, literal: `GUARDA ESTE DECRETO EN TU CORAZÓN`, seguido de
  un subtítulo variable **en cursiva** que describe el tema específico del
  decreto (ej. *"Para activar la prosperidad y el camino de tus hijos"*).
- Cuerpo: decreto/oración en primera persona dirigida a los hijos, tono de
  bendición/afirmación positiva -- sin reencuadre de conflicto, a
  diferencia del movimiento "nombrar la causa oculta" que rige el resto de
  la marca.
- Cierre fijo, literal: `Así es. Gracias, gracias, gracias.` o la variante
  `Hecho está. Gracias.`
- Extensión total (sin contar el CTA): 700-1,000 caracteres.
- Sin hashtags, sin firma.

**CTA obligatorio en ambas variantes (esto es lo nuevo que aporta este
skill -- los ejemplos originales que inspiraron ambas variantes no lo
tenían).**

- Va DESPUÉS del cierre de cada variante: después de la frase entre
  comillas en la Variante 1; después de "gracias, gracias, gracias." (o
  "Hecho está. Gracias.") en la Variante 2.
- Bridge corto, 1-2 líneas, que conecta el tema tratado con el libro
  correcto usando la MISMA tabla de mapeo tema -> libro de
  `FACEBOOK_POST_STRUCTURE` (Dolor, Dinero, Mamá, Papá, Regreso) -- no se
  duplica la tabla aquí, se reutiliza tal cual, incluido el mismo
  fallback a *El dolor que no te pertenece* cuando el tema no mapea
  limpiamente.
- Siempre cierra con la frase literal `El link está en la descripción.` --
  nunca el link inline, mismo principio que el CTA de carrusel: una pieza
  pensada para copiar y pegar directo en Facebook no puede asumir que un
  link dentro del texto sea clicable, así que la instrucción siempre remite
  a la descripción/bio.
- El tono del bridge se adapta a la variante, nunca al revés:
  - Variante 1: directo, en línea con el registro de instrucción/consejo
    de la pieza -- ej. "Si este patrón te tocó, en '[libro]' encontrarás
    cómo soltarlo."
  - Variante 2: mantiene el tono suave de decreto/bendición, nunca un giro
    abrupto a venta -- ej. "Si quieres profundizar en esta sanación, te
    espera '[libro]'."
- El CTA nunca rompe el ritmo ni el registro emocional de la pieza -- debe
  leerse como una continuación natural del cierre, no como un corte
  publicitario pegado al final.

**Alternation (not random rotation).** `post-viral-constelaciones` tracks
the last variant used in `testing/copy_gen_state.json`, key
`"post_viral_variant"` -- a single string ("1" or "2"), not a list like the
other rotation keys, since with only 2 possible values "avoid the last 2"
would mean "never repeat," which strict alternation already guarantees more
simply. Each new piece uses whichever variant is NOT the stored value, then
overwrites it. When generating the daily pair of 2 pieces in one request,
produce one of each variant (in either order) rather than reading state
twice for the same request.

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

**Design mix (fixed, not random):** every slide, including the CTA, carries
a real Pexels photo background (see "Photo sourcing: Pexels, not Gemini"
below) -- no slide uses the flat-color "quote card" treatment from
`BRAND_COLORS` in `image_prompt_style.md` anymore. The CTA was the last
holdout (a real carousel test showed a plain color card reads as a weaker,
disconnected closer next to five photo slides sharing one protagonist); now
every slide, hook through CTA, shows the same protagonist/setting coherence
front to back. This mix repeats on every carousel; it is not optional or
randomized per slide. Baked text per slide type (all via
`generate_post_image.py`'s `render_headline`):
- **Hook (slide 1) only:** título (Poppins Bold `#F2A900`) + subtítulo
  (Playfair Display italic `#FAE8A8`) + a third short line
  (`--headline-extra`, Poppins SemiBold, same pale gold as the subtitle).
  This is the ONLY slide in the carousel that carries a gold title/subtitle
  -- content slides, "Para asentar," and the CTA dropped theirs (see next
  bullet).
  **Placement is forced, deliberate exception:** the hook always uses
  `--force-center-zone`, which bakes the title dead-centered on the whole
  frame with NO face check at all -- if that covers the protagonist's face,
  it covers it, on purpose. This replaces the earlier "safe zone" logic
  (top/bottom picked by an OpenCV face veto, later a middle-band
  preference) that still left the hook feeling unbalanced or empty-heavy on
  real renders; simple fixed centering reads better than any face-avoiding
  placement tried so far. **This exception is limited to the hook slide
  only.** Every other slide of the carousel, and every other skill that
  bakes text (`imagen-post-constelaciones`, `post-constelaciones`,
  `historias-constelaciones`), still runs the normal OpenCV face veto
  unchanged -- covering a face there remains a hard defect, not a style
  choice.
- **Content slides, "Para asentar," and the CTA** (every slide after the
  hook): ONLY that slide's full paragraph, baked as `--body-text` -- Poppins
  Bold, warm white `#F5F0E6` (same color as the reel narration subtitles;
  was cyan `#22D3EE` until user feedback that white read as more legible
  and more cohesive with the brand's warm photo tones), with a dark
  gradient scrim behind it for contrast (same stops as
  `render_reel_json2video.py`'s `GRADIENT_HTML_TEMPLATE`). **No gold title,
  no italic subtitle, no `--headline-main`/`--headline-accent` at all** --
  the earlier per-slide "mini-title" look (each content slide behaving like
  its own small hook) was dropped per user feedback; every slide after the
  hook is body-text only now, and `generate_post_image.py` accepts
  `--body-text` on its own without requiring `--headline-main` for exactly
  this reason. Placement keeps the normal OpenCV face veto (top/bottom,
  never forced center -- that exception is the hook's alone). This is new
  text on the image, not just a distilled headline -- the reader should be
  able to read the actual microdolor (or, for the CTA, the full bridge)
  without opening the caption. The CTA's `--body-text` is the bridge
  paragraph itself (see the CTA rule above).

**Photo sourcing: Pexels, not Gemini.** Every slide (hook + content + Para
asentar + CTA -- the whole carousel, no exceptions) is a real stock photo
from Pexels, sourced with the exact same
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

**Paquete 1 (`post-constelaciones`/`imagen-post-constelaciones`) now bakes
título+subtítulo, same typography system as this carousel's hook -- but
NEVER a CTA, unlike this carousel.** Until 2026-08-12 these two skills left
the title entirely for a manual Canva step (`TITLE_TYPOGRAPHY` in
`canva_title_style.md`); they now pass `--headline-main`/`--headline-accent`
to `generate_post_image.py` directly, so the PNG ships with título (Poppins
Bold `#F2A900`) and subtítulo (Playfair Display italic `#FAE8A8`, typically
the post's "Para asentar" line) already baked in -- no manual Canva step for
these two anymore. Placement always uses the normal OpenCV face veto (never
`--force-center-zone`, which stays this carousel's hook-only exception).

**Hard rule, permanent (2026-08-13): Paquete 1's image NEVER carries a baked
CTA** -- no book mention, no "el link está en la descripción" line, nothing
via `--body-text`. This is a deliberate difference from this carousel's CTA
slide, not an oversight: the carousel's CTA gets its own dedicated slide with
nothing else competing for attention, while a single-image post only has one
frame total, and título+subtítulo+CTA together read as cluttered and compete
with the título for attention (confirmed against a real render before this
rule was set). The full CTA (book + link) keeps living exclusively in the
copy/caption `.docx`, unchanged -- baking título/subtítulo never touches that.
`historias-constelaciones` is unaffected and stays fully manual -- see
`canva_title_style.md`.

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
   "Para asentar" (foto + body-text). Slide 6 es el CTA (foto + body-text).
2. **Lista de comportamientos en paralelo.** 6-8 slides depending on how many
   behaviors fit the topic: hook (foto) + 3-5 behavior slides (foto +
   body-text) + "Para asentar" (foto + body-text) + CTA (foto + body-text).
   Mínimo 3 comportamientos para llegar a 6 slides.
3. **Antes / Después.** 6 slides, siempre (ya no hay variante corta): el
   contraste se desarrolla en dos beats por lado en vez de uno. Slide 1 =
   "Antes" -- cómo se ve/siente el patrón viejo (hook, foto). Slide 2 =
   "Antes" -- una consecuencia concreta de ese patrón (foto + body-text).
   Slide 3 = "Después" -- qué cambia al soltarlo (foto + body-text). Slide 4
   = "Después" -- qué se gana (foto + body-text). Slide 5 = "Para asentar"
   (foto + body-text). Slide 6 = CTA (foto + body-text).
4. **Preguntas de autodiagnóstico.** 6-8 slides depending on how many signs
   fit: hook (foto) + 3-5 self-check question slides (foto + body-text) +
   "Para asentar" (foto + body-text) + CTA (foto + body-text). Mínimo 3
   preguntas para llegar a 6 slides.
5. **Mini-historia con giro: situación → tensión → punto de quiebre →
   revelación → Para asentar → CTA.** 6 slides, siempre. Slide 1 sets the
   situation (hook, foto). Slide 2 the tension building up (foto +
   body-text). Slide 3 the specific breaking point/momento crítico (foto +
   body-text). Slide 4 the revelation/reframe (foto + body-text). Slide 5 is
   "Para asentar" (foto + body-text). Slide 6 is CTA (foto + body-text).

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

## PACKAGING_STANDARD

**Applies to:** `post-constelaciones`, `carrusel-constelaciones`,
`imagen-post-constelaciones`, `post-viral-constelaciones` -- these four call
`scripts/build_paquete_docx.py` to produce a `PAQUETE - *.docx`.
`edicion-reel-json2video` doesn't build a `.docx` package (a reel is a
video) but DOES share the same day+micronicho folder via its own
`--micronicho` flag (see "Numbered subfolders" below) -- it counts as part
of this standard's folder convention even though it never touches
`build_paquete_docx.py`. Does NOT apply to `historias-constelaciones`
(Stories skip hashtags/CTA/book entirely per `STORY_STRUCTURES`, so the
normal packaging shape has nothing to consolidate -- see the
`Carrusel Historias/` note below for how a Story's package is still handled
today) or to `seleccion-clips-pexels`/`narracion-voz-gemini` (intermediate
reel assets, never a publish-ready piece on their own).

Each of the four skills above, in addition to whatever per-format artifacts
it already saves (the individual slide `.docx`/caption files for
`carrusel-constelaciones`, the single copy `.docx` for `post-constelaciones`,
the images in `Desktop/Imagenes Posts/...`, etc. -- **this rule never
replaces those, and none of them move**; the packaging step only adds one
more file on top), also saves ONE consolidated file into a fixed,
numbered subfolder of the day's publication folder:
`Desktop/Constelaciones - Publicaciones/<fecha YYYY-MM-DD> <slug de
micronicho>/<subcarpeta fija del tipo de pieza>/PAQUETE - <hook o tema de la
pieza>.docx`. This is the single file a human actually opens to publish the
piece -- everything they need to copy-paste, in one place, in a fixed order,
so nothing requires hunting across separate slide files or a mental
checklist.

**Carpeta por día + micronicho, no por skill ni por formato.** Before this
folder existed, each skill's packaged file sat next to its own raw output
(`Desktop/Posts Constelaciones/`, or `Virales/` for
`post-viral-constelaciones`), which meant a single day's campaign around one
micronicho ended up with its finished pieces scattered across several
folders. `Desktop/Constelaciones - Publicaciones/<fecha> <slug>/` fixes
that: every `PAQUETE - *.docx` generated for the same micronicho on the same
day lands in the SAME day folder, regardless of which skill produced it --
a carousel, a static post, and both viral pieces from one day's package all
end up as siblings inside it, ready to hand off. The folder (and each
numbered subfolder inside it) is created on first use (`mkdir -p`
semantics) and reused by every later call with the same date+slug, never
recreated.
- **`<fecha>`** is today's date, `YYYY-MM-DD`, computed automatically by
  `scripts/build_paquete_docx.py` unless a piece is explicitly backdated.
- **`<slug de micronicho>`** is a short kebab-case slug (same convention
  `carrusel-constelaciones`/`seleccion-clips-pexels` already use for their
  own slugs) that names the micronicho/topic of the day, NOT the individual
  piece's own hook -- those are two different things and must not be
  confused. A carousel hooked "Ese Miedo Que Sientes No Es Tuyo" and a
  static post hooked "Ese Peso Que Cargas No Nació Contigo" can both belong
  to the same day's micronicho slug `dolor-heredado` even though neither
  hook contains that string. **Whenever a piece is drafted as part of a
  broader daily package together with sibling pieces on the same topic
  (requested in the same conversation), reuse the EXACT SAME micronicho
  slug across every sibling** -- never derive a fresh slug per piece just
  because each piece's own hook differs. Only derive a new slug from a
  piece's own topic when it's a standalone request with no sibling pieces
  that day.
- This folder is exclusively for the consolidated `PAQUETE` files and the
  finished `reel_final.mp4`. Every other artifact each skill produces along
  the way (slide `.docx`, caption `.docx`, plain copy `.docx`, plain PNG
  images) keeps saving exactly where it already did -- `Desktop/Posts
  Constelaciones/`, `Desktop/Posts Constelaciones/Virales/`, `Desktop/
  Imagenes Posts/`, `Desktop/Imagenes Posts/<slug>/` -- unchanged. This was
  a deliberate choice, not an oversight: only the final publish-ready
  artifact needed a cleaner home, not every intermediate file.

**Numbered subfolders, one per piece type, fixed names (never freeform):**
```
<fecha> <slug de micronicho>/
├── Paquete 1 - Imagen y Texto Largo/      <- post-constelaciones,
│                                             imagen-post-constelaciones
├── Paquete 2 - Carrusel/
│   ├── Carrusel Publicación/              <- carrusel-constelaciones
│   └── Carrusel Historias/                <- carrusel-constelaciones's own
│                                             step 17 (6-slide 9:16 reuse of
│                                             the feed carousel, see below);
│                                             historias-constelaciones is a
│                                             separate, unpackaged skill for
│                                             a standalone Story
├── Paquete 3 - Texto Reflexivo/           <- post-viral-constelaciones
│                                             (both variants land here,
│                                             one PAQUETE file each)
├── Paquete 4 - Reel/                      <- edicion-reel-json2video
│                                             (reel_final.mp4, not a
│                                             build_paquete_docx.py file)
└── RESUMEN DEL DÍA.docx                   <- at the top level, not inside
                                               a numbered subfolder
```
`scripts/build_paquete_docx.py`'s `--tipo-pieza` flag
(`imagen-texto`/`carrusel`/`carrusel-historia`/`texto-reflexivo`) computes
the exact subfolder via its `PIECE_TYPE_SUBFOLDERS` constant, so every skill
produces byte-identical folder names instead of each one typing its own
slightly different spelling. `edicion-reel-json2video` doesn't call
`build_paquete_docx.py` at all (a reel is a video, not a `.docx` package) --
`scripts/render_reel_json2video.py` computes `Paquete 4 - Reel/` itself from
its own `--micronicho`/`--fecha` flags.

**`Carrusel Historias/` is now automated -- carrusel-constelaciones's own
step 17, not `historias-constelaciones`.** The originally-planned redesign
("Stories as a carousel-adapted format instead of a standalone shape")
shipped: `carrusel-constelaciones` can optionally also produce a 6-slide
9:16 "Carrusel Historias" package right after building its normal feed
`PAQUETE`, reusing the exact same hook + first 3 content slides (in
published order) + "Para asentar" + CTA of that same feed carousel -- same
photos, same baked text, only re-cropped to `--aspect 9:16`, with the CTA's
closing "en la descripción" swapped for "en mi bio" (Stories has no caption
field, so the original phrasing would be false there). No new copy is
drafted and no new Pexels search runs. Its `PAQUETE - <hook>.docx` still
skips the primer-comentario section (`--primer-comentario` stays optional
in `build_paquete_docx.py` for exactly this reason) since Stories has no
first-comment mechanic -- the CTA that matters is already baked onto the
last image, unlike the feed version where it lives in a separate comment.
**`historias-constelaciones` still exists and is unchanged** for a Story
requested on its own, with its own topic, with no feed carousel behind it
that same day -- it is not part of PACKAGING_STANDARD's "Applies to" list
above (Stories carry no CTA/book/hashtags by design when drafted that way,
see `STORY_STRUCTURES`), and its output still isn't packaged into a
`PAQUETE`.

**Daily package volume, per numbered subfolder:**
```
Paquete 1 - Imagen y Texto Largo/     1 pieza  (post-constelaciones)
Paquete 2 - Carrusel/                 2 piezas (carrusel-constelaciones: el
                                       carrusel de feed normal, MÁS su
                                       versión Carrusel Historias -- ver
                                       arriba, ambas del mismo carrusel)
Paquete 3 - Texto Reflexivo/          2 piezas (post-viral-constelaciones:
                                       Variante 1 + Variante 2, comportamiento
                                       ya existente, sin cambios)
Paquete 4 - Reel/                     2 piezas (edicion-reel-json2video)
```
- **Paquete 2 nunca es "un carrusel + una historia distinta"** -- son
  siempre EL MISMO carrusel en dos formatos (ver el bloque de arriba); no
  hay redacción ni búsqueda de fotos por separado para la pieza 2 de este
  paquete.
- **Paquete 4 son 2 reels cubriendo 2 ángulos distintos del mismo
  micronicho, ambos con guion redactado por el asistente** (no se le pide
  al usuario que escriba los guiones) -- mismo criterio de longitud
  (`REEL_SCRIPT_LENGTH`, 108-136 palabras cada uno) y mismo proceso completo
  (`seleccion-clips-pexels` + `narracion-voz-gemini` +
  `edicion-reel-json2video`) para cada uno, con su propio `<reel_slug>`
  distinto por reel pero el MISMO `--micronicho` para que ambos caigan en
  `Paquete 4 - Reel/` -- ver la nota de namespacing por `reel_slug` en
  `edicion-reel-json2video`'s `SKILL.md` (el nombre de archivo final es
  `reel_final_<reel_slug>.mp4`, no un `reel_final.mp4` fijo, precisamente
  porque esa carpeta ahora es compartida por 2 reels).
- Este es el volumen estándar del paquete diario completo (7 piezas
  publicables + `RESUMEN DEL DÍA.docx`) salvo que el usuario pida
  explícitamente un subconjunto para un día puntual.

**Fixed section order, same for all four skills:**

1. **Imagen(es).** Inserted directly into the `.docx` (not just referenced
   by path) via `python-docx`'s `add_picture`, one per image, in publish
   order (slide 1 -> N for carousels). Each image also gets a one-line
   caption underneath with its file path, for traceability back to
   `Desktop/Imagenes Posts/...`. `post-viral-constelaciones` never has an
   image (it's deliberately text-only per `POST_VIRAL_STRUCTURE`) -- this
   section is omitted entirely for that skill, never left as an empty
   placeholder.
2. **Copy / caption completo.** The exact text a human pastes into
   Facebook/Instagram, verbatim from whatever was already approved --
   never re-summarized or rewritten for the package. For
   `carrusel-constelaciones` this is the caption (not the 7 individual
   slide paragraphs, which are already baked onto the images themselves).
   For `imagen-post-constelaciones` this is the copy text from the file
   the user handed it (written elsewhere, not by this skill) -- included
   for completeness, not re-authored.
3. **Primer comentario (CTA).** A NEW text, not previously part of any of
   these skills' output -- short, 2-3 lines, its own CTA to the book
   mapped by topic using the SAME topic -> book table as
   `FACEBOOK_POST_STRUCTURE` (Dolor, Dinero, Mamá, Papá, Regreso; same
   fallback to *El dolor que no te pertenece* when the topic doesn't map
   cleanly) -- reused as-is, never a second table. Must be worded
   DIFFERENTLY from whatever CTA sentence already lives in the main
   copy/caption, so the two don't read as a repeated line if someone
   reads both back to back. Example shape: "Si esto resonó contigo 👇 En
   'El dolor que no te pertenece' encontrarás cómo soltarlo. Link en la
   descripción." This field is independent of whichever book the main
   copy's own CTA already named (that rule is unchanged, see "Closer,
   CTA, and hashtags" above) -- the primer comentario is free to point to
   the topic-correct book even when the main copy used the standing
   *El dolor que no te pertenece* offer. `--primer-comentario` is
   technically optional in `build_paquete_docx.py` (the section is simply
   omitted when absent), but for these four skills it is mandatory in
   practice -- the flag only exists as an escape hatch for a manual
   `Carrusel Historias/` package, which has no CTA to give it.
4. **Hashtags.** Only included when the format already uses hashtags per
   its own structure rules -- `post-constelaciones` and
   `carrusel-constelaciones`: yes (pulled from the last paragraph of the
   copy/caption, which is always the hashtag line per the "Closer, CTA,
   and hashtags" rules above -- mirrored into its own section for quick
   copy-paste, not re-invented). `post-viral-constelaciones`: no,
   `POST_VIRAL_STRUCTURE` is explicit that neither variant carries
   hashtags -- section omitted. `imagen-post-constelaciones`: inherits
   whatever hashtags the copy file it's illustrating already has, via the
   same last-paragraph extraction; never invents new ones.
5. **Checklist.** Fixed four lines, identical wording every time, always
   last in the document:
   ```
   [ ] Imagen revisada visualmente
   [ ] Copy revisado
   [ ] Primer comentario listo
   [ ] Publicado
   ```

**Implementation:** `scripts/build_paquete_docx.py` assembles the file from
already-saved inputs (the copy/caption `.docx` this skill or a sibling
skill already wrote, the final image path(s), and the primer-comentario
text drafted for this specific piece) -- it never re-derives copy or
re-decides the CTA book itself, those decisions stay with whoever is
drafting the piece. `--tipo-pieza <tipo>` and `--micronicho "<slug>"`
together compute the `Desktop/Constelaciones - Publicaciones/<fecha>
<slug>/<subcarpeta fija>/` destination automatically (today's date unless
`--fecha` overrides it) and are both mandatory unless `--out-dir` is passed
as an explicit one-off override. `scripts/render_reel_json2video.py`
mirrors the same `--micronicho`/`--fecha` flags for `Paquete 4 - Reel/`
(its own script, not `build_paquete_docx.py`, since a reel has no `.docx`
to assemble). See each script's `--help` for exact arguments; every
relevant skill's own `SKILL.md` documents the specific call it makes.

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
