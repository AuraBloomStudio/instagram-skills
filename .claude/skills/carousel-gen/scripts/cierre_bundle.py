"""
cierre_bundle.py - CIERRE OBLIGATORIO de carousel-gen (2026-09-26).

El proceso NO termina cuando Gemini termina. Despues de run_generation(), en este orden:

  1. RESPALDO DETERMINISTA DE TEXTO: cada slide que agoto sus 2 regeneraciones con el
     texto mal (TEXT_QA_FAILED) se corrige con text_fallback.compose_exact_text sobre su
     ultima imagen, se vuelve a pasar el QA y se reemplaza el PNG (el original se
     conserva en carousel/assets/fallback-originals/).
  1b. REVISION FINAL ESTRICTA (strict_review.py) de LOS 10 PNG finales: detecta texto
     deformado, inventado, faltante o duplicado que el Text QA tolerante dejo pasar. Cada
     slide con error real se corrige AUTOMATICAMENTE, en la misma ejecucion y sin
     preguntar: respaldo determinista -> nueva revision; si sigue fallando, regeneracion
     permitida (solo si al slide le queda presupuesto de MAX_REGENERATIONS) -> nueva
     revision -> respaldo otra vez -> nueva revision. Nunca se cierra COMPLETO con un
     slide que no paso esta revision.
  2. manifest.json actualizado DESPUES de las correcciones (carousel/manifest.json y
     copia en la raiz del bundle).
  3. COSTO_CARRUSEL.txt reescrito DESPUES de las correcciones.
  4. Validacion del paquete: 10 PNG, copy/ (4 archivos), 8 hashtags, brief.json,
     COSTO_CARRUSEL.txt, manifest.json, pipeline_result.json.
  5. EXPORTACION LOCAL: solo en Windows se copia el paquete COMPLETO a
     %USERPROFILE%\\Downloads\\Carruseles Carousel-Gen\\<bundle_id>\\, se verifica y, si
     falla, se reintenta una vez. Fuera de Windows se registra que la exportacion no
     puede ejecutarse desde ese entorno (nunca se finge).
  6. ENTREGA CLOUD (fuera de Windows): con el bundle ya cerrado se crea UN UNICO ZIP
     outputs/bundles/<bundle_id>.zip con solo los archivos finales (10 PNG, copy/,
     brief.json, COSTO_CARRUSEL.txt, manifest.json, pipeline_result.json) dentro de la
     carpeta <bundle_id>/, se verifica (abre, CRC, lista exacta, bytes identicos) y se
     registra zip_created/zip_path/zip_verified en manifest.json y pipeline_result.json.
     Si falla, se registra el error y el ZIP no se presenta como descarga.

Nunca pregunta nada, nunca llama a Gemini y nunca lanza excepciones hacia arriba: todo
problema queda registrado en manifest.json y pipeline_result.json.
"""

import hashlib
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from carousel_common import (
    FIXED_SLIDE_COUNT, FIXED_HASHTAG_COUNT, COPY_DIRNAME, COPY_FILENAMES,
    COSTO_CARRUSEL_FILENAME, save_costo_carrusel,
)
from gemini_config import MAX_REGENERATIONS
from qa import run_qa
from text_qa import run_text_qa
import strict_review
import text_fallback

EXPORT_FOLDER_NAME = "Carruseles Carousel-Gen"
ROOT_FILES = ("brief.json", COSTO_CARRUSEL_FILENAME, "manifest.json", "pipeline_result.json")


def _now() -> str:
    return datetime.now().isoformat()


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Respaldo determinista de texto
# ---------------------------------------------------------------------------

def apply_text_fallback(bundle_path: Path, critical_phrases_fn: Optional[Callable] = None,
                        authorized_tokens_fn: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """Corrige los slides TEXT_QA_FAILED. Devuelve un registro por slide tratado."""
    manifest_path = bundle_path / "carousel" / "manifest.json"
    manifest = _read_json(manifest_path)
    brief = _read_json(bundle_path / "brief.json")
    if not manifest or not brief:
        return []
    slides_by_number = {s["number"]: s for s in brief.get("slides", [])}
    extra = authorized_tokens_fn(brief) if authorized_tokens_fn else None
    accent_color = (brief.get("visual_dna", {}).get("slide_1_master_dna") or {}).get("accent_color")
    records: List[Dict[str, Any]] = []
    for entry in manifest.get("carousel", []):
        if entry.get("status") != "TEXT_QA_FAILED":
            continue
        num = entry.get("id")
        slide = slides_by_number.get(num)
        png = bundle_path / "carousel" / f"carousel-{num:02d}.png"
        record: Dict[str, Any] = {"slide": num, "applied": False}
        if not slide or not png.is_file():
            record["error"] = "sin slide en brief.json o sin PNG que corregir"
            records.append(record)
            continue
        originals = bundle_path / "carousel" / "assets" / "fallback-originals"
        originals.mkdir(parents=True, exist_ok=True)
        original_copy = originals / f"carousel-{num:02d}.gemini.png"
        candidate = originals / f"carousel-{num:02d}.fallback.png"
        try:
            shutil.copy2(png, original_copy)
            info = text_fallback.compose_exact_text(png, slide.get("exact_text", ""),
                                                    slide.get("text_placement", ""), candidate)
            uses_mockup = bool(slide.get("uses_product_mockup_directly"))
            structural = run_qa(candidate, expected_aspect_ratio=manifest.get("aspect_ratio", "4:5"),
                                 check_color=not uses_mockup, accent_color=accent_color)
            if not structural.approved:
                raise text_fallback.FallbackError(f"QA estructural del respaldo: {structural.reason}")
            phrases = critical_phrases_fn(brief, slide) if critical_phrases_fn else None
            text_result = run_text_qa(candidate, slide.get("exact_text", ""), critical_phrases=phrases,
                                      authorized_extra_tokens=extra,
                                      uses_product_mockup=bool(slide.get("uses_product_mockup_directly")))
            shutil.copy2(candidate, png)  # reemplaza el PNG fallido por el corregido
            record.update({
                "applied": True, "compose": info, "original_saved": str(original_copy.relative_to(bundle_path)),
                "text_qa_severity": text_result.severity, "text_qa_approved": text_result.approved,
                "text_qa_detail": text_result.detail[:300],
            })
        except Exception as exc:  # noqa: BLE001 - se registra, se conserva la mejor version
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# 1b. Revision final estricta + correccion automatica
# ---------------------------------------------------------------------------

def _review(review_fn: Callable, png: Path, slide: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return review_fn(png, slide.get("exact_text", ""), slide.get("text_placement", ""),
                         bool(slide.get("uses_product_mockup_directly")))
    except Exception as exc:  # noqa: BLE001 - sin OCR no se puede verificar (nunca se aprueba)
        return {"ok": None, "errors": [], "detail": f"{type(exc).__name__}: {exc}"}


def _fallback_candidate(bundle_path: Path, slide: Dict[str, Any], png: Path, aspect_ratio: str,
                        tag: str, accent_color: Optional[str] = None) -> Path:
    """Compone el texto exacto sobre `png` (la escena/mockup no cambian) y pasa el QA estructural."""
    num = slide["number"]
    originals = bundle_path / "carousel" / "assets" / "fallback-originals"
    originals.mkdir(parents=True, exist_ok=True)
    keep = originals / f"carousel-{num:02d}.{tag}.png"
    if not keep.exists():
        shutil.copy2(png, keep)
    candidate = originals / f"carousel-{num:02d}.fallback.png"
    text_fallback.compose_exact_text(png, slide.get("exact_text", ""), slide.get("text_placement", ""), candidate)
    structural = run_qa(candidate, expected_aspect_ratio=aspect_ratio,
                         check_color=not bool(slide.get("uses_product_mockup_directly")),
                         accent_color=accent_color)
    if not structural.approved:
        raise text_fallback.FallbackError(f"QA estructural del respaldo: {structural.reason}")
    return candidate


def _snapshot(bundle_path: Path) -> Dict[Path, bytes]:
    carousel = bundle_path / "carousel"
    files = list(carousel.glob("carousel-*.png")) + [carousel / "manifest.json"]
    return {f: f.read_bytes() for f in files if f.is_file()}


def _restore(snapshot: Dict[Path, bytes], keep: Optional[Path] = None) -> None:
    for path, data in snapshot.items():
        if path != keep:
            path.write_bytes(data)


def strict_final_review(bundle_path: Path, regenerate_fn: Optional[Callable[[int], bool]] = None,
                        review_fn: Callable = strict_review.review_slide) -> Dict[str, Any]:
    """
    Revisa los 10 PNG finales y corrige automaticamente TODOS los slides con errores reales.
    Devuelve {"status", "slides": [registro por slide], "corrected", "failed", "unverified"}.
    `regenerate_fn(n)` hace UN intento nuevo del slide n (lo aporta el pipeline); solo se
    llama si al slide le queda presupuesto de MAX_REGENERATIONS.
    """
    manifest = _read_json(bundle_path / "carousel" / "manifest.json") or {}
    brief = _read_json(bundle_path / "brief.json") or {}
    aspect_ratio = manifest.get("aspect_ratio", "4:5")
    accent_color = (brief.get("visual_dna", {}).get("slide_1_master_dna") or {}).get("accent_color")
    used = {e.get("id"): int(e.get("text_qa_retry_count") or 0) for e in manifest.get("carousel", [])}
    records: List[Dict[str, Any]] = []
    for slide in brief.get("slides", []):
        num = slide["number"]
        png = bundle_path / "carousel" / f"carousel-{num:02d}.png"
        record: Dict[str, Any] = {"slide": num, "actions": []}
        if not png.is_file():
            record.update({"ok": False, "initial_errors": ["no existe el PNG"]})
            records.append(record)
            continue
        review = _review(review_fn, png, slide)
        record["initial_errors"] = review.get("errors", [])
        if review.get("ok") is not False:
            record["ok"] = review.get("ok")
            if review.get("ok") is None:
                record["detail"] = review.get("detail", "OCR no disponible")
            records.append(record)
            continue

        def try_fallback(tag: str) -> bool:
            try:
                candidate = _fallback_candidate(bundle_path, slide, png, aspect_ratio, tag, accent_color)
            except Exception as exc:  # noqa: BLE001
                record["actions"].append({"action": "respaldo", "ok": False,
                                          "error": f"{type(exc).__name__}: {exc}"})
                return False
            check = _review(review_fn, candidate, slide)
            record["actions"].append({"action": "respaldo", "ok": check.get("ok"),
                                      "errors": check.get("errors", [])})
            if check.get("ok"):
                shutil.copy2(candidate, png)
                return True
            return False

        fixed = try_fallback("gemini")
        while not fixed and regenerate_fn and used.get(num, 0) < MAX_REGENERATIONS:
            snapshot = _snapshot(bundle_path)
            used[num] = used.get(num, 0) + 1
            try:
                regenerated = bool(regenerate_fn(num))
            except Exception as exc:  # noqa: BLE001
                regenerated = False
                record["actions"].append({"action": "regeneracion", "ok": False,
                                          "error": f"{type(exc).__name__}: {exc}"})
            # Los demas slides (incluidos sus respaldos) y el manifest quedan como estaban.
            _restore(snapshot, keep=png if regenerated else None)
            if not regenerated:
                continue
            check = _review(review_fn, png, slide)
            record["actions"].append({"action": "regeneracion", "ok": check.get("ok"),
                                      "errors": check.get("errors", [])})
            fixed = bool(check.get("ok")) or try_fallback(f"regen{used[num]}")
        record["ok"] = fixed
        record["regenerations_used"] = used.get(num, 0)
        records.append(record)

    corrected = [r["slide"] for r in records if r["actions"] and r.get("ok")]
    failed = [r["slide"] for r in records if r.get("ok") is False]
    unverified = [r["slide"] for r in records if r.get("ok") is None]
    status = "CON_ERRORES" if failed else ("NO_VERIFICABLE" if unverified else "APROBADA")
    return {"status": status, "slides": records, "corrected": corrected, "failed": failed,
            "unverified": unverified, "checked_at": _now()}


# ---------------------------------------------------------------------------
# 2-3. manifest.json y COSTO_CARRUSEL.txt despues de las correcciones
# ---------------------------------------------------------------------------

def update_manifest(bundle_path: Path, fallback: List[Dict[str, Any]],
                    strict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    manifest_path = bundle_path / "carousel" / "manifest.json"
    manifest = _read_json(manifest_path) or {}
    strict_by_slide = {r["slide"]: r for r in (strict or {}).get("slides", [])}
    by_slide = {r["slide"]: r for r in fallback}
    for entry in manifest.get("carousel", []):
        rec = by_slide.get(entry.get("id"))
        if not rec:
            continue
        entry["text_fallback"] = rec
        if rec.get("applied"):
            ok = rec.get("text_qa_approved")
            entry["status"] = "TEXT_QA_APPROVED" if ok else "TEXT_FALLBACK_UNVERIFIED"
            entry["text_qa_status"] = entry["status"]
    text_qa_block = manifest.setdefault("text_qa", {})
    fixed = {r["slide"] for r in fallback if r.get("applied") and r.get("text_qa_approved")}
    pending = [p for p in text_qa_block.get("pending_slides", []) if p.get("slide") not in fixed]
    for rec in fallback:
        if rec.get("applied") and not rec.get("text_qa_approved"):
            pending = [p for p in pending if p.get("slide") != rec["slide"]]
            pending.append({"slide": rec["slide"], "status": "TEXT_FALLBACK_UNVERIFIED", "attempts": None,
                            "reason": "texto compuesto por el respaldo; el OCR no pudo confirmarlo",
                            "png_delivered": True})
        elif not rec.get("applied"):
            pending = [p for p in pending if p.get("slide") != rec["slide"]]
            pending.append({"slide": rec["slide"], "status": "TEXT_FALLBACK_FAILED", "attempts": None,
                            "reason": rec.get("error"), "png_delivered": True})
    pending.sort(key=lambda p: p.get("slide") or 0)
    text_qa_block["pending_slides"] = pending
    # Se conservan los respaldos de cierres anteriores del mismo bundle.
    text_qa_block["text_fallback_slides"] = sorted(set(text_qa_block.get("text_fallback_slides") or [])
                                                  | {r["slide"] for r in fallback if r.get("applied")})
    strict_fixed = set()
    for entry in manifest.get("carousel", []):
        rec = strict_by_slide.get(entry.get("id"))
        if not rec:
            continue
        entry["strict_review"] = rec
        if rec.get("ok") is False:
            entry["status"] = entry["text_qa_status"] = "TEXT_QA_FAILED"
        elif rec.get("ok") and rec.get("actions"):
            entry["status"] = entry["text_qa_status"] = "TEXT_QA_APPROVED"
            if any(a["action"] == "respaldo" and a.get("ok") for a in rec["actions"]):
                strict_fixed.add(entry.get("id"))
    if strict is not None:
        failed = set(strict.get("failed", []))
        pending = [p for p in text_qa_block["pending_slides"] if p.get("slide") not in failed]
        pending += [{"slide": n, "status": "TEXT_QA_FAILED", "attempts": None, "png_delivered": True,
                     "reason": "revision final estricta: " + "; ".join(strict_by_slide[n].get("initial_errors", []))}
                    for n in sorted(failed)]
        text_qa_block["pending_slides"] = sorted(pending, key=lambda p: p.get("slide") or 0)
        text_qa_block["text_fallback_slides"] = sorted(set(text_qa_block["text_fallback_slides"]) | strict_fixed)
        text_qa_block["strict_review"] = {k: strict[k] for k in ("status", "corrected", "failed", "unverified",
                                                                 "checked_at")}
        fixed = fixed | strict_fixed
        if failed:
            text_qa_block["status"] = "FAILED"
        elif fixed:
            text_qa_block["status"] = "APPROVED_WITH_FALLBACK"
    still_failed = any(e.get("status") == "TEXT_QA_FAILED" for e in manifest.get("carousel", []))
    if text_qa_block.get("status") == "FAILED" and not still_failed:
        text_qa_block["status"] = "APPROVED_WITH_FALLBACK" if fixed else text_qa_block["status"]
    manifest["updated_at"] = _now()
    _write_json(manifest_path, manifest)
    shutil.copy2(manifest_path, bundle_path / "manifest.json")
    return manifest


def rewrite_costo(bundle_path: Path, bundle_id: str, manifest: Dict[str, Any]) -> bool:
    cost_summary = _read_json(bundle_path / "cost_log.json")
    if cost_summary is None:
        return False
    save_costo_carrusel(
        bundle_path, bundle_id, cost_summary, manifest.get("model", "N/D"), manifest.get("image_size", "N/D"),
        manifest.get("aspect_ratio", "4:5"), manifest.get("total_slides") or FIXED_SLIDE_COUNT,
        manifest.get("text_qa"), str(bundle_path),
    )
    return True


# ---------------------------------------------------------------------------
# 4. Validacion del paquete
# ---------------------------------------------------------------------------

def check_package(folder: Path) -> Dict[str, bool]:
    carousel_dir = folder / "carousel"
    copy_dir = folder / COPY_DIRNAME
    pngs = sorted(carousel_dir.glob("carousel-*.png")) if carousel_dir.is_dir() else []
    hashtags = copy_dir / "HASHTAGS.txt"
    n_tags = len(hashtags.read_text(encoding="utf-8").split()) if hashtags.is_file() else 0
    checks = {f"{FIXED_SLIDE_COUNT} PNG en carousel/": len(pngs) == FIXED_SLIDE_COUNT}
    for name in COPY_FILENAMES:
        path = copy_dir / name
        checks[f"copy/{name}"] = path.is_file() and path.stat().st_size > 0
    checks[f"HASHTAGS.txt con exactamente {FIXED_HASHTAG_COUNT}"] = n_tags == FIXED_HASHTAG_COUNT
    for name in ROOT_FILES:
        checks[name] = (folder / name).is_file()
    return checks


# ---------------------------------------------------------------------------
# 5. Exportacion local a Windows
# ---------------------------------------------------------------------------

def windows_export_dir(bundle_id: str) -> Optional[Path]:
    profile = os.environ.get("USERPROFILE")
    if sys.platform != "win32" or not profile:
        return None
    return Path(profile) / "Downloads" / EXPORT_FOLDER_NAME / bundle_id


def _copy_package(bundle_path: Path, dest: Path) -> None:
    (dest / "carousel").mkdir(parents=True, exist_ok=True)
    (dest / COPY_DIRNAME).mkdir(parents=True, exist_ok=True)
    sources = sorted((bundle_path / "carousel").glob("carousel-*.png"))
    wanted = {p.name for p in sources}
    for stale in (dest / "carousel").glob("carousel-*.png"):
        if stale.name not in wanted:
            stale.unlink()
    for src in sources:
        shutil.copy2(src, dest / "carousel" / src.name)
    for name in COPY_FILENAMES:
        src = bundle_path / COPY_DIRNAME / name
        if src.is_file():
            shutil.copy2(src, dest / COPY_DIRNAME / name)
    for name in ROOT_FILES:
        src = bundle_path / name
        if src.is_file():
            shutil.copy2(src, dest / name)


def export_to_windows(bundle_path: Path, bundle_id: str) -> Dict[str, Any]:
    """Copia y verifica el paquete completo en Downloads. Reintenta una vez si falla."""
    dest = windows_export_dir(bundle_id)
    if dest is None:
        return {"status": "NO_DISPONIBLE_FUERA_DE_WINDOWS", "platform": sys.platform,
                "detail": "La exportacion a Downloads de Windows no puede ejecutarse desde este entorno; "
                          "el bundle queda en outputs/bundles/."}
    errors: List[str] = []
    for attempt in (1, 2):
        try:
            _copy_package(bundle_path, dest)
            checks = check_package(dest)
            missing = [name for name, ok in checks.items() if not ok]
            if not missing:
                return {"status": "OK", "path": str(dest), "attempts": attempt, "checks": checks, "errors": errors}
            errors.append(f"intento {attempt}: faltan en la copia: {missing}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"intento {attempt}: {type(exc).__name__}: {exc}")
    return {"status": "FALLIDA", "path": str(dest), "attempts": 2, "errors": errors}


# ---------------------------------------------------------------------------
# 6. Entrega cloud: un unico ZIP verificado del bundle final
# ---------------------------------------------------------------------------

def zip_path_for(bundle_path: Path, bundle_id: str) -> Path:
    return bundle_path.parent / f"{bundle_id}.zip"


def zip_members(bundle_path: Path) -> List[str]:
    """Rutas (relativas al bundle) de los archivos finales que van en el ZIP. Nada mas."""
    members = [f"carousel/carousel-{n:02d}.png" for n in range(1, FIXED_SLIDE_COUNT + 1)]
    members += [f"{COPY_DIRNAME}/{name}" for name in COPY_FILENAMES]
    members += list(ROOT_FILES)
    return members


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bundle_zip(zip_file: Path, bundle_path: Path, bundle_id: str) -> List[str]:
    """Devuelve la lista de problemas (vacia = ZIP correcto y con los archivos finales)."""
    problems: List[str] = []
    expected = {f"{bundle_id}/{m}": bundle_path / m for m in zip_members(bundle_path)}
    try:
        with zipfile.ZipFile(zip_file) as zf:
            bad = zf.testzip()
            if bad:
                problems.append(f"CRC incorrecto en {bad}")
            names = set(zf.namelist())
            if names != set(expected):
                missing = sorted(set(expected) - names)
                extra = sorted(names - set(expected))
                problems.append(f"contenido distinto: faltan {missing} sobran {extra}")
            pngs = [n for n in names if n.startswith(f"{bundle_id}/carousel/") and n.endswith(".png")]
            if len(pngs) != FIXED_SLIDE_COUNT:
                problems.append(f"{len(pngs)} PNG en el ZIP (se esperaban {FIXED_SLIDE_COUNT})")
            for name, src in expected.items():
                if name in names and hashlib.sha256(zf.read(name)).hexdigest() != _sha(src):
                    problems.append(f"{name} no coincide con el archivo final del bundle")
    except (OSError, zipfile.BadZipFile) as exc:
        problems.append(f"el ZIP no se puede abrir: {type(exc).__name__}: {exc}")
    return problems


def _record_zip(bundle_path: Path, result_path: Path, result: Dict[str, Any], info: Dict[str, Any]) -> None:
    """Registra la entrega en manifest.json (carousel/ y raiz) y en pipeline_result.json."""
    manifest_path = bundle_path / "carousel" / "manifest.json"
    manifest = _read_json(manifest_path)
    if manifest is not None:
        manifest["cloud_export"] = info
        _write_json(manifest_path, manifest)
        shutil.copy2(manifest_path, bundle_path / "manifest.json")
    result["cloud_export"] = info
    _write_json(result_path, result)


def create_bundle_zip(bundle_path: Path, bundle_id: str, result_path: Optional[Path] = None,
                      result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Crea y verifica outputs/bundles/<bundle_id>.zip. El registro (zip_created, zip_path,
    zip_verified) se escribe ANTES de comprimir, para que el manifest.json y el
    pipeline_result.json del ZIP sean los finales; si la verificacion falla se reescribe
    con el error y el ZIP se elimina (nunca se presenta como descarga lista).
    """
    result_path = result_path or bundle_path / "pipeline_result.json"
    result = result if result is not None else (_read_json(result_path) or {})
    zip_file = zip_path_for(bundle_path, bundle_id)
    ok_info = {"zip_created": True, "zip_path": str(zip_file), "zip_verified": True,
               "files": len(zip_members(bundle_path)), "created_at": _now()}
    missing = [m for m in zip_members(bundle_path) if not (bundle_path / m).is_file()]
    if missing:
        info = {"zip_created": False, "zip_path": str(zip_file), "zip_verified": False,
                "errors": [f"faltan archivos finales en el bundle: {missing}"]}
        _record_zip(bundle_path, result_path, result, info)
        return info
    _record_zip(bundle_path, result_path, result, ok_info)
    tmp = zip_file.with_name(zip_file.name + ".tmp")
    errors: List[str] = []
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for member in zip_members(bundle_path):
                zf.write(bundle_path / member, f"{bundle_id}/{member}")
        os.replace(tmp, zip_file)
        errors = verify_bundle_zip(zip_file, bundle_path, bundle_id)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        tmp.unlink(missing_ok=True)
    if not errors:
        return ok_info
    zip_file.unlink(missing_ok=True)
    info = {"zip_created": False, "zip_path": str(zip_file), "zip_verified": False, "errors": errors}
    _record_zip(bundle_path, result_path, result, info)
    return info


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------

def close_bundle(bundle_path: Path, bundle_id: str, build_result: Callable[[], Dict[str, Any]],
                 critical_phrases_fn: Optional[Callable] = None,
                 authorized_tokens_fn: Optional[Callable] = None,
                 regenerate_fn: Optional[Callable[[int], bool]] = None,
                 strict_review_enabled: bool = True,
                 review_fn: Callable = strict_review.review_slide) -> Dict[str, Any]:
    """Ejecuta el cierre completo y devuelve el pipeline_result final (ya escrito)."""
    fallback: List[Dict[str, Any]] = []
    manifest: Dict[str, Any] = {}
    errors: List[str] = []
    strict: Optional[Dict[str, Any]] = None
    try:
        fallback = apply_text_fallback(bundle_path, critical_phrases_fn, authorized_tokens_fn)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"respaldo de texto: {type(exc).__name__}: {exc}")
    if strict_review_enabled:
        try:
            strict = strict_final_review(bundle_path, regenerate_fn, review_fn)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"revision final estricta: {type(exc).__name__}: {exc}")
    # manifest, COSTO y pipeline_result se escriben SOLO despues de todas las correcciones.
    try:
        manifest = update_manifest(bundle_path, fallback, strict)
        rewrite_costo(bundle_path, bundle_id, manifest)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"manifest/costo: {type(exc).__name__}: {exc}")

    result = build_result()
    result["text_fallback"] = fallback
    result["strict_review"] = strict if strict is not None else {
        "status": "OMITIDA", "detail": "revision estricta desactivada (imagenes sin texto real)"}
    result_path = bundle_path / "pipeline_result.json"
    _write_json(result_path, result)  # existe antes de validar el paquete

    checks = check_package(bundle_path)
    missing = [name for name, ok in checks.items() if not ok]
    warnings = list(result.get("warnings") or [])
    qa_open = [e.get("id") for e in manifest.get("carousel", []) if e.get("status") == "TEXT_QA_FAILED"]
    strict_failed = list((strict or {}).get("failed", []))
    strict_unverified = list((strict or {}).get("unverified", []))
    if missing or errors or strict_failed:
        status = "INCOMPLETO"  # nunca COMPLETO con un slide cuyo texto no es correcto
    elif warnings or qa_open or strict_unverified:
        status = "COMPLETO_CON_ADVERTENCIAS"
    else:
        status = "COMPLETO"
    result["closure"] = {
        "status": status, "checks": checks, "missing": missing, "errors": errors,
        "slides_with_open_text_errors": sorted(set(qa_open) | set(strict_failed)),
        "slides_text_unverified": strict_unverified, "closed_at": _now(),
    }
    _write_json(result_path, result)

    export = export_to_windows(bundle_path, bundle_id)
    result["windows_export"] = export
    _write_json(result_path, result)
    if export.get("status") == "OK":
        # La copia en Downloads debe tener el pipeline_result final (con la exportacion).
        shutil.copy2(result_path, Path(export["path"]) / "pipeline_result.json")
    elif export.get("status") == "NO_DISPONIBLE_FUERA_DE_WINDOWS":
        # Cloud: la entrega es UN UNICO ZIP del bundle ya cerrado (nunca C:\Users\...).
        create_bundle_zip(bundle_path, bundle_id, result_path, result)
    return result


def format_report(bundle_id: str, bundle_path: Path, result: Dict[str, Any]) -> str:
    """Informe final fijo: el ultimo bloque de la ejecucion. Sin preguntas."""
    closure = result.get("closure", {})
    export = result.get("windows_export", {})
    cost = result.get("cost_usd")
    lines = [
        "=" * 50, "INFORME FINAL carousel-gen", "=" * 50,
        f"Bundle: {bundle_id}",
        f"Estado: {closure.get('status', 'N/D')}",
        f"Generaciones Gemini: {result.get('gemini_calls', 'N/D')} (regeneraciones: {result.get('retries', 'N/D')})",
        f"TEXT QA: {result.get('text_qa_status', 'N/D')}",
        f"Costo estimado: {f'${cost:.4f} USD' if isinstance(cost, (int, float)) else 'N/D'}",
        "Archivos:",
    ]
    lines += [f"  [{'OK' if ok else 'FALTA'}] {name}" for name, ok in closure.get("checks", {}).items()]
    applied = [r["slide"] for r in result.get("text_fallback", []) if r.get("applied")]
    strict = result.get("strict_review") or {}
    applied = sorted(set(applied) | set(strict.get("corrected", [])))
    lines.append(f"Respaldo de texto aplicado: slides {applied}" if applied else "Respaldo de texto: no necesario")
    lines.append(f"Revision final estricta: {strict.get('status', 'N/D')}"
                 + (f" - slides con error: {strict['failed']}" if strict.get("failed") else "")
                 + (f" - sin verificar: {strict['unverified']}" if strict.get("unverified") else ""))
    warnings = result.get("warnings") or []
    lines.append("Advertencias:" if warnings else "Advertencias: ninguna")
    for w in warnings:
        lines.append(f"  Slide {w.get('slide')}: {w.get('status')} - {w.get('reason') or 'N/D'}")
    for err in closure.get("errors", []):
        lines.append(f"  Error: {err}")
    lines.append(f"Bundle: {bundle_path}")
    if export.get("status") == "OK":
        lines.append(f"Downloads: {export['path']} (verificado, intento {export.get('attempts')})")
    elif export.get("status") == "FALLIDA":
        lines.append(f"Downloads: EXPORTACION FALLIDA -> {export.get('errors')}")
    elif result.get("cloud_export"):
        cloud = result["cloud_export"]
        if cloud.get("zip_verified"):
            lines.append(f"Descarga: {cloud['zip_path']} (ZIP unico, verificado)")
        else:
            lines.append(f"Descarga: ZIP NO DISPONIBLE (error) -> {cloud.get('errors')}")
    else:
        lines.append(f"Downloads: {export.get('detail', 'N/D')}")
    lines.append("FIN")
    return "\n".join(lines)


if __name__ == "__main__":
    # Crea y verifica el ZIP de un bundle ya cerrado: python cierre_bundle.py --zip <bundle_id>
    from carousel_common import OUTPUTS_DIR
    if len(sys.argv) != 3 or sys.argv[1] != "--zip":
        print("Uso: python cierre_bundle.py --zip <bundle_id>")
        sys.exit(2)
    info = create_bundle_zip(OUTPUTS_DIR / sys.argv[2], sys.argv[2])
    print(json.dumps(info, ensure_ascii=False, indent=2))
    sys.exit(0 if info.get("zip_verified") else 1)
