"""Configuration settings loaded from environment variables (.env)."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load settings from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Server
HOST: str = os.getenv("HOST", "127.0.0.1")
PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# CORS
CORS_ORIGIN: str = os.getenv("CORS_ORIGIN", "http://localhost:5173")

# Storage & Database
STORAGE_DIR: Path = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_CACHE_DIR: Path = STORAGE_DIR / "audio_cache"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{STORAGE_DIR / 'storyteller.db'}")

# TTS Defaults
DEFAULT_TTS_PROVIDER: str = os.getenv("DEFAULT_TTS_PROVIDER", "edge_tts")
DEFAULT_ENGLISH_VOICE: str = os.getenv("DEFAULT_ENGLISH_VOICE", "en-US-ChristopherNeural")
DEFAULT_BANGLA_VOICE: str = os.getenv("DEFAULT_BANGLA_VOICE", "bn-BD-PradeepNeural")
DEFAULT_ELEVENLABS_VOICE: str = os.getenv("DEFAULT_ELEVENLABS_VOICE", "21m00Tcm4TlvDq8ikWAM")  # Rachel

# ElevenLabs Settings
ELEVENLABS_API_KEY: str | None = os.getenv("ELEVENLABS_API_KEY")

# LLM Text Cleanup (Anthropic Claude)
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")


def get_book_storage_dir(book_id: str) -> Path:
    """Return the dedicated storage path for a book, creating the folder if needed."""
    book_dir = STORAGE_DIR / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    return book_dir
