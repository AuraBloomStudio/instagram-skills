# Mixed visual style (60/30/10) — carousels and reels

Shared reference for the opt-in "mezcla" visual style: `--visual-style mezcla`
in `carrusel-constelaciones`, `--visual-mix` in `seleccion-clips-pexels`. Read
by both skills so the ratio, classification, and no-protagonist rules stay
identical between carousels and reels instead of drifting into two versions.

**This style is opt-in and additive.** Without it, both skills behave exactly
as before -- 100% Pexels photo/video for reels, 100% `photo` (or whichever
single illustrated style the user names) for carousels. Nothing about the
default path changes because this file exists.

## Why this exists

60% of any piece stays real Pexels stock (unchanged). The other 40% needed a
defined source: 30% flat conceptual illustrations, 10% structured diagrams.
Gemini-generated photorealistic faces are known to degrade in quality (see
`illustration_style.md`'s rationale for why the 4 character-illustration
styles avoid photorealism), so both new legs are designed to sidestep faces
entirely rather than lean on Gemini for something it's weak at:

- **Illustrations (30%)** -- `--visual-style mezcla-ilustracion` in
  `generate_post_image.py`. Still a Gemini Flash Image call, but a flat,
  faceless, conceptual/iconographic style (see `STYLE_MEZCLA_ILUSTRACION` in
  `illustration_style.md`) instead of a character scene.
- **Diagrams (10%)** -- `generate_diagram_image.py`, no Gemini call at all.
  Image-generation models are unreliable at rendering legible embedded text
  (labels, numbers), which is exactly what a diagram needs, so diagrams are
  drawn deterministically with Pillow instead.

## Scope: which slides/moments count

The ratio applies only to **content** slides/moments:

- Carousels: every slide EXCEPT the hook (slide 1) and the CTA (last slide),
  which always stay flat-color "quote cards" regardless of visual style --
  unaffected by "mezcla" the same way they're unaffected by `photo` vs. an
  illustrated style today.
- Reels: every one of the 6-8 narrated moments. The optional hook clip
  (`seleccion-clips-pexels`'s separate "Momento gancho" entry) is excluded
  from the ratio and always stays Pexels-sourced, same reasoning as the
  carousel hook slide.

## Classifying each slide/moment

Classify by what the slide/moment's content actually is, not at random:

- **Narrative/emotional** (a scene, "this is what it feels like") -> **photo**
  (Pexels, unchanged).
- **Conceptual/explanatory** ("here's how this works," an idea rather than a
  moment) -> **illustration**.
- **Structured/enumerated** (a numbered list, steps, signs/señales, a
  before/after pair) -> **diagram**.

## Apportionment: keeping 60/30/10 across N content slides/moments

Given N content units, compute ideal shares `0.6N / 0.3N / 0.1N`, floor each,
then distribute the remaining `N - sum(floors)` units one at a time to
whichever category has the largest fractional remainder -- ties broken in
this fixed order: **photo, then illustration, then diagram** (diagram never
wins a tie-break remainder; a diagram has to structurally earn its slot, not
get one from rounding).

With few content slides (N <= 4), 10% of N rounds to 0 under this method --
**do not force a diagram onto a small carousel/reel just to hit the ratio.**
If a genuinely structured beat exists, classify it as illustration instead
(see tie-break rule above) rather than manufacturing a diagram nobody needs.

Example (N=6, the common carousel/reel content-slide count): ideal shares are
3.6 / 1.8 / 0.6 -> floors 3 / 1 / 0 -> 2 units remain, largest remainders are
illustration (0.8) then diagram (0.6) -> final split 3 photo / 2 illustration
/ 1 diagram.

## No protagonist in illustration/diagram slides

Illustration and diagram slides/moments never depict a person and never take
`--protagonist`. Two reasons, not one:

1. **Consistency.** A carousel/reel that mixes a real Pexels protagonist with
   a drawn one mid-piece reads as visually broken -- the same "person"
   switching from a real face to a cartoon face between slides, worse in a
   reel where it's a hard cut mid-video. Keeping illustration/diagram
   conceptual and faceless removes the mismatch instead of trying to manage
   it.
2. **Safety.** Removes any residual risk of Gemini-generated-face quality
   issues, not just "usually avoids" it via non-photorealism like the 4
   character-illustration styles do.

## Diagram content and layout

`generate_diagram_image.py` renders a single fixed layout: a vertical
numbered-steps list (circle + number, connecting line, wrapped label text),
2-6 items. If the slide's/moment's own text is already a list (a "lista de
comportamientos" slide, a "3 señales" moment), use its items directly. If it's
conceptual but not literally a list, break its central idea into 2-4 short
sub-points for the diagram.

The top ~22% of the diagram canvas is left empty on purpose, matching the
photo/illustration negative-space convention for a Canva title overlay (see
`canva_title_style.md`) -- add the slide's short headline there by hand, same
as any other slide. Don't add a second title inside the diagram image itself;
the diagram's own item text is the only baked-in text.

## Choosing `--flat-color` for a diagram

Diagrams take `--flat-color` same as hook/CTA quote cards (`BRAND_COLORS` in
`image_prompt_style.md`), but the diagram's accent (numbered circles,
connecting line) is a fixed gold, independent of the chosen background --
pick a background color distinct from whatever hook/CTA colors that same
carousel/reel already used, same rotation spirit as step 9 of
`carrusel-constelaciones`.

## Consuming a generated illustration/diagram image in a reel

`edicion-reel-json2video`'s renderer already has a native `type: "image"`
element with Ken Burns zoom/pan for the "protagonist has no video, only a
photo" fallback case -- a generated illustration/diagram PNG slots into that
exact same path, no renderer changes needed. `orden_edicion.txt`'s parser
only requires a line matching `<filename>.png -- autor: <anything>` inside a
`Momento NN -- label` block; it does not care whether that file came from
Pexels or was generated locally. See `seleccion-clips-pexels`'s SKILL.md for
the exact block format to write for a generated moment.
