# Master image prompt — Constelaciones Familiares post backgrounds

Reference read directly by `scripts/generate_post_image.py` at runtime. Edit the
fenced blocks below to change what the script generates — no code changes needed
for a style tweak. Each block is delimited by an HTML-comment marker pair
(`<!-- BEGIN:X -->` / `<!-- END:X -->`); the script extracts the text between the
markers verbatim, so keep the markers intact and put your edits inside them.

This file governs the BACKGROUND PHOTO only. Title and signature text are added
afterward by hand in Canva — Gemini never generates on-image text.

## Why this file exists

Early versions of the prompt translated the copy's metaphors literally: a line
about "releasing the weight of others' problems" produced a photo of hands
setting down a physical stone. That reads as generic stock-photo symbolism, not
as an emotional, editorial photograph. The fix: always put people at the center
of the frame, and translate the emotion into their body language instead of
into a prop.

A second round fixed two more drifts: the settings kept turning into open
landscapes and stone paths (mountain vistas, forest trails) instead of the
everyday domestic moments this brand's posts are actually about, and the
posture/body language was a generic "figure turned away" regardless of which
emotion the copy analysis actually detected. Both are now explicit rules, not
left to the model's default instincts.

A third round fixed a related drift: the face-concealment technique itself was
almost always "shot from behind" -- correct per the anonymity rule, but
repetitive across a full batch of posts. CAMERA_ANGLES now separates "how many
people and what are they doing" (COMPOSITION_ARCHETYPES) from "how is the face
kept unidentifiable" (CAMERA_ANGLES), and rotates both independently.

A fourth round dropped the soft-focus camera angle entirely (it read as
artificial/uncanny in practice, not like a real shallow-depth-of-field photo)
and added two carousel-specific needs: a `PROTAGONIST` slot so every slide in
one carousel can be told to depict the same person (gender/age presentation),
not a different generic figure each call, and a `BRAND_COLORS` palette for the
flat-color "quote card" slides that `carrusel-constelaciones` uses for its
hook and CTA slides -- those skip photo generation entirely.

A fifth round softened two things that read as too harsh in practice: the
backlit-silhouette camera angle was going near-black and losing all scene
detail (fixed to ask for gentle fill light instead), and `BRAND_COLORS` was
too saturated/vibrant for a quote-card background (muted toward a dustier,
more vintage tone).

A sixth round fixed the opposite problem: shots were going too wide and flat.
A full establishing shot (garden plus a visible kitchen interior at once) left
the protagonist tiny in the frame, competed with itself for attention, used
even/flat lighting with no drama, and left no clean area for a title to sit
on top of afterward in Canva. Framing, background simplicity, light contrast,
and negative space are now explicit rules instead of left to chance.

## Hard rules

- **People are always the subject.** Never a symbolic object (stones, chains,
  keys, weights, closed doors, ropes, cracked glass, etc.) standing in for the
  emotion as the main element of the frame. A prop may appear only as
  incidental environment detail, never as the thing the image is "about."
- **Conceptual, not literal, translation.** Read the copy's metaphor and
  re-express the *feeling* through a human scene, not the metaphor's literal
  imagery. See the conceptual-translation examples block below.
- **Everyday, recognizable settings.** The scene happens in an ordinary,
  close-to-home location: a kitchen, a living room, a patio or porch, a
  sidewalk, a neighborhood park, a dining table, a balcony, a bedroom. Never
  an open landscape, a stone path/trail, a forest, or a generic
  artistic/cinematic backdrop. It should read as a real domestic or everyday
  moment, not an abstract film production. The script rotates through the
  settings block below and tells the analysis step exactly which location to
  use for this run, so the same room doesn't repeat across consecutive posts.
- **Body language matches the specific emotion.** The posture, gaze, and
  physical distance or contact between people must be a concrete translation
  of the exact emotion this copy was analyzed as (`emotion_en`) -- not a
  generic pose reused for every post. See the emotion -> body-language
  examples inside ANALYSIS_RULES below.
- **Composition variety.** Do not default to "one person alone, seen from
  behind, walking away" every time. The script rotates through the composition
  archetypes block below and tells the analysis step which one to use for this
  run, so the same framing doesn't repeat across consecutive posts either.
- **Anonymity, with a varied technique.** Faces are never sharply focused or
  identifiable, and never a recognizable real person, public figure, or
  celebrity likeness. Achieve this through angle, distance, focus, framing, or
  lighting — not by literally erasing or blurring faces in post. Do not
  default to "shot from behind" every time: the script rotates through the
  camera-angles block below and tells the analysis step which specific
  technique to use for this run, so the same technique doesn't repeat
  back-to-back.
- **No on-image text.** No letters, words, numbers, captions, logos, or
  watermarks anywhere in the image.
- **Color and light.** Full color, cinematic, warm (golds, amber, sunset light
  or soft warm interior light), a film-still / editorial look. Never
  black-and-white, never desaturated, never an old/antique sepia look.
- **Framing: medium or medium-close shot.** The protagonist must fill most of
  the vertical frame, close enough to read their posture and emotion clearly.
  Never a wide establishing shot where the person is small against a large
  environment. Background stays simple and out of focus (shallow depth of
  field) -- one environment only, never two competing zones at once (e.g. not
  an exterior garden and a visible interior room in the same shot).
- **Light and contrast: directional, not flat.** Use a clear light source and
  visible shadow (window light, a doorway, a lamp, golden-hour sun) so the
  image has real contrast and drama, never even, shadowless, all-around
  lighting.
- **Negative space for text.** Leave one clean, uncluttered area (a plain
  wall, soft blurred background, open sky, or shadow) in the top third or
  bottom third of the frame where a title or signature can sit afterward in
  Canva without fighting busy detail.
- **Aspect ratio.** Whatever `--aspect` the calling skill passes to
  `generate_post_image.py` (default 4:5 vertical / 1080x1350px for feed
  posts; 9:16 / 1080x1920px for Stories; 1:1 / 1080x1080px also supported).
  The exact aspect-ratio sentence appended to the prompt lives in code
  (`ASPECT_RATIO_SPECS`), not in `BRAND_STYLE` below, so the written prompt
  always matches the aspectRatio actually sent to the Gemini API. Don't add
  an aspect-ratio sentence back into `BRAND_STYLE` -- it would go stale the
  moment a skill requests a different ratio.

## BRAND_STYLE (verbatim prompt suffix, appended after the scene description)

<!-- BEGIN:BRAND_STYLE -->
Cinematic color photography, warm lighting (golds, amber, sunset light or soft warm interior light), a film-still / editorial aesthetic like a well-shot production with strong cinematography. Full color, never black-and-white or desaturated; a nostalgic warmth, not an old sepia look. Directional, dramatic light with a clear source and visible shadow (window light, doorway light, lamp light, or golden-hour sun) -- never flat, even, shadowless lighting. Shallow depth of field, subtle grain. Medium or medium-close shot: the protagonist fills most of the vertical frame, close enough to read their posture and emotion clearly -- never a wide establishing shot where the person is small against a large environment. Background stays simple and softly out of focus, one environment only, never two competing zones at once (e.g. not an exterior garden and a visible interior room in the same shot). Leave one clean, uncluttered area (a plain wall, soft blurred background, open sky, or shadow) in the top third or bottom third of the frame free of visual clutter, for a title or signature to sit on afterward. Set in an ordinary, recognizable everyday location (a kitchen, a living room, a patio or porch, a sidewalk, a neighborhood park, a dining table, a balcony, a bedroom) -- never an open landscape, a mountain vista, a stone path or trail, a forest, or a generic artistic/cinematic backdrop; this should feel like a real domestic or everyday moment, not a staged production. The scene is always built around one or more generic human figures conveying the emotion through posture, gesture, and interaction -- never through a symbolic object (no stones, chains, keys, weights, closed doors, ropes, or similar props standing in for the feeling). Faces are never sharply focused or identifiable, and never a recognizable real person, public figure, or celebrity likeness; achieve this through angle, distance, or framing (shot from behind, face turned away, face out of frame, or silhouette). Absolutely no text, letters, words, numbers, captions, logos, or watermarks anywhere in the image; this is a bare photographic background, any title or signature will be added separately afterward.
<!-- END:BRAND_STYLE -->

## COMPOSITION_ARCHETYPES (the script rotates through these, avoiding the last 2 used)

<!-- BEGIN:COMPOSITION_ARCHETYPES -->
1. A single generic figure, alone, standing or walking, expressing the emotion purely through posture and the line of their body.
2. A single generic figure in a still, contemplative pose (sitting, leaning against something, head down or tilted, a hand resting on their own chest or shoulder), expressing the emotion through stillness and posture.
3. Two generic figures interacting -- one comforting, supporting, embracing, or holding the other -- expressing the emotion through the physical interaction between them.
4. Two or more generic figures walking together, sitting together, or gathered as a small family group, expressing the emotion through their collective body language, spacing, and closeness (or distance) to each other.
5. A close, cropped shot centered on hands and partial bodies only -- one person's hand on another's shoulder or back, hands clasped together, or hands gently guiding another person -- expressing the emotion through gesture alone.
<!-- END:COMPOSITION_ARCHETYPES -->

## CAMERA_ANGLES (how the face stays unidentifiable; the script rotates through these, avoiding the last 2 used)

<!-- BEGIN:CAMERA_ANGLES -->
1. Shot from directly behind -- the figure's back fully to the camera, no part of the face visible.
2. A profile or three-quarter angle where the face is turned away from camera or falls outside the frame because of the angle, not because of blur.
3. A softly backlit figure against a bright window, doorway, or light source, with gentle fill light keeping some shape, texture, and scene detail visible -- a warm rim-lit look, never a hard, near-black, detail-less silhouette.
4. A tight close-up on hands and gesture only, cropped so no face is in frame at all.
5. Framed from the shoulders or collarbone down -- the head is deliberately outside the top edge of the frame.
<!-- END:CAMERA_ANGLES -->

## SETTINGS (the script rotates through these, avoiding the last 2 used)

<!-- BEGIN:SETTINGS -->
1. A home kitchen -- near the counter, sink, stove, or kitchen table.
2. A living room -- on or near a sofa, armchair, rug, or coffee table.
3. A dining table set in a dining room or open-plan area, not mid-meal.
4. A patio, porch, or backyard, in natural late-day or early-morning light.
5. A bedroom -- sitting on the edge of the bed, or near a window or dresser.
6. A balcony overlooking a street or the neighborhood.
7. A sidewalk or front steps just outside a home, in a residential neighborhood -- not a park, trail, or open landscape.
8. A small neighborhood park bench or picnic table within a city block of home -- not a wilderness trail or open nature scene.
<!-- END:SETTINGS -->

## ANALYSIS_RULES (injected into the emotion/theme analysis step)

<!-- BEGIN:ANALYSIS_RULES -->
The visual_concept_en you write MUST put one or more generic people at the center of the scene, expressing the emotion through their posture, gesture, or interaction with each other.

SETTING: Place the scene specifically in this location: __SETTING__. Do NOT substitute a different type of location, and do NOT use open landscapes, mountain vistas, stone paths or trails, forests, or generic artistic/cinematic backdrops -- this must read as a real domestic or everyday moment captured candidly, not a staged or abstract film production.

METAPHOR: Do NOT translate the copy's metaphor literally into a symbolic object (e.g. do not depict physical stones, weights, chains, keys, or closed doors as the main element, even if the copy talks about "carrying weight" or "releasing a burden" or "closed doors"). Instead, re-express that same feeling through a human body.

BODY LANGUAGE: The posture, gaze, and physical distance or contact between the people MUST be a specific, concrete translation of the exact emotion_en you determined for THIS copy -- not a generic pose you would reuse for any emotion. Match the physical detail to the emotion, for example: guilt -> shoulders dropped, gaze lowered, arms drawn in close to the body; confrontation -> tense, rigid posture, a marked physical distance between the figures, closed or crossed arms; tenderness -> close physical proximity, a soft touch, leaning gently toward each other; relief/liberation -> loosened, open posture, head lifted, shoulders relaxed down and back; grief -> curled inward, a hand resting on the chest or over the face, stillness; anger/resentment -> clenched hands, a body sharply turned away, stiff shoulders. If the detected emotion is not in this list, invent an equally specific and concrete physical detail for it -- never fall back to a generic "looking away" or "walking" pose that could fit any emotion.

COMPOSITION: Follow this specific composition instruction for this scene: __COMPOSITION_ARCHETYPE__

CAMERA ANGLE: Keep the face unidentifiable using specifically this technique, and only this technique -- do not substitute "shot from behind" or any other technique instead: __CAMERA_ANGLE__

PROTAGONIST: __PROTAGONIST__
<!-- END:ANALYSIS_RULES -->

## BRAND_COLORS (flat-color "quote card" slides -- no photo, no Gemini call)

Used by `--flat-color` in `generate_post_image.py` for carousel slides that
carry text as the whole design instead of a photo (see
`carrusel-constelaciones`: hook slide and CTA slide). Placeholder hex values
below -- swap them for the exact Canva hex codes whenever you have them, no
code change needed.

<!-- BEGIN:BRAND_COLORS -->
1. Solido -- Chocolate oscuro (#4B3A30)
2. Solido -- Terracota (#A9714F)
3. Solido -- Dorado (#B8985E)
4. Degradado -- Crema/beige (#E3D5BF) a Dorado (#B8985E)
5. Degradado -- Chocolate oscuro (#4B3A30) a Terracota (#A9714F)
<!-- END:BRAND_COLORS -->

## Conceptual-translation examples

Use these as the pattern for turning a copy's metaphor into a human scene:

- "cargar con el dolor de otros" (carrying others' pain) -> NOT a person carrying
  stones/weights. YES: shoulders slumped and head bowed, or one figure
  physically supporting another who is leaning into them.
- "puertas cerradas" (closed doors) -> NOT a literal closed door as the subject.
  YES: a figure standing still at a threshold, body language guarded or
  hesitant, facing away from an entryway.
- "romper cadenas / liberarse" (breaking chains / freeing yourself) -> NOT
  literal chains. YES: a figure with arms loosening at their sides, shoulders
  dropping in relief, walking forward into open light, or stepping away from a
  group toward their own space.
- "sostener a la familia" (holding the family together) -> NOT a literal
  weight or pillar. YES: one figure's arm around several others, a small group
  leaning inward together.

## Changing the style later

Edit `BRAND_STYLE` for lighting/color/mood changes, `COMPOSITION_ARCHETYPES`,
`CAMERA_ANGLES`, or `SETTINGS` to add/remove framing, face-concealment, or
location options, `ANALYSIS_RULES` to change how metaphors and emotions get
reinterpreted, or `BRAND_COLORS` to change the flat-color slide palette (e.g.
to swap in real Canva hex codes). `scripts/generate_post_image.py` re-reads
this file on every run, so no code edit is needed for a pure style change.

## Rotation state

The script tracks the last 2 composition archetypes, last 2 camera angles, and
last 2 settings it used in `testing/image_gen_state.json` (gitignored,
local-only) and excludes them when picking for the next run, so the same
framing, face-concealment technique, or room can't repeat back-to-back. Delete
that file to reset the rotation (e.g. after editing the lists above).
`BRAND_COLORS` picks and the `--protagonist` string are decided by the calling
skill (`carrusel-constelaciones`), not by this script -- see that skill's
`SKILL.md` for how it rotates flat-color choices across carousels.
