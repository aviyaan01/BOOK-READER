"""Unit tests for tts/multivoice.py — segment synthesis and concatenation."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.tts.multivoice import (
    _raw_concat,
    concatenate_mp3_segments,
    synthesize_multivoice_chunk,
    synthesize_segments,
)


# ─────────────────────────────────────────────────────────────────────────────
# synthesize_segments tests
# ─────────────────────────────────────────────────────────────────────────────

def test_synthesize_segments_creates_files(tmp_path: Path):
    """All segments should be synthesized to numbered temp files."""

    async def run():
        # Fake provider writes dummy bytes to out_path
        async def fake_synthesize(text, out_path, voice=None, rate="+0%"):
            Path(out_path).write_bytes(b"FAKE-MP3-" + text.encode())

        mock_provider = MagicMock()
        mock_provider.synthesize = fake_synthesize

        segments = [("Hello world.", "voice-A"), ("Goodbye!", "voice-B")]
        files = await synthesize_segments(segments, mock_provider, tmp_path)

        assert len(files) == 2
        for f in files:
            assert f.exists()
            assert f.stat().st_size > 0

    asyncio.run(run())


def test_synthesize_segments_skips_failed(tmp_path: Path):
    """Segments that fail synthesis are excluded from the result list."""

    async def run():
        call_n = [0]

        async def sometimes_fail(text, out_path, voice=None, rate="+0%"):
            call_n[0] += 1
            if call_n[0] == 2:
                raise RuntimeError("network failure")
            Path(out_path).write_bytes(b"OK")

        mock_provider = MagicMock()
        mock_provider.synthesize = sometimes_fail

        segments = [("s1", "v1"), ("s2", "v2"), ("s3", "v3")]
        files = await synthesize_segments(segments, mock_provider, tmp_path)

        # Segment 2 failed, so only 2 files returned
        assert len(files) == 2

    asyncio.run(run())


# ─────────────────────────────────────────────────────────────────────────────
# _raw_concat tests
# ─────────────────────────────────────────────────────────────────────────────

def test_raw_concat_creates_combined_file(tmp_path: Path):
    seg1 = tmp_path / "seg1.mp3"
    seg2 = tmp_path / "seg2.mp3"
    seg1.write_bytes(b"PART-ONE-")
    seg2.write_bytes(b"PART-TWO-")

    out = tmp_path / "combined.mp3"
    _raw_concat([seg1, seg2], str(out))

    assert out.exists()
    content = out.read_bytes()
    assert content == b"PART-ONE-PART-TWO-"


def test_raw_concat_skips_missing_file(tmp_path: Path, caplog):
    """Missing segment files are skipped (not raised)."""
    good = tmp_path / "good.mp3"
    good.write_bytes(b"GOOD")
    missing = tmp_path / "missing.mp3"  # does not exist

    out = tmp_path / "out.mp3"
    _raw_concat([good, missing], str(out))
    assert out.exists()
    assert out.read_bytes() == b"GOOD"


# ─────────────────────────────────────────────────────────────────────────────
# concatenate_mp3_segments tests
# ─────────────────────────────────────────────────────────────────────────────

def test_concatenate_falls_back_to_raw_when_pydub_missing(tmp_path: Path):
    """When pydub is not importable, falls back to raw binary concat."""
    seg1 = tmp_path / "s1.mp3"
    seg2 = tmp_path / "s2.mp3"
    seg1.write_bytes(b"A")
    seg2.write_bytes(b"B")
    out = tmp_path / "out.mp3"

    with patch.dict("sys.modules", {"pydub": None}):
        concatenate_mp3_segments([seg1, seg2], str(out))

    assert out.exists()
    assert out.read_bytes() == b"AB"


def test_concatenate_no_segments_raises(tmp_path: Path):
    out = tmp_path / "out.mp3"
    with pytest.raises(ValueError, match="No segment files"):
        concatenate_mp3_segments([], str(out))


# ─────────────────────────────────────────────────────────────────────────────
# synthesize_multivoice_chunk end-to-end
# ─────────────────────────────────────────────────────────────────────────────

def test_synthesize_multivoice_chunk_produces_output(tmp_path: Path):
    """End-to-end: synthesize 2 segments and concatenate to out_path."""

    async def run():
        async def fake_synthesize(text, out_path, voice=None, rate="+0%"):
            Path(out_path).write_bytes(b"AUDIO:" + text.encode()[:10])

        mock_provider = MagicMock()
        mock_provider.synthesize = fake_synthesize

        segments = [("Once upon a time.", "v-narrator"), ("I am the hero!", "v-fox")]
        out = tmp_path / "chunk_001.mp3"

        with patch.dict("sys.modules", {"pydub": None}):  # Force raw concat
            await synthesize_multivoice_chunk(segments, mock_provider, str(out))

        assert out.exists()
        assert out.stat().st_size > 0

    asyncio.run(run())


def test_synthesize_multivoice_chunk_empty_segments_raises(tmp_path: Path):
    async def run():
        mock_provider = MagicMock()
        out = tmp_path / "out.mp3"
        with pytest.raises(ValueError, match="empty segment list"):
            await synthesize_multivoice_chunk([], mock_provider, str(out))

    asyncio.run(run())


def test_synthesize_multivoice_chunk_all_fail_raises(tmp_path: Path):
    """If every segment fails synthesis, a ValueError is raised."""

    async def run():
        async def always_fail(text, out_path, voice=None, rate="+0%"):
            raise RuntimeError("always fails")

        mock_provider = MagicMock()
        mock_provider.synthesize = always_fail

        segments = [("text", "voice")]
        out = tmp_path / "out.mp3"

        with pytest.raises(ValueError, match="All segments failed"):
            with patch.dict("sys.modules", {"pydub": None}):
                await synthesize_multivoice_chunk(segments, mock_provider, str(out))

    asyncio.run(run())
