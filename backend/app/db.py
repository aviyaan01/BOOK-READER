"""SQLAlchemy and SQLite database session configuration."""

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.config import DATABASE_URL

# SQLite engine configuration
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Create all database tables defined in SQLAlchemy metadata and apply column migrations."""
    import backend.app.models  # Ensure models are imported for metadata registration
    Base.metadata.create_all(bind=engine)

    # Lightweight migration for existing SQLite databases
    try:
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA table_info(books)").fetchall()
            existing_columns = [row[1] for row in result]
            if "is_scanned" not in existing_columns:
                conn.exec_driver_sql("ALTER TABLE books ADD COLUMN is_scanned BOOLEAN DEFAULT 0")
                conn.commit()
            if "improve_with_ai" not in existing_columns:
                conn.exec_driver_sql("ALTER TABLE books ADD COLUMN improve_with_ai BOOLEAN DEFAULT 0")
                conn.commit()
            if "total_characters" not in existing_columns:
                conn.exec_driver_sql("ALTER TABLE books ADD COLUMN total_characters INTEGER DEFAULT 0")
                conn.commit()
            if "provider" not in existing_columns:
                conn.exec_driver_sql("ALTER TABLE books ADD COLUMN provider VARCHAR(50) DEFAULT 'edge_tts'")
                conn.commit()
            if "multi_voice" not in existing_columns:
                conn.exec_driver_sql("ALTER TABLE books ADD COLUMN multi_voice BOOLEAN DEFAULT 0")
                conn.commit()
    except Exception:
        pass


def get_db() -> Generator[Session, None, None]:
    """Yield a transactional database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
