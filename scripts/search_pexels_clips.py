#!/usr/bin/env python3
"""Search, score, and download Pexels B-roll for a reel script, locked to one
protagonist author whenever Pexels' search results allow it.

Flow:
  1. Read a JSON file describing the reel's overall theme (`general_terms`)
     and its emotional moments -- each with an order number, a short label,
     the exact guion line it corresponds to, specific English search terms,
     and optional `cutaway_terms` (detail/object shots with no face, used as
     tier B below). That analysis is done by Claude inside the calling skill
     (`seleccion-clips-pexels`), not by this script -- this script only talks
     to the Pexels API and the filesystem.
  2. Pick ONE protagonist author (unless --protagonist-id pins one): search
     `general_terms` broadly (Videos AND Photos APIs), excluding accounts
     that look like production studios/preset shops by name, then test each
     top candidate against every moment's primary search term to see how
     many moments they have at least one candidate for. Best coverage wins.
  3. For each moment, resolve candidates through a 4-tier cascade, always
     orientation=portrait, always preferring video over photo:
       Tier 0 "solo": protagonist alone, moment's own search_terms.
       Tier A "accompanied": protagonist still, but with solitude wording
         (alone/solo) stripped from the terms, so shots where she appears
         WITH other people can surface. Still the same author_id.
       Tier B "cutaway": no protagonist restriction, using the moment's
         `cutaway_terms` (hands, a mug, a window, a door, light -- everyday
         domestic detail with no identifiable face).
       Tier C "different_protagonist": any author, moment's own search_terms.
       Tier D "approximate": any author, generic brand-safe fallback terms.
     Each tier is only tried if the previous one found zero candidates.
  4. Download 1-3 candidates per moment to
     scripts/output_clips/<reel_name>/NN_<label>_<variant>.{mp4,jpg} and
     write orden_edicion.txt, tagging which tier resolved each moment.

CAVEAT: Pexels' public API has no "search by author id" endpoint -- there is
no way to ask Pexels "give me everything by author X". This script works
around that by running each moment's normal keyword search and filtering
the results down to the chosen author client-side. That means a real
"protagonist" match for a given moment can be missed if that author's
content doesn't rank inside Pexels' own top results for that query, even if
it exists somewhere in their catalog. This is a hard limitation of the API,
not a bug in this script. It also means tier-0 "zero candidates" can simply
mean the ORIGINAL search terms were too solitude-specific (e.g. "alone") to
surface accompanied shots that do exist -- tier A exists for exactly that.

PEXELS_API_KEY is never hardcoded. If it is not already set as an
environment variable, this script prompts for it (input is masked) and
offers to save it to the local .env file, which is already gitignored.

Usage:
  python scripts/search_pexels_clips.py "testing/pexels_moments/mi_reel.json"

  # Re-test only some moments (e.g. after tuning terms), reusing a known
  # protagonist and merging results into the existing orden_edicion.txt
  # instead of clobbering it:
  python scripts/search_pexels_clips.py "testing/pexels_moments/mi_reel.json" \\
      --only 5,7,8 --protagonist-id 6928238 --protagonist-name "Liza Summer"
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv, set_key

# Pexels author names can contain any Unicode character, but Windows consoles
# default to cp1252 and crash on print() for anything outside it (seen in
# practice with Turkish/Vietnamese/etc. names). Force UTF-8 with a safe
# fallback so a print never kills a run mid-download.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

PEXELS_VIDEOS_SEARCH_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTOS_SEARCH_URL = "https://api.pexels.com/v1/search"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "scripts" / "output_clips"

MIN_DURATION_SECONDS = 3
MAX_DURATION_SECONDS = 25
TARGET_DURATION_SECONDS = 8  # typical B-roll cut length; candidates near this rank higher
DEFAULT_CANDIDATES_PER_MOMENT = 3
RESULTS_PER_TERM = 15

PROTAGONIST_POOL_PER_PAGE = 40  # generic-term search width when building the author pool
PROTAGONIST_CANDIDATE_COUNT = 3  # how many top authors get coverage-tested
COVERAGE_TEST_PER_PAGE = 15

# Used only when a moment has zero candidates from ANY tier below (protagonist
# solo, protagonist accompanied, cutaway, different protagonist).
GENERIC_FALLBACK_TERMS = [
    "woman sitting home warm light",
    "woman looking out window home",
    "family together home warm",
    "person reflective indoor calm",
]

SOLITUDE_WORDS_RE = re.compile(
    r"\b(alone|solo|by herself|standing alone|sitting alone)\b", re.IGNORECASE
)

# The hook clip (background behind the rewritten on-screen headline, when the
# reel has one) is a separate pseudo-moment, not one of the 6-8 narrated
# beats -- "00" so it sorts before "01" in a plain file listing.
HOOK_LABEL = "gancho"
HOOK_FILE_PREFIX = "00_gancho"

TIER_LABELS = {
    "accompanied": "⚠ protagonista principal, acompañada",
    "cutaway": "ℹ imagen de apoyo (sin rostro)",
    "different_protagonist": "⚠ protagonista distinta",
    "approximate": "⚠ match aproximado (se ampliaron los términos de búsqueda)",
}


class ClipSearchError(RuntimeError):
    pass


def ensure_pexels_api_key() -> str:
    load_dotenv(ENV_PATH)
    import os

    api_key = os.getenv("PEXELS_API_KEY")
    if api_key:
        return api_key

    print("No se encontró PEXELS_API_KEY en el entorno ni en .env.")
    api_key = getpass.getpass(
        "Pega tu API key de Pexels (no se mostrará en pantalla): "
    ).strip()
    if not api_key:
        raise ClipSearchError("No se ingresó ninguna API key. Abortando.")

    save = input(
        f"¿Guardarla en {ENV_PATH.name} para no volver a pedirla? [S/n]: "
    ).strip().lower()
    if save in ("", "s", "si", "sí", "y", "yes"):
        set_key(str(ENV_PATH), "PEXELS_API_KEY", api_key)
        print(f"Guardada en {ENV_PATH} (este archivo está en .gitignore).")
    os.environ["PEXELS_API_KEY"] = api_key
    return api_key


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "clip"


def strip_solitude_words(term: str) -> str:
    """Drop words like 'alone'/'solo' so a protagonist-restricted search can
    also surface shots where she appears with other people (tier A)."""
    stripped = SOLITUDE_WORDS_RE.sub("", term)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped or term


def load_moments(json_path: Path) -> dict:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    if "reel_name" not in data or "moments" not in data:
        raise ClipSearchError(
            f"{json_path} debe tener las claves 'reel_name' y 'moments'."
        )
    if not data.get("general_terms"):
        raise ClipSearchError(
            f"{json_path} debe tener 'general_terms' (3-5 términos genéricos del "
            "tema del reel, usados para elegir un protagonista único)."
        )
    if not (6 <= len(data["moments"]) <= 8):
        print(
            f"Aviso: se esperaban 6-8 momentos, el archivo trae {len(data['moments'])}. "
            "Se continúa igual."
        )
    hook = data.get("hook")
    if hook is not None and not hook.get("search_terms"):
        raise ClipSearchError(
            f"{json_path}: 'hook' debe traer 'search_terms' (2-3 términos en "
            "inglés específicos del texto del gancho) si la clave está presente."
        )
    return data


def _pexels_get(url: str, api_key: str, params: dict) -> dict:
    headers = {"Authorization": api_key}
    for attempt in range(3):
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"  Rate limit de Pexels, esperando {wait}s...")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            raise ClipSearchError(
                f"Pexels devolvió {resp.status_code} para {url} {params}: {resp.text[:200]}"
            )
        return resp.json()
    raise ClipSearchError(f"Rate limit persistente de Pexels en {url} {params}.")


def pick_best_video_file(video: dict) -> Optional[dict]:
    files = [f for f in video.get("video_files", []) if (f.get("height") or 0) > (f.get("width") or 0)]
    if not files:
        files = video.get("video_files", [])
    if not files:
        return None
    quality_rank = {"hd": 0, "sd": 1, "uhd": 2}

    def sort_key(f):
        width_diff = abs((f.get("width") or 0) - 1080)
        return (quality_rank.get(f.get("quality"), 3), width_diff)

    files.sort(key=sort_key)
    return files[0]


def search_videos(term: str, api_key: str, per_page: int = RESULTS_PER_TERM) -> list:
    params = {"query": term, "orientation": "portrait", "per_page": per_page}
    data = _pexels_get(PEXELS_VIDEOS_SEARCH_URL, api_key, params)
    candidates = []
    for position, video in enumerate(data.get("videos", [])):
        duration = video.get("duration") or 0
        if not (MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS):
            continue
        best_file = pick_best_video_file(video)
        if not best_file:
            continue
        candidates.append(
            {
                "key": f"video:{video['id']}",
                "type": "video",
                "author_id": video.get("user", {}).get("id"),
                "author_name": video.get("user", {}).get("name", "desconocido"),
                "pexels_url": video.get("url", ""),
                "duration": duration,
                "file_url": best_file["link"],
                "position": position,
            }
        )
    return candidates


def search_photos(term: str, api_key: str, per_page: int = RESULTS_PER_TERM) -> list:
    params = {"query": term, "orientation": "portrait", "per_page": per_page}
    data = _pexels_get(PEXELS_PHOTOS_SEARCH_URL, api_key, params)
    candidates = []
    for position, photo in enumerate(data.get("photos", [])):
        src = photo.get("src", {})
        file_url = src.get("large2x") or src.get("original") or src.get("large")
        if not file_url:
            continue
        candidates.append(
            {
                "key": f"photo:{photo['id']}",
                "type": "photo",
                "author_id": photo.get("photographer_id"),
                "author_name": photo.get("photographer", "desconocido"),
                "pexels_url": photo.get("url", ""),
                "duration": None,
                "file_url": file_url,
                "position": position,
            }
        )
    return candidates


def gather_candidates(
    terms: list, api_key: str, author_id: Optional[int] = None, per_page: int = RESULTS_PER_TERM,
    include_video: bool = True,
) -> dict:
    """Search each term across Videos + Photos (or Photos only if
    include_video=False -- used by search_pexels_photo.py, which never wants
    video for a static carousel slide); merge by key. If author_id is given,
    only candidates from that author survive (client-side filter -- see the
    module docstring's CAVEAT about why this isn't a native API filter)."""
    candidates: dict = {}
    for term in terms:
        found = search_photos(term, api_key, per_page)
        if include_video:
            found = search_videos(term, api_key, per_page) + found
        for cand in found:
            if author_id is not None and cand["author_id"] != author_id:
                continue
            key = cand["key"]
            if key not in candidates:
                cand["matched_terms"] = set()
                cand["best_rank"] = cand["position"]
                candidates[key] = cand
            candidates[key]["matched_terms"].add(term)
            candidates[key]["best_rank"] = min(candidates[key]["best_rank"], cand["position"])
    return candidates


# Account names containing these words are production houses / preset shops
# that publish many different models under one Pexels account -- a "single
# author" match there does NOT mean a single consistent person on screen.
# Seen in practice: "cottonbro studio" surfaced 5 different women across the
# first 2 moments alone despite "winning" the coverage test.
STUDIO_NAME_BLOCKLIST = (
    "studio", "production", "productions", "crew", "team", "agency",
    "films", "media", "presets", "etsy.com",
)

# A real individual photographer's Pexels display name is never a bare URL --
# confirmed in a real carousel search that "https://kaboompics.com/" won
# protagonist selection (no blocklisted word above matches "kaboompics")
# despite being exactly the same multi-model aggregator problem as a studio
# account: the 5 downloaded "protagonist" photos turned out to be at least 4
# different people, including a child, none matching each other.
_URL_LIKE_AUTHOR_RE = re.compile(r"https?://|www\.|\.(com|net|org|co|io)\b", re.IGNORECASE)


def _looks_like_studio_account(author_name: str) -> bool:
    lowered = author_name.lower()
    if any(word in lowered for word in STUDIO_NAME_BLOCKLIST):
        return True
    return bool(_URL_LIKE_AUTHOR_RE.search(author_name))


def pick_protagonist(
    general_terms: list, moments: list, api_key: str, include_video: bool = True
) -> dict:
    """Phase 0: choose one author with the best candidate coverage across
    the reel's moments, using general_terms to build an author pool and
    each moment's primary search term to test coverage. Multi-model studio
    accounts are excluded up front -- they win on raw coverage but break
    the actual goal (one consistent person across the reel). include_video is
    only False when called from search_pexels_photo.py for a carousel."""
    kind = "fotos + videos" if include_video else "fotos"
    print(f"Buscando protagonista con cobertura en Pexels ({kind})...")
    pool = gather_candidates(
        general_terms, api_key, author_id=None, per_page=PROTAGONIST_POOL_PER_PAGE,
        include_video=include_video,
    )
    author_counts = Counter(c["author_id"] for c in pool.values())
    author_names = {c["author_id"]: c["author_name"] for c in pool.values()}
    ranked_authors = [aid for aid, _ in author_counts.most_common() if aid]
    excluded = [aid for aid in ranked_authors if _looks_like_studio_account(author_names[aid])]
    for aid in excluded:
        print(f"  Descartado (cuenta de estudio/preset, no una sola persona): {author_names[aid]}")
    top_authors = [aid for aid in ranked_authors if aid not in excluded][:PROTAGONIST_CANDIDATE_COUNT]

    if not top_authors:
        raise ClipSearchError(
            "No se encontró ningún autor candidato individual (no-estudio) con los "
            "general_terms dados. Probá con términos más amplios."
        )

    best = None
    for author_id in top_authors:
        covered = 0
        for moment in moments:
            primary_term = moment["search_terms"][0]
            hits = gather_candidates(
                [primary_term], api_key, author_id=author_id, per_page=COVERAGE_TEST_PER_PAGE,
                include_video=include_video,
            )
            if hits:
                covered += 1
        print(f"  Candidato: {author_names[author_id]} -- cubre {covered}/{len(moments)} momentos")
        score = (covered, author_counts[author_id])
        if best is None or score > best["score"]:
            best = {
                "author_id": author_id,
                "author_name": author_names[author_id],
                "covered": covered,
                "total_moments": len(moments),
                "score": score,
            }

    print(f"Protagonista elegido: {best['author_name']} ({best['covered']}/{best['total_moments']} momentos cubiertos)")
    return best


def resolve_moment_candidates(
    moment: dict, protagonist_id: int, api_key: str, include_video: bool = True
) -> tuple:
    """4-tier cascade for one moment. Returns (candidates dict, tier string).
    tier is None for a normal protagonist-solo match."""
    candidates = gather_candidates(
        moment["search_terms"], api_key, author_id=protagonist_id, include_video=include_video
    )
    if candidates:
        return candidates, None

    print("  Sin candidatos de la protagonista en solitario, probando acompañada...")
    accompanied_terms = [strip_solitude_words(t) for t in moment["search_terms"]]
    candidates = gather_candidates(
        accompanied_terms, api_key, author_id=protagonist_id, include_video=include_video
    )
    if candidates:
        return candidates, "accompanied"

    cutaway_terms = moment.get("cutaway_terms") or []
    if cutaway_terms:
        print("  Sin candidatos acompañada, probando imagen de apoyo (sin rostro)...")
        candidates = gather_candidates(cutaway_terms, api_key, author_id=None, include_video=include_video)
        if candidates:
            return candidates, "cutaway"

    print("  Sin imagen de apoyo, buscando cualquier autor para este momento...")
    candidates = gather_candidates(
        moment["search_terms"], api_key, author_id=None, include_video=include_video
    )
    if candidates:
        return candidates, "different_protagonist"

    print("  Sin resultados con los términos originales, ampliando búsqueda...")
    candidates = gather_candidates(GENERIC_FALLBACK_TERMS, api_key, author_id=None, include_video=include_video)
    return candidates, "approximate"


def score_candidate(candidate: dict) -> tuple:
    type_rank = 0 if candidate["type"] == "video" else 1  # prefer video over photo
    duration_gap = abs((candidate["duration"] or TARGET_DURATION_SECONDS) - TARGET_DURATION_SECONDS)
    return (type_rank, -len(candidate["matched_terms"]), candidate["best_rank"], duration_gap)


def download_file(url: str, dest: Path) -> None:
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            fh.write(chunk)


def resolve_and_download_hook(
    hook: dict, protagonist_id: int, protagonist_name: str, api_key: str,
    out_dir: Path, used_keys: set, candidates_per_moment: int,
) -> str:
    """Same 4-tier cascade + scoring + download as a regular moment (see
    resolve_moment_candidates/score_candidate), but for the reel's optional
    rewritten-headline hook instead of a narrated beat -- separate pseudo-
    moment, own file prefix, own block in orden_edicion.txt, never mixed
    into 'Momento 01'. Shares `used_keys` with the moments loop so the hook
    clip and a narration clip can never end up being the exact same
    Pexels file (global dedup rule, same as between any two moments)."""
    print(f"Buscando clip del gancho -- solo {protagonist_name}...")
    candidates, tier = resolve_moment_candidates(hook, protagonist_id, api_key)
    available = {k: c for k, c in candidates.items() if k not in used_keys}
    ranked = sorted(available.values(), key=score_candidate)
    chosen = ranked[:candidates_per_moment]
    for candidate in chosen:
        used_keys.add(candidate["key"])

    lines = [f'Momento {HOOK_LABEL} -- texto: "{hook["text"]}"']
    lines.append(f"  Términos usados: {', '.join(hook['search_terms'])}")
    if tier and tier != "different_protagonist":
        lines.append(f"  {TIER_LABELS[tier]}")
    elif tier == "different_protagonist":
        lines.append(f"  {TIER_LABELS[tier]} -- clip del gancho")

    if not chosen:
        lines.append("  Sin clips disponibles -- buscar manualmente.")
        print("  Sin candidatos utilizables para el clip del gancho.")
        return "\n".join(lines)

    variant_letters = "abcdefghijklmnopqrstuvwxyz"
    for idx, candidate in enumerate(chosen):
        variant = variant_letters[idx]
        ext = "mp4" if candidate["type"] == "video" else "jpg"
        filename = f"{HOOK_FILE_PREFIX}_{variant}.{ext}"
        dest = out_dir / filename
        print(f"  Descargando {filename} (autor: {candidate['author_name']}, tipo: {candidate['type']})...")
        download_file(candidate["file_url"], dest)
        type_note = "" if candidate["type"] == "video" else " [FOTO -- animar o usar como imagen fija]"
        lines.append(
            f"  {filename} -- autor: {candidate['author_name']}{type_note} -- {candidate['pexels_url']}"
        )
    return "\n".join(lines)


def _extract_used_keys(summary_text: str) -> set:
    keys = set()
    for kind, num in re.findall(r"/(video|photo)/[\w-]*-(\d+)/", summary_text):
        keys.add(f"{kind}:{num}")
    return keys


def _merge_moment_blocks(existing_text: str, new_blocks: dict) -> str:
    """Replace only the 'Momento NN -- ...' blocks present in new_blocks;
    leave everything else (header, untouched moments, the hook block if any)
    exactly as-is. The hook block's header ('Momento gancho -- ...') never
    matches \\d+ here on purpose, so it always falls through untouched."""
    blocks = existing_text.strip("\n").split("\n\n")
    merged = []
    for block in blocks:
        m = re.match(r"Momento (\d+) --", block)
        if m and int(m.group(1)) in new_blocks:
            merged.append(new_blocks[int(m.group(1))].rstrip("\n"))
        else:
            merged.append(block)
    return "\n\n".join(merged) + "\n"


def _merge_hook_block(existing_text: str, hook_block: str) -> str:
    """Always REMOVE any existing 'Momento gancho -- ...' block first, then
    (re)insert the new one right before the first 'Momento N -- ...' block --
    never an in-place update at whatever index it happened to already be at.
    Mirrors _merge_moment_blocks but for the single non-numeric hook block,
    which that function never touches.

    First version only replaced-in-place when a hook block already existed,
    which just re-wrote its content at its EXISTING (possibly wrong)
    position instead of relocating it -- confirmed broken on a real re-run:
    a hook block already misplaced after 'Momento 02' (see the position bug
    below) stayed misplaced after "fixing" the position bug, because the
    replace path never repositions.

    Position bug this also fixes: finds the header/first-moment boundary by
    CONTENT (first block matching 'Momento \\d+ --'), not by a fixed block
    count -- a fixed index (e.g. "the header is always 3 blocks") broke on a
    real reel whose orden_edicion.txt had been hand-edited per this skill's
    own step 6 (a 'Nota: ...' paragraph appended straight after the
    protagonist line, no blank line), collapsing what the script normally
    writes as 3 separate header blocks into 1."""
    blocks = existing_text.strip("\n").split("\n\n")
    hook_prefix = f"Momento {HOOK_LABEL} --"
    blocks = [b for b in blocks if not b.startswith(hook_prefix)]
    insert_at = next(
        (i for i, block in enumerate(blocks) if re.match(r"Momento (\d+) --", block)),
        len(blocks),
    )
    blocks.insert(insert_at, hook_block.rstrip("\n"))
    return "\n\n".join(blocks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", help="Archivo JSON con reel_name, general_terms y la lista de moments")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f'Carpeta base de salida (default: "{DEFAULT_OUTPUT_DIR}")',
    )
    parser.add_argument(
        "--candidates-per-moment",
        type=int,
        default=DEFAULT_CANDIDATES_PER_MOMENT,
        help="Máximo de clips a descargar por momento (default: 3)",
    )
    parser.add_argument(
        "--only",
        help="Procesar solo estos números de momento, ej. '5,7,8' -- re-testea sin "
        "rehacer todo el reel; si ya existe orden_edicion.txt, hace merge en vez de "
        "sobreescribirlo.",
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
    parser.add_argument(
        "--hook-only",
        action="store_true",
        help="Procesar SOLO el clip del gancho (requiere 'hook' en el JSON), sin "
        "tocar los 6-8 momentos narrados -- hace merge en orden_edicion.txt igual "
        "que --only. Se puede combinar con --only para re-testear ambos a la vez.",
    )
    args = parser.parse_args()
    if bool(args.protagonist_id) != bool(args.protagonist_name):
        raise ClipSearchError("--protagonist-id y --protagonist-name van juntos.")

    api_key = ensure_pexels_api_key()
    data = load_moments(Path(args.json_path))
    if args.hook_only and not data.get("hook"):
        raise ClipSearchError(
            "--hook-only requiere la clave 'hook' en el JSON (con al menos 'text' y "
            "'search_terms')."
        )
    reel_slug = slugify(data["reel_name"])
    out_dir = Path(args.output_dir) / reel_slug
    summary_path = out_dir / "orden_edicion.txt"

    only_orders = None
    if args.only:
        only_orders = {int(x) for x in args.only.split(",")}

    if args.hook_only and only_orders is None:
        moments_to_process = []  # solo el gancho, ningun momento numerado
    else:
        moments_to_process = [m for m in data["moments"] if only_orders is None or m["order"] in only_orders]
        if not moments_to_process:
            raise ClipSearchError(f"--only {args.only} no coincide con ningún momento del JSON.")

    if args.protagonist_id:
        protagonist = {
            "author_id": args.protagonist_id,
            "author_name": args.protagonist_name,
            "covered": None,
            "total_moments": len(data["moments"]),
        }
        print(f"Protagonista fijada por parámetro: {protagonist['author_name']} (id {protagonist['author_id']})")
    else:
        protagonist = pick_protagonist(data["general_terms"], data["moments"], api_key)

    merge_mode = (only_orders is not None or args.hook_only) and summary_path.exists()
    used_keys: set = set()
    if merge_mode:
        used_keys = _extract_used_keys(summary_path.read_text(encoding="utf-8"))

    variant_letters = "abcdefghijklmnopqrstuvwxyz"

    # Hook clip (optional, separate from the 6-8 narrated moments): only
    # processed on a default full run (no --only/--hook-only) or when
    # explicitly requested via --hook-only. Shares used_keys with the
    # moments loop below either way, so it can never end up downloading the
    # exact same Pexels file as a narration clip.
    should_process_hook = bool(data.get("hook")) and (args.hook_only or only_orders is None)
    hook_block = None
    if should_process_hook:
        hook_block = resolve_and_download_hook(
            data["hook"], protagonist["author_id"], protagonist["author_name"],
            api_key, out_dir, used_keys, args.candidates_per_moment,
        )

    # Pass 1: resolve each moment's candidate pool through the tier cascade.
    moment_pools = []
    for moment in moments_to_process:
        label = slugify(moment["label"])
        print(f"Buscando momento {moment['order']:02d} ({label}) -- solo {protagonist['author_name']}...")
        candidates, tier = resolve_moment_candidates(moment, protagonist["author_id"], api_key)
        moment_pools.append({"moment": moment, "label": label, "candidates": candidates, "tier": tier})

    # Pass 2: pick top N per moment, never re-downloading a clip/photo
    # already used elsewhere in the reel (global dedup, seeded from the
    # existing summary when --only is merging into a prior run).
    moment_results = []
    for pool in moment_pools:
        available = {k: c for k, c in pool["candidates"].items() if k not in used_keys}
        ranked = sorted(available.values(), key=score_candidate)
        chosen = ranked[: args.candidates_per_moment]
        for candidate in chosen:
            used_keys.add(candidate["key"])
        moment_results.append({**pool, "chosen": chosen})

    # Pass 3: download and build a text block per moment.
    new_blocks = {}
    for result in moment_results:
        moment = result["moment"]
        label = result["label"]
        chosen = result["chosen"]
        tier = result["tier"]

        lines = [f"Momento {moment['order']:02d} -- {moment['label']}"]
        lines.append(f"  Línea del guion: {moment['guion_line']}")
        lines.append(f"  Términos usados: {', '.join(moment['search_terms'])}")
        if tier and tier != "different_protagonist":
            lines.append(f"  {TIER_LABELS[tier]}")
        elif tier == "different_protagonist":
            lines.append(
                f"  {TIER_LABELS[tier]} -- momento {moment['order']:02d} "
                f"({protagonist['author_name']} no tenía ningún candidato, ni sola ni "
                "acompañada, ni imagen de apoyo)"
            )

        if not chosen:
            lines.append("  Sin clips disponibles -- buscar manualmente.")
            print(f"  Sin candidatos utilizables para el momento {moment['order']:02d}.")
            new_blocks[moment["order"]] = "\n".join(lines)
            continue

        for idx, candidate in enumerate(chosen):
            variant = variant_letters[idx]
            ext = "mp4" if candidate["type"] == "video" else "jpg"
            filename = f"{moment['order']:02d}_{label}_{variant}.{ext}"
            dest = out_dir / filename
            print(f"  Descargando {filename} (autor: {candidate['author_name']}, tipo: {candidate['type']})...")
            download_file(candidate["file_url"], dest)
            type_note = "" if candidate["type"] == "video" else " [FOTO -- animar o usar como imagen fija]"
            lines.append(
                f"  {filename} -- autor: {candidate['author_name']}{type_note} -- {candidate['pexels_url']}"
            )
        new_blocks[moment["order"]] = "\n".join(lines)

    out_dir.mkdir(parents=True, exist_ok=True)
    if merge_mode:
        text = summary_path.read_text(encoding="utf-8")
        if new_blocks:
            text = _merge_moment_blocks(text, new_blocks)
        if hook_block is not None:
            text = _merge_hook_block(text, hook_block)
        summary_path.write_text(text, encoding="utf-8")
    else:
        header = [
            f"Orden de edición -- {data['reel_name']}",
            "=" * 60,
            f"Protagonista: {protagonist['author_name']}"
            + (
                f" ({protagonist['covered']}/{protagonist['total_moments']} momentos cubiertos en la búsqueda inicial)"
                if protagonist["covered"] is not None
                else ""
            ),
        ]
        all_blocks = [header[0], header[1], header[2]]
        if hook_block is not None:
            all_blocks.append(hook_block)
        for moment in data["moments"]:
            if moment["order"] in new_blocks:
                all_blocks.append(new_blocks[moment["order"]])
        summary_path.write_text("\n\n".join(all_blocks) + "\n", encoding="utf-8")

    print(f"\nListo. Clips en: {out_dir}")
    print(f"Resumen: {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClipSearchError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
