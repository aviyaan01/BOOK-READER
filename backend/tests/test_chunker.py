"""Unit tests for sentence chunking and text packing service."""

import pytest
from backend.app.services.chunker import (
    chunk_text,
    split_sentences,
    split_long_sentence,
)


def test_basic_sentence_splitting():
    """Verify sentence splitting on '.', '!', '?', and Bangla danda '।'."""
    text = (
        "Once upon a time. The knight arrived! Where was the dragon? "
        "এক শান্ত সবুজ বন ছিল। পাখিটি গান গাইল!"
    )
    sentences = split_sentences(text)
    assert len(sentences) == 5
    assert sentences[0] == "Once upon a time."
    assert sentences[1] == "The knight arrived!"
    assert sentences[2] == "Where was the dragon?"
    assert sentences[3] == "এক শান্ত সবুজ বন ছিল।"
    assert sentences[4] == "পাখিটি গান গাইল!"


def test_abbreviations_and_decimals_not_split():
    """Verify abbreviations like 'Mr.' or 'Dr.' and decimals like '3.5' or '৪.৫' are not split."""
    text = (
        "Mr. Smith bought 3.5 kg of apples for $10.99. "
        "Dr. Watson visited at 4.00 PM. "
        "বইটির দাম ছিল ৪.৫ টাকা এবং ওজন ছিল ২.২৫ কেজি।"
    )
    sentences = split_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "Mr. Smith bought 3.5 kg of apples for $10.99."
    assert sentences[1] == "Dr. Watson visited at 4.00 PM."
    assert sentences[2] == "বইটির দাম ছিল ৪.৫ টাকা এবং ওজন ছিল ২.২৫ কেজি।"


def test_bangla_paragraph_chunking():
    """Verify chunking a full Bangla paragraph with multiple sentences ending in danda '।'."""
    bangla_text = (
        "এক শান্ত সবুজ বনে একটি ছোট্ট নীল ঘুঘু বাস করত। "
        "প্রতিদিন ভোরে ঘুঘুটি মিষ্টি সুরে গান গেয়ে সবাইকে জাগাত। "
        "একদিন সে শুনল বনের ওপারে এক সোনালী নদী বয়ে চলেছে! "
        "নদীটির রূপ দেখতে সে কি সেখানে যাবে? "
        "হ্যাঁ, সে আনন্দভরে ডানা মেলল।"
    )
    chunks = chunk_text(bangla_text, max_chars=120)

    # Chunks must be non-empty and respect max_chars
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 120
        assert len(chunk.strip()) > 0
    # Complete text content should be preserved
    joined = " ".join(chunks)
    assert "এক শান্ত সবুজ বনে" in joined
    assert "মিষ্টি সুরে গান" in joined
    assert "ডানা মেলল।" in joined


def test_very_long_sentence_split_at_commas():
    """Verify that a single sentence longer than max_chars splits cleanly at comma boundaries."""
    long_sentence = (
        "In a forgotten realm nestled between high jagged peaks, "
        "where icy winds howled through ancient caverns, "
        "a brave explorer searched for the mythical starlight gem, "
        "which was said to bring eternal spring to the frozen valley."
    )
    max_limit = 100
    chunks = chunk_text(long_sentence, max_chars=max_limit)

    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk) <= max_limit
        assert len(chunk.strip()) > 0

    # Ensure split happened at comma boundaries
    assert any(c.endswith(",") for c in chunks[:-1])
    # Total words preserved
    for word in ["forgotten", "realm", "winds", "howled", "starlight", "gem", "valley."]:
        assert word in " ".join(chunks)


def test_bangla_very_long_sentence_with_commas():
    """Verify a very long Bangla sentence with commas splits at comma boundaries."""
    bangla_long = (
        "এক গভীর অরণ্যের ভেতর দিয়ে, যেখানে সূর্যের আলো কদাচিৎ পৌঁছাত, "
        "নদীর শীতল জলধারা পাথর ছুঁয়ে বয়ে যেত, "
        "আর বনের পশু-পাখিরা তৃষ্ণা মেটাতে সেখানে জড়ো হতো।"
    )
    max_limit = 65
    chunks = chunk_text(bangla_long, max_chars=max_limit)

    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= max_limit
    assert "এক গভীর অরণ্যের ভেতর দিয়ে," in chunks[0]


def test_paragraph_boundary_preference():
    """Verify chunker prefers starting a new chunk at a paragraph boundary when next paragraph doesn't fit."""
    para1 = "This is the first sentence of paragraph one. Here is the second sentence of paragraph one."
    para2 = "This is paragraph two. It has enough text that it cannot fit in the remaining space of chunk one."

    # Total length: len(para1) ~ 90, len(para2) ~ 97
    # If max_chars is 120: para1 fits in chunk 1 (90 <= 120).
    # para2 does not fit in remaining 30 chars of chunk 1.
    # Instead of splitting para2, chunker should start chunk 2 at the paragraph boundary.
    text = f"{para1}\n\n{para2}"
    chunks = chunk_text(text, max_chars=120)

    assert len(chunks) == 2
    assert chunks[0] == para1
    assert chunks[1] == para2


def test_pack_whole_sentences_up_to_max_chars():
    """Verify small sentences are packed together until max_chars is reached."""
    text = "Short one. Short two. Short three. Short four."
    chunks = chunk_text(text, max_chars=50)

    # Each "Short X." is 10 chars. With spaces:
    # "Short one. Short two. Short three." is 33 chars <= 50.
    # "Short one. Short two. Short three. Short four." is 45 chars <= 50.
    assert len(chunks) == 1
    assert chunks[0] == "Short one. Short two. Short three. Short four."


def test_empty_and_whitespace_input():
    """Verify empty or whitespace-only inputs return an empty list."""
    assert chunk_text("") == []
    assert chunk_text("   \n\n   \t  ") == []
