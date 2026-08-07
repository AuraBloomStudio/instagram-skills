# Illustration styles — Constelaciones Familiares carousel slides

Reference read by `scripts/generate_post_image.py` when `--visual-style` is
anything other than `photo` (the default, which instead reads
`image_prompt_style.md` and is completely untouched by this file). Same
`<!-- BEGIN:X --> / <!-- END:X -->` marker convention: edit the blocks below
to tune the output, no code change needed for a pure wording change.

## Why a separate file from image_prompt_style.md

`image_prompt_style.md`'s rules (CAMERA_ANGLES to keep a *real* face
unidentifiable, COMPOSITION_ARCHETYPES, rotating SETTINGS) exist to solve
photorealism-specific problems. A cartoon or storybook face isn't a real,
identifiable person in the same sense, so forcing that machinery onto
illustration would be complexity without a matching benefit. Illustration
mode instead asks Gemini for a fitting scene directly, with a much shorter
rule set, and leans on `--protagonist` for cross-slide consistency.

## Known limitation: cross-slide consistency

Every call to `generate_post_image.py` is an independent, stateless request —
there's no shared seed or reference image between slides, only text. Warm
realistic photography tolerates that well; exact line weight, exact accent
color, and exact character design are harder to keep identical across
separate illustration calls with text alone. `--protagonist` plus precise
style wording (this file) is the "level 1" mitigation being used now. If
drift is visible in practice, especially for `storytelling`, level 2 would be
passing the first generated slide back into later calls as an image
reference (Gemini supports image+text multimodal prompts) — not implemented
yet, revisit only if level 1 proves insufficient.

## ILLUSTRATION_ANALYSIS_RULES (injected into the emotion/theme analysis step)

<!-- BEGIN:ILLUSTRATION_ANALYSIS_RULES -->
The visual_concept_en you write MUST center one or more characters expressing the emotion through pose, expression, and interaction -- never a symbolic object standing in for the metaphor (same veto as the photographic style: do not draw literal stones, chains, weights, or closed doors for "carrying a burden," "breaking free," etc. -- express it through the character's body and face instead).

Set the scene in an everyday, recognizable domestic moment (kitchen, living room, bedroom, park, etc.) consistent with the post's theme -- you choose whatever specific setting fits best, no forced rotation here.

PROTAGONIST: __PROTAGONIST__
<!-- END:ILLUSTRATION_ANALYSIS_RULES -->

## STYLE_MINIMAL

<!-- BEGIN:STYLE_MINIMAL -->
Minimalist line-art illustration: a simple, clean single-weight line drawing, no photorealism, no photographic shading. Either fully monochrome (dark line on a plain light background) or line art plus exactly one accent color used sparingly for emphasis (matching one of the BRAND_COLORS tones from image_prompt_style.md). Generous negative space around the subject -- the composition should feel calm and uncluttered, not dense. No gradients, no background clutter, no texture -- just the essential lines needed to read the scene. Figures are simplified and iconographic, not detailed portraits. No on-image text.
<!-- END:STYLE_MINIMAL -->

## STYLE_BOOK

<!-- BEGIN:STYLE_BOOK -->
Storybook illustration: warm, hand-painted children's-book art style (soft brushwork, gentle color blending, a slightly textured painterly finish), evoking a classic illustrated storybook rather than a photo or a modern flat-design graphic. The image sits inside a subtle decorative frame or border (a thin ornamental line or soft vignette), and the background reads as aged paper or parchment -- soft cream tones, faint visible grain, nothing distracting from the illustration itself. No on-image text.
<!-- END:STYLE_BOOK -->

## STYLE_CARTOON

<!-- BEGIN:STYLE_CARTOON -->
Cartoon illustration: flat-color cartoon style with expressive, slightly exaggerated character features, like the illustrations used in educational or social-media explainer content -- warm and approachable, not photorealistic and not a comic-book action style. Clean bold outlines, simplified shapes, a warm limited color palette matching the brand's warm tones. Everyday domestic scenes matching the post's setting, rendered as cartoon rather than photo. No on-image text.
<!-- END:STYLE_CARTOON -->

## STYLE_STORYTELLING

<!-- BEGIN:STYLE_STORYTELLING -->
Sequential-panel illustration: one panel of an ongoing illustrated mini-story, drawn in a consistent cartoon/storybook style meant to match the rest of this carousel -- same character design, same color palette, same linework style as if pages of the same comic. This panel depicts one distinct beat of the story progressing forward, not a repeated pose or a generic scene. No on-image text, no panel borders or comic-style gutters -- the image itself is the panel.
<!-- END:STYLE_STORYTELLING -->

## Changing the illustration styles later

Edit `STYLE_MINIMAL`, `STYLE_BOOK`, `STYLE_CARTOON`, or `STYLE_STORYTELLING`
for a pure look change, or `ILLUSTRATION_ANALYSIS_RULES` for how scenes get
conceived. `scripts/generate_post_image.py` re-reads this file on every run.
`--flat-color` and `BRAND_COLORS` (in `image_prompt_style.md`) are shared
across every visual style, including these four -- the hook/CTA "quote card"
slides don't change based on `--visual-style`.
