"""Database configuration and session management."""

import os
import types
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.models.models import Base

# Build database path relative to backend folder or read from env
DB_PATH = Path(__file__).parent.parent / "words.db"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

# check_same_thread=False is required for SQLite when used with FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
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
