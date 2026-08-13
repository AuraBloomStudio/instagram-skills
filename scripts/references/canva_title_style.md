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

- **Título + subtítulo -- hook (slide 1) ONLY.** Título: Poppins Bold,
  `#F2A900`, same color as the manual spec above but a different font
  family on purpose. Subtítulo: Playfair Display italic, `#FAE8A8` --
  identical to the manual spec and to the reel hook's accent line
  (`HOOK_ACCENT_FONT_URL` in `render_reel_json2video.py`). Plus a third
  short line below título/subtítulo, Poppins SemiBold, same pale gold
  `#FAE8A8` as the subtitle so it doesn't compete in hierarchy with the
  main headline. **No other slide in the carousel carries a título or
  subtítulo at all** -- content slides, "Para asentar," and the CTA used to
  each get their own gold título + cream subtítulo (making every slide look
  like its own small hook); that per-slide mini-title was dropped per user
  feedback, so the hook is now the only slide with this typography tier.
- **Content slides, "Para asentar," and the CTA (every slide after the
  hook):** ONLY the full microdolor paragraph (or, for the CTA, the full
  bridge), baked as its own block -- Poppins Bold, warm white `#F5F0E6`
  (same color as the reel narration subtitles; was cyan `#22D3EE` until
  user feedback that white read as more legible and more cohesive with the
  brand's warm photo tones than cyan did), with a full-frame dark gradient
  scrim behind it (same stops as `GRADIENT_HTML_TEMPLATE` in
  `render_reel_json2video.py`) for contrast over an uncontrolled real Pexels
  photo. No título, no subtítulo, nothing gold or italic on these slides.
- **Placement -- hook (slide 1):** forced, not face-safe, on purpose.
  `--force-center-zone` bakes the title dead-centered on the whole frame
  regardless of whether it covers the protagonist's face -- a deliberate
  exception (see `constelaciones_brand_voice.md`'s "Design mix" for the
  full reasoning) after simpler face-avoiding placements (top/bottom veto,
  then a middle-band preference) still read as unbalanced on real renders.
- **Placement -- every other slide (content, "Para asentar," CTA):**
  unchanged, still automatic and face-safe -- an OpenCV veto (since a real
  Pexels photo has no requested composition to trust deterministically)
  picks top or bottom, with a wider band (`BODY_BAND_FRACTION`) since a
  full paragraph needs more room than a short headline. These slides never
  use the hook's forced-center exception.

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
