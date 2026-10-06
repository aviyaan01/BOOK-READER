"""Unit and integration tests for FastAPI endpoints in main.py."""

import io
import time
import shutil
import uuid
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.db import SessionLocal, Base, engine
from backend.app.models import Book, Chunk
from backend.app.config import get_book_storage_dir, create_book_storage_dir


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


def test_retry_nonexistent_book(client):
    """Verify POST /api/books/{id}/retry returns 404 for nonexistent book."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    res = client.post(f"/api/books/{fake_id}/retry")
    assert res.status_code == 404
    assert f"Book with id '{fake_id}' not found" in res.json()["detail"]


def test_retry_no_failed_chunks(client):
    """Verify POST /api/books/{id}/retry returns retried_chunks=0 when all chunks are done."""
    with SessionLocal() as db:
        book = Book(
            title="Complete Book",
            language="en",
            original_filename="complete.pdf",
            status="ready",
            total_chunks=2,
            done_chunks=2,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        book_id = book.id

        chunk0 = Chunk(book_id=book_id, index=0, text="First done chunk", status="done")
        chunk1 = Chunk(book_id=book_id, index=1, text="Second done chunk", status="done")
        db.add_all([chunk0, chunk1])
        db.commit()

    try:
        res = client.post(f"/api/books/{book_id}/retry")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == book_id
        assert data["retried_chunks"] == 0
        assert "No failed chunks to retry" in data["message"]
    finally:
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            if b:
                db.delete(b)
                db.commit()


def test_retry_failed_chunks_endpoint(client):
    """Verify POST /api/books/{id}/retry triggers retry for only failed chunks."""
    with SessionLocal() as db:
        book = Book(
            title="Partially Failed Book",
            language="en",
            original_filename="partial.pdf",
            status="failed",
            error_message="1 chunk(s) failed",
            total_chunks=3,
            done_chunks=2,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        book_id = book.id

        c0 = Chunk(book_id=book_id, index=0, text="Completed sentence 1", status="done", audio_path="chunk_000.mp3", duration_seconds=2.5)
        c1 = Chunk(book_id=book_id, index=1, text="Failed sentence 2", status="failed", audio_path=None)
        c2 = Chunk(book_id=book_id, index=2, text="Completed sentence 3", status="done", audio_path="chunk_002.mp3", duration_seconds=3.0)
        db.add_all([c0, c1, c2])
        db.commit()

    try:
        with patch("backend.app.main.retry_failed_chunks") as mock_retry:
            res = client.post(f"/api/books/{book_id}/retry")
            assert res.status_code == 200
            data = res.json()
            assert data["id"] == book_id
            assert data["status"] == "generating"
            assert data["retried_chunks"] == 1
            assert "Queued 1 failed chunk(s)" in data["message"]

        # Verify book status in database updated to generating and error cleared
        with SessionLocal() as db:
            updated_book = db.query(Book).filter(Book.id == book_id).first()
            assert updated_book.status == "generating"
            assert updated_book.error_message is None
    finally:
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            if b:
                db.delete(b)
                db.commit()


@pytest.mark.anyio
async def test_retry_service_only_regenerates_failed_chunks():
    """Verify that retry_failed_chunks regenerates only failed chunks and preserves done chunks."""
    from unittest.mock import MagicMock
    from backend.app.services.pipeline import retry_failed_chunks

    with SessionLocal() as db:
        book = Book(
            title="Service Retry Book",
            language="en",
            original_filename="service.pdf",
            status="failed",
            error_message="1 chunk(s) failed to synthesize audio.",
            total_chunks=3,
            done_chunks=2,
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        book_id = book.id
        create_book_storage_dir(book_id)

        c0 = Chunk(
            book_id=book_id,
            index=0,
            text="Sentence zero already completed.",
            status="done",
            audio_path="existing_chunk_000.mp3",
            duration_seconds=4.2,
        )
        c1 = Chunk(
            book_id=book_id,
            index=1,
            text="Sentence one that previously failed.",
            status="failed",
            audio_path=None,
            duration_seconds=None,
        )
        c2 = Chunk(
            book_id=book_id,
            index=2,
            text="Sentence two already completed.",
            status="done",
            audio_path="existing_chunk_002.mp3",
            duration_seconds=3.8,
        )
        db.add_all([c0, c1, c2])
        db.commit()

    synthesized_texts = []

    async def fake_synthesize(text, out_path, voice):
        synthesized_texts.append(text)
        Path(out_path).touch()

    mock_mp3_obj = MagicMock()
    mock_mp3_obj.info.length = 5.0

    try:
        with patch("backend.app.services.tts.EdgeTTSProvider.synthesize", side_effect=fake_synthesize), \
             patch("backend.app.services.pipeline.MP3", return_value=mock_mp3_obj):
            retried_count = await retry_failed_chunks(book_id)

        assert retried_count == 1
        # Verify that ONLY chunk 1 text was synthesized
        assert synthesized_texts == ["Sentence one that previously failed."]

        # Verify chunks state in database
        with SessionLocal() as db:
            chunks_db = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.index).all()
            assert len(chunks_db) == 3

            # Chunk 0: untouched
            assert chunks_db[0].status == "done"
            assert chunks_db[0].audio_path == "existing_chunk_000.mp3"
            assert chunks_db[0].duration_seconds == 4.2

            # Chunk 1: now done
            assert chunks_db[1].status == "done"
            assert chunks_db[1].audio_path is not None
            assert chunks_db[1].duration_seconds == 5.0

            # Chunk 2: untouched
            assert chunks_db[2].status == "done"
            assert chunks_db[2].audio_path == "existing_chunk_002.mp3"
            assert chunks_db[2].duration_seconds == 3.8

            # Book is now ready
            book_db = db.query(Book).filter(Book.id == book_id).first()
            assert book_db.status == "ready"
            assert book_db.done_chunks == 3
            assert book_db.error_message is None
    finally:
        book_dir = get_book_storage_dir(book_id)
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            if b:
                db.delete(b)
                db.commit()


def test_get_voices_with_elevenlabs_provider(client):
    """Verify GET /api/voices?provider=elevenlabs returns ElevenLabs voices."""
    res = client.get("/api/voices?provider=elevenlabs")
    assert res.status_code == 200
    voices = res.json()
    assert isinstance(voices, list)
    assert len(voices) > 0
    # Check that ElevenLabs voices are present
    voice_ids = [v.get("voice_id") or v.get("ShortName") for v in voices]
    assert "21m00Tcm4TlvDq8ikWAM" in voice_ids  # Rachel


def test_upload_book_with_provider_selection(client):
    """Verify that uploading with provider='elevenlabs' sets the provider field correctly."""
    sample_pdf_path = Path("sample_books/english_story_whispering_tree.pdf")
    if sample_pdf_path.exists():
        pdf_bytes = sample_pdf_path.read_bytes()
    else:
        pdf_bytes = b"%PDF-1.4 dummy valid pdf bytes"

    with patch("backend.app.main.process_book"), patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_api_key_123"}):
        response = client.post(
            "/api/books",
            data={
                "language": "en",
                "voice": "21m00Tcm4TlvDq8ikWAM",
                "provider": "elevenlabs",
            },
            files={"file": ("eleven_story.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert response.status_code == 201
        book_id = response.json()["id"]

    try:
        # Check single book endpoint
        res = client.get(f"/api/books/{book_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "elevenlabs"
        assert data["voice"] == "21m00Tcm4TlvDq8ikWAM"

        # Check list endpoint
        res_list = client.get("/api/books")
        assert res_list.status_code == 200
        items = {item["id"]: item for item in res_list.json()}
        assert items[book_id]["provider"] == "elevenlabs"
    finally:
        client.delete(f"/api/books/{book_id}")


def test_audio_endpoint_security_and_traversal(client):
    """Verify security controls on GET /api/audio/{book_id}/{filename} against path traversal and invalid inputs."""
    # 1. Test "../" traversal in book_id
    res_dotdot = client.get("/api/audio/../chunk_001.mp3")
    assert res_dotdot.status_code in (400, 404)
    assert res_dotdot.status_code != 200

    # 2. Test "%2e%2e" encoded traversal in book_id
    res_encoded = client.get("/api/audio/%2e%2e/chunk_001.mp3")
    assert res_encoded.status_code in (400, 404)
    assert res_encoded.status_code != 200

    # Double-encoded %252e%252e which reaches endpoint as '%2e%2e'
    res_double_encoded = client.get("/api/audio/%252e%252e/chunk_001.mp3")
    assert res_double_encoded.status_code in (400, 404)
    assert res_double_encoded.status_code != 200

    # 3. Test non-UUID string as book_id -> must return 400
    res_non_uuid = client.get("/api/audio/not-a-valid-uuid-123/chunk_001.mp3")
    assert res_non_uuid.status_code == 400
    assert "UUID" in res_non_uuid.json().get("detail", "")

    # 4. Test random non-existent UUID as book_id -> must return 404
    non_existent_uuid = str(uuid.uuid4())
    res_not_found = client.get(f"/api/audio/{non_existent_uuid}/chunk_001.mp3")
    assert res_not_found.status_code == 404
    assert f"Book with id '{non_existent_uuid}' not found." in res_not_found.json().get("detail", "")

    # Create a real book in the database for filename testing
    with SessionLocal() as db:
        book = Book(
            title="Audio Security Test Book",
            language="en",
            original_filename="security_test.pdf",
            status="ready",
        )
        db.add(book)
        db.commit()
        db.refresh(book)
        valid_book_id = book.id

    try:
        # 5. Test filename like "../../etc/passwd.mp3"
        res_file_traversal = client.get(f"/api/audio/{valid_book_id}/../../etc/passwd.mp3")
        assert res_file_traversal.status_code in (400, 404)
        assert res_file_traversal.status_code != 200

        # Filename regex validation (^chunk_\d{3,5}\.mp3$)
        res_invalid_name = client.get(f"/api/audio/{valid_book_id}/passwd.mp3")
        assert res_invalid_name.status_code == 400
        assert "Invalid audio filename format" in res_invalid_name.json().get("detail", "")

        res_invalid_digits = client.get(f"/api/audio/{valid_book_id}/chunk_1.mp3")
        assert res_invalid_digits.status_code == 400

        res_nonexistent_chunk = client.get(f"/api/audio/{valid_book_id}/chunk_001.mp3")
        assert res_nonexistent_chunk.status_code == 404

        # 6. Valid request that returns 200
        book_dir = create_book_storage_dir(valid_book_id)
        valid_chunk_file = book_dir / "chunk_001.mp3"
        valid_chunk_file.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xFF\xFB\x90\x44" * 50)

        res_valid = client.get(f"/api/audio/{valid_book_id}/chunk_001.mp3")
        assert res_valid.status_code == 200
        assert "audio/mpeg" in res_valid.headers.get("content-type", "")
        assert len(res_valid.content) > 0
    finally:
        book_dir = get_book_storage_dir(valid_book_id)
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == valid_book_id).first()
            if b:
                db.delete(b)
                db.commit()


def test_get_book_storage_dir_does_not_mkdir():
    """Verify get_book_storage_dir does not create directories for read operations, but create_book_storage_dir does."""
    non_existent_id = "test-non-existent-read-id-9999"
    test_path = get_book_storage_dir(non_existent_id)
    assert not test_path.exists()

    created_id = "test-created-write-id-9999"
    try:
        created_path = create_book_storage_dir(created_id)
        assert created_path.exists()
    finally:
        del_path = get_book_storage_dir(created_id)
        if del_path.exists():
            shutil.rmtree(del_path, ignore_errors=True)


def test_upload_book_magic_bytes_validation(client):
    """Verify upload rejects files not starting with '%PDF-' and resets seek position for valid files."""
    # 1. Invalid magic bytes
    bad_pdf = io.BytesIO(b"NOT_A_PDF_CONTENT")
    res_bad = client.post(
        "/api/books",
        data={"language": "en"},
        files={"file": ("invalid_magic.pdf", bad_pdf, "application/pdf")},
    )
    assert res_bad.status_code == 400
    assert "Invalid PDF file format" in res_bad.json()["detail"]
    assert "%PDF-" in res_bad.json()["detail"]

    # 2. Valid magic bytes: verifies seek(0) works and saves full content
    valid_pdf_content = b"%PDF-1.5 Valid PDF stream content here"
    valid_pdf = io.BytesIO(valid_pdf_content)
    with patch("backend.app.main.process_book"):
        res_ok = client.post(
            "/api/books",
            data={"language": "en"},
            files={"file": ("valid_magic.pdf", valid_pdf, "application/pdf")},
        )
        assert res_ok.status_code == 201
        book_id = res_ok.json()["id"]

    try:
        # Check that saved file on disk has the complete content from byte 0
        saved_file = get_book_storage_dir(book_id) / "original.pdf"
        assert saved_file.exists()
        assert saved_file.read_bytes() == valid_pdf_content
    finally:
        client.delete(f"/api/books/{book_id}")


def test_upload_book_streaming_size_limit(client):
    """Verify 30MB limit is enforced while streaming to disk and partial file is unlinked."""
    # Patch MAX_FILE_SIZE to 50 bytes to test streaming limit without memory overhead
    with patch("backend.app.main.MAX_FILE_SIZE", 50):
        # 100 bytes payload starting with valid %PDF-
        payload = b"%PDF-" + b"A" * 95
        res = client.post(
            "/api/books",
            data={"language": "en"},
            files={"file": ("too_large.pdf", io.BytesIO(payload), "application/pdf")},
        )
        assert res.status_code == 400
        assert "exceeds maximum allowed size" in res.json()["detail"]

    # Ensure no leftover files or records in database matching too_large
    with SessionLocal() as db:
        book_in_db = db.query(Book).filter(Book.original_filename == "too_large.pdf").first()
        assert book_in_db is None


def test_upload_book_filename_sanitization_and_truncation(client):
    """Verify filename path components are stripped and title & original_filename are truncated to 250 chars."""
    long_name = ("nested_path_dir_" * 20) + "story.pdf"
    traversal_filename = f"../../dangerous/subfolder/{long_name}"
    long_title = "My Ultra Long Storybook Title That Exceeds Normal Limits " * 10
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")

    with patch("backend.app.main.process_book"):
        res = client.post(
            "/api/books",
            data={"language": "en", "title": long_title},
            files={"file": (traversal_filename, valid_pdf, "application/pdf")},
        )
        assert res.status_code == 201
        book_id = res.json()["id"]

    try:
        res_book = client.get(f"/api/books/{book_id}")
        assert res_book.status_code == 200
        data = res_book.json()

        # Path components stripped
        assert "/" not in data["original_filename"]
        assert "\\" not in data["original_filename"]
        assert ".." not in data["original_filename"]

        # Truncated to <= 250 characters
        assert len(data["original_filename"]) <= 250
        assert len(data["title"]) <= 250
        assert len(data["title"]) == 250
    finally:
        client.delete(f"/api/books/{book_id}")


def test_upload_book_provider_whitelist(client):
    """Verify unknown provider values return 400 instead of silently falling back."""
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")
    res_bad = client.post(
        "/api/books",
        data={"language": "en", "provider": "unsupported_tts_engine"},
        files={"file": ("story.pdf", valid_pdf, "application/pdf")},
    )
    assert res_bad.status_code == 400
    assert "Invalid provider 'unsupported_tts_engine'" in res_bad.json()["detail"]
    assert "Supported providers are 'edge_tts' and 'elevenlabs'" in res_bad.json()["detail"]


def test_upload_book_language_and_voice_validation(client):
    """Verify language and voice validations against the provider's voice list."""
    # 1. Invalid language
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")
    res_lang = client.post(
        "/api/books",
        data={"language": "es"},
        files={"file": ("story.pdf", valid_pdf, "application/pdf")},
    )
    assert res_lang.status_code == 400
    assert "Invalid language" in res_lang.json()["detail"]

    # 2. Unknown voice for edge_tts
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")
    res_voice_unknown = client.post(
        "/api/books",
        data={"language": "en", "provider": "edge_tts", "voice": "non_existent_voice_xyz"},
        files={"file": ("story.pdf", valid_pdf, "application/pdf")},
    )
    assert res_voice_unknown.status_code == 400
    assert "Invalid voice 'non_existent_voice_xyz'" in res_voice_unknown.json()["detail"]

    # 3. Voice language mismatch for edge_tts (English voice with Bangla book)
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")
    res_voice_mismatch = client.post(
        "/api/books",
        data={"language": "bn", "provider": "edge_tts", "voice": "en-US-AriaNeural"},
        files={"file": ("story.pdf", valid_pdf, "application/pdf")},
    )
    assert res_voice_mismatch.status_code == 400
    assert "Invalid voice 'en-US-AriaNeural'" in res_voice_mismatch.json()["detail"]

    # 4. Unknown voice for elevenlabs
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")
    with patch.dict("os.environ", {"ELEVENLABS_API_KEY": "test_key"}):
        res_voice_eleven = client.post(
            "/api/books",
            data={"language": "en", "provider": "elevenlabs", "voice": "fake_eleven_voice"},
            files={"file": ("story.pdf", valid_pdf, "application/pdf")},
        )
        assert res_voice_eleven.status_code == 400
        assert "Invalid voice 'fake_eleven_voice'" in res_voice_eleven.json()["detail"]

    # 5. Valid voice for edge_tts
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")
    with patch("backend.app.main.process_book"):
        res_voice_ok = client.post(
            "/api/books",
            data={"language": "en", "provider": "edge_tts", "voice": "en-US-AriaNeural"},
            files={"file": ("story.pdf", valid_pdf, "application/pdf")},
        )
        assert res_voice_ok.status_code == 201
        book_id = res_voice_ok.json()["id"]
        client.delete(f"/api/books/{book_id}")


def test_upload_book_elevenlabs_empty_api_key(client):
    """Verify selecting elevenlabs provider with empty ELEVENLABS_API_KEY returns 400 with clear message."""
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample content")
    with patch.dict("os.environ", {"ELEVENLABS_API_KEY": ""}), patch("backend.app.main.ELEVENLABS_API_KEY", ""):
        res = client.post(
            "/api/books",
            data={"language": "en", "provider": "elevenlabs"},
            files={"file": ("story.pdf", valid_pdf, "application/pdf")},
        )
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert "ELEVENLABS_API_KEY is empty" in detail


@pytest.mark.anyio
async def test_health_responds_quickly_during_book_processing():
    """Verify /health still responds quickly on the event loop while process_book runs worker threads."""
    from backend.app.services.pipeline import process_book

    book_id = str(uuid.uuid4())
    with SessionLocal() as db:
        book = Book(
            id=book_id,
            title="Concurrent Health Test Book",
            language="en",
            original_filename="original.pdf",
            status="pending",
        )
        db.add(book)
        db.commit()

    book_dir = create_book_storage_dir(book_id)
    pdf_path = book_dir / "original.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 dummy book content")

    # Simulate heavy/blocking CPU/disk extraction in a thread
    def slow_extract_pages(*args, **kwargs):
        time.sleep(0.35)
        return ["Chapter 1. The quick brown fox jumps over the lazy dog."], False

    async def fake_synthesize(text, out_path, voice):
        Path(out_path).touch()

    mock_mp3 = MagicMock()
    mock_mp3.info.length = 3.5

    try:
        with patch("backend.app.services.pipeline.extract_pages", side_effect=slow_extract_pages), \
             patch("backend.app.services.tts.EdgeTTSProvider.synthesize", side_effect=fake_synthesize), \
             patch("backend.app.services.pipeline.MP3", return_value=mock_mp3):

            # Start process_book in the background on the asyncio event loop
            proc_task = asyncio.create_task(process_book(book_id))

            # Allow process_book to yield and enter slow_extract_pages on the worker thread
            await asyncio.sleep(0.05)

            # Query /health concurrently while slow_extract_pages is executing
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                t0 = time.perf_counter()
                res = await ac.get("/health")
                elapsed = time.perf_counter() - t0

            assert res.status_code == 200
            assert res.json() == {"status": "ok"}
            # The health check should respond well under the 0.35s extraction block time
            assert elapsed < 0.25, f"Health check took {elapsed:.3f}s, expected < 0.25s"

            # Wait for processing task to finish
            await proc_task

        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            assert b is not None
            assert b.status == "ready"
    finally:
        if book_dir.exists():
            shutil.rmtree(book_dir, ignore_errors=True)
        with SessionLocal() as db:
            b = db.query(Book).filter(Book.id == book_id).first()
            if b:
                db.delete(b)
                db.commit()






