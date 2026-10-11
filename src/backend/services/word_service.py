"""Service for dictionary word retrieval and management."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.backend.models.models import Word


def get_random_word(
    db: Session,
    exclude_word_ids: list[int] | None = None,
) -> Word | None:
    """Fetch a random word from the database, optionally excluding specific IDs.

    Args:
        db: Active database session.
        exclude_word_ids: List of word IDs to exclude (e.g. already played in current game).

    Returns:
        A random Word instance, or None if no available words match.
    """
    stmt = select(Word)
    if exclude_word_ids:
        stmt = stmt.where(Word.id.not_in(exclude_word_ids))

    stmt = stmt.order_by(func.random()).limit(1)
    return db.scalars(stmt).first()


def add_word(db: Session, word: str, definition: str) -> Word:
    """Add a new word and its definition to the dictionary.

    Args:
        db: Active database session.
        word: The word string.
        definition: The official definition.

    Returns:
        The created Word instance.
    """
    new_word = Word(word=word.strip(), definition=definition.strip())
    db.add(new_word)
    db.commit()
    db.refresh(new_word)
    return new_word


def get_words_count(db: Session) -> int:
    """Return the total number of words in the dictionary.

    Args:
        db: Active database session.

    Returns:
        Total count of words.
    """
    stmt = select(func.count(Word.id))
    return db.scalar(stmt) or 0
