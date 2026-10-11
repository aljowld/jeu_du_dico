"""Unit tests for the game manager and game state machine."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.backend.core.constants import (
    DEFAULT_WRITING_TIME,
    MAX_PLAYERS,
    MAX_WRITING_TIME,
    MIN_WRITING_TIME,
)
from src.backend.game.game_manager import GameManager, GameState
from src.backend.models.models import Base
from src.backend.services.word_service import add_word


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


def test_room_settings_writing_time(db_session):
    """Test updating the writing time limit with validation."""
    gm = GameManager()
    room, _host = gm.create_room("Alice")

    # Check default
    assert room.writing_time_limit == DEFAULT_WRITING_TIME
    assert room.writing_time_limit == 60

    # Valid step updates
    assert room.update_writing_time_limit(65) is True
    assert room.writing_time_limit == 65

    assert room.update_writing_time_limit(MIN_WRITING_TIME) is True
    assert room.writing_time_limit == 10

    assert room.update_writing_time_limit(MAX_WRITING_TIME) is True
    assert room.writing_time_limit == 300

    # Invalid below min
    assert room.update_writing_time_limit(5) is False
    assert room.writing_time_limit == 300

    # Invalid above max
    assert room.update_writing_time_limit(305) is False
    assert room.writing_time_limit == 300

    # Invalid step
    assert room.update_writing_time_limit(62) is False
    assert room.writing_time_limit == 300

    # Cannot update once game starts
    add_word(db_session, "testword", "test definition")
    room.draw_word(db_session)
    assert room.state == GameState.WORD_SELECTION
    assert room.update_writing_time_limit(70) is False


def test_room_settings_max_rounds():
    """Test updating the max rounds setting with validation."""
    gm = GameManager()
    room, _host = gm.create_room("Alice")

    from src.backend.core.constants import DEFAULT_ROUNDS, MAX_ROUNDS, MIN_ROUNDS

    # Check default
    assert room.max_rounds == DEFAULT_ROUNDS

    # Valid updates
    assert room.update_max_rounds(3) is True
    assert room.max_rounds == 3

    assert room.update_max_rounds(MIN_ROUNDS) is True
    assert room.max_rounds == MIN_ROUNDS

    assert room.update_max_rounds(MAX_ROUNDS) is True
    assert room.max_rounds == MAX_ROUNDS

    # Invalid below min
    assert room.update_max_rounds(0) is False
    assert room.max_rounds == MAX_ROUNDS

    # Invalid above max
    assert room.update_max_rounds(21) is False
    assert room.max_rounds == MAX_ROUNDS


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
    assert room.writing_started_at is not None

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

    # 7. End game
    assert room.end_game() is True
    assert room.state == GameState.GAME_OVER

    # 8. Return to lobby
    assert room.return_to_lobby() is True
    assert room.state == GameState.LOBBY
    assert room.round_number == 0
    assert len(room.used_word_ids) == 0
    assert host.score == 0
    assert bob.score == 0


def test_writing_timeout_and_empty_definition_fallback(db_session):
    """Test auto-validation of unsubmitted and empty definitions at writing timeout."""
    add_word(db_session, "acrasie", "Agir à l'encontre de son meilleur jugement.")

    gm = GameManager()
    room, host = gm.create_room("Alice")
    bob = room.add_player("Bob")
    charlie = room.add_player("Charlie")

    room.draw_word(db_session)
    room.start_writing()
    assert room.state == GameState.WRITING

    # Alice submitted a definition manually
    assert room.submit_definition(host.id, "Une faiblesse de volonté.") is True
    # Duplicate submission is rejected
    assert room.submit_definition(host.id, "Une autre définition.") is False

    # Bob sends an empty definition (e.g. from timed-out empty textarea)
    assert room.submit_definition(bob.id, "") is True
    assert room.submitted_definitions[bob.id] == "(Aucune proposition)"

    # Charlie never submitted anything before timeout
    assert charlie.id not in room.submitted_definitions

    # Timeout occurs
    assert room.timeout_writing() is True
    assert room.state == GameState.VOTING

    # Charlie got auto-filled with fallback
    assert room.submitted_definitions[charlie.id] == "(Aucune proposition)"

    # Check that all options exist in room.options (1 real + 3 players)
    assert len(room.options) == 4


def test_max_players_limit():
    """Test that room accepts at most MAX_PLAYERS (10)."""
    gm = GameManager()
    room, _host = gm.create_room("Player 1")
    assert len(room.players) == 1

    for i in range(2, MAX_PLAYERS + 1):
        player = room.add_player(f"Player {i}")
        assert player is not None
        assert len(room.players) == i

    assert len(room.players) == MAX_PLAYERS

    # Attempting to add the 11th player must return None
    overflow_player = room.add_player("Player 11")
    assert overflow_player is None
    assert len(room.players) == MAX_PLAYERS


def test_remove_player_and_host_transfer():
    """Test removing a player, host transfer, and empty room cleanup."""
    gm = GameManager()
    room, host = gm.create_room("Alice")
    bob = room.add_player("Bob")
    assert bob is not None

    # Alice is host
    assert room.host_id == host.id
    assert host.is_host is True
    assert bob.is_host is False

    # Remove host Alice -> host transferred to Bob
    assert room.remove_player(host.id) is True
    assert len(room.players) == 1
    assert room.host_id == bob.id
    assert bob.is_host is True

    # Remove Bob -> room is empty
    assert room.remove_player(bob.id) is True
    assert len(room.players) == 0

    # Removing non-existent player returns False
    assert room.remove_player("non-existent") is False



