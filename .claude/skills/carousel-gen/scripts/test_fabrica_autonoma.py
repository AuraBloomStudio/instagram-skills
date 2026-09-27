#!/usr/bin/env python3
"""
test_fabrica_autonoma.py - carousel-gen como fabrica autonoma (2026-09-26).

  TEST 1  — Modo sin preguntas: SKILL.md sin AskUserQuestion ni frases que piden
            confirmacion, pegar texto o el enlace; regla "CERO PREGUNTAS" presente.
  TEST 2  — Bundle creado al inicio y brief completo al primer intento: prepare_carousel
            crea outputs/bundles/<id>/carousel/assets/, guarda ahi la referencia y el
            brief pasa load_brief() con los 6 campos derivados y valores validos.
  TEST 3  — Maximo 2 regeneraciones por slide (techo duro de configuracion).
  TEST 4  — Respaldo determinista: sobre una imagen con el texto MAL, compone el texto
            exacto; el Text QA lo aprueba y el texto erroneo desaparece.
  TEST 5  — Cierre DESPUES de las correcciones: el slide TEXT_QA_FAILED se corrige, el
            original se conserva, manifest/COSTO/pipeline_result se escriben despues del
            PNG corregido y el cierre queda COMPLETO.
  TEST 6  — Exportacion Windows: copia completa y verificada (10 PNG, copy/, manifest,
            pipeline_result); fuera de Windows se registra que no puede ejecutarse.
  TEST 7  — Exportacion: si la primera copia falla, se reintenta una vez y se registra el
            error; si ambas fallan, FALLIDA (nunca se finge).
  TEST 8  — Pipeline completo (proveedor falso): exit 0, cierre COMPLETO, exportacion
            verificada, informe final que termina en FIN y sin preguntas.
  TEST 9  — Revision final estricta: detecta palabra deformada ("necesisitaste"), texto
            inventado, palabra duplicada y palabra faltante; aprueba el texto correcto y el
            "¿" que el OCR pega a la palabra ("gpor").
  TEST 10 — Correccion automatica: un slide que el Text QA tolerante APROBO con el texto mal
            se detecta en el cierre, se corrige con el respaldo sin preguntar, se reverifica
            y el cierre queda COMPLETO.
  TEST 11 — Si el respaldo no basta: regeneracion automatica solo dentro del presupuesto
            (MAX_REGENERATIONS), los demas slides quedan intactos y el cierre NUNCA es
            COMPLETO con un slide que sigue mal.
  TEST 12 — Entrega cloud: fuera de Windows, tras cerrar el bundle, se crea UN UNICO ZIP
            outputs/bundles/<id>.zip con exactamente los archivos finales (10 PNG, copy/,
            brief, COSTO, manifest, pipeline_result) dentro de <id>/, sin originales,
            .previo, staging ni temporales; se verifica y se registra en manifest.json y
            pipeline_result.json; nunca se escribe en Downloads.
  TEST 13 — ZIP fallido = error real: zip_verified False, ZIP eliminado, error registrado,
            el informe NO dice que la descarga esta lista.
  TEST 14 — Windows local conserva su comportamiento: copia verificada a Downloads y
            ningun ZIP.

Sin llamadas a Gemini ($0). Downloads se redirige a una carpeta temporal.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import cierre_bundle  # noqa: E402
import gemini_config  # noqa: E402
import strict_review  # noqa: E402
import text_fallback  # noqa: E402
from carousel_common import OUTPUTS_DIR, REQUIRED_SLIDE_FIELDS, load_brief, FIXED_PURCHASE_URL, FIXED_PRODUCT_NAME  # noqa: E402
from text_qa import run_text_qa, extract_text_from_image, tokenize  # noqa: E402
from test_pipeline import _make_brief, _tiny_png  # noqa: E402
from test_prepare_carousel import _make_decisions  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict] = []
SCRIPTS = Path(__file__).parent
SKILL_DIR = SCRIPTS.parent
EXACT = "No necesariamente porque queramos sufrir, sino porque aquello fue dificil de obtener."
WRONG = "Tiada la differencia es qae mi papa no gace nada de nada."


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    line = f"[{status}] {test_id}: {description}" + (f"\n   {detail}" if detail else "")
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))


def _wrong_text_slide(path: Path) -> None:
    """Slide 1080x1350 (4:5) con foto oscura y el texto MAL dibujado en el tercio inferior."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1080, 1350), (70, 60, 55))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 1080, 700], fill=(120, 110, 100))
    font = ImageFont.truetype(str(text_fallback.FONT_PATH), 52)
    y = 820
    for line in ("Tiada la differencia es qae", "mi papa no gace nada", "de nada."):
        draw.text((110, y), line, font=font, fill=(245, 197, 24))
        y += 72
    img.save(path)


def _only_slide_3(review_calls: List[int] = None):
    """review_fn: revision REAL para el slide 3; los demas (PNG sinteticos sin texto) se dan por buenos."""
    def review(png, exact_text, text_placement="", uses_mockup=False):
        if png.name.startswith("carousel-03") or "fallback" in png.name:
            if review_calls is not None:
                review_calls.append(3)
            return strict_review.review_slide(png, exact_text, text_placement, uses_mockup)
        return {"ok": True, "errors": [], "readings": 0}
    return review


def _render(text: str, path: Path) -> None:
    """Slide 4:5 con `text` dibujado por el respaldo (Poppins) sobre una escena lisa."""
    from PIL import Image
    base = path.with_suffix(".base.png")
    Image.new("RGB", (1080, 1350), (90, 80, 70)).save(base)
    text_fallback.compose_exact_text(base, text, "lower_third_centered", path)
    base.unlink()


def test_1_sin_preguntas():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    header = text.split("---", 2)[1]
    forbidden = ["¿Confirmas", "Pega lo que falte", "pide el enlace", "Pegalo completo", "DETENER y pedir"]
    found = [f for f in forbidden if f in text]
    ok = ("AskUserQuestion" not in header and "FÁBRICA AUTÓNOMA: CERO PREGUNTAS" in text
          and "¿Quieres que" in text and not found)
    report("TEST 1", "Modo sin preguntas: sin AskUserQuestion, regla CERO PREGUNTAS y sin frases que piden "
                     "confirmacion, texto o enlace", ok, f"prohibidas_encontradas={found}")


def test_2_bundle_al_inicio_y_brief_completo():
    bundle_id = "__test-fabrica-brief__"
    bundle = OUTPUTS_DIR / bundle_id
    tmp = Path(tempfile.mkdtemp(prefix="fab_t2_"))
    try:
        decisions = _make_decisions(bundle_id)
        for s in decisions["slides"]:
            s.pop("text_break_reason", None)
        decisions["slides"][2]["text_break_reason"] = "valor_inventado"
        (tmp / "d.json").write_text(json.dumps(decisions), encoding="utf-8")
        (tmp / "ref.png").write_bytes(_tiny_png())
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("CLAUDE_CODE_SESSION_ID", None)
        r = subprocess.run([sys.executable, str(SCRIPTS / "prepare_carousel.py"), str(tmp / "d.json"),
                            "--fake-reference", str(tmp / "ref.png")],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        brief = load_brief(bundle) if r.returncode == 0 else None
        derived = ("word_count", "text_density", "estimated_text_area", "text_area_percentage",
                   "visual_balance", "text_break_reason")
        valid = brief is not None and all(
            all(f in s for f in list(REQUIRED_SLIDE_FIELDS) + list(derived))
            and s["text_density"] in ("LOW", "MEDIUM", "HIGH")
            and s["visual_balance"] in ("balanced", "text_heavy", "underutilized")
            and s["text_break_reason"] in ("natural_sentence_boundary", "paragraph_boundary", "density_rebalance")
            for s in brief["slides"])
        ref = bundle / "carousel" / "assets" / "viral-reference.png"
        ok = r.returncode == 0 and ref.is_file() and "scratchpad" not in str(ref).lower() and valid \
            and len(brief["slides"]) == 10
        report("TEST 2", "Bundle creado al inicio (referencia en carousel/assets/) y brief completo con los 6 "
                         "campos derivados y valores validos al primer intento", ok,
               f"rc={r.returncode} ref={ref.is_file()} brief_valido={valid}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(bundle, ignore_errors=True)


def test_3_maximo_dos_regeneraciones():
    original = os.environ.get("MAX_RETRIES")
    try:
        os.environ["MAX_RETRIES"] = "9"
        value = gemini_config.load_config().max_retries
    finally:
        if original is None:
            os.environ.pop("MAX_RETRIES", None)
        else:
            os.environ["MAX_RETRIES"] = original
    ok = gemini_config.MAX_REGENERATIONS == 2 and value == 2
    report("TEST 3", "Maximo 2 regeneraciones por slide aunque la configuracion pida mas "
                     "(detalle de intentos en test_regen_rule.py)", ok, f"max_retries={value}")


def test_4_respaldo_determinista():
    tmp = Path(tempfile.mkdtemp(prefix="fab_t4_"))
    try:
        src, out = tmp / "wrong.png", tmp / "fixed.png"
        _wrong_text_slide(src)
        before = run_text_qa(src, EXACT)
        info = text_fallback.compose_exact_text(src, EXACT, "lower_third_centered", out)
        after = run_text_qa(out, EXACT)
        rendered = set(tokenize(extract_text_from_image(out) or ""))
        wrong_gone = not ({"tiada", "differencia", "qae", "gace"} & rendered)
        ok = (not before.approved) and after.approved and wrong_gone
        report("TEST 4", "Respaldo determinista: texto MAL -> texto exacto compuesto, Text QA aprueba y el "
                         "texto erroneo desaparece", ok,
               f"antes={before.severity} despues={after.severity} info={info} erroneo_eliminado={wrong_gone}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _fake_bundle(bundle_id: str, profile: Path) -> subprocess.CompletedProcess:
    bundle = OUTPUTS_DIR / bundle_id
    shutil.rmtree(bundle, ignore_errors=True)
    (bundle / "carousel" / "assets").mkdir(parents=True)
    (bundle / "carousel" / "assets" / "viral-reference.png").write_bytes(_tiny_png())
    brief = _make_brief(10, bundle_id)
    brief["product"] = {"product_name": FIXED_PRODUCT_NAME, "purchase_url": FIXED_PURCHASE_URL}
    brief["slides"][2]["exact_text"] = EXACT
    brief["slides"][2]["text_placement"] = "lower_third_centered"
    (bundle / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
    (bundle / "copy.json").write_text(json.dumps({
        "description": "Descripcion", "cta": "CTA", "hashtags": [f"#t{i}" for i in range(1, 9)],
        "product": FIXED_PRODUCT_NAME, "purchase_url": FIXED_PURCHASE_URL}), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", USERPROFILE=str(profile))
    return subprocess.run([sys.executable, str(SCRIPTS / "run_carousel_pipeline.py"), bundle_id,
                           "--copy-json", str(bundle / "copy.json"), "--fake-provider", "--force-direct"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=300)


def test_5_cierre_despues_de_corregir():
    bundle_id = "__test-fabrica-cierre__"
    bundle = OUTPUTS_DIR / bundle_id
    profile = Path(tempfile.mkdtemp(prefix="fab_t5_profile_"))
    try:
        _fake_bundle(bundle_id, profile)
        png = bundle / "carousel" / "carousel-03.png"
        _wrong_text_slide(png)
        wrong_sha = hashlib.sha256(png.read_bytes()).hexdigest()
        manifest_path = bundle / "carousel" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for e in manifest["carousel"]:
            if e["id"] == 3:
                e["status"] = e["text_qa_status"] = "TEXT_QA_FAILED"
        manifest["text_qa"] = {"status": "FAILED", "pending_slides": [
            {"slide": 3, "status": "TEXT_QA_FAILED", "attempts": 3, "reason": "MISSING_TOKEN", "png_delivered": True}]}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        time.sleep(1.1)
        with patch.dict(os.environ, {"USERPROFILE": str(profile)}):
            result = cierre_bundle.close_bundle(bundle, bundle_id, lambda: {"warnings": json.loads(
                (bundle / "carousel" / "manifest.json").read_text(encoding="utf-8"))["text_qa"]["pending_slides"]},
                review_fn=_only_slide_3())
        new_sha = hashlib.sha256(png.read_bytes()).hexdigest()
        final_manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        slide3 = next(e for e in final_manifest["carousel"] if e["id"] == 3)
        png_mtime = png.stat().st_mtime
        written_after = all((bundle / n).stat().st_mtime >= png_mtime for n in
                            ("manifest.json", "COSTO_CARRUSEL.txt", "pipeline_result.json"))
        original_kept = (bundle / "carousel" / "assets" / "fallback-originals" / "carousel-03.gemini.png").is_file()
        ok = (new_sha != wrong_sha and slide3["status"] == "TEXT_QA_APPROVED" and original_kept and written_after
              and result["closure"]["status"] == "COMPLETO" and not final_manifest["text_qa"]["pending_slides"])
        report("TEST 5", "Cierre DESPUES de corregir: PNG reemplazado, original conservado, manifest/COSTO/"
                         "pipeline_result escritos despues, cierre COMPLETO", ok,
               f"status3={slide3['status']} escritos_despues={written_after} cierre={result['closure']['status']}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


def test_6_exportacion_windows():
    bundle_id = "__test-fabrica-export__"
    bundle = OUTPUTS_DIR / bundle_id
    profile = Path(tempfile.mkdtemp(prefix="fab_t6_profile_"))
    try:
        _fake_bundle(bundle_id, profile)
        with patch.dict(os.environ, {"USERPROFILE": str(profile)}), patch.object(sys, "platform", "win32"):
            export = cierre_bundle.export_to_windows(bundle, bundle_id)
        dest = profile / "Downloads" / "Carruseles Carousel-Gen" / bundle_id
        checks = cierre_bundle.check_package(dest)
        with patch.object(sys, "platform", "linux"):
            remote = cierre_bundle.export_to_windows(bundle, bundle_id + "-x")
        ok = (export["status"] == "OK" and all(checks.values())
              and len(list((dest / "carousel").glob("carousel-*.png"))) == 10
              and remote["status"] == "NO_DISPONIBLE_FUERA_DE_WINDOWS"
              and not (profile / "Downloads" / "Carruseles Carousel-Gen" / (bundle_id + "-x")).exists())
        report("TEST 6", "Exportacion Windows completa y verificada (10 PNG, copy/, manifest, pipeline_result); "
                         "fuera de Windows se registra que no puede ejecutarse", ok,
               f"export={export['status']} checks_ok={all(checks.values())} remoto={remote['status']}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


def test_7_reintento_y_fallo_honesto():
    bundle_id = "__test-fabrica-retry__"
    bundle = OUTPUTS_DIR / bundle_id
    profile = Path(tempfile.mkdtemp(prefix="fab_t7_profile_"))
    real_copy = cierre_bundle._copy_package
    calls = {"n": 0}

    def flaky(src, dest):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disco ocupado (simulado)")
        real_copy(src, dest)

    try:
        _fake_bundle(bundle_id, profile)
        with patch.dict(os.environ, {"USERPROFILE": str(profile)}), patch.object(sys, "platform", "win32"):
            with patch.object(cierre_bundle, "_copy_package", side_effect=flaky):
                retried = cierre_bundle.export_to_windows(bundle, bundle_id)
            with patch.object(cierre_bundle, "_copy_package", side_effect=OSError("sin permisos (simulado)")):
                failed = cierre_bundle.export_to_windows(bundle, bundle_id + "-f")
        ok = (retried["status"] == "OK" and retried["attempts"] == 2 and retried["errors"]
              and failed["status"] == "FALLIDA" and len(failed["errors"]) == 2)
        report("TEST 7", "Exportacion: primer fallo -> reintento OK con el error registrado; dos fallos -> "
                         "FALLIDA (nunca se finge)", ok,
               f"reintento={retried['status']}/{retried['attempts']} fallo={failed['status']}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


def test_8_pipeline_completo():
    bundle_id = "__test-fabrica-pipeline__"
    bundle = OUTPUTS_DIR / bundle_id
    profile = Path(tempfile.mkdtemp(prefix="fab_t8_profile_"))
    try:
        r = _fake_bundle(bundle_id, profile)
        result = json.loads((bundle / "pipeline_result.json").read_text(encoding="utf-8"))
        block = r.stdout[r.stdout.find("INFORME FINAL carousel-gen"):]
        dest = profile / "Downloads" / "Carruseles Carousel-Gen" / bundle_id
        exported = json.loads((dest / "pipeline_result.json").read_text(encoding="utf-8")) if dest.exists() else {}
        root_ok = all((bundle / n).is_file() for n in ("brief.json", "COSTO_CARRUSEL.txt", "manifest.json",
                                                        "pipeline_result.json"))
        ok = (r.returncode == 0 and result["closure"]["status"] == "COMPLETO" and root_ok
              and result["windows_export"]["status"] == "OK"
              and exported.get("windows_export", {}).get("status") == "OK"
              and block.rstrip().endswith("FIN") and "¿" not in block and "?" not in block)
        report("TEST 8", "Pipeline completo: exit 0, cierre COMPLETO, raiz del bundle completa, exportacion "
                         "verificada con el pipeline_result final e informe sin preguntas", ok,
               f"rc={r.returncode} cierre={result['closure']['status']} export={result['windows_export']['status']}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


def test_9_revision_estricta_detecta_errores_reales():
    tmp = Path(tempfile.mkdtemp(prefix="fab_t9_"))
    expected = "Aquello que alguna vez necesitaste de papá no determina cuánto vales tú."
    cases = {
        "correcto": ("Aquello que alguna vez necesitaste de papá no determina cuánto vales tú.", True),
        "deformada": ("Aquello que alguna vez necesisitaste de papá no determina cuánto vales tú.", False),
        "inventado": ("Aquello que alguna vez necesitaste de papá no determes; no determina cuánto vales tú.", False),
        "duplicada": ("Aquello que alguna vez necesitaste de de papá no determina cuánto vales tú.", False),
        "faltante": ("Aquello que alguna vez necesitaste de papá no determina vales tú.", False),
    }
    try:
        got = {}
        for name, (text, _) in cases.items():
            png = tmp / f"{name}.png"
            _render(text, png)
            got[name] = strict_review.review_slide(png, expected, "lower_third_centered")
        question = "Una pregunta difícil: ¿por qué no fui suficiente para que quisiera estar?"
        _render(question, tmp / "pregunta.png")
        q = strict_review.review_slide(tmp / "pregunta.png", question, "lower_third_centered")
        glued = strict_review.tokens_equivalent("por", "gpor", after_opening_mark=True)
        not_glued = strict_review.tokens_equivalent("y", "'y") or strict_review.tokens_equivalent("por", "gpor")
        ok = (all(got[n]["ok"] is want for n, (_, want) in cases.items()) and q["ok"] is True
              and glued and not not_glued)
        report("TEST 9", "Revision final estricta: detecta deformada/inventado/duplicada/faltante y aprueba el "
                         "texto correcto y el '¿' pegado por el OCR", ok,
               " ".join(f"{n}={got[n]['ok']}" for n in cases) + f" pregunta={q['ok']} gpor={glued}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_10_correccion_automatica_de_slide_aprobado_con_error():
    bundle_id = "__test-fabrica-estricta__"
    bundle = OUTPUTS_DIR / bundle_id
    profile = Path(tempfile.mkdtemp(prefix="fab_t10_profile_"))
    try:
        _fake_bundle(bundle_id, profile)
        png = bundle / "carousel" / "carousel-03.png"
        _render(EXACT.replace("necesariamente", "necesarisamente"), png)  # el QA tolerante lo aprobo asi
        manifest = json.loads((bundle / "carousel" / "manifest.json").read_text(encoding="utf-8"))
        approved_before = next(e for e in manifest["carousel"] if e["id"] == 3)["status"]
        with patch.dict(os.environ, {"USERPROFILE": str(profile)}):
            result = cierre_bundle.close_bundle(bundle, bundle_id, lambda: {"warnings": []},
                                                review_fn=_only_slide_3())
        final = strict_review.review_slide(png, EXACT, "lower_third_centered")
        final_manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        slide3 = next(e for e in final_manifest["carousel"] if e["id"] == 3)
        costo = (bundle / "COSTO_CARRUSEL.txt").stat().st_mtime >= png.stat().st_mtime
        ok = (approved_before != "TEXT_QA_FAILED" and final["ok"] is True
              and result["strict_review"]["corrected"] == [3] and slide3["status"] == "TEXT_QA_APPROVED"
              and 3 in final_manifest["text_qa"]["text_fallback_slides"] and costo
              and result["closure"]["status"] == "COMPLETO")
        report("TEST 10", "Slide aprobado por el QA tolerante con texto MAL -> detectado en el cierre, corregido "
                          "automaticamente, reverificado y cierre COMPLETO", ok,
               f"antes={approved_before} final={final['ok']} corregidos={result['strict_review']['corrected']} "
               f"cierre={result['closure']['status']}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


def test_11_regeneracion_dentro_del_presupuesto_y_nunca_completo():
    bundle_id = "__test-fabrica-regen__"
    bundle = OUTPUTS_DIR / bundle_id
    profile = Path(tempfile.mkdtemp(prefix="fab_t11_profile_"))
    calls: List[int] = []

    def always_wrong(png, exact_text, text_placement="", uses_mockup=False):
        if png.name.startswith("carousel-03") or "fallback" in png.name:
            return {"ok": False, "errors": ["palabra 'x' faltante o deformada"], "readings": 3}
        return {"ok": True, "errors": [], "readings": 0}

    def regenerate(n):
        calls.append(n)
        # Una regeneracion real reescribe otros archivos: deben quedar restaurados.
        (bundle / "carousel" / "carousel-05.png").write_bytes(b"roto")
        _render(EXACT, bundle / "carousel" / f"carousel-{n:02d}.png")
        return True

    try:
        _fake_bundle(bundle_id, profile)
        manifest_path = bundle / "carousel" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for e in manifest["carousel"]:
            if e["id"] == 3:
                e["text_qa_retry_count"] = 1  # ya uso 1 de las 2 regeneraciones permitidas
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        slide5 = (bundle / "carousel" / "carousel-05.png").read_bytes()
        with patch.dict(os.environ, {"USERPROFILE": str(profile)}):
            result = cierre_bundle.close_bundle(bundle, bundle_id, lambda: {"warnings": []},
                                                regenerate_fn=regenerate, review_fn=always_wrong)
        rec = next(r for r in result["strict_review"]["slides"] if r["slide"] == 3)
        actions = [a["action"] for a in rec["actions"]]
        ok = (calls == [3] and actions == ["respaldo", "regeneracion", "respaldo"]
              and (bundle / "carousel" / "carousel-05.png").read_bytes() == slide5
              and result["strict_review"]["failed"] == [3]
              and result["closure"]["status"] == "INCOMPLETO"
              and 3 in result["closure"]["slides_with_open_text_errors"])
        report("TEST 11", "Respaldo insuficiente -> 1 regeneracion (la unica que quedaba) -> respaldo otra vez; "
                          "otros slides intactos; nunca COMPLETO con el slide mal", ok,
               f"regeneraciones={calls} acciones={actions} cierre={result['closure']['status']}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)


def _cloud_close(bundle_id: str, profile: Path) -> Dict:
    bundle = OUTPUTS_DIR / bundle_id
    with patch.dict(os.environ, {"USERPROFILE": str(profile)}), patch.object(sys, "platform", "linux"):
        return cierre_bundle.close_bundle(bundle, bundle_id, lambda: {"warnings": []}, strict_review_enabled=False)


def test_12_zip_cloud():
    import zipfile
    bundle_id = "__test-fabrica-zip__"
    bundle = OUTPUTS_DIR / bundle_id
    zip_file = OUTPUTS_DIR / f"{bundle_id}.zip"
    profile = Path(tempfile.mkdtemp(prefix="fab_t12_profile_"))
    try:
        _fake_bundle(bundle_id, profile)
        shutil.rmtree(profile / "Downloads", ignore_errors=True)  # lo que dejo el pipeline local
        (bundle / "carousel" / "assets" / "fallback-originals").mkdir(parents=True, exist_ok=True)
        (bundle / "carousel" / "assets" / "fallback-originals" / "carousel-03.gemini.png").write_bytes(_tiny_png())
        (bundle / "carousel" / "carousel-03.png.previo").write_bytes(b"previo")
        (bundle / "staging").mkdir(exist_ok=True)
        (bundle / "staging" / "tmp.txt").write_text("x", encoding="utf-8")
        result = _cloud_close(bundle_id, profile)
        expected = {f"{bundle_id}/{m}" for m in cierre_bundle.zip_members(bundle)}
        with zipfile.ZipFile(zip_file) as zf:
            names = set(zf.namelist())
            crc_ok = zf.testzip() is None
            zipped_manifest = json.loads(zf.read(f"{bundle_id}/manifest.json"))
            zipped_result = json.loads(zf.read(f"{bundle_id}/pipeline_result.json"))
            same = all(zf.read(f"{bundle_id}/{m}") == (bundle / m).read_bytes()
                       for m in cierre_bundle.zip_members(bundle))
        pngs = [n for n in names if n.endswith(".png")]
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        cloud = result.get("cloud_export", {})
        report_text = cierre_bundle.format_report(bundle_id, bundle, result)
        ok = (names == expected and len(pngs) == 10 and len(names) == 18 and crc_ok and same
              and cloud.get("zip_created") and cloud.get("zip_verified") and cloud.get("zip_path") == str(zip_file)
              and manifest.get("cloud_export", {}).get("zip_verified")
              and zipped_manifest.get("cloud_export", {}).get("zip_verified")
              and zipped_result.get("cloud_export", {}).get("zip_verified")
              and result["windows_export"]["status"] == "NO_DISPONIBLE_FUERA_DE_WINDOWS"
              and not (profile / "Downloads").exists()
              and f"Descarga: {zip_file} (ZIP unico, verificado)" in report_text)
        report("TEST 12", "Cloud: ZIP unico con exactamente los 18 archivos finales (10 PNG), verificado, "
                          "registrado en manifest/pipeline_result y sin tocar Downloads", ok,
               f"archivos={len(names)} png={len(pngs)} crc={crc_ok} identicos={same} cloud={cloud}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        zip_file.unlink(missing_ok=True)
        shutil.rmtree(profile, ignore_errors=True)


def test_13_zip_fallido_es_error_real():
    bundle_id = "__test-fabrica-zip-fail__"
    bundle = OUTPUTS_DIR / bundle_id
    zip_file = OUTPUTS_DIR / f"{bundle_id}.zip"
    profile = Path(tempfile.mkdtemp(prefix="fab_t13_profile_"))
    try:
        _fake_bundle(bundle_id, profile)
        with patch.object(cierre_bundle, "verify_bundle_zip", return_value=["CRC incorrecto (simulado)"]):
            result = _cloud_close(bundle_id, profile)
        cloud = result.get("cloud_export", {})
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        saved = json.loads((bundle / "pipeline_result.json").read_text(encoding="utf-8"))
        report_text = cierre_bundle.format_report(bundle_id, bundle, result)
        ok = (cloud.get("zip_created") is False and cloud.get("zip_verified") is False and cloud.get("errors")
              and not zip_file.exists()
              and manifest["cloud_export"]["zip_verified"] is False
              and saved["cloud_export"]["zip_verified"] is False
              and "ZIP NO DISPONIBLE" in report_text and "verificado)" not in report_text)
        report("TEST 13", "ZIP fallido: error real registrado, ZIP eliminado y el informe no dice que la "
                          "descarga esta lista", ok, f"cloud={cloud}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        zip_file.unlink(missing_ok=True)
        shutil.rmtree(profile, ignore_errors=True)


def test_14_windows_sin_zip():
    bundle_id = "__test-fabrica-win__"
    bundle = OUTPUTS_DIR / bundle_id
    zip_file = OUTPUTS_DIR / f"{bundle_id}.zip"
    profile = Path(tempfile.mkdtemp(prefix="fab_t14_profile_"))
    try:
        _fake_bundle(bundle_id, profile)
        with patch.dict(os.environ, {"USERPROFILE": str(profile)}), patch.object(sys, "platform", "win32"):
            result = cierre_bundle.close_bundle(bundle, bundle_id, lambda: {"warnings": []},
                                                strict_review_enabled=False)
        dest = profile / "Downloads" / "Carruseles Carousel-Gen" / bundle_id
        ok = (result["windows_export"]["status"] == "OK" and all(cierre_bundle.check_package(dest).values())
              and "cloud_export" not in result and not zip_file.exists())
        report("TEST 14", "Windows local: copia verificada a Downloads como antes y ningun ZIP", ok,
               f"export={result['windows_export']['status']} zip={zip_file.exists()}")
    finally:
        shutil.rmtree(bundle, ignore_errors=True)
        zip_file.unlink(missing_ok=True)
        shutil.rmtree(profile, ignore_errors=True)


def main():
    print("=" * 70)
    print("FABRICA AUTONOMA carousel-gen — SIN LLAMADAS A GEMINI")
    print("=" * 70)
    for fn in [test_1_sin_preguntas, test_2_bundle_al_inicio_y_brief_completo, test_3_maximo_dos_regeneraciones,
               test_4_respaldo_determinista, test_5_cierre_despues_de_corregir, test_6_exportacion_windows,
               test_7_reintento_y_fallo_honesto, test_8_pipeline_completo,
               test_9_revision_estricta_detecta_errores_reales,
               test_10_correccion_automatica_de_slide_aprobado_con_error,
               test_11_regeneracion_dentro_del_presupuesto_y_nunca_completo,
               test_12_zip_cloud, test_13_zip_fallido_es_error_real, test_14_windows_sin_zip]:
        fn()
    print("\n" + "=" * 70)
    n_pass = sum(1 for r in results_log if r["status"] == PASS)
    n_fail = sum(1 for r in results_log if r["status"] == FAIL)
    print(f"RESULTADO: {n_pass} PASS, {n_fail} FAIL de {len(results_log)} pruebas")
    print("=" * 70)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
