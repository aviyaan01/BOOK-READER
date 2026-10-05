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
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{STORAGE_DIR / 'storyteller.db'}")

# TTS Defaults
DEFAULT_TTS_PROVIDER: str = os.getenv("DEFAULT_TTS_PROVIDER", "edge_tts")
DEFAULT_ENGLISH_VOICE: str = os.getenv("DEFAULT_ENGLISH_VOICE", "en-US-ChristopherNeural")
DEFAULT_BANGLA_VOICE: str = os.getenv("DEFAULT_BANGLA_VOICE", "bn-BD-PradeepNeural")


def get_book_storage_dir(book_id: str) -> Path:
    """Return the dedicated storage path for a book, creating the folder if needed."""
    book_dir = STORAGE_DIR / book_id
    book_dir.mkdir(parents=True, exist_ok=True)
    return book_dir
