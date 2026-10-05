"""Unit tests for TTS abstraction and EdgeTTSProvider."""

import asyncio
from pathlib import Path
import pytest
from backend.app.services.tts.base import TTSProvider
from backend.app.services.tts.edge_tts_provider import (
    EdgeTTSProvider,
    list_voices,
    DEFAULT_BANGLA_VOICE,
    DEFAULT_ENGLISH_VOICE,
)


def test_provider_inheritance():
    """Verify EdgeTTSProvider is an instance and subclass of TTSProvider ABC."""
    provider = EdgeTTSProvider()
    assert isinstance(provider, TTSProvider)
    assert provider.default_bangla_voice == "bn-BD-NabanitaNeural"
    assert provider.default_english_voice == "en-US-AriaNeural"


def test_list_voices_filter():
    """Verify list_voices returns voices filtered by language code."""
    async def run():
        en_voices = await list_voices(language="en")
        bn_voices = await list_voices(language="bn")

        assert len(en_voices) > 0
        assert len(bn_voices) > 0

        # Ensure Bangla voices contain bn
        for v in bn_voices:
            locale = v.get("Locale", "").lower()
            assert "bn" in locale

        # Ensure English voices contain en
        for v in en_voices:
            locale = v.get("Locale", "").lower()
            assert "en" in locale

    asyncio.run(run())


def test_synthesize_english_and_bangla(tmp_path: Path):
    """Verify synthesize generates valid non-empty audio files for both languages."""
    async def run():
        provider = EdgeTTSProvider()

        # English synthesis
        en_out = tmp_path / "en_test.mp3"
        await provider.synthesize("Hello world.", str(en_out))
        assert en_out.exists()
        assert en_out.stat().st_size > 500

        # Bangla synthesis
        bn_out = tmp_path / "bn_test.mp3"
        await provider.synthesize("শুভ সকাল।", str(bn_out))
        assert bn_out.exists()
        assert bn_out.stat().st_size > 500

    asyncio.run(run())


def test_empty_text_error(tmp_path: Path):
    """Verify empty text raises ValueError."""
    async def run():
        provider = EdgeTTSProvider()
        out = tmp_path / "empty.mp3"
        with pytest.raises(ValueError):
            await provider.synthesize("", str(out))

    asyncio.run(run())
