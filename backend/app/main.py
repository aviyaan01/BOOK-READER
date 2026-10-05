"""Main entry point for the PDF Storyteller FastAPI application."""

import shutil
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
    get_book_storage_dir,
    DEFAULT_ENGLISH_VOICE,
    DEFAULT_BANGLA_VOICE,
)
from backend.app.db import init_db, get_db
from backend.app.models import Book, Chunk
from backend.app.services.pipeline import process_book
from backend.app.services.tts.edge_tts_provider import list_voices

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB


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
    voice: Optional[str] = Form(None),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Upload a storybook PDF (max 30MB), save as original.pdf, and launch background processing.

    Args:
        background_tasks: FastAPI background tasks queue.
        file: Multipart uploaded PDF file (max 30MB).
        language: Language code, must be 'bn' (Bangla) or 'en' (English).
        voice: Optional voice ID or name to use for speech narration.
        db: SQLAlchemy transactional database session.

    Returns:
        JSON response containing the created book ID and initial status.
    """
    # 1. Validate language
    lang_clean = language.strip().lower()
    if lang_clean not in ("bn", "en"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid language. Supported values are 'bn' (Bangla) or 'en' (English).",
        )

    # 2. Validate file type
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF documents (.pdf) are accepted.",
        )

    # 3. Create Book row first to obtain a UUID
    default_voice = DEFAULT_BANGLA_VOICE if lang_clean == "bn" else DEFAULT_ENGLISH_VOICE
    chosen_voice = voice.strip() if voice and voice.strip() else default_voice
    book_title = Path(filename).stem.replace("_", " ").strip().title() or "Untitled Story"

    book = Book(
        title=book_title,
        language=lang_clean,
        original_filename=filename,
        status="uploaded",
        voice=chosen_voice,
    )
    db.add(book)
    db.commit()
    db.refresh(book)

    # 4. Stream and save PDF to storage/<book_id>/original.pdf (validating max 30MB)
    book_dir = get_book_storage_dir(book.id)
    target_path = book_dir / "original.pdf"
    total_bytes = 0

    try:
        with open(target_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # Read in 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE:
                    buffer.close()
                    if target_path.exists():
                        target_path.unlink()
                    # Clean up Book record
                    db.delete(book)
                    db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File exceeds maximum allowed size of 30MB.",
                    )
                buffer.write(chunk)

        if total_bytes == 0:
            if target_path.exists():
                target_path.unlink()
            db.delete(book)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded PDF file is empty (0 bytes).",
            )
    except HTTPException:
        raise
    except Exception as exc:
        db.delete(book)
        db.commit()
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {str(exc)}",
        )

    # 5. Launch asynchronous background processing
    background_tasks.add_task(process_book, book.id)

    return {"id": book.id, "status": book.status}


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
            "error_message": b.error_message,
            "total_chunks": b.total_chunks,
            "done_chunks": b.done_chunks,
            "voice": b.voice,
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

    return {
        "id": book.id,
        "title": book.title,
        "language": book.language,
        "original_filename": book.original_filename,
        "status": book.status,
        "error_message": book.error_message,
        "total_chunks": book.total_chunks,
        "done_chunks": book.done_chunks,
        "progress": progress_ratio,
        "progress_percent": progress_percent,
        "voice": book.voice,
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


@app.get("/api/audio/{book_id}/{filename}")
def serve_audio_chunk(book_id: str, filename: str) -> FileResponse:
    """Serve an MP3 audio file with native HTTP Range request support."""
    # Sanitize filename to prevent directory traversal
    clean_filename = Path(filename).name
    if not clean_filename.lower().endswith(".mp3"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid audio format requested. Only MP3 files are served.",
        )

    book_dir = get_book_storage_dir(book_id)
    audio_path = book_dir / clean_filename

    if not audio_path.exists() or not audio_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio file '{clean_filename}' for book '{book_id}' was not found.",
        )

    # FileResponse natively handles HTTP Range headers (status 206 Partial Content)
    return FileResponse(
        path=str(audio_path),
        media_type="audio/mpeg",
        filename=clean_filename,
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
    book_dir = get_book_storage_dir(id)
    if book_dir.exists():
        shutil.rmtree(book_dir, ignore_errors=True)

    # Delete database record (cascades to chunks)
    db.delete(book)
    db.commit()

    return {"message": f"Book '{id}' and all associated storage files deleted successfully."}


@app.get("/api/voices")
async def get_voices(language: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Retrieve available TTS storyteller voices optionally filtered by language code."""
    return await list_voices(language=language)
