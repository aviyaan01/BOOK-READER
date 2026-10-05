"""Test script to synthesize one Bangla sentence and one English sentence using EdgeTTS."""

import sys
import asyncio
from pathlib import Path
import tempfile

# Ensure workspace root is in sys.path
workspace_root = Path(__file__).resolve().parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from backend.app.services.tts.edge_tts_provider import EdgeTTSProvider


async def run_tts_test() -> None:
    """Synthesize one Bangla sentence and one English sentence into /tmp."""
    provider = EdgeTTSProvider()

    # Determine /tmp directory (handles Windows C:\tmp and Unix /tmp cleanly)
    tmp_dir = Path("/tmp")
    try:
        tmp_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        tmp_dir = Path(tempfile.gettempdir())

    bangla_path = tmp_dir / "test_bangla.mp3"
    english_path = tmp_dir / "test_english.mp3"

    bangla_sentence = "একদা এক শান্ত সবুজ বনে একটি ছোট্ট নীল ঘুঘু বাস করত।"
    english_sentence = "The brave little hummingbird flew across the golden valley."

    print("Synthesizing Bangla sentence...")
    await provider.synthesize(bangla_sentence, str(bangla_path))
    print(f"Bangla audio path: {bangla_path.resolve()} ({bangla_path.stat().st_size} bytes)")

    print("Synthesizing English sentence...")
    await provider.synthesize(english_sentence, str(english_path))
    print(f"English audio path: {english_path.resolve()} ({english_path.stat().st_size} bytes)")


def main() -> None:
    """Entry point for the TTS test script."""
    asyncio.run(run_tts_test())


if __name__ == "__main__":
    main()
