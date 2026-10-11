"""Unit tests for user account management and authentication."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.models.models import Base
from src.backend.models.schemas import UserCreate
from src.backend.services.user_service import (
    UserAlreadyExistsError,
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()


def test_create_user_success(db_session):
    """Test successful user creation."""
    user_in = UserCreate(
        username="alice",
        email="alice@example.com",
        password="securepassword123",
    )
    user = create_user(db_session, user_in)

    assert user.id is not None
    assert user.username == "alice"
    assert user.email == "alice@example.com"
    assert user.hashed_password != "securepassword123"
    assert user.is_active is True


def test_create_user_duplicate_username(db_session):
    """Test creating a user with an existing username raises an error."""
    user_in1 = UserCreate(
        username="bob",
        email="bob1@example.com",
        password="securepassword123",
    )
    create_user(db_session, user_in1)

    user_in2 = UserCreate(
        username="bob",
        email="bob2@example.com",
        password="anotherpassword123",
    )
    with pytest.raises(UserAlreadyExistsError, match="username 'bob' already exists"):
        create_user(db_session, user_in2)


def test_create_user_duplicate_email(db_session):
    """Test creating a user with an existing email raises an error."""
    user_in1 = UserCreate(
        username="carol1",
        email="carol@example.com",
        password="securepassword123",
    )
    create_user(db_session, user_in1)

    user_in2 = UserCreate(
        username="carol2",
        email="carol@example.com",
        password="anotherpassword123",
    )
    with pytest.raises(UserAlreadyExistsError, match="email 'carol@example.com' already exists"):
        create_user(db_session, user_in2)


def test_authenticate_user(db_session):
    """Test authentication logic with valid and invalid passwords."""
    user_in = UserCreate(
        username="dave",
        email="dave@example.com",
        password="mypassword123",
    )
    create_user(db_session, user_in)

    # Valid credentials
    authenticated = authenticate_user(db_session, "dave", "mypassword123")
    assert authenticated is not None
    assert authenticated.username == "dave"

    # Invalid password
    assert authenticate_user(db_session, "dave", "wrongpassword") is None

    # Non-existent user
    assert authenticate_user(db_session, "unknown", "mypassword123") is None

