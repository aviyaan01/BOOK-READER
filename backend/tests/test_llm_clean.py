"""Unit tests for optional LLM text cleanup service using Anthropic Claude."""

import hashlib
from unittest.mock import MagicMock, patch
import pytest

from backend.app.services.llm_clean import (
    SYSTEM_PROMPT,
    split_into_segments,
    is_valid_output_length,
    compute_segment_hash,
    clean_segment_with_llm,
    clean_text_with_llm,
    clear_cache,
    set_cached_segment,
    get_cached_segment,
)


@pytest.fixture(autouse=True)
def reset_llm_cache():
    """Ensure clean cache before and after each test."""
    clear_cache()
    yield
    clear_cache()


def test_system_prompt_exact_wording():
    """Verify system prompt exact requirements."""
    expected = (
        "You are a text restorer for audiobook narration. "
        "Fix OCR errors, broken words, and stray characters. "
        "NEVER add, remove, summarize, or rephrase story content. "
        "Keep the original language. Return only the corrected text."
    )
    assert SYSTEM_PROMPT == expected


def test_compute_segment_hash():
    """Verify segment hashing computes correct SHA-256 digest."""
    text = "Once upon a time in a magical forest."
    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert compute_segment_hash(text) == expected_hash


@pytest.mark.parametrize(
    "in_len, out_len, expected_valid",
    [
        (100, 100, True),    # 100%
        (100, 90, True),     # 90% (lower bound)
        (100, 110, True),    # 110% (upper bound)
        (100, 95, True),     # 95%
        (100, 105, True),    # 105%
        (100, 89, False),    # 89% (too short)
        (100, 111, False),   # 111% (too long)
        (100, 50, False),    # 50%
        (100, 150, False),   # 150%
        (0, 0, True),
        (100, 0, False),     # empty output
    ],
)
def test_is_valid_output_length(in_len, out_len, expected_valid):
    """Verify length checking accurately validates 90%-110% boundary."""
    input_str = "a" * in_len
    output_str = "b" * out_len
    assert is_valid_output_length(input_str, output_str) == expected_valid


def test_split_into_segments_short_text():
    """Short text (<3000 chars) should remain a single segment."""
    text = "This is a brief story."
    segments = split_into_segments(text, target_size=3000)
    assert segments == [text]


def test_split_into_segments_long_text():
    """Long text should split into segments of approximately target_size characters."""
    paragraphs = [f"Paragraph {i}: " + ("word " * 150) for i in range(10)]
    full_text = "\n\n".join(paragraphs)
    assert len(full_text) > 7000

    segments = split_into_segments(full_text, target_size=3000)
    assert len(segments) >= 2
    for seg in segments:
        assert len(seg) > 0
        # Reasonable upper bound per segment
        assert len(seg) <= 4000


def test_clean_segment_with_llm_success():
    """Verify successful cleanup with mock Anthropic client and length within 90-110%."""
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Once upon a time there lived a wise deer in the emerald forest."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    input_segment = "0nce upon a tim there livd a wise deer in the emrald forest."
    result = clean_segment_with_llm(input_segment, client=mock_client)

    assert result == mock_block.text
    # Verify API call params
    mock_client.messages.create.assert_called_once()
    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["system"] == SYSTEM_PROMPT
    assert kwargs["messages"] == [{"role": "user", "content": input_segment}]


def test_clean_segment_with_llm_length_violation_fallback():
    """When output length is outside 90%-110%, it must fall back to original segment."""
    mock_client = MagicMock()
    # Output too short (summarized)
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Short summary."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    input_segment = "A " * 100  # 200 chars
    result = clean_segment_with_llm(input_segment, client=mock_client)

    # Should fall back to input_segment
    assert result == input_segment


def test_clean_segment_with_llm_caching():
    """Verify result is cached by hash of input segment and subsequent calls skip API."""
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Cleaned segment text that matches length."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    input_segment = "Cleand segment txt that matches length."

    # First call - calls API
    res1 = clean_segment_with_llm(input_segment, client=mock_client)
    assert res1 == mock_block.text
    assert mock_client.messages.create.call_count == 1

    # Second call with same segment - should hit cache
    res2 = clean_segment_with_llm(input_segment, client=mock_client)
    assert res2 == mock_block.text
    # API should still only have been called once!
    assert mock_client.messages.create.call_count == 1


def test_clean_segment_with_llm_api_failure_fallback():
    """When Anthropic API throws an exception, gracefully fall back to original segment."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("Anthropic API rate limit / connection timeout")

    input_segment = "Original story text."
    result = clean_segment_with_llm(input_segment, client=mock_client)
    assert result == input_segment


def test_clean_text_with_llm_missing_api_key_fallback(monkeypatch):
    """When ANTHROPIC_API_KEY is not set, clean_text_with_llm falls back gracefully."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    text = "Some uncorrected text without API key."
    result = clean_text_with_llm(text)
    assert result == text


def test_clean_text_with_llm_multiple_segments():
    """Verify clean_text_with_llm splits text into segments and cleans each."""
    mock_client = MagicMock()
    def fake_messages_create(*args, **kwargs):
        content = kwargs["messages"][0]["content"]
        block = MagicMock()
        block.type = "text"
        block.text = content.replace("OCR_ERR", "RESTORED")
        resp = MagicMock()
        resp.content = [block]
        return resp

    mock_client.messages.create.side_effect = fake_messages_create

    seg1 = "Paragraph 1 with OCR_ERR. " + ("word " * 500)
    seg2 = "Paragraph 2 with OCR_ERR. " + ("word " * 500)
    combined = f"{seg1}\n\n{seg2}"

    progress_calls = []
    def on_progress(done, total):
        progress_calls.append((done, total))

    cleaned = clean_text_with_llm(
        combined,
        target_segment_size=2000,
        client=mock_client,
        progress_callback=on_progress,
    )

    assert "RESTORED" in cleaned
    assert "OCR_ERR" not in cleaned
    assert len(progress_calls) >= 2
    assert progress_calls[-1][0] == progress_calls[-1][1]
