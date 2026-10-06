"""ElevenLabs TTS Provider implementation supporting neural speech synthesis and caching."""

import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx

from backend.app.services.tts.base import TTSProvider
from backend.app.services.tts.cache import get_cached_audio, save_to_cache
from backend.app.config import ELEVENLABS_API_KEY, DEFAULT_ELEVENLABS_VOICE

DEFAULT_VOICE_ID = DEFAULT_ELEVENLABS_VOICE or "21m00Tcm4TlvDq8ikWAM"  # Rachel

CURATED_ELEVENLABS_VOICES: List[Dict[str, Any]] = [
    {
        "name": "Rachel",
        "ShortName": "21m00Tcm4TlvDq8ikWAM",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "Locale": "en-US",
        "LocaleName": "English (US)",
        "Gender": "Female",
        "FriendlyName": "Rachel - Calm & Expressive (Multilingual)",
        "Language": "en",
        "provider": "elevenlabs",
    },
    {
        "name": "Adam",
        "ShortName": "pNInz6obpgDQGcFmaJgB",
        "voice_id": "pNInz6obpgDQGcFmaJgB",
        "Locale": "en-US",
        "LocaleName": "English (US)",
        "Gender": "Male",
        "FriendlyName": "Adam - Deep Storyteller (Multilingual)",
        "Language": "en",
        "provider": "elevenlabs",
    },
    {
        "name": "Antoni",
        "ShortName": "ErXwobaYiN019PkySvjV",
        "voice_id": "ErXwobaYiN019PkySvjV",
        "Locale": "en-US",
        "LocaleName": "English (US)",
        "Gender": "Male",
        "FriendlyName": "Antoni - Warm Narration (Multilingual)",
        "Language": "en",
        "provider": "elevenlabs",
    },
    {
        "name": "Bella",
        "ShortName": "EXAVITQu4vr4xnSDxMaL",
        "voice_id": "EXAVITQu4vr4xnSDxMaL",
        "Locale": "en-US",
        "LocaleName": "English (US)",
        "Gender": "Female",
        "FriendlyName": "Bella - Soft & Gentle (Multilingual)",
        "Language": "en",
        "provider": "elevenlabs",
    },
    {
        "name": "Josh",
        "ShortName": "TxGEqnHWrfWFTfGW9XjX",
        "voice_id": "TxGEqnHWrfWFTfGW9XjX",
        "Locale": "en-US",
        "LocaleName": "English (US)",
        "Gender": "Male",
        "FriendlyName": "Josh - Resonant Classic Storyteller (Multilingual)",
        "Language": "en",
        "provider": "elevenlabs",
    },
    {
        "name": "Domi",
        "ShortName": "AZnzlk1XvdvUeBnXmlld",
        "voice_id": "AZnzlk1XvdvUeBnXmlld",
        "Locale": "en-US",
        "LocaleName": "English (US)",
        "Gender": "Female",
        "FriendlyName": "Domi - Vibrant & Confident (Multilingual)",
        "Language": "en",
        "provider": "elevenlabs",
    },
    {
        "name": "Elli",
        "ShortName": "MF3mGyEYCl7XYWbV9V6O",
        "voice_id": "MF3mGyEYCl7XYWbV9V6O",
        "Locale": "en-US",
        "LocaleName": "English (US)",
        "Gender": "Female",
        "FriendlyName": "Elli - Emotional & Dramatic (Multilingual)",
        "Language": "en",
        "provider": "elevenlabs",
    },
]

VOICE_NAME_TO_ID = {
    v["name"].lower(): v["voice_id"] for v in CURATED_ELEVENLABS_VOICES
}


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs TTS Provider supporting multilingual narration and automatic audio caching."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_voice_id: str = DEFAULT_VOICE_ID,
    ) -> None:
        """Initialize provider with API key from argument or environment."""
        self._api_key = api_key
        self.default_voice_id = default_voice_id

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    @property
    def api_key(self) -> Optional[str]:
        """Read API key dynamically from instance or environment."""
        return self._api_key or os.getenv("ELEVENLABS_API_KEY") or ELEVENLABS_API_KEY

    def resolve_voice(self, voice: Optional[str]) -> str:
        """Map human-readable voice name or ID to an ElevenLabs voice ID."""
        if not voice or not voice.strip():
            return self.default_voice_id

        cleaned = voice.strip()
        cleaned_lower = cleaned.lower()

        # Check friendly name alias map
        if cleaned_lower in VOICE_NAME_TO_ID:
            return VOICE_NAME_TO_ID[cleaned_lower]

        # If a voice string from Edge TTS was passed by mistake (e.g., 'en-US-AriaNeural'), fallback
        if cleaned.startswith("en-") or cleaned.startswith("bn-"):
            return self.default_voice_id

        # Assume it is a valid ElevenLabs voice ID
        return cleaned

    async def list_voices(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve available ElevenLabs voices, falling back to curated list."""
        api_key = self.api_key
        if api_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        "https://api.elevenlabs.io/v1/voices",
                        headers={"xi-api-key": api_key},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_voices = data.get("voices", [])
                        if raw_voices:
                            formatted = []
                            for v in raw_voices:
                                vid = v.get("voice_id")
                                name = v.get("name", "Voice")
                                category = v.get("category", "")
                                formatted.append({
                                    "name": name,
                                    "ShortName": vid,
                                    "voice_id": vid,
                                    "Locale": "en-US",
                                    "LocaleName": "Multilingual",
                                    "Gender": v.get("labels", {}).get("gender", "Narrator").title(),
                                    "FriendlyName": f"{name} ({category or 'Premade'})",
                                    "Language": "en",
                                    "provider": "elevenlabs",
                                })
                            return formatted
            except Exception:
                pass

        return CURATED_ELEVENLABS_VOICES

    async def synthesize(
        self,
        text: str,
        out_path: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
    ) -> None:
        """Synthesize text into speech using ElevenLabs API with hash caching.

        Args:
            text: Text content to narrate.
            out_path: Target path for the generated MP3 file.
            voice: Voice ID or friendly name.
            rate: Speech rate adjustment (not used by ElevenLabs default).

        Raises:
            ValueError: If input text is empty or ELEVENLABS_API_KEY is missing.
            RuntimeError: If the ElevenLabs HTTP request fails.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty for speech synthesis.")

        chosen_voice = self.resolve_voice(voice)

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

        # 2. Check API key
        api_key = self.api_key
        if not api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is not set. Please add ELEVENLABS_API_KEY to your .env file."
            )

        dest_dir = Path(out_path).parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{chosen_voice}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text.strip(),
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                params={"output_format": "mp3_44100_128"},
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"ElevenLabs synthesis failed with HTTP {response.status_code}: {response.text}"
                )

            with open(out_path, "wb") as f:
                f.write(response.content)

        # 3. Save synthesized audio to cache
        save_to_cache(
            text=text,
            voice=chosen_voice,
            provider=self.provider_name,
            source_audio_path=out_path,
        )
