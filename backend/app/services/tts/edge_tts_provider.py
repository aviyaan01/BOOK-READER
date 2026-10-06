"""Edge TTS Provider implementation using Microsoft Edge neural speech synthesis."""

import os
import re
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
import edge_tts
from backend.app.services.tts.base import TTSProvider

DEFAULT_BANGLA_VOICE = "bn-BD-NabanitaNeural"
DEFAULT_ENGLISH_VOICE = "en-US-AriaNeural"

# Fallback curated catalog in case of offline or rapid voice lookup
CURATED_VOICES: List[Dict[str, Any]] = [
    {
        "name": "en-US-AriaNeural",
        "ShortName": "en-US-AriaNeural",
        "Locale": "en-US",
        "Gender": "Female",
        "Language": "en",
    },
    {
        "name": "en-US-ChristopherNeural",
        "ShortName": "en-US-ChristopherNeural",
        "Locale": "en-US",
        "Gender": "Male",
        "Language": "en",
    },
    {
        "name": "en-US-JennyNeural",
        "ShortName": "en-US-JennyNeural",
        "Locale": "en-US",
        "Gender": "Female",
        "Language": "en",
    },
    {
        "name": "bn-BD-NabanitaNeural",
        "ShortName": "bn-BD-NabanitaNeural",
        "Locale": "bn-BD",
        "Gender": "Female",
        "Language": "bn",
    },
    {
        "name": "bn-BD-PradeepNeural",
        "ShortName": "bn-BD-PradeepNeural",
        "Locale": "bn-BD",
        "Gender": "Male",
        "Language": "bn",
    },
    {
        "name": "bn-IN-BashkarNeural",
        "ShortName": "bn-IN-BashkarNeural",
        "Locale": "bn-IN",
        "Gender": "Male",
        "Language": "bn",
    },
    {
        "name": "bn-IN-TanishaaNeural",
        "ShortName": "bn-IN-TanishaaNeural",
        "Locale": "bn-IN",
        "Gender": "Female",
        "Language": "bn",
    },
]


def is_bangla_text(text: str) -> bool:
    """Return True if text contains Bangla Unicode characters."""
    return bool(re.search(r"[\u0980-\u09FF]", text))


async def list_voices(language: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve available Edge TTS voices filtered optionally by language ('en' or 'bn')."""
    try:
        raw_voices = await edge_tts.list_voices()
    except Exception:
        raw_voices = CURATED_VOICES

    if not language:
        return raw_voices

    lang_lower = language.lower()
    filtered: List[Dict[str, Any]] = []
    for v in raw_voices:
        locale = v.get("Locale", "").lower()
        if locale.startswith(lang_lower) or f"-{lang_lower}" in locale:
            filtered.append(v)

    return filtered


import shutil
from backend.app.services.tts.cache import get_cached_audio, save_to_cache


class EdgeTTSProvider(TTSProvider):
    """TTS Provider utilizing Microsoft Edge neural speech synthesis with retry backoff and caching."""

    def __init__(
        self,
        default_english_voice: str = DEFAULT_ENGLISH_VOICE,
        default_bangla_voice: str = DEFAULT_BANGLA_VOICE,
    ) -> None:
        """Initialize the provider with default English and Bangla voices."""
        self.default_english_voice = default_english_voice
        self.default_bangla_voice = default_bangla_voice

    @property
    def provider_name(self) -> str:
        return "edge_tts"

    async def list_voices(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return available voices filtered by language code."""
        return await list_voices(language=language)

    async def synthesize(
        self,
        text: str,
        out_path: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
    ) -> None:
        """Synthesize text into speech and save audio to out_path with caching and backoff retries.

        Args:
            text: Text to narrate.
            out_path: Filepath where MP3 audio will be saved.
            voice: Optional voice name. Defaults to 'bn-BD-NabanitaNeural' for Bangla
                   or 'en-US-AriaNeural' for English.
            rate: Speech rate adjustment string (default '+0%').

        Raises:
            ValueError: If the input text is empty.
            Exception: If all 3 retry attempts fail due to network or service errors.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for speech synthesis.")

        # Determine voice if not explicitly provided
        if not voice:
            chosen_voice = self.default_bangla_voice if is_bangla_text(text) else self.default_english_voice
        else:
            chosen_voice = voice

        # 1. Check cache by hash(text + voice + provider)
        cached_file = get_cached_audio(
            text=text,
            voice=chosen_voice,
            provider=self.provider_name,
        )
        if cached_file:
            dest_dir = Path(out_path).parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached_file, out_path)
            return

        # Ensure destination directory exists
        dest_dir = Path(out_path).parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        max_retries = 3
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                communicate = edge_tts.Communicate(
                    text=text.strip(),
                    voice=chosen_voice,
                    rate=rate,
                )
                await communicate.save(out_path)

                # Save synthesized audio to cache
                save_to_cache(
                    text=text,
                    voice=chosen_voice,
                    provider=self.provider_name,
                    source_audio_path=out_path,
                )
                return
            except Exception as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = 1.0 * (2 ** attempt)
                    await asyncio.sleep(delay)

        if last_exception:
            raise last_exception

