"""Integration tests for FastAPI authentication endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.backend.core.database import get_db
from src.backend.main import app
from src.backend.models.models import Base


@pytest.fixture
def client_and_db():
    """Create a TestClient with an isolated in-memory SQLite database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_health_check(client_and_db):
    """Test the service health check endpoint."""
    response = client_and_db.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_and_login_flow(client_and_db):
    """Test user registration, login, and authenticated profile retrieval."""
    register_payload = {
        "username": "charlie",
        "email": "charlie@example.com",
        "password": "strongpassword123",
    }
    # 1. Register
    reg_response = client_and_db.post("/api/auth/register", json=register_payload)
    assert reg_response.status_code == 201
    user_data = reg_response.json()
    assert user_data["username"] == "charlie"
    assert user_data["email"] == "charlie@example.com"
    assert "password" not in user_data
    assert "hashed_password" not in user_data

    # 2. Duplicate registration conflict
    dup_response = client_and_db.post("/api/auth/register", json=register_payload)
    assert dup_response.status_code == 409

    # 3. Login with correct credentials
    login_response = client_and_db.post(
        "/api/auth/login",
        json={"username": "charlie", "password": "strongpassword123"},
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # 4. Access protected profile route with token
    token = token_data["access_token"]
    me_response = client_and_db.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "charlie"

    # 5. Access protected profile route without token
    unauthorized_response = client_and_db.get("/api/auth/me")
    assert unauthorized_response.status_code == 401


def test_login_invalid_credentials(client_and_db):
    """Test login with non-existent user and bad password."""
    response = client_and_db.post(
        "/api/auth/login",
        json={"username": "nonexistent", "password": "wrongpassword"},
    )
    assert response.status_code == 401
