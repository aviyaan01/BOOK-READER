"""Unit and integration tests for process_book pipeline."""

import os
import json
import shutil
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from mutagen.mp3 import MP3

from backend.app.db import SessionLocal, Base, engine, init_db
from backend.app.models import Book, Chunk
from backend.app.config import get_book_storage_dir, create_book_storage_dir
from backend.app.services.pipeline import process_book, retry_failed_chunks


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database tables and column migrations are initialized before tests."""
    init_db()
    yield


def test_process_book_missing_pdf():
    """Verify missing PDF file sets status to 'failed' and populates book.error_message."""
    async def run():
        with SessionLocal() as db:
            book = Book(
                title="Missing PDF Book",
                language="en",
                original_filename="does_not_exist.pdf",
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            book_id = book.id

        await process_book(book_id)

        with SessionLocal() as db:
            updated = db.query(Book).filter(Book.id == book_id).first()
            assert updated is not None
            assert updated.status == "failed"
            assert updated.error_message is not None
            assert "not found" in updated.error_message.lower()

            # Clean up
            db.delete(updated)
            db.commit()

    asyncio.run(run())


def test_process_book_success_and_resume():
    """Verify full end-to-end execution of process_book and crash-resumption capability."""
    async def run():
        sample_source = Path("sample_books/english_story_whispering_tree.pdf")
        if not sample_source.exists():
            pytest.skip("Sample PDF not found.")

        # 1. Setup book record
        with SessionLocal() as db:
            book = Book(
                title="Whispering Tree Pipeline Test",
                language="en",
                original_filename="english_story_whispering_tree.pdf",
                voice="en-US-AriaNeural",
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            book_id = book.id

        # Place source PDF in storage/<book_id>/source.pdf
        book_dir = create_book_storage_dir(book_id)
        target_pdf = book_dir / "source.pdf"
        shutil.copyfile(sample_source, target_pdf)

        try:
            # 2. Run process_book
            await process_book(book_id)

            with SessionLocal() as db:
                processed_book = db.query(Book).filter(Book.id == book_id).first()
                assert processed_book.status == "ready"
                assert processed_book.error_message is None
                assert processed_book.total_chunks > 0
                assert processed_book.done_chunks == processed_book.total_chunks
                assert processed_book.total_characters > 0

                chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.index).all()
                assert len(chunks) == processed_book.total_chunks

                for c in chunks:
                    assert c.status == "done"
                    assert c.audio_path is not None
                    assert os.path.exists(c.audio_path)
                    # Duration verified from mutagen
                    assert c.duration_seconds is not None
                    assert c.duration_seconds > 0.5
                    # Formatted as chunk_XXX.mp3
                    assert Path(c.audio_path).name == f"chunk_{c.index:03d}.mp3"

            # 3. Test resume: run again without modifying files
            await process_book(book_id)

            with SessionLocal() as db:
                resumed_book = db.query(Book).filter(Book.id == book_id).first()
                assert resumed_book.status == "ready"
                assert resumed_book.done_chunks == resumed_book.total_chunks

        finally:
            # Clean up test artifacts
            with SessionLocal() as db:
                b = db.query(Book).filter(Book.id == book_id).first()
                if b:
                    db.delete(b)
                    db.commit()
            if book_dir.exists():
                shutil.rmtree(book_dir, ignore_errors=True)

    asyncio.run(run())


def test_process_bangla_book():
    """Verify process_book correctly processes a Bangla PDF with default Bangla voice."""
    async def run():
        sample_source = Path("sample_books/bangla_story_blue_dove.pdf")
        if not sample_source.exists():
            pytest.skip("Bangla sample PDF not found.")

        with SessionLocal() as db:
            book = Book(
                title="ছোট্ট নীল ঘুঘু",
                language="bn",
                original_filename="bangla_story_blue_dove.pdf",
                voice="bn-BD-NabanitaNeural",
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            book_id = book.id

        book_dir = create_book_storage_dir(book_id)
        target_pdf = book_dir / "source.pdf"
        shutil.copyfile(sample_source, target_pdf)

        try:
            await process_book(book_id)

            with SessionLocal() as db:
                processed = db.query(Book).filter(Book.id == book_id).first()
                assert processed.status == "ready"
                assert processed.total_chunks > 0
                assert processed.done_chunks == processed.total_chunks

                chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.index).all()
                for c in chunks:
                    assert c.status == "done"
                    assert os.path.exists(c.audio_path)
                    assert c.duration_seconds > 0.5
        finally:
            with SessionLocal() as db:
                b = db.query(Book).filter(Book.id == book_id).first()
                if b:
                    db.delete(b)
                    db.commit()
            if book_dir.exists():
                shutil.rmtree(book_dir, ignore_errors=True)

    asyncio.run(run())


def test_process_book_with_llm_clean():
    """Verify clean_text_with_llm is triggered during pipeline processing when improve_with_ai is True."""
    async def run():
        sample_source = Path("sample_books/english_story_whispering_tree.pdf")
        if not sample_source.exists():
            pytest.skip("Sample PDF not found.")

        with SessionLocal() as db:
            book = Book(
                title="AI Cleaned Storybook",
                language="en",
                original_filename="english_story_whispering_tree.pdf",
                voice="en-US-AriaNeural",
                improve_with_ai=True,
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            book_id = book.id

        book_dir = create_book_storage_dir(book_id)
        target_pdf = book_dir / "source.pdf"
        shutil.copyfile(sample_source, target_pdf)

        try:
            from unittest.mock import patch
            with patch("backend.app.services.pipeline.clean_text_with_llm", side_effect=lambda txt: txt) as mock_llm_clean:
                await process_book(book_id)
                mock_llm_clean.assert_called_once()
        finally:
            with SessionLocal() as db:
                b = db.query(Book).filter(Book.id == book_id).first()
                if b:
                    db.delete(b)
                    db.commit()
            if book_dir.exists():
                shutil.rmtree(book_dir, ignore_errors=True)

    asyncio.run(run())


def test_process_book_stores_character_count_before_tts():
    """Verify total_characters is calculated and stored on Book before TTS synthesis starts."""
    async def run():
        sample_source = Path("sample_books/english_story_whispering_tree.pdf")
        if not sample_source.exists():
            pytest.skip("Sample PDF not found.")

        with SessionLocal() as db:
            book = Book(
                title="Char Count Pre-TTS Test",
                language="en",
                original_filename="english_story_whispering_tree.pdf",
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            book_id = book.id

        book_dir = create_book_storage_dir(book_id)
        target_pdf = book_dir / "source.pdf"
        shutil.copyfile(sample_source, target_pdf)

        captured_chars_at_tts_start = []

        try:
            from unittest.mock import patch

            async def fake_synthesize(text, out_path, voice):
                # When TTS synthesize is called, check what is in the DB
                with SessionLocal() as check_db:
                    b = check_db.query(Book).filter(Book.id == book_id).first()
                    if b:
                        captured_chars_at_tts_start.append(b.total_characters)
                # Create small dummy mp3
                Path(out_path).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xFF\xFB\x90\x44" * 30)

            with patch("backend.app.services.tts.edge_tts_provider.EdgeTTSProvider.synthesize", side_effect=fake_synthesize):
                await process_book(book_id)

            assert len(captured_chars_at_tts_start) > 0, "TTS should have been called"
            # Every call to synthesize saw total_characters already stored and > 0!
            for char_count in captured_chars_at_tts_start:
                assert char_count > 0, "Character count must be stored on Book before TTS begins"

            with SessionLocal() as db:
                final_book = db.query(Book).filter(Book.id == book_id).first()
                assert final_book.total_characters == captured_chars_at_tts_start[0]

        finally:
            with SessionLocal() as db:
                b = db.query(Book).filter(Book.id == book_id).first()
                if b:
                    db.delete(b)
                    db.commit()
            if book_dir.exists():
                shutil.rmtree(book_dir, ignore_errors=True)

    asyncio.run(run())


def test_retry_failed_chunks_multi_voice_preserves_cast():
    """Verify retry_failed_chunks uses multi-voice synthesis and preserves existing character cast."""
    async def run():
        # 1. Setup book with multi_voice=True and pre-existing voice_cast
        with SessionLocal() as db:
            book = Book(
                title="Multi-Voice Retry Test Book",
                language="en",
                original_filename="multivoice_retry.pdf",
                voice="en-US-AriaNeural",
                multi_voice=True,
                voice_cast={
                    "narrator": "en-US-AriaNeural",
                    "fox": "en-US-ChristopherNeural",
                },
                status="failed",
                error_message="1 chunk(s) failed to synthesize audio.",
                total_chunks=2,
                done_chunks=1,
            )
            db.add(book)
            db.commit()
            db.refresh(book)
            book_id = book.id

            book_dir = create_book_storage_dir(book_id)

            c0 = Chunk(
                book_id=book_id,
                index=0,
                text="The narrator introduced the woods.",
                status="done",
                audio_path=str(book_dir / "chunk_000.mp3"),
                duration_seconds=4.0,
            )
            c1 = Chunk(
                book_id=book_id,
                index=1,
                text="The fox grinned. 'I have a plan!' said the fox.",
                status="failed",
                audio_path=None,
                duration_seconds=None,
            )
            db.add_all([c0, c1])
            db.commit()

        captured_multivoice_calls = []

        async def fake_multivoice_chunk(segments, tts_provider, out_path):
            captured_multivoice_calls.append({
                "segments": segments,
                "tts_provider": tts_provider,
                "out_path": out_path,
            })
            Path(out_path).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xFF\xFB\x90\x44" * 30)

        mock_tts_provider = MagicMock()
        mock_tts_provider.provider_name = "edge_tts"
        mock_tts_provider.synthesize = AsyncMock()

        mock_mp3 = MagicMock()
        mock_mp3.info.length = 6.25

        claude_tagged_output = [
            {"sentence": "The fox grinned.", "speaker": "narrator"},
            {"sentence": "'I have a plan!' said the fox.", "speaker": "fox"},
        ]

        try:
            with patch("backend.app.services.voice_cast.tag_sentences_with_claude", return_value=claude_tagged_output) as mock_claude, \
                 patch("backend.app.services.pipeline.get_tts_provider", return_value=mock_tts_provider), \
                 patch("backend.app.services.pipeline.synthesize_multivoice_chunk", side_effect=fake_multivoice_chunk) as mock_multi_synth, \
                 patch("backend.app.services.pipeline.MP3", return_value=mock_mp3):

                retried_count = await retry_failed_chunks(book_id)

            # 1. Only chunk 1 was retried
            assert retried_count == 1

            # 2. Claude tagging was called with chunk 1 text
            mock_claude.assert_called_once()
            assert "The fox grinned" in mock_claude.call_args[0][0]

            # 3. Assert the multi-voice path was used (synthesize_multivoice_chunk called, single-voice synthesize NOT called)
            mock_multi_synth.assert_called_once()
            mock_tts_provider.synthesize.assert_not_called()

            # 4. Assert that the same voice cast was applied
            assert len(captured_multivoice_calls) == 1
            call_segments = captured_multivoice_calls[0]["segments"]
            assert len(call_segments) == 2
            # narrator sentence received narrator voice
            assert call_segments[0] == ("The fox grinned.", "en-US-AriaNeural")
            # fox sentence received the pre-existing voice assigned to fox: "en-US-ChristopherNeural"
            assert call_segments[1] == ("'I have a plan!' said the fox.", "en-US-ChristopherNeural")

            # 5. Verify database updates
            with SessionLocal() as db:
                updated_book = db.query(Book).filter(Book.id == book_id).first()
                assert updated_book.status == "ready"
                assert updated_book.error_message is None
                assert updated_book.done_chunks == 2
                assert updated_book.voice_cast is not None

                cast_dict = updated_book.voice_cast if isinstance(updated_book.voice_cast, dict) else json.loads(updated_book.voice_cast)
                assert cast_dict.get("fox") == "en-US-ChristopherNeural"
                assert cast_dict.get("narrator") == "en-US-AriaNeural"

                c1_db = db.query(Chunk).filter(Chunk.book_id == book_id, Chunk.index == 1).first()
                assert c1_db.status == "done"
                assert c1_db.audio_path is not None
                assert c1_db.duration_seconds == 6.25

        finally:
            with SessionLocal() as db:
                b = db.query(Book).filter(Book.id == book_id).first()
                if b:
                    db.delete(b)
                    db.commit()
            if book_dir.exists():
                shutil.rmtree(book_dir, ignore_errors=True)

    asyncio.run(run())


