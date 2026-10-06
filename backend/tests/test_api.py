"""Unit and integration tests for FastAPI endpoints in main.py."""

import io
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import SessionLocal, Base, engine
from backend.app.models import Book, Chunk
from backend.app.config import get_book_storage_dir


@pytest.fixture(scope="module", autouse=True)
def init_test_db():
    """Ensure database schema is created before API tests."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    """Provide a FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client):
    """Verify GET /health returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_voices_endpoint(client):
    """Verify GET /api/voices and GET /api/voices?language=bn."""
    # All voices
    res_all = client.get("/api/voices")
    assert res_all.status_code == 200
    voices_all = res_all.json()
    assert isinstance(voices_all, list)
    assert len(voices_all) > 0

    # Bangla filtered
    res_bn = client.get("/api/voices?language=bn")
    assert res_bn.status_code == 200
    voices_bn = res_bn.json()
    assert isinstance(voices_bn, list)
    assert len(voices_bn) > 0
    for v in voices_bn:
        locale = v.get("Locale", "").lower()
        assert "bn" in locale


def test_upload_book_invalid_inputs(client):
    """Verify validation errors for bad language, non-PDF file, and empty file."""
    # 1. Invalid language
    fake_pdf = io.BytesIO(b"%PDF-1.4 test content")
    res_lang = client.post(
        "/api/books",
        data={"language": "fr"},
        files={"file": ("test.pdf", fake_pdf, "application/pdf")},
    )
    assert res_lang.status_code == 400
    assert "Invalid language" in res_lang.json()["detail"]

    # 2. Non-PDF file
    fake_txt = io.BytesIO(b"Hello world text file")
    res_file = client.post(
        "/api/books",
        data={"language": "en"},
        files={"file": ("test.txt", fake_txt, "text/plain")},
    )
    assert res_file.status_code == 400
    assert "Only PDF documents" in res_file.json()["detail"]

    # 3. Empty PDF file (0 bytes)
    empty_pdf = io.BytesIO(b"")
    res_empty = client.post(
        "/api/books",
        data={"language": "en"},
        files={"file": ("empty.pdf", empty_pdf, "application/pdf")},
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["detail"].lower()


def test_book_crud_lifecycle(client):
    """Test full lifecycle: POST /api/books, GET /api/books, GET /api/books/{id}, chunks, audio, DELETE."""
    sample_pdf_path = Path("sample_books/english_story_whispering_tree.pdf")
    if sample_pdf_path.exists():
        pdf_bytes = sample_pdf_path.read_bytes()
    else:
        pdf_bytes = b"%PDF-1.4 dummy valid pdf bytes"

    # Patch process_book to prevent long synthesis during synchronous endpoint test
    with patch("backend.app.main.process_book") as mock_pipeline:
        # 1. POST /api/books
        response = client.post(
            "/api/books",
            data={"language": "en", "voice": "en-US-AriaNeural"},
            files={"file": ("sample_story.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "uploaded"
        book_id = data["id"]

        # Verify background task was queued with book_id
        mock_pipeline.assert_called_once_with(book_id)

    try:
        # Verify original.pdf was saved in storage/<book_id>/
        book_dir = get_book_storage_dir(book_id)
        original_pdf = book_dir / "original.pdf"
        assert original_pdf.exists()
        assert original_pdf.stat().st_size == len(pdf_bytes)

        # 2. GET /api/books
        res_list = client.get("/api/books")
        assert res_list.status_code == 200
        books = res_list.json()
        assert any(b["id"] == book_id for b in books)

        # 3. GET /api/books/{id}
        res_book = client.get(f"/api/books/{book_id}")
        assert res_book.status_code == 200
        book_info = res_book.json()
        assert book_info["id"] == book_id
        assert book_info["language"] == "en"
        assert book_info["progress"] == "0/0"

        # Seed mock chunks to test GET /api/books/{id}/chunks and audio serving
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            b.total_chunks = 2
            b.done_chunks = 1
            chunk1 = Chunk(
                book_id=book_id,
                index=0,
                text="The tree whispered quietly.",
                status="done",
                audio_path=str(book_dir / "chunk_000.mp3"),
                duration_seconds=3.5,
            )
            chunk2 = Chunk(
                book_id=book_id,
                index=1,
                text="The wind answered back.",
                status="pending",
                audio_path=None,
                duration_seconds=None,
            )
            db.add_all([chunk1, chunk2])
            db.commit()

        # Create dummy mp3 file for chunk_000.mp3
        mp3_file = book_dir / "chunk_000.mp3"
        dummy_audio = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xFF\xFB\x90\x44" * 50
        mp3_file.write_bytes(dummy_audio)

        # 4. GET /api/books/{id} again to check updated progress ratio
        res_progress = client.get(f"/api/books/{book_id}")
        assert res_progress.status_code == 200
        assert res_progress.json()["progress"] == "1/2"
        assert res_progress.json()["progress_percent"] == 50.0

        # 5. GET /api/books/{id}/chunks
        res_chunks = client.get(f"/api/books/{book_id}/chunks")
        assert res_chunks.status_code == 200
        chunks_data = res_chunks.json()
        assert len(chunks_data) == 2
        assert chunks_data[0]["index"] == 0
        assert chunks_data[0]["status"] == "done"
        assert chunks_data[0]["audio_url"] == f"/api/audio/{book_id}/chunk_000.mp3"
        assert chunks_data[0]["duration_seconds"] == 3.5
        assert chunks_data[1]["index"] == 1
        assert chunks_data[1]["status"] == "pending"
        assert chunks_data[1]["audio_url"] is None

        # 6. GET /api/audio/{book_id}/{filename}
        # Non-mp3 validation error
        res_bad_audio = client.get(f"/api/audio/{book_id}/notes.txt")
        assert res_bad_audio.status_code == 400
        assert "Only MP3" in res_bad_audio.json()["detail"]

        # Missing mp3 404
        res_missing_audio = client.get(f"/api/audio/{book_id}/chunk_999.mp3")
        assert res_missing_audio.status_code == 404

        # Valid mp3 200
        res_audio = client.get(f"/api/audio/{book_id}/chunk_000.mp3")
        assert res_audio.status_code == 200
        assert res_audio.headers["content-type"] == "audio/mpeg"
        assert len(res_audio.content) == len(dummy_audio)
        res_audio.close()

        # HTTP Range request (Partial Content 206)
        res_range = client.get(
            f"/api/audio/{book_id}/chunk_000.mp3",
            headers={"Range": "bytes=0-9"},
        )
        assert res_range.status_code == 206
        assert len(res_range.content) == 10
        assert "bytes 0-9/" in res_range.headers.get("content-range", "")
        res_range.close()

        # 7. DELETE /api/books/{id}
        res_del = client.delete(f"/api/books/{book_id}")
        assert res_del.status_code == 200
        res_del.close()

        # Verify book and chunks deleted from DB
        with SessionLocal() as db:
            assert db.query(Book).filter(Book.id == book_id).first() is None
            assert db.query(Chunk).filter(Chunk.book_id == book_id).count() == 0

        # Verify storage folder deleted
        import gc, time
        gc.collect()
        for _ in range(10):
            if not book_dir.exists():
                break
            time.sleep(0.05)
        if book_dir.exists():
            print("REMAINING IN BOOK_DIR:", list(book_dir.iterdir()))
        assert not book_dir.exists()

        # Subsequent GET should return 404
        res_after_del = client.get(f"/api/books/{book_id}")
        assert res_after_del.status_code == 404

    finally:
        # Cleanup in case of assertion failure
        book_dir = get_book_storage_dir(book_id)
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            if b:
                db.delete(b)
                db.commit()


def test_scanned_book_warning_in_api(client):
    """Verify that is_scanned=True returns the scanned PDF warning message in API responses."""
    with SessionLocal() as db:
        book = Book(
            title="Scanned Storybook",
            language="en",
            original_filename="scanned.pdf",
            is_scanned=True,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        book_id = book.id

    try:
        res = client.get(f"/api/books/{book_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["is_scanned"] is True
        assert data["warning_message"] == (
            "This looks like a scanned PDF, text recognition may take longer and can contain errors."
        )

        res_list = client.get("/api/books")
        assert res_list.status_code == 200
        item = next(b for b in res_list.json() if b["id"] == book_id)
        assert item["is_scanned"] is True
        assert item["warning_message"] == (
            "This looks like a scanned PDF, text recognition may take longer and can contain errors."
        )
    finally:
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            if b:
                db.delete(b)
                db.commit()


def test_not_found_endpoints(client):
    """Verify 404 responses for non-existent books."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    res_book = client.get(f"/api/books/{fake_id}")
    assert res_book.status_code == 404
    assert f"Book with id '{fake_id}' not found" in res_book.json()["detail"]

    res_chunks = client.get(f"/api/books/{fake_id}/chunks")
    assert res_chunks.status_code == 404
    assert f"Book with id '{fake_id}' not found" in res_chunks.json()["detail"]

    res_del = client.delete(f"/api/books/{fake_id}")
    assert res_del.status_code == 404
    assert f"Book with id '{fake_id}' not found" in res_del.json()["detail"]


def test_upload_book_with_improve_with_ai_toggle(client):
    """Verify that uploading with improve_with_ai=true sets the toggle flag correctly."""
    sample_pdf_path = Path("sample_books/english_story_whispering_tree.pdf")
    if sample_pdf_path.exists():
        pdf_bytes = sample_pdf_path.read_bytes()
    else:
        pdf_bytes = b"%PDF-1.4 dummy valid pdf bytes"

    with patch("backend.app.main.process_book"):
        response = client.post(
            "/api/books",
            data={"language": "en", "voice": "en-US-AriaNeural", "improve_with_ai": "true"},
            files={"file": ("ai_story.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert response.status_code == 201
        book_id = response.json()["id"]

    try:
        res = client.get(f"/api/books/{book_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["improve_with_ai"] is True
    finally:
        client.delete(f"/api/books/{book_id}")


def test_cost_warning_for_large_book(client):
    """Verify that books with >= 10,000 characters receive cost/size warnings in API."""
    with SessionLocal() as db:
        book_normal = Book(
            title="Short Book",
            language="en",
            original_filename="short.pdf",
            total_characters=2500,
        )
        book_large = Book(
            title="Large Epic Book",
            language="en",
            original_filename="epic.pdf",
            total_characters=25000,
        )
        db.add_all([book_normal, book_large])
        db.commit()
        db.refresh(book_normal)
        db.refresh(book_large)
        id_normal = book_normal.id
        id_large = book_large.id

    try:
        # Check normal book
        res_normal = client.get(f"/api/books/{id_normal}")
        assert res_normal.status_code == 200
        normal_data = res_normal.json()
        assert normal_data["total_characters"] == 2500
        assert normal_data["cost_warning"] is None

        # Check large book
        res_large = client.get(f"/api/books/{id_large}")
        assert res_large.status_code == 200
        large_data = res_large.json()
        assert large_data["total_characters"] == 25000
        assert large_data["cost_warning"] is not None
        assert "25,000 characters" in large_data["cost_warning"]

        # Check list endpoint
        res_list = client.get("/api/books")
        assert res_list.status_code == 200
        items = {item["id"]: item for item in res_list.json()}
        assert items[id_normal]["total_characters"] == 2500
        assert items[id_normal]["cost_warning"] is None
        assert items[id_large]["total_characters"] == 25000
        assert items[id_large]["cost_warning"] is not None
    finally:
        with SessionLocal() as db:
            for bid in (id_normal, id_large):
                b = db.query(Book).filter(Book.id == bid).first()
                if b:
                    db.delete(b)
            db.commit()

