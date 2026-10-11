"""In-memory game state and room management for the dictionary party game."""

import random
import secrets
import string
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from src.backend.core.constants import (
    DEFAULT_ROUNDS,
    DEFAULT_WRITING_TIME,
    MAX_PLAYERS,
    MAX_ROUNDS,
    MAX_WRITING_TIME,
    MIN_ROUNDS,
    MIN_WRITING_TIME,
    STEP_WRITING_TIME,
)
from src.backend.models.models import Word
from src.backend.services.word_service import get_random_word


class GameState(StrEnum):
    """Possible game states for a room."""

    LOBBY = "LOBBY"
    WORD_SELECTION = "WORD_SELECTION"
    WRITING = "WRITING"
    VOTING = "VOTING"
    REVEAL = "REVEAL"
    GAME_OVER = "GAME_OVER"


@dataclass
class Player:
    """Represents a player in a game room."""

    id: str
    name: str
    score: int = 0
    is_host: bool = False
    is_connected: bool = True
    disconnected_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert player data to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "is_host": self.is_host,
            "is_connected": self.is_connected,
        }


@dataclass
class DefinitionOption:
    """Represents a displayed definition choice during voting."""

    id: str
    text: str
    author_id: str | None  # None for real dictionary definition


@dataclass
class GameRoom:
    """Represents an active game room and its round state."""

    code: str
    host_id: str
    players: dict[str, Player] = field(default_factory=dict)
    state: GameState = GameState.LOBBY
    used_word_ids: list[int] = field(default_factory=list)
    current_word: Word | None = None
    submitted_definitions: dict[str, str] = field(default_factory=dict)  # player_id -> text
    options: list[DefinitionOption] = field(default_factory=list)
    votes: dict[str, str] = field(default_factory=dict)  # player_id -> option_id
    round_results: dict[str, Any] | None = None
    round_number: int = 0
    max_rounds: int = DEFAULT_ROUNDS
    writing_time_limit: int = DEFAULT_WRITING_TIME
    writing_started_at: float | None = None

    @property
    def connected_players(self) -> list[Player]:
        """Return list of currently connected players."""
        return [p for p in self.players.values() if p.is_connected]

    def update_writing_time_limit(self, seconds: int) -> bool:
        """Update writing time limit if within permitted bounds.

        Args:
            seconds: Target duration in seconds.

        Returns:
            True if updated, False otherwise.
        """
        if self.state != GameState.LOBBY:
            return False
        if MIN_WRITING_TIME <= seconds <= MAX_WRITING_TIME and seconds % STEP_WRITING_TIME == 0:
            self.writing_time_limit = seconds
            return True
        return False

    def update_max_rounds(self, rounds: int) -> bool:
        """Update max rounds setting if within permitted bounds.

        Args:
            rounds: Target number of rounds.

        Returns:
            True if updated, False otherwise.
        """
        if self.state != GameState.LOBBY:
            return False
        if MIN_ROUNDS <= rounds <= MAX_ROUNDS:
            self.max_rounds = rounds
            return True
        return False

    def end_game(self) -> bool:
        """End the game and show final scores."""
        self.state = GameState.GAME_OVER
        return True

    def return_to_lobby(self) -> bool:
        """Return the room to the lobby state, resetting game data."""
        if self.state != GameState.GAME_OVER:
            return False
        self.state = GameState.LOBBY
        self.round_number = 0
        self.used_word_ids.clear()
        self.current_word = None
        self.submitted_definitions.clear()
        self.options.clear()
        self.votes.clear()
        self.round_results = None
        for p in self.players.values():
            p.score = 0
        return True

    def add_player(self, name: str, *, is_host: bool = False) -> Player | None:
        """Add a new player to the room if player limit is not reached.

        Args:
            name: Player display name.
            is_host: Whether this player is the room creator.

        Returns:
            The created Player instance, or None if the room is full.
        """
        if len(self.players) >= MAX_PLAYERS:
            return None

        player_id = str(uuid.uuid4())
        player = Player(id=player_id, name=name, is_host=is_host)
        self.players[player_id] = player
        return player

    def remove_player(self, player_id: str) -> bool:
        """Remove a player from the room (e.g. disconnect timeout or voluntary leave).

        Args:
            player_id: Unique player ID to remove.

        Returns:
            True if player was removed, False if player was not found.
        """
        if player_id not in self.players:
            return False

        is_removed_host = self.players[player_id].is_host
        del self.players[player_id]

        # Clean up any submitted definitions or votes for this player
        self.submitted_definitions.pop(player_id, None)
        self.votes.pop(player_id, None)

        # If no players remain, return True (room can be cleaned up)
        if not self.players:
            return True

        # If the host was removed, transfer host rights to the next player
        if is_removed_host:
            connected = self.connected_players
            new_host = connected[0] if connected else next(iter(self.players.values()))
            new_host.is_host = True
            self.host_id = new_host.id

        # In-game checks: if in WRITING and all remaining connected players have submitted
        if (
            self.state == GameState.WRITING
            and self.connected_players
            and len(self.submitted_definitions) >= len(self.connected_players)
        ):
            self.start_voting()

        # In-game checks: if in VOTING and all remaining connected players have voted
        elif (
            self.state == GameState.VOTING
            and self.connected_players
            and len(self.votes) >= len(self.connected_players)
        ):
            self.reveal_results()

        return True

    def draw_word(self, db: Session) -> bool:
        """Draw a random word for a new round.

        Args:
            db: Database session.

        Returns:
            True if a word was drawn, False if no words are available.
        """
        word = get_random_word(db, exclude_word_ids=self.used_word_ids)
        if word is None:
            return False

        self.current_word = word
        self.used_word_ids.append(word.id)
        self.submitted_definitions.clear()
        self.options.clear()
        self.votes.clear()
        self.round_results = None
        self.round_number += 1
        self.state = GameState.WORD_SELECTION
        return True

    def reroll_word(self, db: Session) -> bool:
        """Reroll the current word if someone knows it.

        Args:
            db: Database session.

        Returns:
            True if a new word was drawn, False if no words are available.
        """
        if self.state != GameState.WORD_SELECTION:
            return False

        word = get_random_word(db, exclude_word_ids=self.used_word_ids)
        if word is None:
            return False

        self.current_word = word
        self.used_word_ids.append(word.id)
        return True

    def start_writing(self) -> bool:
        """Transition from word selection to writing phase.

        Returns:
            True if transition succeeded, False otherwise.
        """
        if self.state != GameState.WORD_SELECTION or self.current_word is None:
            return False
        self.writing_started_at = time.time()
        self.state = GameState.WRITING
        return True

    def submit_definition(self, player_id: str, definition: str) -> bool:
        """Submit an invented definition for the current word.

        Args:
            player_id: Submitting player's ID.
            definition: The invented definition text.

        Returns:
            True if successfully recorded, False otherwise.
        """
        if self.state != GameState.WRITING or player_id not in self.players:
            return False

        if player_id in self.submitted_definitions:
            return False

        clean_def = definition.strip() or "(Aucune proposition)"
        self.submitted_definitions[player_id] = clean_def

        # If all connected players have submitted, prepare voting automatically
        if len(self.submitted_definitions) >= len(self.connected_players):
            self.start_voting()

        return True

    def timeout_writing(self) -> bool:
        """Handle writing timeout: fill missing definitions and transition to voting.

        Returns:
            True if state transitioned to VOTING, False otherwise.
        """
        if self.state != GameState.WRITING:
            return False

        # Fill missing definitions for any connected players who did not submit in time
        for player in self.connected_players:
            if player.id not in self.submitted_definitions:
                self.submitted_definitions[player.id] = "(Aucune proposition)"

        self.start_voting()
        return True

    def start_voting(self) -> None:
        """Prepare shuffled definitions and switch state to VOTING."""
        if self.current_word is None:
            return

        all_options: list[DefinitionOption] = [
            DefinitionOption(
                id=str(uuid.uuid4()),
                text=self.current_word.definition,
                author_id=None,
            ),
        ]

        for p_id, def_text in self.submitted_definitions.items():
            all_options.append(
                DefinitionOption(
                    id=str(uuid.uuid4()),
                    text=def_text,
                    author_id=p_id,
                ),
            )

        random.shuffle(all_options)
        self.options = all_options
        self.state = GameState.VOTING

    def submit_vote(self, player_id: str, option_id: str) -> bool:
        """Submit a vote for a definition option.

        Args:
            player_id: Voter player ID.
            option_id: Chosen definition option ID.

        Returns:
            True if vote was registered, False otherwise.
        """
        if self.state != GameState.VOTING or player_id not in self.players:
            return False

        # Find chosen option
        option = next((opt for opt in self.options if opt.id == option_id), None)
        if option is None:
            return False

        # Players cannot vote for their own definition
        if option.author_id == player_id:
            return False

        self.votes[player_id] = option_id

        # If all connected players have voted, reveal results automatically
        if len(self.votes) >= len(self.connected_players):
            self.reveal_results()

        return True

    def reveal_results(self) -> None:
        """Calculate round scores and build reveal data."""
        self.state = GameState.REVEAL

        points_awarded: dict[str, int] = dict.fromkeys(self.players, 0)
        breakdown = []

        # Find the real option
        real_option = next((opt for opt in self.options if opt.author_id is None), None)
        real_option_id = real_option.id if real_option else None

        for opt in self.options:
            # Find voters for this option
            voters_ids = [p_id for p_id, v_id in self.votes.items() if v_id == opt.id]
            voters_names = [self.players[v_id].name for v_id in voters_ids if v_id in self.players]

            is_real = opt.author_id is None
            author_name = (
                "Le Vrai Dictionnaire"
                if is_real
                else (
                    self.players[opt.author_id].name if opt.author_id in self.players else "Inconnu"
                )
            )

            # Score calculation:
            # 1. Voters get 1 point if they guessed the real definition
            if is_real:
                for v_id in voters_ids:
                    points_awarded[v_id] += 1
            # 2. Author gets 1 point per player they fooled
            elif opt.author_id in points_awarded:
                points_awarded[opt.author_id] += len(voters_ids)

            breakdown.append(
                {
                    "option_id": opt.id,
                    "text": opt.text,
                    "is_real": is_real,
                    "author_name": author_name,
                    "author_id": opt.author_id,
                    "voters": voters_names,
                }
            )

        # Apply points to overall scores
        for p_id, pts in points_awarded.items():
            if p_id in self.players:
                self.players[p_id].score += pts

        self.round_results = {
            "word": self.current_word.word if self.current_word else "",
            "real_definition": self.current_word.definition if self.current_word else "",
            "real_option_id": real_option_id,
            "options": breakdown,
            "points_awarded": points_awarded,
            "scoreboard": [
                p.to_dict()
                for p in sorted(
                    self.players.values(),
                    key=lambda p: p.score,
                    reverse=True,
                )
            ],
        }

    def get_state_for_player(self, player_id: str) -> dict[str, Any]:
        """Return public / sanitized state visible to a specific player.

        Args:
            player_id: ID of the player requesting the state.

        Returns:
            Sanitized room view suitable for client serialization.
        """
        base: dict[str, Any] = {
            "room_code": self.code,
            "host_id": self.host_id,
            "state": self.state,
            "round_number": self.round_number,
            "max_rounds": self.max_rounds,
            "players": [p.to_dict() for p in self.players.values()],
            "max_players": MAX_PLAYERS,
            "is_host": self.host_id == player_id,
            "writing_time_limit": self.writing_time_limit,
        }

        if self.state in {GameState.WORD_SELECTION, GameState.WRITING} and self.current_word:
            base["current_word"] = self.current_word.word
            base["has_submitted"] = player_id in self.submitted_definitions
            base["submissions_count"] = len(self.submitted_definitions)
            base["total_needed"] = len(self.connected_players)
            if self.state == GameState.WRITING:
                base["writing_started_at"] = self.writing_started_at

        elif self.state == GameState.VOTING and self.current_word:
            base["current_word"] = self.current_word.word
            base["has_voted"] = player_id in self.votes
            base["votes_count"] = len(self.votes)
            base["total_needed"] = len(self.connected_players)
            # Find which option belongs to this player (so they can't vote for it)
            base["options"] = [
                {
                    "id": opt.id,
                    "text": opt.text,
                    "is_own": opt.author_id == player_id,
                }
                for opt in self.options
            ]

        elif self.state in {GameState.REVEAL, GameState.GAME_OVER}:
            base["results"] = self.round_results

        return base


class GameManager:
    """Manages active game rooms in memory."""

    def __init__(self) -> None:
        """Initialize the GameManager."""
        self.rooms: dict[str, GameRoom] = {}

    def generate_room_code(self) -> str:
        """Generate a unique 4-character uppercase alphanumeric code.

        Returns:
            A unique room code string.
        """
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(secrets.choice(chars) for _ in range(4))
            if code not in self.rooms:
                return code

    def create_room(self, host_name: str) -> tuple[GameRoom, Player]:
        """Create a new game room with host player.

        Args:
            host_name: Display name of the host.

        Returns:
            Tuple containing the new GameRoom and host Player.
        """
        code = self.generate_room_code()
        room = GameRoom(code=code, host_id="")
        host = room.add_player(name=host_name, is_host=True)
        room.host_id = host.id
        self.rooms[code] = room
        return room, host

    def get_room(self, room_code: str) -> GameRoom | None:
        """Retrieve a game room by its code.

        Args:
            room_code: 4-character room code.

        Returns:
            GameRoom instance if found, None otherwise.
        """
        return self.rooms.get(room_code.upper())


# Global singleton instance
game_manager = GameManager()
