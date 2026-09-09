"""SQLAlchemy database models for the application."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""


class Word(Base):
    """Represents a dictionary word entry and its definition."""

    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    definition: Mapped[str] = mapped_column(String(500))

    def __repr__(self) -> str:
        """Return the string representation of a Word instance."""
        return f"<Word(word={self.word!r})>"


class User(Base):
    """Represents a registered user account."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        """Return the string representation of a User instance."""
        return f"<User(username={self.username!r})>"
