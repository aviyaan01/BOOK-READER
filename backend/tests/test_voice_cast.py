"""Unit tests for voice_cast.py — Claude sentence tagging and voice assignment."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.app.services.voice_cast import (
    DEFAULT_VOICE_POOL_EN,
    DEFAULT_VOICE_POOL_BN,
    assign_voice_to_speaker,
    build_voice_segments,
    compute_cast_hash,
    get_voice_pool,
    tag_sentences_with_claude,
    _extract_json_array,
)


# ─────────────────────────────────────────────────────────────────────────────
# Voice pool tests
# ─────────────────────────────────────────────────────────────────────────────

def test_get_voice_pool_english():
    pool = get_voice_pool("en")
    assert pool == DEFAULT_VOICE_POOL_EN
    assert len(pool) >= 2


def test_get_voice_pool_bangla():
    pool = get_voice_pool("bn")
    assert pool == DEFAULT_VOICE_POOL_BN
    assert len(pool) >= 2


def test_get_voice_pool_custom():
    custom = ["voice-A", "voice-B"]
    pool = get_voice_pool("en", custom_voices=custom)
    assert pool == custom


# ─────────────────────────────────────────────────────────────────────────────
# assign_voice_to_speaker tests
# ─────────────────────────────────────────────────────────────────────────────

def test_narrator_always_gets_first_pool_slot():
    cast = {}
    pool = ["en-US-AriaNeural", "en-US-ChristopherNeural"]
    voice = assign_voice_to_speaker("narrator", cast, pool)
    assert voice == "en-US-AriaNeural"
    assert cast["narrator"] == "en-US-AriaNeural"


def test_narrator_gets_explicit_override():
    cast = {}
    pool = ["en-US-AriaNeural", "en-US-ChristopherNeural"]
    voice = assign_voice_to_speaker("narrator", cast, pool, narrator_voice="en-US-JennyNeural")
    assert voice == "en-US-JennyNeural"


def test_characters_assigned_different_voices():
    cast = {}
    pool = ["en-US-AriaNeural", "en-US-ChristopherNeural", "en-US-JennyNeural"]
    v_narrator = assign_voice_to_speaker("narrator", cast, pool)
    v_fox = assign_voice_to_speaker("fox", cast, pool)
    v_wolf = assign_voice_to_speaker("wolf", cast, pool)
    # All different
    assert v_narrator != v_fox
    assert v_fox != v_wolf
    assert v_narrator != v_wolf


def test_same_speaker_always_same_voice():
    cast = {}
    pool = DEFAULT_VOICE_POOL_EN
    v1 = assign_voice_to_speaker("alice", cast, pool)
    v2 = assign_voice_to_speaker("alice", cast, pool)
    assert v1 == v2


def test_pool_exhaustion_cycles_deterministically():
    """When pool exhausted, assignment still works without raising."""
    cast = {}
    pool = ["v-narrator", "v-char1"]  # Only 2 slots
    assign_voice_to_speaker("narrator", cast, pool)
    assign_voice_to_speaker("char1", cast, pool)
    # Third character — pool exhausted, should cycle
    v3 = assign_voice_to_speaker("char2", cast, pool)
    assert v3 is not None


# ─────────────────────────────────────────────────────────────────────────────
# _extract_json_array tests
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_json_array_clean():
    raw = '[{"sentence": "Hello.", "speaker": "narrator"}]'
    result = _extract_json_array(raw)
    assert result == [{"sentence": "Hello.", "speaker": "narrator"}]


def test_extract_json_array_with_markdown_fence():
    raw = '```json\n[{"sentence": "Hi.", "speaker": "Alice"}]\n```'
    result = _extract_json_array(raw)
    assert result is not None
    assert result[0]["speaker"] == "Alice"


def test_extract_json_array_embedded_in_text():
    raw = 'Here is the result:\n[{"sentence": "Go!", "speaker": "Fox"}]\nThat is all.'
    result = _extract_json_array(raw)
    assert result is not None
    assert result[0]["speaker"] == "Fox"


def test_extract_json_array_invalid_returns_none():
    result = _extract_json_array("not json at all")
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# tag_sentences_with_claude tests (mocked)
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_client(json_payload: list) -> MagicMock:
    """Return a mock Anthropic client that returns json_payload as text."""
    mock_block = MagicMock()
    mock_block.text = json.dumps(json_payload)

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_tag_sentences_parses_narrator_and_character():
    payload = [
        {"sentence": "Once upon a time.", "speaker": "narrator"},
        {"sentence": "I am the hero!", "speaker": "Alice"},
    ]
    client = _make_mock_client(payload)
    result = tag_sentences_with_claude("Some text.", client=client)
    assert len(result) == 2
    assert result[0]["speaker"] == "narrator"
    assert result[1]["speaker"] == "Alice"


def test_tag_sentences_normalizes_speaker():
    """Speakers are kept as-is (voice assignment normalizes via lower())."""
    payload = [{"sentence": "Roar!", "speaker": "BIG WOLF"}]
    client = _make_mock_client(payload)
    result = tag_sentences_with_claude("Roar!", client=client)
    assert result[0]["speaker"] == "BIG WOLF"


def test_tag_sentences_falls_back_on_api_error(monkeypatch):
    """Falls back to narrator-only when API raises."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("network error")
    result = tag_sentences_with_claude("Test sentence.", client=mock_client)
    assert len(result) == 1
    assert result[0]["speaker"] == "narrator"


def test_tag_sentences_no_api_key_fallback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = tag_sentences_with_claude("Hello world.", client=None)
    assert len(result) == 1
    assert result[0]["speaker"] == "narrator"


def test_tag_sentences_empty_text():
    result = tag_sentences_with_claude("", client=MagicMock())
    assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# build_voice_segments integration
# ─────────────────────────────────────────────────────────────────────────────

def test_build_voice_segments_returns_text_voice_tuples():
    payload = [
        {"sentence": "The forest was dark.", "speaker": "narrator"},
        {"sentence": "Run!", "speaker": "Fox"},
    ]
    client = _make_mock_client(payload)
    cast = {}
    pool = DEFAULT_VOICE_POOL_EN
    segments = build_voice_segments(
        "The forest was dark. Run!",
        cast=cast,
        voice_pool=pool,
        client=client,
    )
    assert len(segments) == 2
    text0, voice0 = segments[0]
    text1, voice1 = segments[1]
    assert text0 == "The forest was dark."
    assert voice0 == pool[0]  # narrator → first slot
    assert text1 == "Run!"
    assert voice1 != voice0   # Fox gets a different voice


def test_build_voice_segments_cast_consistency():
    """Same character in different chunks gets same voice."""
    cast = {}
    pool = DEFAULT_VOICE_POOL_EN

    payload1 = [{"sentence": "Hello.", "speaker": "Alice"}]
    payload2 = [{"sentence": "Goodbye.", "speaker": "Alice"}]

    client1 = _make_mock_client(payload1)
    client2 = _make_mock_client(payload2)

    segs1 = build_voice_segments("Hello.", cast=cast, voice_pool=pool, client=client1)
    segs2 = build_voice_segments("Goodbye.", cast=cast, voice_pool=pool, client=client2)

    _, voice1 = segs1[0]
    _, voice2 = segs2[0]
    assert voice1 == voice2  # Same cast = same voice


# ─────────────────────────────────────────────────────────────────────────────
# compute_cast_hash
# ─────────────────────────────────────────────────────────────────────────────

def test_compute_cast_hash_deterministic():
    h1 = compute_cast_hash("Once upon a time")
    h2 = compute_cast_hash("Once upon a time")
    assert h1 == h2
    assert len(h1) == 16


def test_compute_cast_hash_different_inputs():
    h1 = compute_cast_hash("text A")
    h2 = compute_cast_hash("text B")
    assert h1 != h2
