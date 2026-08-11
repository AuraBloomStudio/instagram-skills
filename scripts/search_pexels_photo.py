#!/usr/bin/env python3
"""Search, score, and download Pexels stock PHOTOS for a carrusel-constelaciones
carousel, locked to one protagonist author whenever Pexels' search results
allow it -- the same mechanism seleccion-clips-pexels already uses for reel
B-roll, reused here by import instead of duplicated.

Flow (identical to search_pexels_clips.py's, Photos-only):
  1. Read a JSON file describing the carousel's overall theme (`general_terms`)
     and its slides -- each with an order number, a short label, English
     search terms, and optional `cutaway_terms`. That analysis is done by
     Claude inside carrusel-constelaciones, not by this script.
  2. Pick ONE protagonist author (unless --protagonist-id pins one): search
     `general_terms` broadly (Photos API only -- a carousel slide is a still
     image, never a video), excluding accounts that look like production
     studios/preset shops by name, then test each top candidate against every
     slide's primary search term to see how many slides they have at least
     one candidate for. Best coverage wins.
  3. For each slide, resolve candidates through the same 4-tier cascade as
     reels: solo -> accompanied -> cutaway (no face) -> different author ->
     approximate. Each tier is only tried if the previous one found zero
     candidates.
  4. Download 1-3 candidates per slide to
     scripts/output_photos/<carousel_slug>/NN_<label>_<variant>.jpg and write
     resumen_fotos.txt, tagging which tier resolved each slide.

PEXELS_API_KEY is never hardcoded -- same .env pattern as
search_pexels_clips.py and generate_post_image.py.

Usage:
  python scripts/search_pexels_photo.py "testing/pexels_carousels/mi_carrusel.json"

  # Re-test only some slides, reusing a known protagonist:
  python scripts/search_pexels_photo.py "testing/pexels_carousels/mi_carrusel.json" \\
      --only 2,4 --protagonist-id 6928238 --protagonist-name "Liza Summer"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Reuse the reel pipeline's author-cascade/protagonist-selection machinery by
# import instead of duplicating it -- both scripts live in scripts/, so a
# plain import works when run as `python scripts/search_pexels_photo.py` from
# the repo root. include_video=False everywhere here restricts every search
# to the Photos API only; the reel script's own default (True) is untouched.
from search_pexels_clips import (
    ClipSearchError,
    download_file,
    ensure_pexels_api_key,
    pick_protagonist,
    resolve_moment_candidates,
    score_candidate,
    slugify,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "scripts" / "output_photos"
DEFAULT_CANDIDATES_PER_SLIDE = 3

_SLIDE_HEADER_RE_TEMPLATE = r"^Slide\s+(\d+)\s*--\s*(.+)$"


def load_slides(json_path: Path) -> dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if "carousel_name" not in data or "slides" not in data:
        raise ClipSearchError(
            f"{json_path} debe tener las claves 'carousel_name' y 'slides'."
        )
    if not data.get("general_terms"):
        raise ClipSearchError(
            f"{json_path} debe tener 'general_terms' (3-5 términos genéricos del "
            "tema del carrusel, usados para elegir un protagonista único)."
        )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", help="Archivo JSON con carousel_name, general_terms y slides")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f'Carpeta base de salida (default: "{DEFAULT_OUTPUT_DIR}")',
    )
    parser.add_argument(
        "--candidates-per-slide",
        type=int,
        default=DEFAULT_CANDIDATES_PER_SLIDE,
        help="Máximo de fotos a descargar por slide (default: 3)",
    )
    parser.add_argument(
        "--only",
        help="Procesar solo estos números de slide, ej. '2,4' -- re-testea sin "
        "rehacer todo el carrusel; si ya existe resumen_fotos.txt, hace merge en "
        "vez de sobreescribirlo.",
    )
    parser.add_argument(
        "--protagonist-id",
        type=int,
        help="Saltar la Fase 0 y usar este author_id de Pexels como protagonista "
        "(requiere --protagonist-name también).",
    )
    parser.add_argument(
        "--protagonist-name",
        help="Nombre a mostrar del protagonista cuando se usa --protagonist-id.",
    )
    args = parser.parse_args()
    if bool(args.protagonist_id) != bool(args.protagonist_name):
        raise ClipSearchError("--protagonist-id y --protagonist-name van juntos.")

    api_key = ensure_pexels_api_key()
    data = load_slides(Path(args.json_path))
    carousel_slug = slugify(data["carousel_name"])
    out_dir = Path(args.output_dir) / carousel_slug
    summary_path = out_dir / "resumen_fotos.txt"

    only_orders = None
    if args.only:
        only_orders = {int(x) for x in args.only.split(",")}

    slides_to_process = [s for s in data["slides"] if only_orders is None or s["order"] in only_orders]
    if not slides_to_process:
        raise ClipSearchError(f"--only {args.only} no coincide con ningún slide del JSON.")

    if args.protagonist_id:
        protagonist = {
            "author_id": args.protagonist_id,
            "author_name": args.protagonist_name,
            "covered": None,
            "total_moments": len(data["slides"]),
        }
        print(f"Protagonista fijada por parámetro: {protagonist['author_name']} (id {protagonist['author_id']})")
    else:
        protagonist = pick_protagonist(data["general_terms"], data["slides"], api_key, include_video=False)

    merge_mode = only_orders is not None and summary_path.exists()
    used_keys: set = set()
    if merge_mode:
        import re
        used_keys = {
            f"photo:{m}" for m in re.findall(r"-(\d+)/", summary_path.read_text(encoding="utf-8"))
        }

    variant_letters = "abcdefghijklmnopqrstuvwxyz"

    # Pass 1: resolve each slide's candidate pool through the tier cascade.
    slide_pools = []
    for slide in slides_to_process:
        label = slugify(slide["label"])
        print(f"Buscando slide {slide['order']:02d} ({label}) -- solo {protagonist['author_name']}...")
        candidates, tier = resolve_moment_candidates(
            slide, protagonist["author_id"], api_key, include_video=False
        )
        slide_pools.append({"slide": slide, "label": label, "candidates": candidates, "tier": tier})

    # Pass 2: pick top N per slide, never re-downloading a photo already used
    # elsewhere in the carousel (global dedup, seeded from the existing
    # summary when --only is merging into a prior run).
    slide_results = []
    for pool in slide_pools:
        available = {k: c for k, c in pool["candidates"].items() if k not in used_keys}
        ranked = sorted(available.values(), key=score_candidate)
        chosen = ranked[: args.candidates_per_slide]
        for candidate in chosen:
            used_keys.add(candidate["key"])
        slide_results.append({**pool, "chosen": chosen})

    tier_labels = {
        "accompanied": "⚠ protagonista principal, acompañada",
        "cutaway": "ℹ imagen de apoyo (sin rostro)",
        "different_protagonist": "⚠ protagonista distinta",
        "approximate": "⚠ match aproximado (se ampliaron los términos de búsqueda)",
    }

    # Pass 3: download and build a text block per slide.
    new_blocks = {}
    for result in slide_results:
        slide = result["slide"]
        label = result["label"]
        chosen = result["chosen"]
        tier = result["tier"]

        lines = [f"Slide {slide['order']:02d} -- {slide['label']}"]
        lines.append(f"  Términos usados: {', '.join(slide['search_terms'])}")
        if tier and tier != "different_protagonist":
            lines.append(f"  {tier_labels[tier]}")
        elif tier == "different_protagonist":
            lines.append(
                f"  {tier_labels[tier]} -- slide {slide['order']:02d} "
                f"({protagonist['author_name']} no tenía ningún candidato, ni sola ni "
                "acompañada, ni imagen de apoyo)"
            )

        if not chosen:
            lines.append("  Sin fotos disponibles -- buscar manualmente.")
            print(f"  Sin candidatos utilizables para el slide {slide['order']:02d}.")
            new_blocks[slide["order"]] = "\n".join(lines)
            continue

        for idx, candidate in enumerate(chosen):
            variant = variant_letters[idx]
            filename = f"{slide['order']:02d}_{label}_{variant}.jpg"
            dest = out_dir / filename
            print(f"  Descargando {filename} (autor: {candidate['author_name']})...")
            download_file(candidate["file_url"], dest)
            lines.append(
                f"  {filename} -- autor: {candidate['author_name']} -- {candidate['pexels_url']}"
            )
        new_blocks[slide["order"]] = "\n".join(lines)

    out_dir.mkdir(parents=True, exist_ok=True)
    if merge_mode:
        text = summary_path.read_text(encoding="utf-8")
        blocks = text.strip("\n").split("\n\n")
        merged = []
        import re as _re
        for block in blocks:
            m = _re.match(r"Slide (\d+) --", block)
            if m and int(m.group(1)) in new_blocks:
                merged.append(new_blocks[int(m.group(1))].rstrip("\n"))
            else:
                merged.append(block)
        summary_path.write_text("\n\n".join(merged) + "\n", encoding="utf-8")
    else:
        header = [
            f"Fotos de Pexels -- {data['carousel_name']}",
            "=" * 60,
            f"Protagonista: {protagonist['author_name']}"
            + (
                f" ({protagonist['covered']}/{protagonist['total_moments']} slides cubiertos en la búsqueda inicial)"
                if protagonist["covered"] is not None
                else ""
            ),
        ]
        all_blocks = list(header)
        for slide in data["slides"]:
            if slide["order"] in new_blocks:
                all_blocks.append(new_blocks[slide["order"]])
        summary_path.write_text("\n\n".join(all_blocks) + "\n", encoding="utf-8")

    print(f"\nListo. Fotos en: {out_dir}")
    print(f"Resumen: {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClipSearchError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
