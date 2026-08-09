#!/usr/bin/env python3
"""Generate the voice narration for a Constelaciones Familiares reel.

Flow:
  1. Read the full reel script (guion) from a .txt file.
  2. If it is longer than CHUNK_SPLIT_THRESHOLD_WORDS, split it into
     sentence-boundary chunks of roughly CHUNK_TARGET_WORDS words each --
     long single calls are where Gemini TTS quality visibly degrades, so
     splitting keeps every chunk well inside the model's comfortable range.
  3. Call Gemini TTS once per chunk, always with the "Sulafat" prebuilt
     voice (the brand's one official narration voice -- never chosen per
     call) and a style instruction asking for the calm, warm, reflective
     pacing of the brand's "tu" voice.
  4. Wrap each chunk's raw PCM response in a WAV header, trim off any
     anomalous trailing silence (Gemini TTS occasionally pads its response
     with minutes of near-silence after the real narration ends), then
     concatenate all chunks with ffmpeg (short silence between them so joins
     don't sound abrupt) and encode the final result as MP3.
  5. Save to scripts/output_audio/<reel_slug>/narracion.mp3.

GEMINI_API_KEY is never hardcoded. If it is not already set as an
environment variable, this script prompts for it (input is masked) and
offers to save it to the local .env file, which is already gitignored --
same pattern as generate_post_image.py.

Usage:
  python scripts/generate_reel_narration.py "testing/reel_scripts/<slug>.txt" <slug>
"""
from __future__ import annotations

import argparse
import base64
import getpass
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv, set_key

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

# The one official brand narration voice. Hard-coded on purpose -- this
# skill never asks the user which voice to use.
BRAND_VOICE = "Sulafat"

STYLE_INSTRUCTION = (
    "Narra el siguiente guion en espanol, con un tono calido y cercano, a "
    "un ritmo vivo y agil, un poco mas rapido que una conversacion pausada "
    "-- como alguien contando algo importante con ganas de que la otra "
    "persona lo entienda, sin alargar las vocales ni estirar las pausas "
    "entre frases, evitando por completo la cadencia lenta y solemne de "
    "una meditacion guiada, pero sin caer en un ritmo apurado ni en "
    "entonacion de anuncio publicitario:"
)

# Gemini TTS quality is reported to degrade on long single calls; splitting
# comfortably below that keeps every chunk safe. At ~150-160 words/min of
# paced narration, 500 words is roughly 3 minutes and 350 words roughly
# 2-2.5 minutes.
CHUNK_SPLIT_THRESHOLD_WORDS = 500
CHUNK_TARGET_WORDS = 350

DEFAULT_OUTPUT_DIR = REPO_ROOT / "scripts" / "output_audio"

# Raw PCM format Gemini TTS returns (audio/L16;rate=24000, mono).
PCM_SAMPLE_RATE = 24000
PCM_SAMPLE_WIDTH = 2
PCM_CHANNELS = 1

# Silence inserted between concatenated chunks so joins don't sound abrupt.
INTER_CHUNK_SILENCE_MS = 400

# Gemini TTS has been observed to return a large near-silent tail after the
# actual narration ends (confirmed via spectrogram on a real response: audio
# content stopped at ~103s but the buffer ran to 4:28). Every chunk gets
# checked for that anomalous trailing silence before concatenation, so
# padding doesn't accumulate into long dead air in the final file.
#
# The trim only fires when a silence period runs all the way to end-of-file
# (i.e. it's a trailing pad, not an internal pause) AND lasts at least
# TRAILING_SILENCE_MIN_DURATION_S. That duration is deliberately long (well
# above any natural sentence-final pause) so a soft, low-volume ending on the
# last word or phrase -- which briefly dips under the dB threshold as part of
# a normal decrescendo -- never gets misread as the start of padding. A first
# version used a much shorter duration (0.6s) and cut real speech off the end
# of the narration because of exactly that: a quiet trailing syllable
# triggered the "silence" detector.
TRAILING_SILENCE_THRESHOLD_DB = -40
TRAILING_SILENCE_MIN_DURATION_S = 2.5
# Extra buffer kept after the detected silence start, so the cut lands safely
# past any real audio decay/reverb instead of flush against the boundary.
TRAILING_SILENCE_SAFETY_MARGIN_S = 0.6
# Safety guard: if trimming would remove more than this fraction of the
# chunk, assume detection mistook real content for padding and keep the
# original instead of risking a truncated narration.
MAX_TRIM_FRACTION = 0.85


class GenerationError(RuntimeError):
    pass


RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _post_with_retry(url: str, api_key: str, payload: dict, timeout: float, attempts: int = 4) -> requests.Response:
    """POST to a Gemini endpoint, retrying transient failures (503 high-demand,
    429 rate limit, network hiccups) with exponential backoff."""
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            resp = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            resp = None
        if resp is not None and resp.status_code not in RETRYABLE_STATUSES:
            return resp
        if attempt == attempts - 1:
            if resp is not None:
                return resp
            raise last_exc
        delay = 2 * (2 ** attempt)
        print(f"  (intento {attempt + 1}/{attempts} fallo, reintentando en {delay}s...)")
        time.sleep(delay)
    raise AssertionError("unreachable")


def ensure_gemini_api_key() -> str:
    load_dotenv(ENV_PATH)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key

    print("No se encontro GEMINI_API_KEY en el entorno ni en .env.")
    api_key = getpass.getpass(
        "Pega tu API key de Gemini (no se mostrara en pantalla): "
    ).strip()
    if not api_key:
        raise GenerationError("No se ingreso ninguna API key. Abortando.")

    save = input(
        f"¿Guardarla en {ENV_PATH.name} para no volver a pedirla? [S/n]: "
    ).strip().lower()
    if save in ("", "s", "si", "sí", "y", "yes"):
        set_key(str(ENV_PATH), "GEMINI_API_KEY", api_key)
        print(f"Guardada en {ENV_PATH} (este archivo esta en .gitignore).")
    os.environ["GEMINI_API_KEY"] = api_key
    return api_key


def read_guion(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise GenerationError(f"El archivo {path} esta vacio o no se pudo leer texto.")
    return text


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_into_chunks(text: str, target_words: int) -> list:
    """Split `text` into chunks of roughly `target_words` words each,
    breaking only at sentence boundaries so no chunk cuts a sentence in
    half (which would land Gemini TTS mid-thought)."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    chunks = []
    current: list = []
    current_words = 0
    for sentence in sentences:
        words_in_sentence = len(sentence.split())
        if current and current_words + words_in_sentence > target_words:
            chunks.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += words_in_sentence
    if current:
        chunks.append(" ".join(current))
    return chunks


def generate_tts_audio(text: str, api_key: str) -> bytes:
    """Call Gemini TTS for one chunk of text, returning raw PCM bytes
    (audio/L16, 24kHz, mono, as documented for Gemini TTS output)."""
    url = f"{GEMINI_API_BASE}/{TTS_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": f"{STYLE_INSTRUCTION}\n\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": BRAND_VOICE}
                }
            },
        },
    }
    resp = _post_with_retry(url, api_key, payload, timeout=180)
    if resp.status_code >= 400:
        raise GenerationError(
            f"Gemini TTS (modelo={TTS_MODEL}) HTTP {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as e:
        raise GenerationError(f"Respuesta de audio inesperada: {data}") from e

    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    raise GenerationError(f"Gemini no devolvio datos de audio: {data}")


def pcm_to_wav(pcm_bytes: bytes, out_path: Path) -> None:
    with wave.open(str(out_path), "wb") as wav_file:
        wav_file.setnchannels(PCM_CHANNELS)
        wav_file.setsampwidth(PCM_SAMPLE_WIDTH)
        wav_file.setframerate(PCM_SAMPLE_RATE)
        wav_file.writeframes(pcm_bytes)


def write_silence_wav(out_path: Path, duration_ms: int) -> None:
    num_frames = int(PCM_SAMPLE_RATE * duration_ms / 1000)
    silence = b"\x00\x00" * num_frames
    pcm_to_wav(silence, out_path)


def probe_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise GenerationError(f"ffprobe fallo en {path}:\n{result.stderr[-500:]}")
    return float(result.stdout.strip())


_SILENCE_START_RE = re.compile(r"silence_start:\s*([\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([\d.]+)")


def _find_trailing_silence_start(wav_path: Path, total_duration: float) -> Optional[float]:
    """Return the timestamp where an anomalous trailing silence begins, or
    None if there isn't one. Only a silence period that (a) lasts at least
    TRAILING_SILENCE_MIN_DURATION_S and (b) runs all the way to end-of-file
    counts -- that combination is what distinguishes the Gemini TTS padding
    bug from an ordinary pause between sentences, which is always shorter
    and always followed by more speech.

    ffmpeg's silencedetect always emits a matching silence_end for a
    trailing silence too (using the stream's end as that timestamp), so
    "end of file" has to be recognized by the last silence_end landing at
    (approximately) total_duration -- an unmatched trailing silence_start
    never actually happens in practice, but is still handled as a fallback."""
    cmd = [
        "ffmpeg", "-i", str(wav_path),
        "-af", f"silencedetect=noise={TRAILING_SILENCE_THRESHOLD_DB}dB:d={TRAILING_SILENCE_MIN_DURATION_S}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    starts = [float(x) for x in _SILENCE_START_RE.findall(result.stderr)]
    ends = [float(x) for x in _SILENCE_END_RE.findall(result.stderr)]
    if not starts:
        return None
    if len(starts) > len(ends):
        return starts[-1]
    if abs(ends[-1] - total_duration) <= 0.1:
        return starts[-1]
    return None


def trim_trailing_silence(wav_path: Path) -> None:
    """Cut an anomalous trailing silence off `wav_path` in place, if one is
    detected. Keeps TRAILING_SILENCE_SAFETY_MARGIN_S of buffer after the
    detected silence start before cutting, so the boundary lands safely past
    any real audio decay instead of flush against it. Falls back to the
    untrimmed original if the cut would remove more than MAX_TRIM_FRACTION of
    the audio, as a last-resort guard against truncating real speech."""
    original_duration = probe_duration_seconds(wav_path)
    silence_start = _find_trailing_silence_start(wav_path, original_duration)
    if silence_start is None:
        return

    cut_at = silence_start + TRAILING_SILENCE_SAFETY_MARGIN_S
    if cut_at >= original_duration:
        return

    removed_fraction = 1 - (cut_at / original_duration) if original_duration else 0
    if removed_fraction > MAX_TRIM_FRACTION:
        print(
            f"    (recorte de silencio final descartado: habria quitado "
            f"{removed_fraction:.0%} del audio, se conserva el original)"
        )
        return

    trimmed_path = wav_path.with_name(wav_path.stem + "_trimmed.wav")
    cmd = ["ffmpeg", "-y", "-i", str(wav_path), "-t", f"{cut_at:.3f}", str(trimmed_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        trimmed_path.unlink(missing_ok=True)
        raise GenerationError(f"ffmpeg fallo al recortar silencio final:\n{result.stderr[-2000:]}")

    print(
        f"    Silencio final anomalo recortado: {original_duration:.1f}s -> "
        f"{cut_at:.1f}s (dejando {TRAILING_SILENCE_SAFETY_MARGIN_S}s de margen "
        f"tras el ultimo sonido detectado)"
    )
    trimmed_path.replace(wav_path)


def concat_and_encode_mp3(wav_paths: list, out_path: Path) -> None:
    """Concatenate wav_paths (already interleaved with silence clips) via
    ffmpeg's concat demuxer, then encode straight to the final MP3."""
    list_file = out_path.parent / "_concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for wav_path in wav_paths:
            escaped = str(wav_path.resolve()).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-codec:a", "libmp3lame", "-qscale:a", "2",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    list_file.unlink(missing_ok=True)
    if result.returncode != 0:
        raise GenerationError(f"ffmpeg fallo al unir/convertir el audio:\n{result.stderr[-2000:]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("guion_file", help="Ruta al .txt con el guion completo del reel")
    parser.add_argument("reel_slug", help="Nombre/slug del reel (define la carpeta de salida)")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f'Carpeta base de salida (default: "{DEFAULT_OUTPUT_DIR}")',
    )
    args = parser.parse_args()

    guion_path = Path(args.guion_file)
    if not guion_path.exists():
        print(f"No existe el archivo: {guion_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) / args.reel_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / "narracion.mp3"

    tmp_dir = out_dir / "_tmp_chunks"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        api_key = ensure_gemini_api_key()

        print(f"Leyendo guion: {guion_path.name}")
        guion_text = read_guion(guion_path)
        word_count = len(guion_text.split())
        print(f"  {word_count} palabras")

        if word_count > CHUNK_SPLIT_THRESHOLD_WORDS:
            chunks = split_into_chunks(guion_text, CHUNK_TARGET_WORDS)
            print(f"  Guion largo: dividido en {len(chunks)} fragmentos")
        else:
            chunks = [guion_text]

        silence_path = tmp_dir / "silence.wav"
        write_silence_wav(silence_path, INTER_CHUNK_SILENCE_MS)

        wav_sequence = []
        for i, chunk in enumerate(chunks, start=1):
            print(f"Generando audio del fragmento {i}/{len(chunks)} con voz '{BRAND_VOICE}'...")
            pcm_bytes = generate_tts_audio(chunk, api_key)
            chunk_wav = tmp_dir / f"chunk_{i:02d}.wav"
            pcm_to_wav(pcm_bytes, chunk_wav)
            trim_trailing_silence(chunk_wav)
            wav_sequence.append(chunk_wav)
            if i < len(chunks):
                wav_sequence.append(silence_path)

        print(f"Uniendo {len(chunks)} fragmento(s) y codificando a MP3...")
        concat_and_encode_mp3(wav_sequence, final_path)

        for f in tmp_dir.glob("*"):
            f.unlink()
        tmp_dir.rmdir()

        print(f"Narracion guardada en: {final_path}")
    except GenerationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
