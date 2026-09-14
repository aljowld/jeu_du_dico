"""Integration tests for game rooms REST and WebSocket endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.backend.database import get_db
from src.backend.main import app
from src.backend.models import Base
from src.backend.word_service import add_word


@pytest.fixture
def client_with_seeded_words():
    """Create a TestClient with initialized database and seeded words."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Seed test words
    with testing_session_local() as db:
        add_word(db, "oriflamme", "Bannière d'apparat rouge orangé.")
        add_word(db, "marcescent", "Qui se flétrit sans se détacher.")

    def override_get_db():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    # Also patch SessionLocal in game routers so actions use this in-memory DB
    import src.backend.routers.game as game_router_mod
    original_session_local = game_router_mod.SessionLocal
    game_router_mod.SessionLocal = testing_session_local

    with TestClient(app) as test_client:
        yield test_client

    game_router_mod.SessionLocal = original_session_local
    app.dependency_overrides.clear()


def test_create_and_join_room(client_with_seeded_words):
    """Test room creation and player join via REST."""
    # 1. Create room
    create_resp = client_with_seeded_words.post(
        "/api/rooms",
        json={"host_name": "HostUser"},
    )
    assert create_resp.status_code == 201
    host_data = create_resp.json()
    assert len(host_data["room_code"]) == 4
    assert host_data["is_host"] is True
    room_code = host_data["room_code"]

    # 2. Get room info
    info_resp = client_with_seeded_words.get(f"/api/rooms/{room_code}")
    assert info_resp.status_code == 200
    assert info_resp.json()["player_count"] == 1
    assert info_resp.json()["max_players"] == 10

    # 3. Join room
    join_resp = client_with_seeded_words.post(
        f"/api/rooms/{room_code}/join",
        json={"player_name": "PlayerTwo"},
    )
    assert join_resp.status_code == 200
    player2_data = join_resp.json()
    assert player2_data["is_host"] is False
    assert player2_data["room_code"] == room_code

    # 4. Fill room to 10 players
    for i in range(3, 11):
        resp = client_with_seeded_words.post(
            f"/api/rooms/{room_code}/join",
            json={"player_name": f"Player{i}"},
        )
        assert resp.status_code == 200

    # 5. 11th player should be rejected with 400
    overflow_resp = client_with_seeded_words.post(
        f"/api/rooms/{room_code}/join",
        json={"player_name": "PlayerEleven"},
    )
    assert overflow_resp.status_code == 400
    assert "complète" in overflow_resp.json()["detail"]



def test_websocket_game_flow(client_with_seeded_words):
    """Test real-time WebSocket connection and basic game commands."""
    create_resp = client_with_seeded_words.post(
        "/api/rooms",
        json={"host_name": "HostAlice"},
    )
    host_data = create_resp.json()
    room_code = host_data["room_code"]
    host_id = host_data["player_id"]

    # Connect via WebSocket
    with client_with_seeded_words.websocket_connect(
        f"/ws/rooms/{room_code}/{host_id}"
    ) as ws:
        # Initial connection state update
        msg = ws.receive_json()
        assert msg["type"] == "STATE_UPDATE"
        assert msg["data"]["state"] == "LOBBY"
        assert msg["data"]["writing_time_limit"] == 60

        # Host updates settings
        ws.send_json({"action": "UPDATE_SETTINGS", "writing_time_limit": 75})
        settings_msg = ws.receive_json()
        assert settings_msg["data"]["writing_time_limit"] == 75

        # Host starts the game
        ws.send_json({"action": "START_GAME"})
        msg2 = ws.receive_json()
        assert msg2["type"] == "STATE_UPDATE"
        assert msg2["data"]["state"] == "WORD_SELECTION"
        assert "current_word" in msg2["data"]


@pytest.mark.anyio
async def test_disconnect_timeout_cleanup(client_with_seeded_words):
    """Test that disconnected player is cleaned up after timeout."""
    from src.backend.game_manager import game_manager
    from src.backend.routers.game import schedule_disconnect_cleanup

    create_resp = client_with_seeded_words.post(
        "/api/rooms",
        json={"host_name": "HostUser"},
    )
    room_code = create_resp.json()["room_code"]
    room = game_manager.get_room(room_code)
    assert room is not None
    player2 = room.add_player("GuestPlayer")
    assert player2 is not None
    assert len(room.players) == 2

    # Simulate player2 disconnecting
    player2.is_connected = False

    # Run cleanup with short timeout
    await schedule_disconnect_cleanup(room_code, player2.id, timeout_seconds=0.01)

    # Player 2 is removed
    assert player2.id not in room.players
    assert len(room.players) == 1


