"""SQLAlchemy models for Book and Chunk entities."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from backend.app.db import Base


def generate_uuid() -> str:
    """Generate a standard UUID4 string."""
    return str(uuid.uuid4())


class Book(Base):
    """Database model representing an uploaded storybook."""

    __tablename__ = "books"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    language = Column(String(10), default="en", nullable=False)  # "bn" or "en"
    original_filename = Column(String(255), nullable=False)
    status = Column(
        String(20),
        default="uploaded",
        nullable=False,
    )  # "uploaded", "extracting", "generating", "ready", "failed"
    is_scanned = Column(Boolean, default=False, nullable=False)
    improve_with_ai = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    total_chunks = Column(Integer, default=0, nullable=False)
    done_chunks = Column(Integer, default=0, nullable=False)
    total_characters = Column(Integer, default=0, nullable=False)
    voice = Column(String(100), default="en-US-AriaNeural", nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    chunks = relationship(
        "Chunk",
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="Chunk.index",
    )


class Chunk(Base):
    """Database model representing an individual narratable sentence chunk."""

    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    book_id = Column(
        String(36),
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    index = Column(Integer, nullable=False, index=True)
    text = Column(Text, nullable=False)
    audio_path = Column(String(500), nullable=True)
    status = Column(
        String(20),
        default="pending",
        nullable=False,
    )  # "pending", "done", "failed"
    duration_seconds = Column(Float, nullable=True)

    book = relationship("Book", back_populates="chunks")
