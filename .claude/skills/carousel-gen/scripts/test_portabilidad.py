#!/usr/bin/env python3
"""
test_portabilidad.py - Mockup versionado en la skill (ruta relativa) y REFERENCE_IMAGE
explicita (2026-09-26).

  TEST 1  — products.json usa una ruta RELATIVA; el mockup existe dentro de la skill y
            su sha256 es el aprobado (0f8853cb...).
  TEST 2  — El mockup se encuentra igual desde otro directorio de trabajo y con otro
            HOME: no depende del PC ni de Windows.
  TEST 3  — Rutas absolutas (Windows, /home/user, /root) o que salen de la skill se
            rechazan; archivo inexistente o sha distinto -> error, sin sustituto.
  TEST 4  — Ningun script ni products.json contiene rutas absolutas de usuario.
  TEST 5  — REFERENCE_IMAGE = imagen del mensaje del copy, nunca "la ultima imagen".
  TEST 6  — Seleccion ambigua o ausente -> sin referencia (nunca "la ultima").
  TEST 7  — CLI con transcript: seleccion explicita OK (role=REFERENCE_IMAGE); sin
            seleccion -> exit 2 REFERENCE_IMAGE_NOT_IDENTIFIED.
  TEST 8  — prepare_carousel.py sin reference_image -> REFERENCE_IMAGE_NOT_IDENTIFIED.
  TEST 9  — El mockup interno no se confunde con REFERENCE_IMAGE: si la referencia
            elegida ES el mockup -> STOP; con una referencia real, cada archivo queda en
            su sitio con su propio sha256.

Sin llamadas a Gemini ($0).
"""

import base64
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))

import prepare_carousel  # noqa: E402
import save_reference_image as sri  # noqa: E402
from carousel_common import OUTPUTS_DIR, FIXED_PRODUCT_NAME  # noqa: E402
from test_prepare_carousel import _make_decisions  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results_log: List[Dict] = []
SCRIPTS = Path(__file__).parent
SKILL_DIR = SCRIPTS.parent
EXPECTED_SHA_PREFIX = "0f8853cb"


def report(test_id: str, description: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results_log.append({"test": test_id, "status": status})
    line = f"[{status}] {test_id}: {description}" + (f"\n   {detail}" if detail else "")
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))


def _entry() -> dict:
    return json.loads((SKILL_DIR / "products.json").read_text(encoding="utf-8"))["products"][FIXED_PRODUCT_NAME]


def _png(color: int) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (6, 6), (color, color, color)).save(buf, "PNG")
    return buf.getvalue()


COPY = "Mi mama me dio todo y mi papa no me dio nada. La diferencia es que eligio."
REF, OTHER = _png(10), _png(120)


def _user_msg(text: str, images: List[bytes]) -> dict:
    content = [{"type": "text", "text": text}] if text else []
    content += [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": base64.b64encode(img).decode()}} for img in images]
    return {"type": "user", "sessionId": "s1", "timestamp": "2026-09-26T10:00:00Z",
            "message": {"role": "user", "content": content}}


def _write_transcript(path: Path, messages: List[dict]) -> None:
    path.write_text("\n".join(json.dumps(m) for m in messages) + "\n", encoding="utf-8")


def test_1_mockup_relativo_en_la_skill():
    entry = _entry()
    mp = entry["mockup_path"]
    relative = not re.match(r"^[A-Za-z]:|^[\\/]", mp) and "\\" not in mp and ".." not in mp
    found = prepare_carousel.find_product_mockup()
    sha = hashlib.sha256(found.read_bytes()).hexdigest()
    inside = SKILL_DIR.resolve() in found.resolve().parents
    ok = (relative and mp.startswith("assets/") and inside and found.is_file()
          and sha == entry["mockup_sha256"] and sha.startswith(EXPECTED_SHA_PREFIX))
    report("TEST 1", "products.json usa ruta RELATIVA; el mockup esta dentro de la skill con el sha256 aprobado",
           ok, f"mockup_path={mp} sha={sha[:12]} dentro_de_la_skill={inside}")


def test_2_independiente_del_pc():
    tmp = Path(tempfile.mkdtemp(prefix="port_t2_"))
    try:
        code = ("import sys; sys.path.insert(0, r'%s'); import prepare_carousel as p, hashlib; "
                "f = p.find_product_mockup(); print(f); print(hashlib.sha256(f.read_bytes()).hexdigest())") % SCRIPTS
        env = dict(os.environ, HOME=str(tmp), USERPROFILE=str(tmp), PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-c", code], cwd=str(tmp), capture_output=True, text=True,
                           encoding="utf-8", env=env)
        lines = r.stdout.strip().splitlines()
        ok = (r.returncode == 0 and len(lines) == 2
              and Path(lines[0]).resolve() == (SKILL_DIR / _entry()["mockup_path"]).resolve()
              and lines[1].startswith(EXPECTED_SHA_PREFIX))
        report("TEST 2", "El mockup se resuelve igual desde otro directorio de trabajo y otro HOME (no depende "
                         "del PC)", ok, f"rc={r.returncode} salida={lines}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_3_rutas_invalidas_y_sha():
    tmp = Path(tempfile.mkdtemp(prefix="port_t3_"))
    original = prepare_carousel.PRODUCTS_JSON
    outcomes = []
    try:
        (tmp / "assets").mkdir()
        (tmp / "assets" / "otro.png").write_bytes(_png(50))
        cases = [
            ("ruta Windows", "C:\\Users\\USUARIO\\Downloads\\mockup.png", "0" * 64, "absoluta"),
            ("ruta /home/user", "/home/user/mockup.png", "0" * 64, "absoluta"),
            ("ruta /root", "/root/mockup.png", "0" * 64, "absoluta"),
            ("sale de la skill", "../../fuera.png", "0" * 64, "sale del directorio"),
            ("archivo inexistente", "assets/no-existe.png", "0" * 64, "no existe"),
            ("sha distinto", "assets/otro.png", "0" * 64, "no es el mockup aprobado"),
        ]
        for label, path, sha, expected in cases:
            (tmp / "products.json").write_text(json.dumps({"products": {FIXED_PRODUCT_NAME: {
                "mockup_path": path, "mockup_sha256": sha}}}), encoding="utf-8")
            prepare_carousel.PRODUCTS_JSON = tmp / "products.json"
            bundle = tmp / "bundle"
            try:
                prepare_carousel.copy_mockup_to_bundle(bundle, True)
                outcomes.append((label, False, "no lanzo error"))
            except prepare_carousel.MockupError as e:
                no_substitute = not (bundle / "carousel" / "assets" / "book-mockup-original.png").exists()
                outcomes.append((label, expected in str(e) and no_substitute, str(e)[:70]))
    finally:
        prepare_carousel.PRODUCTS_JSON = original
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(v for _, v, _ in outcomes)
    report("TEST 3", "Rutas absolutas (Windows, /home/user, /root) o fuera de la skill rechazadas; inexistente o "
                     "sha distinto -> error sin sustituto", ok, "; ".join(f"{l}: {'OK' if v else 'FALLO'}" for l, v, _ in outcomes))


def test_4_sin_rutas_absolutas_de_usuario():
    pattern = re.compile(r"[A-Za-z]:\\\\?Users|/home/user|/root/|Downloads[\\/]+01 - Infoproductos")
    offenders = []
    targets = [SKILL_DIR / "products.json"] + [p for p in SCRIPTS.glob("*.py") if not p.name.startswith("test_")]
    for path in targets:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and not line.lstrip().startswith("#") and "absoluta (C:" not in line:
                offenders.append(f"{path.name}:{n}")
    report("TEST 4", "Ningun script de carousel-gen ni products.json contiene rutas absolutas de usuario",
           not offenders, f"{offenders}")


def test_5_referencia_nunca_la_ultima():
    tmp = Path(tempfile.mkdtemp(prefix="port_t5_"))
    try:
        t = tmp / "s.jsonl"
        _write_transcript(t, [_user_msg(COPY, [REF]), _user_msg("otra imagen mas", [OTHER])])
        images = sri.list_user_images(t)
        img, reason = sri.select_reference(images, message_text_contains=COPY[:60])
        ok = img is not None and img["_bytes"] == REF and images[-1]["_bytes"] == OTHER
        report("TEST 5", "REFERENCE_IMAGE = imagen del mensaje del copy aunque despues llegue otra (nunca la ultima)",
               ok, f"reason={reason!r} imagenes={len(images)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_6_ambigua_o_ausente():
    tmp = Path(tempfile.mkdtemp(prefix="port_t6_"))
    outcomes = {}
    try:
        t = tmp / "s.jsonl"
        _write_transcript(t, [_user_msg(COPY, [REF, OTHER])])
        outcomes["2 imagenes en el mensaje"] = sri.select_reference(sri.list_user_images(t), message_text_contains=COPY[:60])
        _write_transcript(t, [_user_msg(COPY, [REF]), _user_msg("otra", [OTHER])])
        outcomes["sin seleccion"] = sri.select_reference(sri.list_user_images(t))
        sha = hashlib.sha256(REF).hexdigest()
        outcomes["indice con sha de otra imagen"] = sri.select_reference(
            sri.list_user_images(t), attachment_index=2, sha256_prefix=sha[:10])
        ok = all(img is None and reason for img, reason in outcomes.values())
        report("TEST 6", "Seleccion ambigua, ausente o con sha que no cuadra -> sin referencia (nunca la ultima)",
               ok, "; ".join(f"{k}: {r}" for k, (_, r) in outcomes.items()))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_7_cli_transcript():
    tmp = Path(tempfile.mkdtemp(prefix="port_t7_"))
    try:
        project = tmp / "home" / ".claude" / "projects" / "proj"
        project.mkdir(parents=True)
        _write_transcript(project / "sess-1.jsonl", [_user_msg(COPY, [REF]), _user_msg("otra", [OTHER])])
        env = dict(os.environ, CLAUDE_CODE_SESSION_ID="sess-1", HOME=str(tmp / "home"),
                   USERPROFILE=str(tmp / "home"), PYTHONIOENCODING="utf-8")
        dest = tmp / "out" / "viral-reference.png"
        good = subprocess.run([sys.executable, str(SCRIPTS / "save_reference_image.py"), str(dest),
                               "--message-text-contains", COPY[:60]],
                              capture_output=True, text=True, encoding="utf-8", env=env)
        audit = json.loads((dest.parent / "reference_audit.json").read_text(encoding="utf-8")) if dest.exists() else {}
        bad = subprocess.run([sys.executable, str(SCRIPTS / "save_reference_image.py"), str(tmp / "x.png")],
                             capture_output=True, text=True, encoding="utf-8", env=env)
        ok = (good.returncode == 0 and dest.read_bytes() == REF and audit.get("role") == "REFERENCE_IMAGE"
              and bad.returncode == 2 and bad.stdout.startswith("REFERENCE_IMAGE_NOT_IDENTIFIED")
              and not (tmp / "x.png").exists())
        report("TEST 7", "CLI: seleccion explicita -> REFERENCE_IMAGE auditada; sin seleccion -> exit 2 "
                         "REFERENCE_IMAGE_NOT_IDENTIFIED", ok,
               f"ok_rc={good.returncode} role={audit.get('role')} sin_seleccion_rc={bad.returncode}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run_prepare(decisions: dict, extra: List[str]) -> subprocess.CompletedProcess:
    tmp = Path(tempfile.mkdtemp(prefix="port_prep_"))
    try:
        (tmp / "d.json").write_text(json.dumps(decisions), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("CLAUDE_CODE_SESSION_ID", None)
        return subprocess.run([sys.executable, str(SCRIPTS / "prepare_carousel.py"), str(tmp / "d.json")] + extra,
                              capture_output=True, text=True, encoding="utf-8", env=env)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_8_prepare_sin_referencia():
    bundle_id = "__test-port-sin-referencia__"
    try:
        r = _run_prepare(_make_decisions(bundle_id), [])
        ok = r.returncode != 0 and "REFERENCE_IMAGE_NOT_IDENTIFIED" in r.stdout
        report("TEST 8", "prepare_carousel sin reference_image -> STOP REFERENCE_IMAGE_NOT_IDENTIFIED", ok,
               f"rc={r.returncode}")
    finally:
        shutil.rmtree(OUTPUTS_DIR / bundle_id, ignore_errors=True)


def test_9_mockup_no_es_referencia():
    tmp = Path(tempfile.mkdtemp(prefix="port_t9_"))
    b_bad, b_ok = "__test-port-ref-es-mockup__", "__test-port-ref-y-mockup__"
    try:
        mockup = SKILL_DIR / _entry()["mockup_path"]
        r_bad = _run_prepare(_make_decisions(b_bad), ["--fake-reference", str(mockup)])
        ref_file = tmp / "ref.png"
        ref_file.write_bytes(REF)
        decisions = _make_decisions(b_ok)
        decisions["slides"][9]["uses_product_mockup_directly"] = True
        r_ok = _run_prepare(decisions, ["--fake-reference", str(ref_file)])
        assets = OUTPUTS_DIR / b_ok / "carousel" / "assets"
        ref_sha = hashlib.sha256((assets / "viral-reference.png").read_bytes()).hexdigest() if r_ok.returncode == 0 else ""
        mock_sha = hashlib.sha256((assets / "book-mockup-original.png").read_bytes()).hexdigest() if r_ok.returncode == 0 else ""
        ok = (r_bad.returncode != 0 and "REFERENCE_IMAGE_NOT_IDENTIFIED" in r_bad.stdout
              and "mockup interno" in r_bad.stdout
              and r_ok.returncode == 0 and ref_sha == hashlib.sha256(REF).hexdigest()
              and mock_sha.startswith(EXPECTED_SHA_PREFIX) and ref_sha != mock_sha)
        report("TEST 9", "El mockup interno no se confunde con REFERENCE_IMAGE: referencia = mockup -> STOP; "
                         "referencia real -> cada archivo con su sha256", ok,
               f"rc_mockup_como_ref={r_bad.returncode} rc_normal={r_ok.returncode} ref={ref_sha[:10]} mockup={mock_sha[:10]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(OUTPUTS_DIR / b_bad, ignore_errors=True)
        shutil.rmtree(OUTPUTS_DIR / b_ok, ignore_errors=True)


def main():
    print("=" * 70)
    print("PORTABILIDAD DEL MOCKUP Y REFERENCE_IMAGE EXPLICITA — SIN LLAMADAS A GEMINI")
    print("=" * 70)
    for fn in [test_1_mockup_relativo_en_la_skill, test_2_independiente_del_pc, test_3_rutas_invalidas_y_sha,
               test_4_sin_rutas_absolutas_de_usuario, test_5_referencia_nunca_la_ultima, test_6_ambigua_o_ausente,
               test_7_cli_transcript, test_8_prepare_sin_referencia, test_9_mockup_no_es_referencia]:
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
