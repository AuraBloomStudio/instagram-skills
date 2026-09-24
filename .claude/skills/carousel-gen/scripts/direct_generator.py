"""
direct_generator.py - DIRECT MODE: genera slides llamando a Gemini de forma sincrona,
uno por request. Pensado para pruebas rapidas, desarrollo, debugging y regeneracion
individual (ver SKILL.md, seccion "MODO DIRECTO").

Usa el MISMO `GeminiClient` (o `FakeGeminiClient` en tests) que batch_manager.py — nunca
duplica la construccion de prompts ni la config de generacion.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from gemini_client import GeminiImageResult

# FABRICA RAPIDA (ver SKILL.md): con MAX_SLIDES=10, la Fase B nunca tiene mas de 9
# slides pendientes (10 - el Slide 1, generado aparte). 9 workers permite generar TODOS
# los slides restantes en una unica tanda paralela, en vez de 2-3 tandas secuenciales de
# 4 — es la forma principal en que el pipeline evita latencia innecesaria.
_MAX_WORKERS = 9


@dataclass
class GenerationTask:
    """Unidad de trabajo: un slide que necesita generarse (ya decidido por el
    orquestador que NO puede reutilizarse de cache)."""
    slide_number: int
    prompt: str
    reference_images: List[bytes] = field(default_factory=list)
    prompt_hash: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


def generate_direct(client, tasks: List[GenerationTask]) -> Dict[int, GeminiImageResult]:
    """
    Ejecuta cada tarea contra `client.generate_image_direct(...)`. Con mas de un task,
    se paraleliza con un pool moderado (no ilimitado, para respetar rate limits reales).
    Devuelve {slide_number: GeminiImageResult}.
    """
    results: Dict[int, GeminiImageResult] = {}

    if not tasks:
        return results

    def _run_one(task: GenerationTask) -> tuple:
        # `_slide_number` es un parametro extra que solo FakeGeminiClient usa (para
        # poder simular fallos deterministas por slide en los tests); el cliente real
        # lo ignora si no esta en su firma gracias a **kwargs implicito de Python al
        # llamar por posicion/keyword coincidente — aqui se llama explicitamente con
        # try/except para soportar ambas firmas sin acoplar direct_generator al tipo
        # concreto del cliente.
        try:
            result = client.generate_image_direct(
                task.prompt, task.reference_images, _slide_number=task.slide_number
            )
        except TypeError:
            result = client.generate_image_direct(task.prompt, task.reference_images)
        return task.slide_number, result

    if len(tasks) == 1:
        slide_number, result = _run_one(tasks[0])
        results[slide_number] = result
        return results

    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(tasks))) as executor:
        futures = [executor.submit(_run_one, task) for task in tasks]
        for future in as_completed(futures):
            slide_number, result = future.result()
            results[slide_number] = result

    return results
