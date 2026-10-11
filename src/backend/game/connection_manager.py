"""Connection manager for real-time WebSocket communication."""

import logging
from typing import Any, Protocol

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class RoomStateProvider(Protocol):
    """Protocol for objects that provide customized player state."""

    def get_state_for_player(self, player_id: str) -> dict[str, Any]:
        """Return the sanitized state for a player.

        Args:
            player_id: Target player ID.

        Returns:
            Dictionary representation of the player's view.
        """
        ...


class ConnectionManager:
    """Manages active WebSocket connections mapped by room and player."""

    def __init__(self) -> None:
        """Initialize connection storage."""
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, room_code: str, player_id: str, websocket: WebSocket) -> None:
        """Accept and register a player's WebSocket connection.

        Args:
            room_code: The room code.
            player_id: Unique player ID.
            websocket: Active WebSocket instance.
        """
        await websocket.accept()
        if room_code not in self.active_connections:
            self.active_connections[room_code] = {}
        self.active_connections[room_code][player_id] = websocket

    def disconnect(self, room_code: str, player_id: str) -> None:
        """Remove a player's connection.

        Args:
            room_code: The room code.
            player_id: Unique player ID.
        """
        if room_code in self.active_connections:
            self.active_connections[room_code].pop(player_id, None)
            if not self.active_connections[room_code]:
                del self.active_connections[room_code]

    async def send_personal_message(
        self,
        room_code: str,
        player_id: str,
        message: dict[str, Any],
    ) -> None:
        """Send a JSON message to a specific player in a room.

        Args:
            room_code: The room code.
            player_id: Target player ID.
            message: JSON-serializable dictionary.
        """
        ws = self.active_connections.get(room_code, {}).get(player_id)
        if ws is not None:
            try:
                await ws.send_json(message)
            except RuntimeError:
                logger.warning("Failed to send message to disconnected player %s", player_id)

    async def broadcast_state(
        self,
        room_code: str,
        room_getter: RoomStateProvider,
    ) -> None:
        """Broadcast personalized sanitized state to each player in a room.

        Args:
            room_code: The room code.
            room_getter: Object providing get_state_for_player(player_id).
        """
        connections = self.active_connections.get(room_code, {})
        for player_id, ws in list(connections.items()):
            try:
                state = room_getter.get_state_for_player(player_id)
                await ws.send_json({"type": "STATE_UPDATE", "data": state})
            except RuntimeError:
                logger.warning("Connection lost while sending state to %s", player_id)


manager = ConnectionManager()
