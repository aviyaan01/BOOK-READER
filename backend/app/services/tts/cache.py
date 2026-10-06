"""Audio caching service to prevent duplicate speech synthesis.

Caches synthesized audio files keyed by SHA-256 hash of (text + voice + provider).
"""

import hashlib
import shutil
from pathlib import Path
from typing import Optional
from backend.app.config import AUDIO_CACHE_DIR


def compute_audio_hash(text: str, voice: Optional[str], provider: str) -> str:
    """Compute a deterministic SHA-256 hash for (text + voice + provider).

    Args:
        text: Normalized text to synthesize.
        voice: Voice identifier or name.
        provider: TTS provider name (e.g., 'elevenlabs', 'edge_tts').

    Returns:
        Hexadecimal SHA-256 hash string.
    """
    clean_text = text.strip()
    clean_voice = (voice or "").strip().lower()
    clean_provider = (provider or "").strip().lower()
    payload = f"{clean_text}|{clean_voice}|{clean_provider}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def get_cached_audio_path(hash_key: str) -> Path:
    """Return the filesystem path for a cached audio file."""
    return AUDIO_CACHE_DIR / f"{hash_key}.mp3"


def get_cached_audio(text: str, voice: Optional[str], provider: str) -> Optional[Path]:
    """Retrieve existing cached audio file path if present and valid.

    Args:
        text: Synthesized text.
        voice: Voice name or ID.
        provider: TTS provider name.

    Returns:
        Path to cached audio file if it exists and has content, otherwise None.
    """
    if not text or not text.strip():
        return None

    hash_key = compute_audio_hash(text, voice, provider)
    cached_file = get_cached_audio_path(hash_key)
    if cached_file.exists() and cached_file.is_file() and cached_file.stat().st_size > 0:
        return cached_file
    return None


def save_to_cache(
    text: str,
    voice: Optional[str],
    provider: str,
    source_audio_path: str | Path,
) -> Path:
    """Save an audio file to cache keyed by hash(text + voice + provider).

    Args:
        text: Synthesized text.
        voice: Voice name or ID.
        provider: TTS provider name.
        source_audio_path: Path to the generated audio file to cache.

    Returns:
        Path to the saved cache file.
    """
    source_path = Path(source_audio_path)
    if not source_path.exists() or source_path.stat().st_size == 0:
        return source_path

    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    hash_key = compute_audio_hash(text, voice, provider)
    cached_file = get_cached_audio_path(hash_key)

    try:
        if source_path.resolve() != cached_file.resolve():
            shutil.copyfile(source_path, cached_file)
    except Exception:
        pass

    return cached_file
