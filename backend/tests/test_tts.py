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


def test_elevenlabs_provider_inheritance():
    """Verify ElevenLabsProvider implements TTSProvider ABC."""
    from backend.app.services.tts.elevenlabs_provider import ElevenLabsProvider
    provider = ElevenLabsProvider(api_key="test_key_123")
    assert isinstance(provider, TTSProvider)
    assert provider.provider_name == "elevenlabs"
    assert provider.api_key == "test_key_123"


def test_elevenlabs_reads_api_key_from_env(monkeypatch):
    """Verify ElevenLabsProvider reads ELEVENLABS_API_KEY from environment."""
    from backend.app.services.tts.elevenlabs_provider import ElevenLabsProvider
    monkeypatch.setenv("ELEVENLABS_API_KEY", "env_secret_key_456")
    provider = ElevenLabsProvider()
    assert provider.api_key == "env_secret_key_456"


def test_elevenlabs_missing_api_key_error(tmp_path: Path, monkeypatch):
    """Verify ElevenLabsProvider raises ValueError when API key is missing."""
    from backend.app.services.tts.elevenlabs_provider import ElevenLabsProvider
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    provider = ElevenLabsProvider(api_key=None)

    out = tmp_path / "eleven_missing.mp3"
    with pytest.raises(ValueError) as excinfo:
        asyncio.run(provider.synthesize("A magical forest tale.", str(out)))
    assert "ELEVENLABS_API_KEY is not set" in str(excinfo.value)


def test_audio_cache_hash_uniqueness():
    """Verify compute_audio_hash is deterministic and unique per text+voice+provider."""
    from backend.app.services.tts.cache import compute_audio_hash
    h1 = compute_audio_hash("Once upon a time", "Rachel", "elevenlabs")
    h2 = compute_audio_hash("Once upon a time", "Rachel", "elevenlabs")
    # Identical inputs produce identical hash
    assert h1 == h2

    # Different provider produces different hash
    h_edge = compute_audio_hash("Once upon a time", "Rachel", "edge_tts")
    assert h1 != h_edge

    # Different voice produces different hash
    h_adam = compute_audio_hash("Once upon a time", "Adam", "elevenlabs")
    assert h1 != h_adam

    # Different text produces different hash
    h_diff_text = compute_audio_hash("Once upon another time", "Rachel", "elevenlabs")
    assert h1 != h_diff_text


def test_elevenlabs_synthesize_caches_and_avoids_duplicate_synthesis(tmp_path: Path):
    """Verify audio is cached by hash(text+voice+provider) so identical text is never synthesized twice."""
    import uuid
    from unittest.mock import patch, MagicMock
    from backend.app.services.tts.elevenlabs_provider import ElevenLabsProvider
    from backend.app.services.tts.cache import get_cached_audio

    provider = ElevenLabsProvider(api_key="mock_api_key")
    text = f"Unique fairy tale text for caching verification {uuid.uuid4()}."
    voice = "Rachel"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"ID3-MOCK-ELEVENLABS-AUDIO-PAYLOAD-FOR-TESTING"

    call_count = 0

    async def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_response

    async def run():
        out1 = tmp_path / "out1.mp3"
        out2 = tmp_path / "out2.mp3"

        with patch("httpx.AsyncClient.post", side_effect=fake_post):
            # First synthesis: Cache MISS -> Calls API
            await provider.synthesize(text, str(out1), voice=voice)
            assert out1.exists()
            assert out1.read_bytes() == mock_response.content
            assert call_count == 1

            # Verify file exists in audio_cache
            cached_path = get_cached_audio(text, "21m00Tcm4TlvDq8ikWAM", "elevenlabs")
            assert cached_path is not None
            assert cached_path.exists()

            # Second synthesis: Cache HIT -> Reads from cache, NEVER calls API again!
            await provider.synthesize(text, str(out2), voice=voice)
            assert out2.exists()
            assert out2.read_bytes() == mock_response.content
            # API was NOT called a second time!
            assert call_count == 1

    asyncio.run(run())

