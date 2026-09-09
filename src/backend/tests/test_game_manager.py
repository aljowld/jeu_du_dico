"""Unit tests for the game manager and game state machine."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.backend.game_manager import GameManager, GameState
from src.backend.models import Base
from src.backend.word_service import add_word


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


def test_full_game_loop_and_scoring(db_session):
    """Test full game round from lobby to reveal and scoring."""
    # Seed words
    add_word(db_session, "nycthémère", "Période de 24 heures comprenant un jour et une nuit.")
    add_word(db_session, "acrasie", "Agir à l'encontre de son meilleur jugement.")

    gm = GameManager()
    room, host = gm.create_room("Alice")
    assert room.state == GameState.LOBBY
    assert host.is_host is True

    # Player 2 joins
    bob = room.add_player("Bob")
    assert len(room.players) == 2

    # 1. Draw word
    assert room.draw_word(db_session) is True
    assert room.state == GameState.WORD_SELECTION
    first_word = room.current_word.word

    # 2. Reroll word
    assert room.reroll_word(db_session) is True
    second_word = room.current_word.word
    assert first_word != second_word

    # 3. Start writing
    assert room.start_writing() is True
    assert room.state == GameState.WRITING

    # 4. Submit definitions
    # Alice submits
    assert room.submit_definition(host.id, "Une plante rare des Alpes.") is True
    assert room.state == GameState.WRITING  # Bob hasn't submitted yet

    # Bob submits -> triggers voting
    assert room.submit_definition(bob.id, "Un instrument de navigation ancien.") is True
    assert room.state == GameState.VOTING
    assert len(room.options) == 3  # 1 real + 2 fakes

    # Identify options
    real_opt = next(opt for opt in room.options if opt.author_id is None)
    alice_opt = next(opt for opt in room.options if opt.author_id == host.id)
    bob_opt = next(opt for opt in room.options if opt.author_id == bob.id)

    # 5. Voting
    # Player cannot vote for their own definition
    assert room.submit_vote(host.id, alice_opt.id) is False

    # Alice votes for the REAL definition (Alice gets 1 point)
    assert room.submit_vote(host.id, real_opt.id) is True
    assert room.state == GameState.VOTING

    # Bob votes for ALICE's fake definition (Alice gets 1 point for fooling Bob)
    assert room.submit_vote(bob.id, alice_opt.id) is True

    # State transitions to REVEAL
    assert room.state == GameState.REVEAL

    # 6. Check scoring:
    # Alice: +1 for finding the real def, +1 for Bob voting on her def = 2 points
    # Bob: 0 points (voted wrong, no one voted for his def)
    assert host.score == 2
    assert bob.score == 0

    results = room.round_results
    assert results is not None
    assert results["points_awarded"][host.id] == 2
    assert results["points_awarded"][bob.id] == 0

