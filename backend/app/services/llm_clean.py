"""Optional LLM text cleanup service using Anthropic Claude API."""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a text restorer for audiobook narration. "
    "Fix OCR errors, broken words, and stray characters. "
    "NEVER add, remove, summarize, or rephrase story content. "
    "Keep the original language. Return only the corrected text."
)

_CACHE_MAP: Dict[str, str] = {}


def _get_cache_file_path() -> Path:
    """Return persistent JSON cache file path in backend/storage/.cache."""
    try:
        from backend.app.config import STORAGE_DIR
        cache_dir = STORAGE_DIR / ".cache"
    except Exception:
        cache_dir = Path("backend/storage/.cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "llm_clean_cache.json"


def _load_cache_from_disk() -> Dict[str, str]:
    """Load cached segment hashes from disk if present."""
    global _CACHE_MAP
    cache_path = _get_cache_file_path()
    if cache_path.exists():
        try:
            content = cache_path.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                _CACHE_MAP.update(data)
        except Exception as exc:
            logger.warning("Failed loading LLM clean cache: %s", exc)
    return _CACHE_MAP


def _save_cache_to_disk() -> None:
    """Persist in-memory cache map to disk."""
    cache_path = _get_cache_file_path()
    try:
        cache_path.write_text(
            json.dumps(_CACHE_MAP, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Failed saving LLM clean cache to disk: %s", exc)


def compute_segment_hash(segment: str) -> str:
    """Generate SHA-256 hash for a given text segment."""
    return hashlib.sha256(segment.encode("utf-8")).hexdigest()


def get_cached_segment(seg_hash: str) -> Optional[str]:
    """Retrieve cleaned segment from memory or disk cache."""
    if not _CACHE_MAP:
        _load_cache_from_disk()
    return _CACHE_MAP.get(seg_hash)


def set_cached_segment(seg_hash: str, cleaned_text: str) -> None:
    """Store cleaned segment into cache and persist."""
    _CACHE_MAP[seg_hash] = cleaned_text
    _save_cache_to_disk()


def clear_cache() -> None:
    """Clear in-memory and disk cache (primarily for tests)."""
    global _CACHE_MAP
    _CACHE_MAP.clear()
    cache_path = _get_cache_file_path()
    if cache_path.exists():
        try:
            cache_path.unlink()
        except Exception:
            pass


def is_valid_output_length(input_text: str, output_text: str) -> bool:
    """Verify that output length is within 90%-110% of input length."""
    in_len = len(input_text)
    out_len = len(output_text)
    if in_len == 0 and out_len == 0:
        return True
    if not output_text or not output_text.strip():
        return False
    if in_len == 0:
        return False
    return (0.9 * in_len) <= out_len <= (1.1 * in_len)


def split_into_segments(text: str, target_size: int = 3000) -> List[str]:
    """Split text into coherent segments of approximately target_size characters."""
    if not text:
        return []
    if len(text) <= target_size:
        return [text]

    paragraphs = text.split("\n\n")
    segments: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for para in paragraphs:
        p_len = len(para)
        # Check if adding paragraph exceeds target_size
        if current_chunk and (current_len + p_len + 2 > target_size):
            segments.append("\n\n".join(current_chunk))
            current_chunk = []
            current_len = 0

        # If a single paragraph is larger than target_size, break by lines
        if p_len > target_size:
            if current_chunk:
                segments.append("\n\n".join(current_chunk))
                current_chunk = []
                current_len = 0

            lines = para.split("\n")
            line_chunk: List[str] = []
            line_chunk_len = 0
            for line in lines:
                if line_chunk and (line_chunk_len + len(line) + 1 > target_size):
                    segments.append("\n".join(line_chunk))
                    line_chunk = []
                    line_chunk_len = 0

                if len(line) > target_size:
                    for i in range(0, len(line), target_size):
                        segments.append(line[i : i + target_size])
                else:
                    line_chunk.append(line)
                    line_chunk_len += len(line) + 1

            if line_chunk:
                segments.append("\n".join(line_chunk))
        else:
            current_chunk.append(para)
            current_len += p_len + 2

    if current_chunk:
        segments.append("\n\n".join(current_chunk))

    return segments


def clean_segment_with_llm(
    segment: str,
    client: Optional[anthropic.Anthropic] = None,
    model: Optional[str] = None,
) -> str:
    """Clean an individual text segment using Anthropic Claude with length validation and caching."""
    if not segment or not segment.strip():
        return segment

    # 1. Check cache by hash
    seg_hash = compute_segment_hash(segment)
    cached = get_cached_segment(seg_hash)
    if cached is not None:
        logger.debug("Found cached LLM restoration for segment hash %s", seg_hash[:8])
        return cached

    # 2. Resolve client and API key
    if client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "ANTHROPIC_API_KEY not found in environment. Skipping LLM cleanup."
            )
            return segment
        client = anthropic.Anthropic(api_key=api_key)

    chosen_model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # 3. Request restoration from Anthropic Messages API
    try:
        response = client.messages.create(
            model=chosen_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": segment}],
        )

        cleaned_content = ""
        for block in response.content:
            if getattr(block, "type", None) == "text" or hasattr(block, "text"):
                cleaned_content += block.text

        cleaned_text = cleaned_content.strip()

        # 4. Verify length within 90%-110% of input
        if is_valid_output_length(segment, cleaned_text):
            set_cached_segment(seg_hash, cleaned_text)
            return cleaned_text
        else:
            logger.warning(
                "LLM restoration output length (%d) outside 90%%-110%% of input (%d). "
                "Falling back to original segment.",
                len(cleaned_text),
                len(segment),
            )
            return segment

    except Exception as exc:
        logger.error(
            "Anthropic API error during LLM cleanup: %s. Falling back to original segment.",
            exc,
        )
        return segment


def clean_text_with_llm(
    text: str,
    target_segment_size: int = 3000,
    client: Optional[anthropic.Anthropic] = None,
    model: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Send text in segments of ~3000 chars to Anthropic Claude for OCR restoration.

    Args:
        text: Input story text to be cleaned.
        target_segment_size: Segment size target (default ~3000 chars).
        client: Optional pre-configured Anthropic client instance.
        model: Optional Claude model override.
        progress_callback: Optional progress reporter (completed_segments, total_segments).

    Returns:
        Restored text with OCR and formatting errors corrected.
    """
    if not text or not text.strip():
        return text

    segments = split_into_segments(text, target_size=target_segment_size)
    if not segments:
        return text

    cleaned_segments: List[str] = []
    total = len(segments)

    for idx, seg in enumerate(segments, start=1):
        cleaned_seg = clean_segment_with_llm(seg, client=client, model=model)
        cleaned_segments.append(cleaned_seg)
        if progress_callback:
            try:
                progress_callback(idx, total)
            except Exception:
                pass

    return "\n\n".join(cleaned_segments)
