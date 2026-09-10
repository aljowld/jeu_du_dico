"""Game room management and WebSocket routes for real-time play."""

import logging
from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from src.backend.connection_manager import manager
from src.backend.database import SessionLocal
from src.backend.game_manager import GameRoom, Player, game_manager
from src.backend.schemas import (
    CreateRoomRequest,
    JoinRoomRequest,
    RoomAccessResponse,
    RoomInfoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])
ws_router = APIRouter(tags=["websockets"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new game room",
)
def create_room(payload: CreateRoomRequest) -> RoomAccessResponse:
    """Create a new room and return room code and host player credentials.

    Args:
        payload: Host nickname data.

    Returns:
        RoomAccessResponse with room code and host player ID.
    """
    room, host = game_manager.create_room(host_name=payload.host_name)
    return RoomAccessResponse(
        room_code=room.code,
        player_id=host.id,
        player_name=host.name,
        is_host=True,
    )


@router.post(
    "/{room_code}/join",
    summary="Join an existing game room",
)
def join_room(room_code: str, payload: JoinRoomRequest) -> RoomAccessResponse:
    """Join an existing game room.

    Args:
        room_code: 4-character room code.
        payload: Joining player data.

    Returns:
        RoomAccessResponse with room code and player ID.

    Raises:
        HTTPException: If the room is not found.
    """
    room = game_manager.get_room(room_code)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room '{room_code.upper()}' not found.",
        )

    player = room.add_player(name=payload.player_name, is_host=False)
    return RoomAccessResponse(
        room_code=room.code,
        player_id=player.id,
        player_name=player.name,
        is_host=False,
    )


@router.get(
    "/{room_code}",
    summary="Get room overview information",
)
def get_room_info(room_code: str) -> RoomInfoResponse:
    """Retrieve basic info about a game room.

    Args:
        room_code: 4-character room code.

    Returns:
        RoomInfoResponse containing code, state, and player count.

    Raises:
        HTTPException: If the room is not found.
    """
    room = game_manager.get_room(room_code)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Room '{room_code.upper()}' not found.",
        )

    return RoomInfoResponse(
        room_code=room.code,
        state=room.state,
        player_count=len(room.players),
    )


def handle_game_action(
    action: str | None,
    data: dict[str, Any],
    room: GameRoom,
    player: Player,
) -> bool:
    """Execute a player game action and indicate whether state changed.

    Args:
        action: Game action identifier.
        data: Additional payload received from WebSocket.
        room: Target game room.
        player: Action initiator player.

    Returns:
        True if the room state was modified, False otherwise.
    """
    if action in {"START_GAME", "NEXT_ROUND"} and player.is_host:
        with SessionLocal() as db:
            return room.draw_word(db)

    if action == "REROLL_WORD" and player.is_host:
        with SessionLocal() as db:
            return room.reroll_word(db)

    if action == "START_WRITING" and player.is_host:
        return room.start_writing()

    if action == "SUBMIT_DEFINITION":
        definition = str(data.get("definition", "")).strip()
        return bool(definition and room.submit_definition(player.id, definition))

    if action == "SUBMIT_VOTE":
        option_id = str(data.get("option_id", "")).strip()
        return bool(option_id and room.submit_vote(player.id, option_id))

    return False


@ws_router.websocket("/ws/rooms/{room_code}/{player_id}")
async def websocket_game_endpoint(
    websocket: WebSocket,
    room_code: str,
    player_id: str,
) -> None:
    """Handle persistent real-time WebSocket connection for a player in a room.

    Args:
        websocket: Client WebSocket connection.
        room_code: Target room code.
        player_id: Unique player ID.
    """
    code = room_code.upper()
    room = game_manager.get_room(code)
    if room is None or player_id not in room.players:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    player = room.players[player_id]
    player.is_connected = True

    await manager.connect(code, player_id, websocket)
    await manager.broadcast_state(code, room)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            if handle_game_action(action, data, room, player):
                await manager.broadcast_state(code, room)

    except WebSocketDisconnect:
        player.is_connected = False
        manager.disconnect(code, player_id)
        await manager.broadcast_state(code, room)
