"""Database configuration and session management."""

import types
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.models import Base

# Build database path relative to backend folder
DB_PATH = Path(__file__).parent / "words.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False is required for SQLite when used with FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_db() -> types.GeneratorType:
    """Yield a database session for request lifecycle."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
