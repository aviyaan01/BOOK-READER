"""Multi-voice synthesis: tag sentences with voice cast, synthesize each segment,
and concatenate the resulting audio segments into a single MP3 file.

Dependencies:
    - pydub (audio concatenation) — installed via pip install pydub
    - pydub requires ffmpeg or libav on PATH for MP3 encode/decode.
    - Falls back to sequential single-voice if pydub is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.app.services.tts.base import TTSProvider

logger = logging.getLogger(__name__)


async def synthesize_segments(
    segments: List[Tuple[str, str]],
    tts_provider: TTSProvider,
    tmp_dir: Path,
) -> List[Path]:
    """Synthesize each (text, voice) segment to a numbered temp MP3 file.

    Args:
        segments: List of (sentence_text, voice) tuples.
        tts_provider: TTS provider instance to use.
        tmp_dir: Temporary directory to store per-segment MP3 files.

    Returns:
        Ordered list of Path objects for each synthesized segment file.
        Segments that fail are skipped (logged, not raised).
    """
    segment_files: List[Optional[Path]] = [None] * len(segments)
    semaphore = asyncio.Semaphore(3)  # Respect provider rate limits

    async def _synth_one(idx: int, text: str, voice: str) -> None:
        seg_file = tmp_dir / f"seg_{idx:04d}.mp3"
        async with semaphore:
            try:
                await tts_provider.synthesize(
                    text=text,
                    out_path=str(seg_file),
                    voice=voice,
                )
                if seg_file.exists() and seg_file.stat().st_size > 0:
                    segment_files[idx] = seg_file
                else:
                    logger.warning("Segment %d produced empty audio; skipping.", idx)
            except Exception as exc:
                logger.warning("Segment %d synthesis failed: %s; skipping.", idx, exc)

    tasks = [
        _synth_one(i, text, voice)
        for i, (text, voice) in enumerate(segments)
    ]
    await asyncio.gather(*tasks)

    # Filter out None entries (failed segments)
    return [f for f in segment_files if f is not None]


def concatenate_mp3_segments(segment_files: List[Path], out_path: str) -> None:
    """Concatenate MP3 segment files into a single output MP3.

    Uses pydub if available (requires ffmpeg); falls back to raw binary
    concatenation (works for CBR MP3s without chapter tags).

    Args:
        segment_files: Ordered list of MP3 file paths.
        out_path: Destination path for the combined MP3 output.
    """
    if not segment_files:
        raise ValueError("No segment files to concatenate.")

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        from pydub import AudioSegment  # type: ignore

        combined = AudioSegment.empty()
        for seg_path in segment_files:
            try:
                combined += AudioSegment.from_mp3(str(seg_path))
            except Exception as exc:
                logger.warning("pydub: failed to load %s: %s; skipping segment.", seg_path, exc)

        if len(combined) == 0:
            raise ValueError("Combined audio has zero duration.")

        combined.export(str(out_path), format="mp3", bitrate="128k")
        logger.debug("pydub: concatenated %d segments → %s", len(segment_files), out_path)

    except ImportError:
        logger.warning(
            "pydub not installed — falling back to raw binary MP3 concatenation. "
            "Install pydub + ffmpeg for gapless multi-voice output."
        )
        _raw_concat(segment_files, out_path)


def _raw_concat(segment_files: List[Path], out_path: str) -> None:
    """Naive binary concatenation of MP3 files (works for CBR, may have minor artefacts)."""
    out_file = Path(out_path)
    with open(out_file, "wb") as fout:
        for seg_path in segment_files:
            try:
                fout.write(seg_path.read_bytes())
            except Exception as exc:
                logger.warning("Raw concat: failed reading %s: %s; skipping.", seg_path, exc)


async def synthesize_multivoice_chunk(
    segments: List[Tuple[str, str]],
    tts_provider: TTSProvider,
    out_path: str,
) -> None:
    """End-to-end multi-voice synthesis for one story chunk.

    1. Synthesizes each (text, voice) segment to a temp MP3.
    2. Concatenates the results into `out_path`.
    3. Cleans up temp files.

    Args:
        segments: Ordered list of (text, voice) pairs produced by voice_cast.
        tts_provider: TTS provider instance.
        out_path: Final combined MP3 output path.

    Raises:
        ValueError: If no valid segments were synthesized.
    """
    if not segments:
        raise ValueError("Cannot synthesize: empty segment list.")

    with tempfile.TemporaryDirectory(prefix="multivoice_") as tmp_str:
        tmp_dir = Path(tmp_str)
        segment_files = await synthesize_segments(segments, tts_provider, tmp_dir)

        if not segment_files:
            raise ValueError("All segments failed synthesis; cannot produce output audio.")

        concatenate_mp3_segments(segment_files, out_path)
