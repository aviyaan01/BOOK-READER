"""Unit tests for SQLAlchemy models, table initialization, and session dependency."""

import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.db import Base, get_db, init_db
from backend.app.models import Book, Chunk


def test_book_and_chunk_models(tmp_path):
    """Verify Book and Chunk creation, default values, and relational integrity."""
    test_db_path = tmp_path / "test.db"
    test_engine = create_engine(f"sqlite:///{test_db_path}")
    TestSessionLocal = sessionmaker(bind=test_engine)

    # Create tables
    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()
    try:
        # Create a test book
        book = Book(
            title="The Whispering Tree",
            language="en",
            original_filename="whispering_tree.pdf",
            voice="en-US-AriaNeural",
        )
        db.add(book)
        db.commit()
        db.refresh(book)

        # Check default values
        assert book.id is not None
        assert len(book.id) == 36  # Standard UUID length
        assert book.status == "uploaded"
        assert book.total_chunks == 0
        assert book.done_chunks == 0
        assert book.error_message is None
        assert book.created_at is not None

        # Add chunks
        chunk1 = Chunk(
            book_id=book.id,
            index=1,
            text="Once upon a time in an ancient forest.",
        )
        chunk2 = Chunk(
            book_id=book.id,
            index=2,
            text="A magical deer appeared under the stars.",
            audio_path="/storage/test/chunk_002.mp3",
            status="done",
            duration_seconds=3.45,
        )
        db.add_all([chunk1, chunk2])
        db.commit()
        db.refresh(book)

        # Verify relationship and ordering
        assert len(book.chunks) == 2
        assert book.chunks[0].index == 1
        assert book.chunks[0].status == "pending"
        assert book.chunks[1].index == 2
        assert book.chunks[1].status == "done"
        assert book.chunks[1].duration_seconds == 3.45

        # Verify cascade delete
        db.delete(book)
        db.commit()
        remaining_chunks = db.query(Chunk).filter_by(book_id=book.id).all()
        assert len(remaining_chunks) == 0

    finally:
        db.close()


def test_get_db_dependency():
    """Verify get_db helper yields an active SQLAlchemy Session and closes cleanly."""
    gen = get_db()
    session = next(gen)
    try:
        assert session.is_active
    finally:
        # Complete generator to close session
        try:
            next(gen)
        except StopIteration:
            pass


def test_init_db():
    """Verify init_db creates tables without error."""
    init_db()
