"""
gemini_client.py - Cliente de generacion de imagenes contra Google Gemini (Nano Banana 2
Lite), usado tanto por DIRECT MODE como por BATCH MODE.

Este modulo es el UNICO lugar donde se construyen las llamadas reales al SDK
`google-genai`. batch_manager.py y direct_generator.py NUNCA llaman al SDK
directamente — siempre pasan por aqui, para que el modelo/aspect_ratio/image_size
configurados en gemini_config.py se apliquen de forma idéntica en ambos modos.

Incluye un `FakeGeminiClient` inyectable (nunca llama a la red, nunca gasta credito)
para poder probar toda la orquestacion (cache, retries, QA, batch-vs-direct) sin una
GEMINI_API_KEY real — ver PRUEBAS en SKILL.md, seccion "COST OPTIMIZATION".
"""

import io
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from gemini_config import GeminiConfig


@dataclass
class GeminiImageResult:
    success: bool
    image_bytes: Optional[bytes] = None
    error: Optional[str] = None
    usage_metadata: Optional[Dict[str, Any]] = None  # uso REAL devuelto por la API (tokens)


class GeminiClient:
    """Cliente real, respaldado por el SDK oficial `google-genai`."""

    def __init__(self, config: GeminiConfig):
        if not config.has_api_key():
            raise RuntimeError(
                "GEMINI_API_KEY no configurada. Crea/actualiza $HOME/.claude/skills/"
                "carousel-gen/.env con GEMINI_API_KEY=tu-api-key (ver .env.example)."
            )
        # Import diferido: asi el modulo se puede importar (para tests con
        # FakeGeminiClient) incluso en entornos sin el SDK instalado.
        from google import genai
        from google.genai import types
        self._genai = genai
        self._types = types
        self._client = genai.Client(api_key=config.api_key)
        self.config = config

    def _build_contents(self, prompt: str, reference_images: List[bytes]) -> list:
        parts: list = [prompt]
        for img_bytes in reference_images:
            parts.append(self._types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
        return parts

    def _build_generation_config(self):
        return self._types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=self._types.ImageConfig(
                aspect_ratio=self.config.aspect_ratio,
                image_size=self.config.image_size,
            ),
        )

    def generate_image_direct(self, prompt: str, reference_images: Optional[List[bytes]] = None) -> GeminiImageResult:
        """Genera UNA imagen en modo directo (sincrono). Usado por direct_generator.py."""
        reference_images = reference_images or []
        try:
            response = self._client.models.generate_content(
                model=self.config.image_model,
                contents=self._build_contents(prompt, reference_images),
                config=self._build_generation_config(),
            )
            return self._extract_result(response)
        except Exception as e:  # noqa: BLE001 - reportar cualquier fallo de API como resultado fallido
            return GeminiImageResult(success=False, error=str(e))

    def build_inlined_request(self, prompt: str, reference_images: Optional[List[bytes]], metadata: Dict[str, str]):
        """Construye un `types.InlinedRequest` para enviar dentro de un trabajo Batch.
        Usado exclusivamente por batch_manager.py."""
        reference_images = reference_images or []
        return self._types.InlinedRequest(
            model=self.config.image_model,
            contents=self._build_contents(prompt, reference_images),
            config=self._build_generation_config(),
            metadata=metadata,
        )

    def submit_batch(self, inlined_requests: list):
        """Envia un trabajo Batch con las requests ya construidas. Devuelve el
        `BatchJob` del SDK (contiene `.name` para poder consultarlo despues)."""
        return self._client.batches.create(model=self.config.image_model, src=inlined_requests)

    def get_batch(self, name: str):
        """Consulta el estado actual de un trabajo Batch por su `name`."""
        return self._client.batches.get(name=name)

    def _extract_result(self, response) -> GeminiImageResult:
        usage = None
        if getattr(response, "usage_metadata", None) is not None:
            try:
                usage = response.usage_metadata.model_dump()
            except Exception:  # noqa: BLE001
                usage = {"raw": str(response.usage_metadata)}

        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", None) or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is not None and getattr(inline_data, "data", None):
                    return GeminiImageResult(success=True, image_bytes=inline_data.data, usage_metadata=usage)

        return GeminiImageResult(success=False, error="La respuesta de Gemini no contiene ninguna imagen (inline_data vacio).", usage_metadata=usage)


class FakeGeminiClient:
    """
    Cliente FALSO para pruebas locales sin GEMINI_API_KEY y sin gastar credito real.

    Genera un PNG 1x1 valido de verdad (no basura binaria) para que el resto del
    pipeline (descarga a disco, QA con PIL, export) pueda ejecutarse end-to-end de forma
    determinista. NUNCA hace ninguna llamada de red.
    """

    def __init__(self, config: GeminiConfig, fail_slides: Optional[set] = None, fail_until_attempt: Optional[Dict[int, int]] = None):
        self.config = config
        # Conjuntos de slide_number que deben simular un fallo (para probar retries/QA).
        self.fail_slides = fail_slides or set()
        # slide_number -> intento en el que por fin tiene exito (1-indexado). Si no esta
        # aqui, un slide en fail_slides falla SIEMPRE.
        self.fail_until_attempt = fail_until_attempt or {}
        self._attempt_counts: Dict[int, int] = {}

    @staticmethod
    def _tiny_png(seed: bytes) -> bytes:
        """PNG 1x1 real y minimo, con un byte derivado de `seed` en el pixel — asi dos
        prompts distintos producen bytes distintos, util para verificar en tests que no
        se reutilizo una imagen equivocada."""
        def chunk(tag: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        width, height = 1, 1
        pixel_val = seed[0] if seed else 0
        ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        raw = bytes([0, pixel_val, pixel_val, pixel_val])
        idat = zlib.compress(raw)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
        return png

    def _slide_number_from_metadata(self, metadata: Dict[str, str]) -> Optional[int]:
        raw = (metadata or {}).get("slide_number")
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _should_fail(self, slide_number: Optional[int]) -> bool:
        if slide_number is None or slide_number not in self.fail_slides:
            return False
        attempt = self._attempt_counts.get(slide_number, 0) + 1
        self._attempt_counts[slide_number] = attempt
        success_at = self.fail_until_attempt.get(slide_number)
        if success_at is not None and attempt >= success_at:
            return False
        return True

    def generate_image_direct(self, prompt: str, reference_images: Optional[List[bytes]] = None, _slide_number: Optional[int] = None) -> GeminiImageResult:
        if self._should_fail(_slide_number):
            return GeminiImageResult(success=False, error="[FAKE] fallo simulado de generacion")
        seed = prompt.encode("utf-8")[:1] or b"\x00"
        return GeminiImageResult(
            success=True,
            image_bytes=self._tiny_png(seed),
            usage_metadata={"fake": True, "prompt_token_count": len(prompt.split())},
        )

    def build_inlined_request(self, prompt: str, reference_images: Optional[List[bytes]], metadata: Dict[str, str]):
        return {"prompt": prompt, "metadata": metadata}

    def submit_batch(self, inlined_requests: list):
        @dataclass
        class _FakeBatchJob:
            name: str
            state: str = "JOB_STATE_SUCCEEDED"
            _requests: list = field(default_factory=list)

        job = _FakeBatchJob(name="fake-batch-job", _requests=inlined_requests)
        return job

    def get_batch(self, name: str):
        return self._last_job

    def run_fake_batch_and_get_results(self, inlined_requests: list) -> list:
        """Atajo de test: en vez de simular polling asincrono, resuelve el batch
        inmediatamente y devuelve una lista de (metadata, GeminiImageResult)."""
        results = []
        for req in inlined_requests:
            metadata = req["metadata"]
            slide_number = self._slide_number_from_metadata(metadata)
            result = self.generate_image_direct(req["prompt"], _slide_number=slide_number)
            results.append((metadata, result))
        return results
