"""Game room management and WebSocket routes for real-time play."""

import asyncio
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
from src.backend.game_manager import GameRoom, GameState, Player, game_manager
from src.backend.schemas import (
    CreateRoomRequest,
    JoinRoomRequest,
    RoomAccessResponse,
    RoomInfoResponse,
)

logger = logging.getLogger(__name__)

background_tasks: set[asyncio.Task[Any]] = set()


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


async def schedule_writing_timeout(
    room_code: str,
    round_number: int,
    duration_seconds: int,
) -> None:
    """Wait for writing duration to expire, then auto-submit pending definitions.

    Args:
        room_code: 4-character room code.
        round_number: Round number when timer was started.
        duration_seconds: Duration in seconds to wait.
    """
    await asyncio.sleep(duration_seconds + 1.0)
    room = game_manager.get_room(room_code)
    if room and room.state == GameState.WRITING and room.round_number == round_number:
        logger.info(
            "Writing timer expired for room %s (round %s), auto-submitting pending definitions.",
            room_code,
            round_number,
        )
        if room.timeout_writing():
            await manager.broadcast_state(room_code, room)


def start_writing_timer(room_code: str, round_number: int, duration_seconds: int) -> None:
    """Launch background timeout task for writing phase.

    Args:
        room_code: 4-character room code.
        round_number: Round number when timer was started.
        duration_seconds: Duration in seconds to wait.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    task = loop.create_task(
        schedule_writing_timeout(room_code, round_number, duration_seconds)
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


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
    changed = False

    if action in {"START_GAME", "NEXT_ROUND"} and player.is_host:
        with SessionLocal() as db:
            changed = room.draw_word(db)

    elif action == "REROLL_WORD" and player.is_host:
        with SessionLocal() as db:
            changed = room.reroll_word(db)

    elif action == "START_WRITING" and player.is_host:
        changed = room.start_writing()
        if changed:
            start_writing_timer(room.code, room.round_number, room.writing_time_limit)

    elif action == "UPDATE_SETTINGS" and player.is_host:
        writing_time = data.get("writing_time_limit")
        if isinstance(writing_time, int):
            changed = room.update_writing_time_limit(writing_time)

    elif action == "SUBMIT_DEFINITION":
        definition = str(data.get("definition", "")).strip()
        changed = bool(definition and room.submit_definition(player.id, definition))
        raw_definition = str(data.get("definition", "")).strip()
        definition = raw_definition or "(Aucune proposition)"
        changed = room.submit_definition(player.id, definition)

    elif action == "SUBMIT_VOTE":
        option_id = str(data.get("option_id", "")).strip()
        changed = bool(option_id and room.submit_vote(player.id, option_id))

    return changed



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
