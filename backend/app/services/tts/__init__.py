"""TTS services package."""

from typing import Optional
from backend.app.services.tts.base import TTSProvider
from backend.app.services.tts.edge_tts_provider import EdgeTTSProvider, list_voices as list_edge_voices
from backend.app.services.tts.elevenlabs_provider import ElevenLabsProvider
from backend.app.services.tts.cache import compute_audio_hash, get_cached_audio, save_to_cache


def get_tts_provider(provider_name: Optional[str] = None) -> TTSProvider:
    """Factory returning the appropriate TTSProvider based on provider string.

    Args:
        provider_name: Name of provider, e.g. 'elevenlabs' or 'edge_tts'.

    Returns:
        TTSProvider instance.
    """
    clean = (provider_name or "edge_tts").strip().lower()
    if clean in ("elevenlabs", "eleven_labs", "eleven-labs"):
        return ElevenLabsProvider()
    return EdgeTTSProvider()


__all__ = [
    "TTSProvider",
    "EdgeTTSProvider",
    "ElevenLabsProvider",
    "get_tts_provider",
    "list_edge_voices",
    "compute_audio_hash",
    "get_cached_audio",
    "save_to_cache",
]
