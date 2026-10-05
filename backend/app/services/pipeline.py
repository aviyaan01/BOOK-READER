"""Orchestration pipeline connecting PDF extraction, cleaning, chunking, and TTS synthesis."""

import os
import asyncio
from pathlib import Path
from typing import Optional, List
from mutagen.mp3 import MP3

from backend.app.db import SessionLocal
from backend.app.models import Book, Chunk
from backend.app.config import get_book_storage_dir
from backend.app.services.pdf_extract import extract_pages
from backend.app.services.text_clean import clean_pages, detect_language
from backend.app.services.chunker import chunk_text
from backend.app.services.tts.edge_tts_provider import EdgeTTSProvider


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

            # Update status to extracting
            book.status = "extracting"
            book.error_message = None
            db.commit()

            # Extract, clean, and chunk
            pages, _ = extract_pages(str(pdf_path))
            cleaned_text = clean_pages(pages)
            if not cleaned_text.strip():
                raise ValueError("No readable narrative text found in the PDF document.")

            if not book.language or book.language == "auto":
                book.language = detect_language(cleaned_text)

            text_chunks = chunk_text(cleaned_text, max_chars=1000)
            if not text_chunks:
                raise ValueError("Failed to create text chunks from document.")

            # Save chunks to DB if not already present
            existing_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.index).all()
            if not existing_chunks:
                for idx, txt in enumerate(text_chunks, start=1):
                    chunk = Chunk(
                        book_id=book.id,
                        index=idx,
                        text=txt,
                        status="pending",
                        audio_path=None,
                        duration_seconds=None,
                    )
                    db.add(chunk)
                db.commit()
                book.total_chunks = len(text_chunks)
            else:
                book.total_chunks = len(existing_chunks)

            # Count any chunks that are already completed from an earlier run
            all_chunks = db.query(Chunk).filter(Chunk.book_id == book_id).order_by(Chunk.index).all()
            done_count = sum(
                1 for c in all_chunks
                if c.status == "done" and c.audio_path and os.path.exists(c.audio_path)
            )
            book.done_chunks = done_count

            # 2. Transition status to generating
            book.status = "generating"
            db.commit()

            # Snapshot needed chunk data before closing session
            chunk_data_list = [
                (c.id, c.index, c.text, c.audio_path, c.status)
                for c in all_chunks
            ]
            voice = book.voice
            language = book.language

        # TTS Provider setup
        tts_provider = EdgeTTSProvider()
        chosen_voice = voice or (
            tts_provider.default_bangla_voice if language == "bn" else tts_provider.default_english_voice
        )

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
                    audio_info = MP3(out_path)
                    duration = round(audio_info.info.length, 2)
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
                            s_db.commit()
                    return
                except Exception:
                    pass

            # 2. Concurrency controlled by semaphore
            async with semaphore:
                try:
                    await tts_provider.synthesize(
                        text=chunk_text_content,
                        out_path=out_path,
                        voice=chosen_voice,
                    )

                    # 4. Get MP3 duration using mutagen
                    audio_info = MP3(out_path)
                    duration = round(audio_info.info.length, 2)

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
                            s_db.commit()

                except Exception:
                    # 5. Mark chunk as failed after retries and continue
                    async with db_lock:
                        with SessionLocal() as s_db:
                            c_rec = s_db.query(Chunk).filter(Chunk.id == chunk_id).first()
                            if c_rec:
                                c_rec.status = "failed"
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
                err_db.commit()
