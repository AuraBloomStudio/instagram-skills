# Canva title typography — Constelaciones Familiares

Canonical spec for the title text added by hand in Canva on top of the
background photos this repo generates (feed posts, carousel slides, stories).
Cited by `imagen-post-constelaciones`, `post-constelaciones`,
`carrusel-constelaciones`, and `historias-constelaciones`. Edit this file to
change the spec — don't duplicate its content inside any `SKILL.md`.

This file governs on-image TEXT typography only. Background photo style
(palette, composition, face rules) lives in `image_prompt_style.md` and is
unaffected by this file.

## Hard rules

- **No brand signature, full stop.** Never add "por Diana Barreto",
  "@constelacionesydespertar", any other name/handle, or anything in their
  place, to any post, carousel slide, or story. These posts publish to a new
  Facebook page and new TikTok/YouTube channels; the old signature does not
  carry over and nothing replaces it. The image carries title text only — no
  footer/corner attribution of any kind.

## TITLE_TYPOGRAPHY (verbatim spec, approved 2026-08-10)

- **Main headline** (the punch phrase / hook text): bold, condensed
  sans-serif, poster/impact style (Anton or Oswald Bold, or an equivalent
  condensed-bold poster font available in Canva). Color: vivid yellow/orange,
  default `#F2A900`.
- **Closing/secondary line** (when the structure has one, e.g. a "Para
  asentar" line or a short reframe under the headline): elegant script/
  cursive font. Color: a pale, desaturated gold, default `#FAE8A8` — clearly
  lighter and less saturated than the headline color, never white. Size it
  with real visual presence, comparable in weight to the headline — not a
  small caption-sized afterthought.
- **Layout: centered.** Both the headline and the closing line are
  horizontally centered in the frame, not left-aligned.
- **Vertical position: judged per photo, not a fixed value.** Leave visible
  air between the top edge of the image and the start of the title block —
  the approved reference render starts roughly 20% down from the top edge on
  a 1080x1350 canvas, but that is a starting point, not a universal constant.
  Each background photo's clean/negative-space area (see
  `image_prompt_style.md`'s "Negative space for text" rule) sits in a
  different place depending on that photo's composition. Always check the
  actual photo before placing the block, and slide it up or down as needed so
  it never overlaps the protagonist's face or hair — do not paste the same
  pixel offset onto every post without checking.

## CARROUSEL_BAKED_TYPOGRAPHY (carrusel-constelaciones only, automated, no Canva step)

`carrusel-constelaciones` no longer uses the manual `TITLE_TYPOGRAPHY` spec
above at all -- every slide's text is baked automatically with Pillow via
`generate_post_image.py`'s `render_headline` (see that script and
`constelaciones_brand_voice.md`'s "Design mix" rule). Its typography is
deliberately **Poppins**, not Anton/Oswald, so carousels and reels
(`render_reel_json2video.py`'s hook text) read as one brand system instead of
two different ones:

- **Título** (main headline, every slide): Poppins Bold, `#F2A900`, same
  color as the manual spec above but a different font family on purpose.
- **Subtítulo** (accent line, every slide that has one): Playfair Display
  italic, `#FAE8A8` -- identical to the manual spec and to the reel hook's
  accent line (`HOOK_ACCENT_FONT_URL` in `render_reel_json2video.py`).
- **Hook (slide 1) only:** a third short line below título/subtítulo,
  Poppins SemiBold, same pale gold `#FAE8A8` as the subtitle so it doesn't
  compete in hierarchy with the main headline.
- **Content slides + "Para asentar" only:** the full microdolor paragraph,
  baked separately as its own block -- Poppins Bold, cyan `#22D3EE` (same
  color as the reel narration subtitles), with a full-frame dark gradient
  scrim behind it (same stops as `GRADIENT_HTML_TEMPLATE` in
  `render_reel_json2video.py`) for contrast over an uncontrolled real Pexels
  photo. Never combined with the hook's third line on the same slide.
- **CTA (slide 6) only:** título + subtítulo, no third block -- the CTA's
  weight comes from the bridge sentence itself (see
  `constelaciones_brand_voice.md`), not from an extra text tier.
- **Placement:** automatic, not manual -- a face-safe zone (OpenCV veto,
  since a real Pexels photo has no requested composition to trust
  deterministically) picks the top or bottom band of the frame; the content-
  slide body block gets a wider band (`BODY_BAND_FRACTION`) since a full
  paragraph needs more room than a short headline.

## Reference render

`canva_title_style_example.png` (same folder) is the approved 2026-08-10
mockup, built on `Durante años creí que solo tenía mal carácter.png`
(existing background photo), using Impact (headline) and French Script
(closing line) as placeholder fonts standing in for the real Anton/Oswald +
script font chosen in Canva. Kept as the permanent visual reference for this
spec — open it directly to see actual color/weight/position instead of
re-deriving them from the text description above.

## Changing this spec

Edit `TITLE_TYPOGRAPHY` above — no code change needed, since this is a manual
Canva step, not something `generate_post_image.py` renders.
