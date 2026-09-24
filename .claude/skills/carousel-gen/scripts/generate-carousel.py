#!/usr/bin/env python3
"""
generate-carousel.py - Genera carruseles Instagram usando Kie AI (Nano Banana)

Uso:
    python3 generate-carousel.py <bundle_id>
    python3 generate-carousel.py <bundle_id> --regenerate-slides "2,4,6"
    python3 generate-carousel.py <bundle_id> --dry-run

Ejemplo:
    python3 generate-carousel.py 2026-01-14-vacio-existencial
    python3 generate-carousel.py 2026-01-14-vacio-existencial --regenerate-slides "3"

Requisitos:
    - Variable de entorno KIE_AI_API_KEY configurada
    - Archivo brief.json en el bundle (creado por el workflow de SKILL.md), con:
        reference_image, visual_dna, carousel_type, slide_count, slides[]
"""

import os
import sys
import json
import time
import base64
import argparse
import requests
from pathlib import Path
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
from carousel_common import (  # noqa: E402
    PROJECT_ROOT, OUTPUTS_DIR, DOWNLOADS_EXPORT_DIR, MAX_SLIDES,
    REQUIRED_BRIEF_TOP_FIELDS, REQUIRED_SLIDE_FIELDS,
    load_brief, detect_tools_in_text, detect_entities_in_slides,
    format_visual_dna_block, GLOBAL_DESIGN_RULES, IMAGE_ROLE_INSTRUCTIONS,
    build_prompt_for_slide, generate_assets_needed_md, generate_manifest,
    build_para_facebook_folder, export_final_slides_to_downloads,
    save_copy_deliverables,
)

# Cargar .env desde la raiz del proyecto
load_dotenv(Path(__file__).parent.parent / ".env")

# NOTA (migracion economica, ver SKILL.md "COST OPTIMIZATION"): este script es el
# generador LEGACY basado en Kie AI. Toda la logica compartida con el generador
# economico (scripts/generate-carousel-gemini.py) vive en carousel_common.py — ver ese
# modulo para MAX_SLIDES, validacion de brief, construccion de prompts y exportacion.
# Este archivo NUNCA se llama automaticamente: por defecto KIE_ENABLED=false (ver
# gemini_config.py) y el generador principal es Gemini. Este script solo se ejecuta si
# se invoca explicitamente (o si en el futuro se reactiva Kie a proposito).

# API Kie AI
KIE_API_BASE = "https://api.kie.ai/api/v1/jobs"
KIE_CREATE_TASK = f"{KIE_API_BASE}/createTask"
KIE_RECORD_INFO = f"{KIE_API_BASE}/recordInfo"

# Configuración de generación
# Modelo de generación principal (migrado de nano-banana-pro a nano-banana-2 para reducir
# costo). Confirmado en la documentación oficial de Kie AI (docs.kie.ai/market/google/nanobanana2):
# mismo endpoint createTask, soporta resolution "1K"/"2K"/"4K", aspect_ratio "4:5" y
# image_input (hasta 14 imágenes) — sin cambios de arquitectura necesarios más allá del
# identificador de modelo y la resolución por defecto.
MODEL = "nano-banana-2"
ASPECT_RATIO = "4:5"  # Instagram carousel (1080x1350px)
RESOLUTION = "1K"
FORMAT = "png"
MAX_POLL_ATTEMPTS = 60  # 5 minutos máximo
POLL_INTERVAL = 5  # segundos
COST_PER_IMAGE_USD = 0.04  # nano-banana-2 @ 1K, precio publicado por Kie AI (kie.ai/nano-banana-2)

# MAX_SLIDES, REQUIRED_BRIEF_TOP_FIELDS, REQUIRED_SLIDE_FIELDS: importados de
# carousel_common (ver arriba) — compartidos con el generador economico de Gemini, nunca
# duplicados aqui.


def get_api_key() -> str:
    """Obtiene la API key de Kie AI."""
    api_key = os.environ.get("KIE_AI_API_KEY")
    if not api_key:
        print("[ERROR] Error: Variable de entorno KIE_AI_API_KEY no configurada")
        print("   Ejecuta: export KIE_AI_API_KEY='tu-api-key'")
        sys.exit(1)
    return api_key


def download_asset_from_url(url: str, entity: str, assets_dir: Path) -> Optional[Path]:
    """Descarga una imagen desde URL y la guarda en assets/."""
    try:
        from PIL import Image
        from io import BytesIO

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content))

        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        asset_path = assets_dir / f"{entity}.png"
        img.save(asset_path, 'PNG')

        print(f"   [OK] Asset descargado: {asset_path.name}")
        return asset_path

    except Exception as e:
        print(f"   [ERROR] Error descargando asset: {e}")
        return None


def create_kie_task(api_key: str, prompt: str, image_input: Optional[List[str]] = None) -> Optional[str]:
    """Crea una tarea en Kie AI (modelo principal: MODEL, ver configuración arriba) y retorna el taskId."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    input_params = {
        "prompt": prompt,
        "aspect_ratio": ASPECT_RATIO,
        "resolution": RESOLUTION,
        "output_format": FORMAT
    }

    if image_input:
        input_params["image_input"] = image_input

    payload = {
        "model": MODEL,
        "input": input_params
    }

    try:
        response = requests.post(KIE_CREATE_TASK, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get("code") == 200:
            task_id = result.get("data", {}).get("taskId")
            if task_id:
                return task_id
            print(f"   [ERROR] Error: No se recibió taskId de Kie AI")
            print(f"   [LIST] Respuesta: {result}")
            return None
        else:
            print(f"   [ERROR] Error: No se recibió taskId de Kie AI")
            print(f"   [LIST] Respuesta: {result}")
            return None

    except Exception as e:
        print(f"   [ERROR] Error creando tarea: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   [LIST] Respuesta HTTP: {e.response.text}")
        return None


def poll_task_status(api_key: str, task_id: str) -> Optional[str]:
    """Hace polling del status de una tarea hasta que complete."""
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(MAX_POLL_ATTEMPTS):
        try:
            response = requests.get(
                KIE_RECORD_INFO,
                headers=headers,
                params={"taskId": task_id},
                timeout=30
            )
            response.raise_for_status()

            data = response.json().get("data") or {}
            state = data.get("state", "")

            if state == "success":
                result_json = data.get("resultJson", "{}")
                result = json.loads(result_json)
                urls = result.get("resultUrls", [])
                if urls:
                    return urls[0]
                else:
                    print(f"   [ERROR] Tarea completada pero sin URLs en resultado")
                    return None

            elif state == "fail":
                fail_msg = data.get("failMsg", "Unknown error")
                print(f"   [ERROR] Tarea falló: {fail_msg}")
                return None

            elif state in ["waiting", "queuing", "generating"]:
                print(f"   Estado: {state}... ({attempt + 1}/{MAX_POLL_ATTEMPTS})")
                time.sleep(POLL_INTERVAL)

            else:
                print(f"   [WARN] Estado desconocido: '{state}' (intento {attempt + 1}/{MAX_POLL_ATTEMPTS})")
                time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"   [ERROR] Error en polling: {e}")
            time.sleep(POLL_INTERVAL)

    print(f"   [ERROR] Timeout esperando resultado (intentos: {MAX_POLL_ATTEMPTS})")
    return None


def download_image(url: str, output_path: Path) -> bool:
    """Descarga imagen desde URL."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True

    except Exception as e:
        print(f"   [ERROR] Error descargando imagen: {e}")
        return False


def upload_asset_to_kie(api_key: str, asset_path: Path) -> Optional[str]:
    """
    Obtiene URL pública de un asset para usar con Kie AI.

    Primero busca en urls.json (URLs de Cloudinary u otras CDN públicas).
    Si no encuentra, sube el archivo local a Kie AI como fallback. Este fallback
    es el camino normal para la imagen de referencia viral (que llega como adjunto
    local, no como URL).
    """
    entity_name = asset_path.stem.lower()
    urls_candidates = [
        asset_path.parent / "urls.json",          # carousel/assets/urls.json
        asset_path.parent.parent / "urls.json",    # carousel/urls.json
    ]
    for urls_file in urls_candidates:
        if urls_file.exists():
            try:
                with open(urls_file, "r") as f:
                    urls_map = json.load(f)
                if entity_name in urls_map:
                    public_url = urls_map[entity_name]
                    print(f"   [OK] URL pública encontrada: {entity_name} (desde {urls_file.parent.name}/urls.json)")
                    return public_url
            except Exception:
                pass

    KIE_FILE_UPLOAD_URL = "https://kieai.redpandaai.co/api/file-base64-upload"

    try:
        with open(asset_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        ext = asset_path.suffix.lower()
        mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/png")

        payload = {
            "base64Data": f"data:{mime_type};base64,{b64_data}",
            "uploadPath": "carousel-gen/assets",
            "fileName": asset_path.name
        }

        response = requests.post(
            KIE_FILE_UPLOAD_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()

        if result.get("code") == 200:
            file_url = result.get("data", {}).get("downloadUrl")
            if file_url:
                print(f"   [OK] Asset subido via Base64: {asset_path.name} -> {file_url}")
                return file_url
            print(f"   [ERROR] Upload exitoso pero sin downloadUrl en respuesta")
            return None
        else:
            print(f"   [ERROR] Error en upload: {result}")
            return None

    except Exception as e:
        print(f"   [ERROR] Error subiendo asset: {e}")
        return None


def find_asset_for_slide(assets_dir: Path, tools: List[str]) -> Optional[Path]:
    """Busca un asset (logo) apropiado para un slide basado en las herramientas detectadas."""
    if not tools or not assets_dir.exists():
        return None

    for tool in tools:
        patterns = [
            f"{tool}-logo.png",
            f"{tool}.png",
            f"{tool}-icon.png"
        ]

        for pattern in patterns:
            asset_path = assets_dir / pattern
            if asset_path.exists():
                return asset_path

    return None


def edit_slide_with_logo(
    api_key: str,
    generated_image_url: str,
    logo_url: str,
    slide_title: str,
    slide_content: str,
    slide_type: str
) -> Optional[str]:
    """Edita un slide generado para integrar un logo real usando nano-banana-edit."""
    edit_prompt = f"""Edit this carousel slide to integrate the provided logo/icon image naturally.

THE SECOND IMAGE IS A LOGO. You must:
1. Place the real logo from the second image onto the slide
2. Position it prominently (top-center or beside the title)
3. Keep the logo EXACTLY as it is - do not redraw or modify the logo
4. Size: approximately 150-200px

CRITICAL - DO NOT:
- Redraw or reinvent the logo
- Change the logo colors or shape
- Remove any existing text from the slide

PRESERVE:
- All existing text content on the slide
- Overall composition and layout
- Original visual style

Slide title: {slide_title}
Slide type: {slide_type}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "google/nano-banana-edit",
        "input": {
            "prompt": edit_prompt,
            "image_urls": [generated_image_url, logo_url],
            "output_format": "png",
            "image_size": "4:5"
        }
    }

    try:
        print(f"   [WAIT] Editando con nano-banana-edit (integrando logo)...")

        response = requests.post(KIE_CREATE_TASK, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get("code") == 200:
            task_id = result.get("data", {}).get("taskId")
            if not task_id:
                print(f"   [ERROR] No se recibió taskId de nano-banana-edit")
                return None
        else:
            print(f"   [ERROR] Error nano-banana-edit: {result}")
            return None

        print(f"   Esperando resultado edit (taskId: {task_id[:12]}...)...")
        image_url = poll_task_status(api_key, task_id)

        return image_url

    except Exception as e:
        print(f"   [ERROR] Error en edición: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Genera carruseles Instagram con Nano Banana a partir de brief.json")
    parser.add_argument("bundle_id", help="ID del bundle (ej: 2026-01-14-vacio-existencial)")
    parser.add_argument("--skip-interactive", action="store_true",
                        help="Salta input() interactivo, usa assets ya existentes en /carousel/assets/")
    parser.add_argument("--regenerate-slides", type=str, default=None,
                        help="Lista de slides a regenerar (ej: '2,4,6')")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra brief y entidades detectadas, no genera imagenes")
    parser.add_argument("--add-copy", type=str, default=None, metavar="COPY_JSON_PATH",
                        help="Guarda el copy de publicacion unificado (COPY_FINAL.txt) de un "
                             "carrusel YA generado, a partir de un JSON local con las claves "
                             "description, cta, hashtags (lista), product, purchase_url. NO "
                             "genera ni toca ninguna imagen ni el brief.json — ver SKILL.md PASO 9.")

    args = parser.parse_args()
    bundle_id = args.bundle_id

    print(f"\n{'='*60}")
    print(f"CAROUSEL GENERATOR - Nano Banana")
    print(f"{'='*60}")
    print(f"\n[BUNDLE] Bundle: {bundle_id}")

    bundle_path = OUTPUTS_DIR / bundle_id
    if not bundle_path.exists():
        print(f"[ERROR] Error: el bundle no existe: {bundle_path}")
        print(f"   El bundle y su brief.json deben crearse desde el workflow de SKILL.md antes de ejecutar este script.")
        sys.exit(1)

    print(f"[DIR] Path: {bundle_path}\n")

    if args.add_copy:
        # Modo aislado: SOLO guarda COPY_FINAL.txt (copy de publicacion unificado) +
        # actualiza manifest.json. Nunca llama a Kie AI, nunca toca brief.json ni
        # carousel-NN.png.
        copy_json_path = Path(args.add_copy)
        if not copy_json_path.exists():
            print(f"[ERROR] Error: no se encontró el archivo de copy en {copy_json_path}")
            sys.exit(1)
        with open(copy_json_path, "r", encoding="utf-8") as f:
            copy_data = json.load(f)

        missing = [k for k in ("description", "cta", "hashtags") if k not in copy_data]
        if missing:
            print(f"[ERROR] Error: faltan campos obligatorios en el JSON de copy: {missing}")
            sys.exit(1)

        # Regla de no finalizar incompleto (SKILL.md PASO 10): si hay un producto elegido
        # pero no tiene purchase_url resuelto, el paquete NO se guarda — hay que resolver
        # el enlace primero (products.json o preguntarle al usuario), nunca inventarlo.
        if copy_data.get("product") and not copy_data.get("purchase_url"):
            print(f"[ERROR] Error: el producto '{copy_data['product']}' no tiene 'purchase_url'.")
            print("   Regla de no finalizar incompleto: el paquete no se guarda sin el enlace de "
                  "compra. Resuelve el enlace (buscar en products.json o pedirlo al usuario) y "
                  "vuelve a ejecutar --add-copy — nunca inventar ni usar el enlace de otro producto.")
            sys.exit(1)

        n_hashtags = len(copy_data.get("hashtags") or [])
        if not (8 <= n_hashtags <= 10):
            print(f"[WARN] Advertencia: se esperaban entre 8 y 10 hashtags, hay {n_hashtags}. "
                  f"Continua igualmente (no bloqueante).")

        save_copy_deliverables(
            bundle_path,
            description=copy_data["description"],
            cta=copy_data["cta"],
            hashtags=copy_data["hashtags"],
            product=copy_data.get("product"),
            purchase_url=copy_data.get("purchase_url"),
        )

        # Regla permanente: al quedar completo el paquete de copy, se refresca la copia
        # en Descargas para que incluya tambien COPY_FINAL.txt/manifest.json junto a los
        # carousel-NN.png ya copiados anteriormente (ver export_final_slides_to_downloads).
        # Nunca regenera ni toca ninguna imagen.
        print("\nActualizando copia en Descargas con el paquete completo...")
        export_final_slides_to_downloads(bundle_id, bundle_path, bundle_path / "carousel")

        print(f"\n{'='*60}")
        print(f"ENTREGABLES DE COPY GUARDADOS (sin generar ni tocar ninguna imagen)")
        print(f"{'='*60}\n")
        sys.exit(0)

    # Cargar brief.json (fuente de verdad unica)
    print("[LOAD] Cargando brief.json...")
    brief = load_brief(bundle_path)

    if not brief:
        sys.exit(1)

    slides = brief["slides"]
    visual_dna = brief["visual_dna"]
    carousel_type = brief["carousel_type"]
    slide_count = brief["slide_count"]
    reference_image_info = brief["reference_image"]
    product_mockup_info = brief.get("product_mockup")

    carousel_dir = bundle_path / "carousel"
    carousel_dir.mkdir(exist_ok=True)

    assets_dir = carousel_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    # FASE 1: Mostrar brief y detectar entidades (para logos opcionales)
    print("\n" + "="*60)
    print("BRIEF DEL CARRUSEL")
    print("="*60)

    print(f"\nFormato: {carousel_type}")
    print(f"Total slides: {len(slides)} (recomendado: {slide_count.get('recommended')}, "
          f"confirmado: {slide_count.get('confirmed')})")
    print(f"Formato de imagen: 1080x1350px (4:5)")
    print(f"Estilo visual: detectado del ADN visual de la referencia (ver brief.json)\n")

    slides_for_detection = [
        {
            "number": s["number"],
            "title": s.get("role", ""),
            "content": " ".join(filter(None, [s.get("message", ""), s.get("exact_text", ""), s.get("scene_description", "")])),
        }
        for s in slides
    ]

    for slide in slides:
        print(f"  Slide {slide['number']} [{slide.get('role', '')}]: {slide.get('narrative_objective', '')}")

    entities_by_slide = detect_entities_in_slides(slides_for_detection)

    all_entities = set()
    for ents in entities_by_slide.values():
        all_entities.update(ents)

    if all_entities:
        print(f"\nHerramientas detectadas (para logos opcionales): {', '.join(sorted(all_entities))}")
    else:
        print(f"\nNo se detectaron herramientas especificas (no es necesario para este carrusel)")

    print(f"\n" + "="*60)

    if args.dry_run:
        print(f"\n(dry-run) Brief mostrado. No se generaron imagenes.")
        print(f"Ejecuta sin --dry-run para generar las imagenes.")
        sys.exit(0)

    api_key = get_api_key()

    # FASE 2: Mapeo de logos opcionales (independiente del ADN visual)
    print(f"\nMAPEO DE LOGOS OPCIONALES\n")

    asset_map = {}  # slide_num -> (Path, entity)

    if entities_by_slide:
        reserved_asset_stems = {"viral-reference"}
        if product_mockup_info:
            reserved_asset_stems.add(Path(product_mockup_info["local_path"]).stem.lower())

        existing_assets = [
            p for p in assets_dir.glob("*.png") if p.stem.lower() not in reserved_asset_stems
        ]

        if existing_assets:
            print(f"   Assets encontrados en /carousel/assets/:")
            for asset in existing_assets:
                print(f"      - {asset.name}")

            for slide_num, entities in entities_by_slide.items():
                for entity in entities:
                    asset_path = assets_dir / f"{entity}.png"
                    if asset_path.exists():
                        asset_map[slide_num] = (asset_path, entity)
                        print(f"      -> '{entity}.png' asignado a slide {slide_num}")
                        break

            print(f"\n   Logos mapeados: {len(asset_map)}")

        elif not args.skip_interactive:
            print(f"   Modo interactivo: preguntando por logos...\n")
            for slide_num, entities in entities_by_slide.items():
                slide = next(s for s in slides_for_detection if s['number'] == slide_num)

                print(f"\n   Slide {slide_num} - {slide['title']}")
                print(f"   Detecte: {', '.join(entities)}")

                for entity in entities:
                    print(f"\n   Tienes un logo para {entity}?")
                    print(f"   - Pega URL de imagen")
                    print(f"   - O escribe 'skip' para continuar sin imagen")

                    user_input = input(f"   {entity} -> ").strip()

                    if user_input.lower() == 'skip':
                        print(f"   Continuando sin logo para {entity}")
                        continue

                    if not user_input.startswith('http'):
                        print(f"   URL invalida, continuando sin logo")
                        continue

                    asset_path = download_asset_from_url(user_input, entity, assets_dir)

                    if asset_path:
                        asset_map[slide_num] = (asset_path, entity)
                        print(f"   Logo registrado para slide {slide_num}")
                        break

            print(f"\n   Logos recolectados: {len(asset_map)}")
        else:
            print(f"   Modo no-interactivo: sin logos, generando solo con ADN visual de la referencia")
    else:
        print(f"   No hay herramientas detectadas, no aplica")

    # Resolver imagen de referencia viral (OBLIGATORIA, solo para el slide marcado)
    reference_local_path = bundle_path / reference_image_info["local_path"]
    if not reference_local_path.exists():
        print(f"\n[ERROR] Error: no se encontró la imagen de referencia en {reference_local_path}")
        print(f"   Debe guardarse ahí durante el workflow de SKILL.md (Paso 6) antes de generar.")
        sys.exit(1)

    reference_url_cache: Dict[str, Optional[str]] = {}

    def get_reference_url() -> Optional[str]:
        if "url" not in reference_url_cache:
            print(f"\n   Subiendo imagen de referencia para obtener URL pública...")
            reference_url_cache["url"] = upload_asset_to_kie(api_key, reference_local_path)
        return reference_url_cache["url"]

    # Resolver mockup de producto original (OPCIONAL, solo si el usuario lo proporciono).
    # Cuando existe, es SIEMPRE un asset provisto por el usuario (portada de libro, ebook,
    # curso, etc.) que debe usarse tal cual en el/los slide(s) marcados con
    # "uses_product_mockup_directly": true en brief.json. Nunca se inventa ni se sube
    # automaticamente sin que el usuario lo haya adjuntado primero.
    product_mockup_local_path = None
    if product_mockup_info:
        candidate_path = bundle_path / product_mockup_info["local_path"]
        if candidate_path.exists():
            product_mockup_local_path = candidate_path
        else:
            print(f"\n[WARN] Advertencia: brief.json referencia 'product_mockup' pero no se encontró "
                  f"el archivo en {candidate_path}")

    mockup_url_cache: Dict[str, Optional[str]] = {}

    def get_product_mockup_url() -> Optional[str]:
        if not product_mockup_local_path:
            return None
        if "url" not in mockup_url_cache:
            print(f"\n   Subiendo mockup de producto original para obtener URL pública...")
            mockup_url_cache["url"] = upload_asset_to_kie(api_key, product_mockup_local_path)
        return mockup_url_cache["url"]

    # Parse --regenerate-slides filter
    only_slides = None
    if args.regenerate_slides:
        only_slides = set(int(s.strip()) for s in args.regenerate_slides.split(","))
        print(f"\n[REGEN] Regenerando solo slides: {sorted(only_slides)}\n")

    start_time = time.time()
    slides_generated = []

    def process_slide(slide_num, info):
        task_id = info['task_id']
        headers = {"Authorization": f"Bearer {api_key}"}

        for attempt in range(MAX_POLL_ATTEMPTS):
            try:
                response = requests.get(
                    KIE_RECORD_INFO,
                    headers=headers,
                    params={"taskId": task_id},
                    timeout=30
                )
                response.raise_for_status()

                data = response.json().get("data") or {}
                state = data.get("state", "")

                if state == "success":
                    result_json = data.get("resultJson", "{}")
                    result = json.loads(result_json)
                    urls = result.get("resultUrls", [])
                    if urls:
                        return urls[0]
                    else:
                        print(f"   [Slide {slide_num}] [ERROR] Completada pero sin URLs")
                        return None

                elif state == "fail":
                    fail_msg = data.get("failMsg", "Unknown error")
                    print(f"   [Slide {slide_num}] [ERROR] Fallo: {fail_msg}")
                    return None

                elif state in ["waiting", "queuing", "generating"]:
                    if attempt % 6 == 0:
                        print(f"   [Slide {slide_num}] {state}... ({attempt * POLL_INTERVAL}s)")
                    time.sleep(POLL_INTERVAL)

                else:
                    time.sleep(POLL_INTERVAL)

            except Exception as e:
                print(f"   [Slide {slide_num}] [WARN] Error polling: {e}")
                time.sleep(POLL_INTERVAL)

        print(f"   [Slide {slide_num}] [ERROR] Timeout ({MAX_POLL_ATTEMPTS * POLL_INTERVAL}s)")
        return None

    # ------------------------------------------------------------------
    # FASE 3a: SLIDE 1 = ANCLA VISUAL MAESTRA
    #
    # El Slide 1 ya no es "un slide mas" generado en paralelo con el resto:
    # se genera PRIMERO y en solitario, y su imagen resultante se usa como
    # referencia visual real (image_input) para todos los slides 2+, ademas
    # del ADN visual en texto. Esto garantiza continuidad real (temperatura
    # de color, contraste, grano, luminosidad) en vez de una paleta nominal
    # parecida. Cadena: REFERENCE IMAGE -> VISUAL DNA -> SLIDE 1 -> ANCLA -> SLIDES 2+
    # ------------------------------------------------------------------
    slide1 = next((s for s in slides if s.get("uses_reference_image_directly")), None)
    slide1_num = slide1["number"] if slide1 else None
    slide1_in_scope = slide1 is not None and (only_slides is None or slide1_num in only_slides)

    anchor_url = None

    if slide1_in_scope:
        print(f"\n{'='*60}")
        print(f"FASE 3a: GENERANDO SLIDE 1 (ANCLA VISUAL MAESTRA)")
        print(f"{'='*60}\n")

        ref_url = get_reference_url()
        if not ref_url:
            print(f"   [ERROR] Slide {slide1_num} - no se pudo obtener URL de la referencia, se omite")
        else:
            prompt1 = build_prompt_for_slide(slide1, visual_dna, carousel_type, attached_images=["reference"])
            task_id_1 = create_kie_task(api_key, prompt1, [ref_url])
            if not task_id_1:
                print(f"   [ERROR] Slide {slide1_num} - error creando tarea")
            else:
                print(f"   [OK] Slide {slide1_num} - tarea enviada (taskId: {task_id_1[:12]}...), esperando resultado...")
                image_url_1 = process_slide(slide1_num, {'task_id': task_id_1})
                if image_url_1:
                    output_filename = f"carousel-{slide1_num:02d}.png"
                    output_path = carousel_dir / output_filename
                    if download_image(image_url_1, output_path):
                        print(f"   [OK] Slide {slide1_num} - guardado: {output_filename} (ancla visual lista)")
                        slides_generated.append({
                            "id": slide1_num,
                            "role": slide1.get('role', ''),
                            "narrative_objective": slide1.get('narrative_objective', ''),
                            "filename": output_filename,
                            "success": True,
                            "used_reference_directly": True,
                            "used_product_mockup_directly": False,
                            "used_slide1_anchor": False,
                            "with_logo": None,
                        })
                        # Reutilizamos la URL publica que ya devolvio Kie AI como ancla
                        # visual para los slides 2+ (evita un re-upload innecesario).
                        anchor_url = image_url_1
                    else:
                        print(f"   [ERROR] Slide {slide1_num} - error descargando imagen")
    elif slide1 is not None:
        # Slide 1 no esta en el alcance de esta regeneracion (--regenerate-slides sin el
        # 1) pero sigue existiendo en brief.json: reutilizamos el archivo ya generado en
        # disco como ancla visual para los slides que si se estan regenerando.
        existing_slide1_path = carousel_dir / f"carousel-{slide1_num:02d}.png"
        if existing_slide1_path.exists():
            print(f"\n   Slide 1 no esta en esta regeneracion — usando {existing_slide1_path.name} "
                  f"ya existente como ancla visual...")
            anchor_url = upload_asset_to_kie(api_key, existing_slide1_path)
        else:
            print(f"\n[WARN] Advertencia: no existe {existing_slide1_path.name} en disco y el Slide 1 no "
                  f"esta en esta regeneracion — los slides 2+ se generaran solo con el ADN visual en "
                  f"texto, sin ancla visual real.")

    # FASE 3b: Enviar el resto de tareas a Kie AI EN PARALELO, usando el Slide 1 como ancla
    print(f"\n{'='*60}")
    print(f"FASE 3b: ENVIANDO TAREAS EN PARALELO (Slides 2+)")
    print(f"{'='*60}\n")

    pending_tasks = {}
    total_requested = len(only_slides) if only_slides else len(slides)

    for slide in slides:
        slide_num = slide["number"]

        if only_slides and slide_num not in only_slides:
            print(f"   Slide {slide_num} (saltando)")
            continue

        if slide1 is not None and slide_num == slide1_num and slide1_in_scope:
            # Ya generado en la FASE 3a
            continue

        uses_reference = bool(slide.get("uses_reference_image_directly"))
        uses_product_mockup = bool(slide.get("uses_product_mockup_directly"))
        has_logo = slide_num in asset_map
        entity = asset_map[slide_num][1] if has_logo else None

        image_input = []
        attached_images = []

        if uses_reference:
            # Caso excepcional: slide marcado como referencia viral pero no coincide con
            # el slide1 detectado, o slide1 fallo en FASE 3a — fallback al comportamiento
            # original (imagen de referencia directa, sin ancla).
            ref_url = get_reference_url()
            if ref_url:
                image_input.append(ref_url)
                attached_images.append("reference")
        else:
            if anchor_url:
                image_input.append(anchor_url)
                attached_images.append("anchor")
            if uses_product_mockup:
                mockup_url = get_product_mockup_url()
                if mockup_url:
                    image_input.append(mockup_url)
                    attached_images.append("mockup")
                else:
                    print(f"   [ERROR] Slide {slide_num} - marcado con 'uses_product_mockup_directly' pero no "
                          f"hay mockup disponible, se omite")
                    continue
            elif has_logo:
                asset_path = asset_map[slide_num][0]
                asset_url = upload_asset_to_kie(api_key, asset_path)
                if asset_url:
                    image_input.append(asset_url)
                    attached_images.append("logo")

        info_str = (
            " [referencia viral]" if "reference" in attached_images
            else " [" + " + ".join(
                {"anchor": "ancla Slide 1", "mockup": "mockup de producto", "logo": f"logo: {entity}"}[r]
                for r in attached_images
            ) + "]" if attached_images
            else " [solo ADN en texto]"
        )
        print(f"   Slide {slide_num} [{slide.get('role', '')}]{info_str}")

        prompt = build_prompt_for_slide(slide, visual_dna, carousel_type, attached_images=attached_images)

        task_id = create_kie_task(api_key, prompt, image_input if image_input else None)

        if not task_id:
            print(f"   [ERROR] Slide {slide_num} - error creando tarea")
            continue

        pending_tasks[slide_num] = {
            'task_id': task_id,
            'slide': slide,
            'entity': entity,
            'used_anchor': "anchor" in attached_images,
        }
        print(f"   [OK] Slide {slide_num} - tarea enviada (taskId: {task_id[:12]}...)")

    if not pending_tasks and not slides_generated:
        print("\n[ERROR] No se pudieron crear tareas. Verifica tu API key y creditos.")
        sys.exit(1)

    # FASE 4: Poll en paralelo (slides 2+; el Slide 1 ya se resolvio en FASE 3a)
    if pending_tasks:
        print(f"\n{'='*60}")
        print(f"ESPERANDO RESULTADOS ({len(pending_tasks)} slides en paralelo)")
        print(f"{'='*60}\n")

    with ThreadPoolExecutor(max_workers=max(len(pending_tasks), 1)) as executor:
        futures = {}
        for slide_num, info in pending_tasks.items():
            future = executor.submit(process_slide, slide_num, info)
            futures[future] = (slide_num, info)

        for future in as_completed(futures):
            slide_num, info = futures[future]
            image_url = future.result()

            if not image_url:
                print(f"   [ERROR] Slide {slide_num} - no se pudo generar")
                continue

            output_filename = f"carousel-{slide_num:02d}.png"
            output_path = carousel_dir / output_filename

            if download_image(image_url, output_path):
                print(f"   [OK] Slide {slide_num} - guardado: {output_filename}")
                slides_generated.append({
                    "id": slide_num,
                    "role": info['slide'].get('role', ''),
                    "narrative_objective": info['slide'].get('narrative_objective', ''),
                    "filename": output_filename,
                    "success": True,
                    "used_reference_directly": bool(info['slide'].get('uses_reference_image_directly')),
                    "used_product_mockup_directly": bool(info['slide'].get('uses_product_mockup_directly')),
                    "used_slide1_anchor": bool(info.get('used_anchor')),
                    "with_logo": info['entity']
                })
            else:
                print(f"   [ERROR] Slide {slide_num} - error descargando imagen")

    slides_generated.sort(key=lambda x: x['id'])

    print("\nGenerando guia de logos opcionales...")
    generate_assets_needed_md(bundle_id, bundle_path, slides_for_detection, entities_by_slide)

    print("Generando manifest...")
    generate_manifest(
        bundle_id,
        carousel_dir,
        slides_generated,
        carousel_type,
        slide_count.get("confirmed"),
        reference_local_path.name,
    )

    print("\nCopiando slides finales a Descargas...")
    downloads_dest = export_final_slides_to_downloads(bundle_id, bundle_path, carousel_dir)

    elapsed_time = time.time() - start_time
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)

    print(f"\n{'='*60}")
    print(f"CARRUSEL GENERADO EXITOSAMENTE")
    print(f"{'='*60}")
    print(f"\nUbicacion: {carousel_dir}")
    print(f"Imagenes: {len(slides_generated)}/{total_requested} slides generados")
    print(f"Modelo: {MODEL} @ {RESOLUTION}")
    print(f"Costo estimado: ~${len(slides_generated) * COST_PER_IMAGE_USD:.2f}")
    print(f"Tiempo: {minutes}m {seconds}s (generacion en paralelo)")
    if downloads_dest:
        print(f"Carrusel guardado en: {downloads_dest}")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
