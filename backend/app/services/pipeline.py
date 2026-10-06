"""Orchestration pipeline connecting PDF extraction, cleaning, chunking, and TTS synthesis."""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from mutagen.mp3 import MP3

from backend.app.db import SessionLocal
from backend.app.models import Book, Chunk
from backend.app.config import get_book_storage_dir
from backend.app.services.pdf_extract import extract_pages
from backend.app.services.text_clean import clean_pages, detect_language
from backend.app.services.llm_clean import clean_text_with_llm
from backend.app.services.chunker import chunk_text
from backend.app.services.tts import get_tts_provider
from backend.app.services.voice_cast import (
    build_voice_segments,
    get_voice_pool,
)
from backend.app.services.tts.multivoice import synthesize_multivoice_chunk


def _load_persisted_cast(book: Book) -> Dict[str, str]:
    """Load existing cast dictionary from Book model if present."""
    saved_cast = getattr(book, "voice_cast", None)
    if isinstance(saved_cast, dict):
        return dict(saved_cast)
    if isinstance(saved_cast, str) and saved_cast.strip():
        try:
            parsed = json.loads(saved_cast)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def _read_mp3_duration(path: str) -> float:
    """Read duration in seconds from an MP3 file using mutagen."""
    audio_info = MP3(path)
    return round(audio_info.info.length, 2)


async def process_book(book_id: str) -> None:
    """Execute end-to-end processing of a storybook PDF.

    Flow:
    1. Sets status to 'extracting', extracts pages, cleans, chunks, and saves to DB.
    2. Sets status to 'generating', synthesizes chunks up to 3 concurrently.
    3. Skips chunks that already have audio for crash-resilience.
    4. Calculates and stores the MP3 duration of each chunk using mutagen.
    5. Marks individual failed chunks as 'failed' and continues.
    6. Sets book status to 'ready' if all chunks succeed, or 'failed' if errors occurred.
    7. Catches all exceptions and records them in book.error_message.
    """
    use_multi_voice = False
    cast = {}
    try:
        # 1. Fetch book record and initialize extraction
        with SessionLocal() as db:
            book = db.query(Book).filter(Book.id == book_id).first()
            if not book:
                raise ValueError(f"Book with id '{book_id}' does not exist.")

            book_dir = get_book_storage_dir(book_id)

            # Locate source PDF (prefers original.pdf)
            pdf_path = book_dir / "original.pdf"
            if not pdf_path.exists():
                pdf_path = book_dir / "source.pdf"
            if not pdf_path.exists():
                pdf_path = book_dir / book.original_filename
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF source file not found for book '{book_id}'.")

            # Extract plain values to avoid passing ORM objects across threads
            pdf_path_str = str(pdf_path)
            book_language = book.language or "en"
            improve_ai = bool(getattr(book, "improve_with_ai", False))
            voice = book.voice
            language = book.language
            provider_name = book.provider
            use_multi_voice = bool(getattr(book, "multi_voice", False))
            cast = _load_persisted_cast(book)

            # Update status to extracting
            book.status = "extracting"
            book.error_message = None
            db.commit()

        def on_scanned_found():
            with SessionLocal() as s_db:
                b_rec = s_db.query(Book).filter(Book.id == book_id).first()
                if b_rec:
                    b_rec.is_scanned = True
                    s_db.commit()

        # Extract pages in a worker thread to keep the asyncio event loop responsive
        pages, is_scanned_flag = await asyncio.to_thread(
            extract_pages,
            pdf_path_str,
            language=book_language,
            on_scanned_detected=on_scanned_found,
        )
        if is_scanned_flag:
            with SessionLocal() as db:
                b_rec = db.query(Book).filter(Book.id == book_id).first()
                if b_rec:
                    b_rec.is_scanned = True
                    db.commit()

        # Clean pages in a worker thread to keep the asyncio event loop responsive
        cleaned_text = await asyncio.to_thread(clean_pages, pages)
        if not cleaned_text.strip():
            raise ValueError("No readable narrative text found in the PDF document.")

        # Optional LLM cleanup step if enabled by user
        if improve_ai:
            cleaned_text = await asyncio.to_thread(clean_text_with_llm, cleaned_text)

        # Store total character count and language on Book after extraction and before TTS
        total_chars = len(cleaned_text)
        detected_lang = detect_language(cleaned_text) if not language or language == "auto" else language

        with SessionLocal() as db:
            b_rec = db.query(Book).filter(Book.id == book_id).first()
            if b_rec:
                b_rec.total_characters = total_chars
                if not b_rec.language or b_rec.language == "auto":
                    b_rec.language = detected_lang
                    language = detected_lang
                db.commit()

        text_chunks = await asyncio.to_thread(chunk_text, cleaned_text, max_chars=1000)
        if not text_chunks:
            raise ValueError("Failed to create text chunks from document.")

        # Save chunks to DB if not already present
        with SessionLocal() as db:
            existing_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.index).all()
            if not existing_chunks:
                for idx, txt in enumerate(text_chunks, start=1):
                    chunk = Chunk(
                        book_id=book_id,
                        index=idx,
                        text=txt,
                        status="pending",
                        audio_path=None,
                        duration_seconds=None,
                    )
                    db.add(chunk)
                b_rec = db.query(Book).filter(Book.id == book_id).first()
                if b_rec:
                    b_rec.total_chunks = len(text_chunks)
                db.commit()
            else:
                b_rec = db.query(Book).filter(Book.id == book_id).first()
                if b_rec:
                    b_rec.total_chunks = len(existing_chunks)
                    if not b_rec.total_characters:
                        b_rec.total_characters = sum(len(c.text) for c in existing_chunks)
                db.commit()

            # Count any chunks that are already completed from an earlier run
            all_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.index).all()
            done_count = sum(
                1 for c in all_chunks
                if c.status == "done" and c.audio_path and os.path.exists(c.audio_path)
            )
            b_rec = db.query(Book).filter(Book.id == book_id).first()
            if b_rec:
                b_rec.done_chunks = done_count
                b_rec.status = "generating"
            db.commit()

            # Snapshot needed chunk data before closing session
            chunk_data_list = [
                (c.id, c.index, c.text, c.audio_path, c.status)
                for c in all_chunks
            ]

        # TTS Provider setup
        tts_provider = get_tts_provider(provider_name)
        if getattr(tts_provider, "provider_name", "") == "elevenlabs":
            chosen_voice = tts_provider.resolve_voice(voice)
        else:
            chosen_voice = voice or (
                getattr(tts_provider, "default_bangla_voice", "bn-BD-NabanitaNeural")
                if language == "bn"
                else getattr(tts_provider, "default_english_voice", "en-US-AriaNeural")
            )

        # Multi-voice: shared cast dict and voice pool for deterministic assignment
        voice_pool = get_voice_pool(language)
        narrator_voice = chosen_voice  # narrator always gets the user's selected voice

        semaphore = asyncio.Semaphore(3)
        db_lock = asyncio.Lock()

        async def synthesize_single_chunk(
            chunk_id: str,
            chunk_index: int,
            chunk_text_content: str,
            audio_path_val: Optional[str],
            status_val: str,
        ) -> None:
            """Synthesize audio for an individual chunk with concurrency gating and duration calculation."""
            out_file = book_dir / f"chunk_{chunk_index:03d}.mp3"
            out_path = str(out_file)

            # 3. Skip chunks that already have valid audio on disk
            if status_val == "done" and audio_path_val and os.path.exists(audio_path_val):
                return

            # Check if file exists on disk from an interrupted process
            if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
                try:
                    duration = await asyncio.to_thread(_read_mp3_duration, out_path)
                    async with db_lock:
                        with SessionLocal() as s_db:
                            c_rec = s_db.query(Chunk).filter(Chunk.id == chunk_id).first()
                            b_rec = s_db.query(Book).filter(Book.id == book_id).first()
                            if c_rec:
                                c_rec.status = "done"
                                c_rec.audio_path = out_path
                                c_rec.duration_seconds = duration
                            if b_rec:
                                b_rec.done_chunks = s_db.query(Chunk).filter(
                                    Chunk.book_id == book_id, Chunk.status == "done"
                                ).count()
                                if use_multi_voice:
                                    b_rec.voice_cast = dict(cast)
                            s_db.commit()
                    return
                except Exception:
                    pass

            # 2. Concurrency controlled by semaphore
            async with semaphore:
                try:
                    if use_multi_voice:
                        # Multi-voice path: tag sentences with Claude, synthesize per speaker
                        segments = build_voice_segments(
                            text=chunk_text_content,
                            cast=cast,
                            voice_pool=voice_pool,
                            narrator_voice=narrator_voice,
                        )
                        await synthesize_multivoice_chunk(
                            segments=segments,
                            tts_provider=tts_provider,
                            out_path=out_path,
                        )
                    else:
                        await tts_provider.synthesize(
                            text=chunk_text_content,
                            out_path=out_path,
                            voice=chosen_voice,
                        )

                    # 4. Get MP3 duration using mutagen in a worker thread
                    duration = await asyncio.to_thread(_read_mp3_duration, out_path)

                    # Update chunk and book done_chunks
                    async with db_lock:
                        with SessionLocal() as s_db:
                            c_rec = s_db.query(Chunk).filter(Chunk.id == chunk_id).first()
                            b_rec = s_db.query(Book).filter(Book.id == book_id).first()
                            if c_rec:
                                c_rec.status = "done"
                                c_rec.audio_path = out_path
                                c_rec.duration_seconds = duration
                            if b_rec:
                                b_rec.done_chunks = s_db.query(Chunk).filter(
                                    Chunk.book_id == book_id, Chunk.status == "done"
                                ).count()
                                if use_multi_voice:
                                    b_rec.voice_cast = dict(cast)
                            s_db.commit()

                except Exception:
                    # 5. Mark chunk as failed after retries and continue
                    async with db_lock:
                        with SessionLocal() as s_db:
                            c_rec = s_db.query(Chunk).filter(Chunk.id == chunk_id).first()
                            b_rec = s_db.query(Book).filter(Book.id == book_id).first()
                            if c_rec:
                                c_rec.status = "failed"
                            if b_rec and use_multi_voice:
                                b_rec.voice_cast = dict(cast)
                            s_db.commit()

        # Run up to 3 chunks concurrently in order
        tasks = [
            synthesize_single_chunk(cid, cidx, ctxt, cpath, cstat)
            for cid, cidx, ctxt, cpath, cstat in chunk_data_list
        ]
        await asyncio.gather(*tasks)

        # 5. Evaluate final book status
        with SessionLocal() as final_db:
            final_book = final_db.query(Book).filter(Book.id == book_id).first()
            final_chunks = final_db.query(Chunk).filter(Chunk.book_id == book_id).all()

            total = len(final_chunks)
            done = sum(1 for c in final_chunks if c.status == "done")
            failed = sum(1 for c in final_chunks if c.status == "failed")

            if final_book:
                final_book.total_chunks = total
                final_book.done_chunks = done
                if not getattr(final_book, "total_characters", 0) and total_chars:
                    final_book.total_characters = total_chars
                if use_multi_voice:
                    final_book.voice_cast = dict(cast)
                if failed == 0 and done == total and total > 0:
                    final_book.status = "ready"
                    final_book.error_message = None
                else:
                    final_book.status = "failed"
                    final_book.error_message = f"{failed} chunk(s) failed to synthesize audio."
                final_db.commit()

    except Exception as exc:
        # Catch all exceptions and record them in book.error_message
        with SessionLocal() as err_db:
            err_book = err_db.query(Book).filter(Book.id == book_id).first()
            if err_book:
                err_book.status = "failed"
                err_book.error_message = str(exc)
                if use_multi_voice and cast:
                    err_book.voice_cast = dict(cast)
                err_db.commit()


async def retry_failed_chunks(book_id: str) -> int:
    """Regenerate only failed or uncompleted chunks for a book without repeating PDF extraction.

    Args:
        book_id: UUID string of the book.

    Returns:
        Number of chunks submitted for regeneration.
    """
    use_multi_voice = False
    cast = {}
    try:
        with SessionLocal() as db:
            book = db.query(Book).filter(Book.id == book_id).first()
            if not book:
                raise ValueError(f"Book with id '{book_id}' does not exist.")

            book_dir = get_book_storage_dir(book_id)

            # Find failed or uncompleted chunks (never regenerate chunks that are already done)
            failed_chunks = db.query(Chunk).filter(
                Chunk.book_id == book_id,
                Chunk.status != "done",
            ).order_by(Chunk.index).all()

            if not failed_chunks:
                # All chunks are done; mark book ready if needed
                all_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).all()
                if all_chunks and all(c.status == "done" for c in all_chunks):
                    book.status = "ready"
                    book.error_message = None
                    db.commit()
                return 0

            # Reset status of targeted chunks to pending
            for c in failed_chunks:
                c.status = "pending"
                c.audio_path = None
                c.duration_seconds = None

            book.status = "generating"
            book.error_message = None
            db.commit()

            chunk_data_list = [
                (c.id, c.index, c.text)
                for c in failed_chunks
            ]
            voice = book.voice
            language = book.language
            provider_name = book.provider
            use_multi_voice = bool(getattr(book, "multi_voice", False))
            cast: dict = _load_persisted_cast(book)

        tts_provider = get_tts_provider(provider_name)
        if getattr(tts_provider, "provider_name", "") == "elevenlabs":
            chosen_voice = tts_provider.resolve_voice(voice)
        else:
            chosen_voice = voice or (
                getattr(tts_provider, "default_bangla_voice", "bn-BD-NabanitaNeural")
                if language == "bn"
                else getattr(tts_provider, "default_english_voice", "en-US-AriaNeural")
            )

        voice_pool = get_voice_pool(language)
        narrator_voice = chosen_voice

        semaphore = asyncio.Semaphore(3)
        db_lock = asyncio.Lock()

        async def retry_single_chunk(chunk_id: str, chunk_index: int, chunk_text: str) -> None:
            out_file = book_dir / f"chunk_{chunk_index:03d}.mp3"
            out_path = str(out_file)

            async with semaphore:
                try:
                    if use_multi_voice:
                        segments = build_voice_segments(
                            text=chunk_text,
                            cast=cast,
                            voice_pool=voice_pool,
                            narrator_voice=narrator_voice,
                        )
                        await synthesize_multivoice_chunk(
                            segments=segments,
                            tts_provider=tts_provider,
                            out_path=out_path,
                        )
                    else:
                        await tts_provider.synthesize(
                            text=chunk_text,
                            out_path=out_path,
                            voice=chosen_voice,
                        )
                    duration = await asyncio.to_thread(_read_mp3_duration, out_path)

                    async with db_lock:
                        with SessionLocal() as s_db:
                            c_rec = s_db.query(Chunk).filter(Chunk.id == chunk_id).first()
                            b_rec = s_db.query(Book).filter(Book.id == book_id).first()
                            if c_rec:
                                c_rec.status = "done"
                                c_rec.audio_path = out_path
                                c_rec.duration_seconds = duration
                            if b_rec:
                                b_rec.done_chunks = s_db.query(Chunk).filter(
                                    Chunk.book_id == book_id, Chunk.status == "done"
                                ).count()
                                if use_multi_voice:
                                    b_rec.voice_cast = dict(cast)
                            s_db.commit()
                except Exception:
                    async with db_lock:
                        with SessionLocal() as s_db:
                            c_rec = s_db.query(Chunk).filter(Chunk.id == chunk_id).first()
                            b_rec = s_db.query(Book).filter(Book.id == book_id).first()
                            if c_rec:
                                c_rec.status = "failed"
                            if b_rec and use_multi_voice:
                                b_rec.voice_cast = dict(cast)
                            s_db.commit()

        tasks = [
            retry_single_chunk(cid, cidx, ctxt)
            for cid, cidx, ctxt in chunk_data_list
        ]
        await asyncio.gather(*tasks)

        # Final status evaluation
        with SessionLocal() as final_db:
            final_book = final_db.query(Book).filter(Book.id == book_id).first()
            final_chunks = final_db.query(Chunk).filter(Chunk.book_id == book_id).all()
            total = len(final_chunks)
            done = sum(1 for c in final_chunks if c.status == "done")
            failed = sum(1 for c in final_chunks if c.status == "failed")

            if final_book:
                final_book.total_chunks = total
                final_book.done_chunks = done
                if use_multi_voice:
                    final_book.voice_cast = dict(cast)
                if failed == 0 and done == total and total > 0:
                    final_book.status = "ready"
                    final_book.error_message = None
                else:
                    final_book.status = "failed"
                    final_book.error_message = f"{failed} chunk(s) failed to synthesize audio."
                final_db.commit()

        return len(chunk_data_list)

    except Exception as exc:
        with SessionLocal() as err_db:
            err_book = err_db.query(Book).filter(Book.id == book_id).first()
            if err_book:
                err_book.status = "failed"
                err_book.error_message = str(exc)
                if 'use_multi_voice' in locals() and use_multi_voice and 'cast' in locals():
                    err_book.voice_cast = dict(cast)
                err_db.commit()
        return 0
