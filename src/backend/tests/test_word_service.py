"""Unit tests for the word service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.backend.models import Base
from src.backend.word_service import add_word, get_random_word, get_words_count


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


def test_add_and_count_words(db_session):
    """Test adding words and counting them."""
    assert get_words_count(db_session) == 0

    add_word(db_session, "borborygme", "Bruit causé par les gaz intestinaux.")
    assert get_words_count(db_session) == 1

    add_word(db_session, "zinzolin", "D'une couleur violet rougeâtre.")
    assert get_words_count(db_session) == 2


def test_get_random_word(db_session):
    """Test retrieving a random word, including exclusion."""
    w1 = add_word(db_session, "mot1", "def1")
    w2 = add_word(db_session, "mot2", "def2")

    drawn = get_random_word(db_session)
    assert drawn is not None
    assert drawn.word in {"mot1", "mot2"}

    # Exclude mot1
    drawn_excluded = get_random_word(db_session, exclude_word_ids=[w1.id])
    assert drawn_excluded is not None
    assert drawn_excluded.id == w2.id

    # Exclude all
    drawn_none = get_random_word(db_session, exclude_word_ids=[w1.id, w2.id])
    assert drawn_none is None

