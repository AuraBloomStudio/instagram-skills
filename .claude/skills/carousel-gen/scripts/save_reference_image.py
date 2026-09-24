#!/usr/bin/env python3
"""
Guarda la imagen de referencia viral del transcript JSONL de la sesion actual.

Mecanismo: leer el transcript JSONL identificado por CLAUDE_CODE_SESSION_ID,
recorrer los mensajes en orden y extraer el ULTIMO bloque type:image de usuario.
Ese bloque contiene el attachment que el usuario adjunto en esta ejecucion.

NO usa clipboard. NO busca bundles anteriores. NO busca AppData/Temp/Downloads.
NO acepta imagenes de sesiones distintas a la actual.

Registro de auditoria en <dest_dir>/reference_audit.json:
  session_id, message_timestamp, media_type, size_bytes, dimensions, sha256, mechanism

Uso:
    python3 save_reference_image.py <dest_path>

    dest_path: ruta destino absoluta, ej.
      C:\\...\\outputs\\bundles\\2026-09-18-mi-carrusel\\carousel\\assets\\viral-reference.png

Exit codes:
    0 - archivo guardado y validado correctamente
    1 - STOP (sin imagen, sesion no encontrada, o error de IO)
"""
import sys
import os
import json
import base64
import hashlib
import pathlib
from datetime import datetime, timezone


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
# Extraer el ultimo bloque image del transcript
# ---------------------------------------------------------------------------

def extract_last_image(transcript_path: pathlib.Path) -> "dict | None":
    """
    Recorre el JSONL en orden y retorna el ULTIMO bloque type:image
    perteneciente a un mensaje de usuario.

    La imagen mas reciente es siempre la que el usuario acaba de adjuntar,
    garantizando que la referencia corresponde a ESTA ejecucion.

    Retorna None si no hay ningun bloque de imagen.
    """
    last_image = None
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            # Filtro rapido antes de parsear JSON completo (el JSONL puede ser grande)
            if '"image"' not in line:
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

            for block in content:
                if block.get("type") != "image":
                    continue
                src = block.get("source", {})
                if src.get("type") != "base64":
                    continue
                data = src.get("data", "")
                if not data:
                    continue
                # Este es un candidato valido — sobrescribir last_image para
                # garantizar que al terminar el loop tenemos el MAS RECIENTE
                last_image = {
                    "data": data,
                    "media_type": src.get("media_type", "image/png"),
                    "timestamp": entry.get("timestamp", ""),
                    "session_id": entry.get("sessionId", ""),
                }

    return last_image


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
    if len(sys.argv) < 2:
        print("ERROR: uso: save_reference_image.py <dest_path>", file=sys.stderr)
        return 1

    dest = pathlib.Path(sys.argv[1]).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

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

    # 3. Extraer el ultimo bloque image de usuario en el transcript de ESTA sesion
    image_data = extract_last_image(transcript)
    if not image_data:
        print(
            "STOP: El transcript de esta sesion no contiene ningun attachment de imagen. "
            "Adjunta la imagen de referencia (arrastra desde Explorer o copia al portapapeles) "
            "y ejecuta el skill de nuevo."
        )
        return 1

    # 4. Decodificar base64 (sin imprimir los bytes)
    try:
        img_bytes = base64.b64decode(image_data["data"])
    except Exception as e:
        print(f"STOP: Error decodificando base64 del attachment: {e}")
        return 1

    # 5. Escribir archivo destino
    try:
        dest.write_bytes(img_bytes)
    except Exception as e:
        print(f"STOP: Error escribiendo {dest}: {e}")
        return 1

    # 6. Validar: archivo existe, tamano > 0, imagen valida, dimensiones validas
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

    # 7. SHA-256 del archivo guardado (para auditoria)
    sha256 = hashlib.sha256(img_bytes).hexdigest()

    # 8. Registro de auditoria en reference_audit.json junto al archivo
    audit = {
        "session_id": image_data["session_id"] or session_id,
        "message_timestamp": image_data["timestamp"],
        "media_type": image_data["media_type"],
        "size_bytes": size,
        "dimensions": {"width": width, "height": height},
        "sha256": sha256,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "mechanism": "session_transcript_jsonl",
        "transcript_file": transcript.name,
    }
    audit_path = dest.parent / "reference_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    # 9. Resumen (sin imprimir datos de imagen)
    print(f"OK: {dest}")
    print(f"    {size:,} bytes | {width}x{height} | {fmt}")
    print(f"    sha256: {sha256[:32]}...")
    print(f"    Fuente: {transcript.name} | ts={image_data['timestamp']}")
    print(f"    Auditoria: {audit_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
