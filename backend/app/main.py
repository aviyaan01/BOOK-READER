"""Main entry point for the PDF Storyteller FastAPI application."""

import os
import re
import shutil
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any, AsyncGenerator

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    Query,
)
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.app.config import (
    CORS_ORIGIN,
    STORAGE_DIR,
    get_book_storage_dir,
    create_book_storage_dir,
    DEFAULT_ENGLISH_VOICE,
    DEFAULT_BANGLA_VOICE,
    DEFAULT_ELEVENLABS_VOICE,
    DEFAULT_TTS_PROVIDER,
    ELEVENLABS_API_KEY,
)
from backend.app.db import init_db, get_db
from backend.app.models import Book, Chunk
from backend.app.services.pdf_extract import SCANNED_PDF_WARNING
from backend.app.services.pipeline import process_book, retry_failed_chunks
from backend.app.services.tts import get_tts_provider
from backend.app.services.tts.edge_tts_provider import list_voices

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB
CHUNK_FILENAME_REGEX = re.compile(r"^chunk_\d{3,5}\.mp3$")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Execute startup and shutdown events, initializing database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="PDF Storyteller API",
    description="Backend API for narrating PDF storybooks in natural, expressive voices.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS specifically for the frontend application
allowed_origins = [
    CORS_ORIGIN,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Health check endpoint verifying server status and database connectivity."""
    return {"status": "ok"}


@app.post("/api/books", status_code=status.HTTP_201_CREATED)
@app.post("/api/books/upload", status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form(...),
    title: Optional[str] = Form(None),
    voice: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    improve_with_ai: bool = Form(False),
    multi_voice: bool = Form(False),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Upload a storybook PDF (max 30MB), save as original.pdf, and launch background processing.

    Args:
        background_tasks: FastAPI background tasks queue.
        file: Multipart uploaded PDF file (max 30MB).
        language: Language code, must be 'bn' (Bangla) or 'en' (English).
        title: Optional custom book title (truncated to 250 characters).
        voice: Optional voice ID or name to use for speech narration.
        provider: Optional TTS provider ('elevenlabs' or 'edge_tts').
        improve_with_ai: Optional flag to run AI text cleanup using Anthropic Claude.
        multi_voice: Optional flag to enable per-character voice casting using Claude.
        db: SQLAlchemy transactional database session.

    Returns:
        JSON response containing the created book ID and initial status.
    """
    # 1. Strip path components from filename and check .pdf extension
    raw_filename = file.filename or "uploaded.pdf"
    clean_filename = Path(raw_filename.replace("\\", "/")).name.strip()
    if not clean_filename:
        clean_filename = "uploaded.pdf"

    if not clean_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF documents (.pdf) are accepted.",
        )

    # 2. Read first 5 bytes and check magic number b"%PDF-", then seek back to 0
    header = await file.read(5)
    await file.seek(0)
    if len(header) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF file is empty (0 bytes).",
        )
    if header != b"%PDF-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file format. File must start with '%PDF-'.",
        )

    # 3. Truncate original_filename and title to 250 characters
    original_filename = clean_filename[:250]
    if title and title.strip():
        book_title = title.strip()
    else:
        book_title = Path(clean_filename).stem.replace("_", " ").strip().title() or "Untitled Story"
    book_title = book_title[:250]

    # 4. Validate language ("bn"/"en")
    lang_clean = (language or "").strip().lower()
    if lang_clean not in ("bn", "en"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid language. Supported values are 'bn' (Bangla) or 'en' (English).",
        )

    # 5. Whitelist provider values ("edge_tts", "elevenlabs")
    if provider is None or not provider.strip():
        chosen_provider = DEFAULT_TTS_PROVIDER or "edge_tts"
    else:
        prov_clean = provider.strip().lower()
        if prov_clean in ("edge_tts", "edgetts"):
            chosen_provider = "edge_tts"
        elif prov_clean in ("elevenlabs", "eleven_labs", "eleven-labs"):
            chosen_provider = "elevenlabs"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider '{provider}'. Supported providers are 'edge_tts' and 'elevenlabs'.",
            )

    # 6. Check ELEVENLABS_API_KEY when provider is "elevenlabs"
    if chosen_provider == "elevenlabs":
        api_key = os.getenv("ELEVENLABS_API_KEY") or ELEVENLABS_API_KEY
        if not api_key or not api_key.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ElevenLabs provider is selected, but ELEVENLABS_API_KEY is empty. Please configure ELEVENLABS_API_KEY in your .env.",
            )

    # 7. Validate voice against the provider's voice list
    p_instance = get_tts_provider(chosen_provider)
    if voice and voice.strip():
        voice_clean = voice.strip()
        available_voices = await p_instance.list_voices(language=lang_clean)
        valid_identifiers = set()
        for v in available_voices:
            for k in ("ShortName", "name", "Name", "voice_id"):
                val = v.get(k)
                if val:
                    valid_identifiers.add(str(val).strip().lower())
                    valid_identifiers.add(str(val).strip())
        if chosen_provider == "elevenlabs":
            from backend.app.services.tts.elevenlabs_provider import VOICE_NAME_TO_ID
            for k in VOICE_NAME_TO_ID:
                valid_identifiers.add(k.lower())

        if voice_clean.lower() not in valid_identifiers and voice_clean not in valid_identifiers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid voice '{voice}' for provider '{chosen_provider}' and language '{lang_clean}'.",
            )
        if chosen_provider == "elevenlabs":
            chosen_voice = p_instance.resolve_voice(voice_clean)
        else:
            chosen_voice = voice_clean
    else:
        if chosen_provider == "elevenlabs":
            chosen_voice = DEFAULT_ELEVENLABS_VOICE
        else:
            chosen_voice = DEFAULT_BANGLA_VOICE if lang_clean == "bn" else DEFAULT_ENGLISH_VOICE

    # 8. Create Book record
    book = Book(
        title=book_title,
        language=lang_clean,
        original_filename=original_filename,
        status="uploaded",
        voice=chosen_voice,
        provider=chosen_provider,
        improve_with_ai=bool(improve_with_ai),
        multi_voice=bool(multi_voice),
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    # 9. Stream and save PDF to storage/<book_id>/original.pdf, enforcing 30MB while streaming
    book_dir = create_book_storage_dir(book.id)
    target_path = book_dir / "original.pdf"
    total_bytes = 0

    try:
        with open(target_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # Read in 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File exceeds maximum allowed size of 30MB.",
                    )
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded PDF file is empty (0 bytes).",
            )
    except HTTPException:
        if target_path.exists():
            target_path.unlink()
        db.delete(book)
        db.commit()
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)
        raise
    except Exception as exc:
        if target_path.exists():
            target_path.unlink()
        db.delete(book)
        db.commit()
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(exc)}",
        )

    # 10. Launch asynchronous background processing
    background_tasks.add_task(process_book, book.id)

    return {"id": book.id, "status": book.status}


LARGE_BOOK_CHAR_THRESHOLD = 10000


def get_cost_warning(total_characters: int) -> Optional[str]:
    """Return a warning string if document character count exceeds large threshold."""
    if total_characters >= LARGE_BOOK_CHAR_THRESHOLD:
        return (
            f"Large storybook ({total_characters:,} characters). Extended synthesis time "
            "and higher processing/API usage expected."
        )
    return None


@app.get("/api/books")
def list_books(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Retrieve all uploaded books ordered by creation timestamp."""
    books = db.query(Book).order_by(Book.created_at.desc()).all()
    return [
        {
            "id": b.id,
            "title": b.title,
            "language": b.language,
            "original_filename": b.original_filename,
            "status": b.status,
            "is_scanned": bool(getattr(b, "is_scanned", False)),
            "improve_with_ai": bool(getattr(b, "improve_with_ai", False)),
            "multi_voice": bool(getattr(b, "multi_voice", False)),
            "warning_message": (
                SCANNED_PDF_WARNING if getattr(b, "is_scanned", False) else None
            ),
            "total_characters": getattr(b, "total_characters", 0) or 0,
            "cost_warning": get_cost_warning(getattr(b, "total_characters", 0) or 0),
            "error_message": b.error_message,
            "total_chunks": b.total_chunks,
            "done_chunks": b.done_chunks,
            "voice": b.voice,
            "provider": getattr(b, "provider", "edge_tts") or "edge_tts",
            "voice_cast": getattr(b, "voice_cast", None),
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in books
    ]


@app.get("/api/books/{id}")
def get_book_details(id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve book details and narration progress."""
    book = db.query(Book).filter(Book.id == id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id '{id}' not found.",
        )

    progress_ratio = f"{book.done_chunks}/{book.total_chunks}"
    progress_percent = (
        round((book.done_chunks / book.total_chunks) * 100, 1)
        if book.total_chunks > 0
        else 0.0
    )
    total_chars = getattr(book, "total_characters", 0) or 0

    return {
        "id": book.id,
        "title": book.title,
        "language": book.language,
        "original_filename": book.original_filename,
        "status": book.status,
        "is_scanned": bool(getattr(book, "is_scanned", False)),
        "improve_with_ai": bool(getattr(book, "improve_with_ai", False)),
        "multi_voice": bool(getattr(book, "multi_voice", False)),
        "warning_message": (
            SCANNED_PDF_WARNING if getattr(book, "is_scanned", False) else None
        ),
        "total_characters": total_chars,
        "cost_warning": get_cost_warning(total_chars),
        "error_message": book.error_message,
        "total_chunks": book.total_chunks,
        "done_chunks": book.done_chunks,
        "progress": progress_ratio,
        "progress_percent": progress_percent,
        "voice": book.voice,
        "provider": getattr(book, "provider", "edge_tts") or "edge_tts",
        "voice_cast": getattr(book, "voice_cast", None),
        "created_at": book.created_at.isoformat() if book.created_at else None,
    }


@app.get("/api/books/{id}/chunks")
def get_book_chunks(id: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Retrieve all text chunks for a book ordered by sentence index with audio stream URLs."""
    book = db.query(Book).filter(Book.id == id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id '{id}' not found.",
        )

    chunks = db.query(Chunk).filter(Chunk.book_id == id).order_by(Chunk.index).all()
    results: List[Dict[str, Any]] = []

    for c in chunks:
        filename = f"chunk_{c.index:03d}.mp3"
        audio_url = f"/api/audio/{book.id}/{filename}" if c.status == "done" and c.audio_path else None

        results.append({
            "id": c.id,
            "index": c.index,
            "text": c.text,
            "status": c.status,
            "audio_url": audio_url,
            "duration_seconds": c.duration_seconds,
        })

    return results


@app.post("/api/books/{id}/retry")
def retry_failed_chunks_endpoint(
    id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Regenerate only failed or uncompleted chunks for a book.

    Args:
        id: Book identifier (UUID).
        background_tasks: FastAPI background tasks queue.
        db: SQLAlchemy session.

    Returns:
        JSON response with retry status and count of chunks queued for retry.
    """
    book = db.query(Book).filter(Book.id == id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id '{id}' not found.",
        )

    # Find failed or uncompleted chunks (never regenerate chunks that are already done)
    failed_chunks = db.query(Chunk).filter(
        Chunk.book_id == id,
        Chunk.status != "done",
    ).all()
    failed_count = len(failed_chunks)

    if failed_count == 0:
        return {
            "id": book.id,
            "status": book.status,
            "retried_chunks": 0,
            "message": "No failed chunks to retry.",
        }

    # Set book status to generating and clear error
    book.status = "generating"
    book.error_message = None
    db.commit()

    background_tasks.add_task(retry_failed_chunks, id)

    return {
        "id": book.id,
        "status": "generating",
        "retried_chunks": failed_count,
        "message": f"Queued {failed_count} failed chunk(s) for retry.",
    }


@app.get("/api/audio/{book_id}/{filename}")
def serve_audio_chunk(
    book_id: str,
    filename: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve an MP3 audio file with native HTTP Range request support."""
    # 1. Validate that book_id is a valid UUID (return 400 if invalid)
    try:
        uuid.UUID(book_id)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid book ID format. Must be a valid UUID.",
        )

    # Validate that the Book exists in the database (404 if not)
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id '{book_id}' not found.",
        )

    # 2. Validate filename with a strict regex: ^chunk_\d{3,5}\.mp3$
    if not CHUNK_FILENAME_REGEX.match(filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid audio filename format. Only MP3 files matching chunk_XXX.mp3 are served.",
        )

    # 3. Build path as STORAGE_DIR / book_id / filename, call .resolve(),
    # and confirm it is inside STORAGE_DIR.resolve() using is_relative_to.
    # Return 404 otherwise.
    audio_path = (STORAGE_DIR / book_id / filename).resolve()
    storage_resolved = STORAGE_DIR.resolve()

    if not audio_path.is_relative_to(storage_resolved) or not audio_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio file '{filename}' for book '{book_id}' was not found.",
        )

    # FileResponse natively handles HTTP Range headers (status 206 Partial Content)
    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=filename,
    )


@app.delete("/api/books/{id}")
def delete_book(id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Delete a book, its database chunks, and its storage directory."""
    book = db.query(Book).filter(Book.id == id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id '{id}' not found.",
        )

    # Remove storage folder and audio files
    import gc
    import time
    gc.collect()
    book_dir = get_book_storage_dir(id)
    if book_dir.exists():
        for _ in range(10):
            shutil.rmtree(book_dir, ignore_errors=True)
            if not book_dir.exists():
                break
            time.sleep(0.05)

    # Delete database record (cascades to chunks)
    db.delete(book)
    db.commit()

    return {"message": f"Book '{id}' and all associated storage files deleted successfully."}


@app.get("/api/voices")
async def get_voices(
    language: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """Retrieve available TTS storyteller voices optionally filtered by language code and provider."""
    prov_clean = (provider or "").strip().lower()
    if prov_clean in ("elevenlabs", "eleven_labs", "eleven-labs"):
        from backend.app.services.tts.elevenlabs_provider import ElevenLabsProvider
        p = ElevenLabsProvider()
        return await p.list_voices(language=language)
    return await list_voices(language=language)
