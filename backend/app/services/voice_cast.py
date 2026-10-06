"""Voice cast service: uses Claude API to tag sentences with speaker roles.

For each chunk of story text, this module:
1. Sends the text to Claude with a structured prompt.
2. Receives JSON: [{sentence, speaker}] where speaker is "narrator" or a character name.
3. Builds a stable cast mapping {speaker -> voice} using available voices from the provider.
4. Returns a list of (sentence_text, voice) tuples ready for per-segment synthesis.

The voice cast assignment is deterministic: the same characters always get the same
voices within a book's processing session (cast dict is maintained externally).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import anthropic

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Cast-assignment helpers
# ─────────────────────────────────────────────────────────────────────────────

# Built-in pool of Edge TTS voices for multi-voice narration (one per role slot)
DEFAULT_VOICE_POOL_EN: List[str] = [
    "en-US-AriaNeural",        # narrator (female, calm)
    "en-US-ChristopherNeural", # character 1 (male, deep)
    "en-US-JennyNeural",       # character 2 (female, warm)
    "en-US-GuyNeural",         # character 3 (male, energetic)
    "en-US-AnaNeural",         # character 4 (child female)
    "en-US-DavisNeural",       # character 5 (male, authoritative)
    "en-US-JaneNeural",        # character 6 (female, expressive)
    "en-US-JasonNeural",       # character 7 (male, casual)
]

DEFAULT_VOICE_POOL_BN: List[str] = [
    "bn-BD-NabanitaNeural",  # narrator (female)
    "bn-BD-PradeepNeural",   # character 1 (male)
    "bn-IN-TanishaaNeural",  # character 2 (female)
    "bn-IN-BashkarNeural",   # character 3 (male)
]


def get_voice_pool(language: str, custom_voices: Optional[List[str]] = None) -> List[str]:
    """Return ordered voice pool for the given language."""
    if custom_voices:
        return custom_voices
    if language and language.lower().startswith("bn"):
        return DEFAULT_VOICE_POOL_BN
    return DEFAULT_VOICE_POOL_EN


def assign_voice_to_speaker(
    speaker: str,
    cast: Dict[str, str],
    voice_pool: List[str],
    narrator_voice: Optional[str] = None,
) -> str:
    """Return the voice assigned to `speaker`, creating one if not yet in cast.

    Args:
        speaker: Normalised speaker key (lower-stripped).
        cast: Mutable dict {speaker -> voice} shared across the whole book.
        voice_pool: Ordered list of available voices.
        narrator_voice: Explicit narrator voice override.

    Returns:
        Voice string for the given speaker.
    """
    if speaker in cast:
        return cast[speaker]

    # Narrator always gets first slot (or explicit override)
    if speaker in ("narrator", "narrador", "বর্ণনাকারী"):
        voice = narrator_voice or voice_pool[0]
        cast[speaker] = voice
        return voice

    # Assign next unused pool slot (skip index 0, reserved for narrator)
    used_voices = set(cast.values())
    for v in voice_pool[1:]:
        if v not in used_voices:
            cast[speaker] = v
            return v

    # If pool exhausted, cycle through character slots deterministically
    char_voices = voice_pool[1:] or voice_pool
    idx = (len(cast) - 1) % len(char_voices)
    cast[speaker] = char_voices[idx]
    return cast[speaker]


# ─────────────────────────────────────────────────────────────────────────────
# Claude tagging
# ─────────────────────────────────────────────────────────────────────────────

TAGGING_SYSTEM_PROMPT = """\
You are an audiobook narrator assistant that labels each sentence of a story with
its speaker for multi-voice narration.

Rules:
1. Return ONLY valid JSON — an array of objects with exactly two keys:
   "sentence" (the original sentence text, unchanged) and
   "speaker"  (one of: "narrator", or a CHARACTER NAME in Title Case).
2. Dialogue inside quotation marks belongs to the character speaking it.
   Assign the character name if known, or "Unknown Character" if unnamed.
3. Descriptive/action sentences that are NOT dialogue → "narrator".
4. DO NOT paraphrase, summarize, split, or merge sentences.
5. Preserve the original language of the text.
6. Keep character names consistent throughout.
7. Output must be a JSON array — nothing else before or after it.

Example output format:
[
  {"sentence": "Once upon a time, there was a clever fox.", "speaker": "narrator"},
  {"sentence": "I will outsmart the wolf!", "speaker": "Fox"},
  {"sentence": "The wolf growled angrily.", "speaker": "narrator"}
]
"""


def _extract_json_array(raw: str) -> Optional[List[Dict[str, str]]]:
    """Best-effort extractor: parse JSON even if Claude wraps it in markdown."""
    raw = raw.strip()
    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Try to pull the first JSON array out of freeform text
    match = re.search(r"\[[\s\S]*?\]", raw)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return None


def tag_sentences_with_claude(
    text: str,
    client: Optional[anthropic.Anthropic] = None,
    model: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Call Claude API to annotate each sentence with a speaker label.

    Args:
        text: Story chunk text containing multiple sentences.
        client: Optional pre-built Anthropic client.
        model: Optional Claude model override.

    Returns:
        List of dicts [{sentence: str, speaker: str}].
        Falls back to [{sentence: whole_text, speaker: "narrator"}] on any error.
    """
    if not text or not text.strip():
        return []

    # Resolve Anthropic client
    if client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                "ANTHROPIC_API_KEY not set; voice casting unavailable. "
                "Falling back to narrator-only for this chunk."
            )
            return [{"sentence": text.strip(), "speaker": "narrator"}]
        client = anthropic.Anthropic(api_key=api_key)

    chosen_model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    try:
        response = client.messages.create(
            model=chosen_model,
            max_tokens=4096,
            system=TAGGING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text.strip()}],
        )

        raw = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw += block.text

        parsed = _extract_json_array(raw)
        if parsed is not None and len(parsed) > 0:
            # Normalize speaker keys
            cleaned = []
            for item in parsed:
                speaker = str(item.get("speaker", "narrator")).strip()
                sentence = str(item.get("sentence", "")).strip()
                if sentence:
                    cleaned.append({"sentence": sentence, "speaker": speaker})
            if cleaned:
                return cleaned

        logger.warning("Claude returned unparseable voice-cast output; using narrator fallback.")
        return [{"sentence": text.strip(), "speaker": "narrator"}]

    except Exception as exc:
        logger.error("Claude voice-cast API error: %s. Falling back to narrator only.", exc)
        return [{"sentence": text.strip(), "speaker": "narrator"}]


# ─────────────────────────────────────────────────────────────────────────────
# Chunk-level processing
# ─────────────────────────────────────────────────────────────────────────────

def build_voice_segments(
    text: str,
    cast: Dict[str, str],
    voice_pool: List[str],
    narrator_voice: Optional[str] = None,
    client: Optional[anthropic.Anthropic] = None,
    model: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Tag chunk text with Claude and resolve voice per sentence.

    Args:
        text: Story chunk text.
        cast: Mutable cast dict shared across chunks for consistent assignment.
        voice_pool: Ordered list of available voices.
        narrator_voice: Explicit narrator voice override.
        client: Optional Anthropic client.
        model: Optional model override.

    Returns:
        List of (sentence_text, voice_name) tuples.
    """
    tagged = tag_sentences_with_claude(text, client=client, model=model)
    segments: List[Tuple[str, str]] = []

    for item in tagged:
        sentence = item.get("sentence", "").strip()
        speaker = item.get("speaker", "narrator").strip().lower()
        if not sentence:
            continue
        voice = assign_voice_to_speaker(
            speaker=speaker,
            cast=cast,
            voice_pool=voice_pool,
            narrator_voice=narrator_voice,
        )
        segments.append((sentence, voice))

    return segments

