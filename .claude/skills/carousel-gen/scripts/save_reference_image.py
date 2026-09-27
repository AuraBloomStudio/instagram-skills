#!/usr/bin/env python3
"""
Guarda la REFERENCE_IMAGE (imagen de referencia viral) del transcript JSONL de la
sesion actual, identificada EXPLICITAMENTE.

REGLA PERMANENTE (2026-09-26): nunca se usa automaticamente "la ultima imagen
adjunta" ni "la ultima imagen de la sesion". El mockup del producto es un asset interno
de la skill (assets/, ver products.json) y nunca se toma de la conversacion. La
referencia se selecciona de una de estas dos formas:

  1. --message-text-contains "<fragmento del copy>": la imagen adjunta en el MISMO
     mensaje del usuario que contiene ese texto (flujo normal: una imagen + el copy).
     Debe existir exactamente un mensaje con ese texto y exactamente una imagen en el.
  2. --attachment-index N --sha256-prefix P: la imagen N (1-based, en orden de la
     sesion, ver --list) cuyo sha256 empieza por P (minimo 8 caracteres hex).

Si no se puede identificar de forma inequivoca, termina con:
  REFERENCE_IMAGE_NOT_IDENTIFIED: <motivo>        (exit 2, nunca una pregunta)

NO usa clipboard. NO busca bundles anteriores. NO busca AppData/Temp/Downloads.
NO acepta imagenes de sesiones distintas a la actual.

Registro de auditoria en <dest_dir>/reference_audit.json:
  role=REFERENCE_IMAGE, selection, attachment_index, session_id, message_timestamp,
  media_type, size_bytes, dimensions, sha256, mechanism

Uso:
    python3 save_reference_image.py --list
    python3 save_reference_image.py <dest_path> --message-text-contains "<texto>"
    python3 save_reference_image.py <dest_path> --attachment-index N --sha256-prefix P

Exit codes:
    0 - archivo guardado y validado correctamente (o listado impreso)
    1 - STOP (sesion/transcript no encontrado, o error de IO)
    2 - REFERENCE_IMAGE_NOT_IDENTIFIED
"""
import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import sys
from datetime import datetime, timezone

NOT_IDENTIFIED = "REFERENCE_IMAGE_NOT_IDENTIFIED"
_MIN_SHA_PREFIX = 8
_MIN_TEXT_SNIPPET = 20


# ---------------------------------------------------------------------------
# Localizar el transcript JSONL de esta sesion
# ---------------------------------------------------------------------------

def find_transcript(session_id: str) -> "pathlib.Path | None":
    """
    Busca el transcript JSONL en una sola pasada de un nivel sobre
    ~/.claude/projects/<project-slug>/<session_id>.jsonl.
    No hace ninguna busqueda recursiva.
    """
    projects_dir = pathlib.Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Enumerar las imagenes adjuntas por el usuario (nunca elegir "la ultima")
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def list_user_images(transcript_path: pathlib.Path) -> list:
    """
    Todas las imagenes adjuntas por el usuario en la sesion, en orden, con su indice
    (1-based), sha256, mensaje de origen y el texto de ese mismo mensaje.
    """
    images = []
    message_number = 0
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"user"' not in line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "user":
                continue
            content = entry.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            message_number += 1
            text = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
            position = 0
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "image":
                    continue
                src = block.get("source", {})
                data = src.get("data", "") if src.get("type") == "base64" else ""
                if not data:
                    continue
                try:
                    raw = base64.b64decode(data)
                except Exception:  # noqa: BLE001 - adjunto corrupto: no es candidato
                    continue
                position += 1
                images.append({
                    "attachment_index": len(images) + 1,
                    "message_number": message_number,
                    "position_in_message": position,
                    "timestamp": entry.get("timestamp", ""),
                    "session_id": entry.get("sessionId", ""),
                    "media_type": src.get("media_type", "image/png"),
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "message_text": text,
                    "_bytes": raw,
                })
    return images


def select_reference(images: list, attachment_index=None, sha256_prefix=None,
                     message_text_contains=None) -> "tuple[dict | None, str]":
    """
    Devuelve (imagen, "") si la REFERENCE_IMAGE se identifica de forma inequivoca, o
    (None, motivo) si no. Nunca cae en "la ultima imagen".
    """
    if not images:
        return None, "la sesion no contiene ninguna imagen adjunta por el usuario"

    if attachment_index is not None:
        prefix = (sha256_prefix or "").lower()
        if len(prefix) < _MIN_SHA_PREFIX or not re.fullmatch(r"[0-9a-f]+", prefix):
            return None, f"--attachment-index requiere --sha256-prefix de al menos {_MIN_SHA_PREFIX} caracteres hex"
        match = [img for img in images if img["attachment_index"] == attachment_index]
        if not match:
            return None, f"no existe la imagen adjunta numero {attachment_index} (hay {len(images)})"
        if not match[0]["sha256"].startswith(prefix):
            return None, (f"la imagen {attachment_index} no coincide con el sha256 indicado "
                          f"({match[0]['sha256'][:12]}... != {prefix}...)")
        return match[0], ""

    if message_text_contains is not None:
        snippet = _normalize(message_text_contains)
        if len(snippet) < _MIN_TEXT_SNIPPET:
            return None, f"--message-text-contains requiere al menos {_MIN_TEXT_SNIPPET} caracteres"
        candidates = [img for img in images if snippet in _normalize(img["message_text"])]
        messages = {img["message_number"] for img in candidates}
        if not candidates:
            return None, "ningun mensaje con imagen contiene ese texto"
        if len(messages) > 1:
            return None, f"{len(messages)} mensajes con imagen contienen ese texto"
        if len(candidates) > 1:
            return None, f"el mensaje con ese texto tiene {len(candidates)} imagenes adjuntas"
        return candidates[0], ""

    return None, "no se indico que imagen es la referencia (nunca se usa la ultima adjunta)"


# ---------------------------------------------------------------------------
# Validar imagen guardada
# ---------------------------------------------------------------------------

def validate_image(path: pathlib.Path) -> "tuple[int, int, str]":
    """
    Abre la imagen con PIL y retorna (width, height, format).
    Lanza Exception si el archivo no es una imagen valida.
    """
    from PIL import Image

    # Primer pase: verify() comprueba integridad del archivo
    with Image.open(path) as img:
        img.verify()

    # Segundo pase: obtener dimensiones (verify() cierra el handler)
    with Image.open(path) as img:
        width, height = img.size
        fmt = img.format or "PNG"

    return width, height, fmt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Guarda la REFERENCE_IMAGE identificada explicitamente")
    parser.add_argument("dest_path", nargs="?")
    parser.add_argument("--list", action="store_true", help="Lista las imagenes adjuntas de la sesion y sale")
    parser.add_argument("--attachment-index", type=int, default=None)
    parser.add_argument("--sha256-prefix", default=None)
    parser.add_argument("--message-text-contains", default=None)
    args = parser.parse_args()

    # 1. Obtener session ID del entorno
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not session_id:
        print(
            "STOP: No se encontro CLAUDE_CODE_SESSION_ID en el entorno. "
            "Este script debe ejecutarse dentro de una sesion de Claude Code."
        )
        return 1

    # 2. Localizar transcript JSONL de esta sesion (una sola busqueda de 1 nivel)
    transcript = find_transcript(session_id)
    if not transcript:
        print(
            f"STOP: No se encontro el transcript JSONL para la sesion {session_id}. "
            "Verifica que el directorio ~/.claude/projects existe y que la sesion esta activa."
        )
        return 1

    images = list_user_images(transcript)

    if args.list:
        listing = [{k: v for k, v in img.items() if k != "_bytes"} for img in images]
        for item in listing:
            item["message_text"] = item["message_text"][:120]
        print(json.dumps(listing, ensure_ascii=False, indent=2))
        return 0

    if not args.dest_path:
        print("ERROR: falta dest_path (o usa --list)", file=sys.stderr)
        return 1

    # 3. Seleccionar la REFERENCE_IMAGE de forma explicita e inequivoca
    image, reason = select_reference(
        images, attachment_index=args.attachment_index, sha256_prefix=args.sha256_prefix,
        message_text_contains=args.message_text_contains,
    )
    if image is None:
        print(f"{NOT_IDENTIFIED}: {reason}")
        return 2

    dest = pathlib.Path(args.dest_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    img_bytes = image["_bytes"]

    # 4. Escribir archivo destino
    try:
        dest.write_bytes(img_bytes)
    except Exception as e:
        print(f"STOP: Error escribiendo {dest}: {e}")
        return 1

    # 5. Validar: archivo existe, tamano > 0, imagen valida, dimensiones validas
    size = dest.stat().st_size
    if size == 0:
        print(f"STOP: El archivo guardado esta vacio: {dest}")
        dest.unlink(missing_ok=True)
        return 1

    try:
        width, height, fmt = validate_image(dest)
    except Exception as e:
        print(f"STOP: El archivo guardado no es una imagen valida: {e}")
        dest.unlink(missing_ok=True)
        return 1

    if width == 0 or height == 0:
        print(f"STOP: Dimensiones invalidas: {width}x{height}")
        dest.unlink(missing_ok=True)
        return 1

    # 6. Registro de auditoria en reference_audit.json junto al archivo
    selection = ({"method": "attachment_index", "attachment_index": args.attachment_index,
                  "sha256_prefix": args.sha256_prefix}
                 if args.attachment_index is not None
                 else {"method": "message_text_contains", "message_text_contains": args.message_text_contains})
    audit = {
        "role": "REFERENCE_IMAGE",
        "selection": selection,
        "attachment_index": image["attachment_index"],
        "images_in_session": len(images),
        "session_id": image["session_id"] or session_id,
        "message_timestamp": image["timestamp"],
        "media_type": image["media_type"],
        "size_bytes": size,
        "dimensions": {"width": width, "height": height},
        "sha256": image["sha256"],
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "mechanism": "session_transcript_jsonl_explicit_selection",
        "transcript_file": transcript.name,
    }
    audit_path = dest.parent / "reference_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    # 7. Resumen (sin imprimir datos de imagen)
    print(f"OK: REFERENCE_IMAGE -> {dest}")
    print(f"    imagen adjunta {image['attachment_index']} de {len(images)} | {size:,} bytes | {width}x{height} | {fmt}")
    print(f"    sha256: {image['sha256'][:32]}...")
    print(f"    Auditoria: {audit_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
