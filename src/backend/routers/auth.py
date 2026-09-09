"""Authentication endpoints for user registration, login, and profile."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.backend.database import get_db
from src.backend.dependencies import get_current_user
from src.backend.models import User
from src.backend.schemas import Token, UserCreate, UserLogin, UserRead
from src.backend.security import create_access_token
from src.backend.user_service import UserAlreadyExistsError, authenticate_user, create_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Register a new user account with unique username and email.

    Args:
        user_in: Input user creation schema with username, email, and password.
        db: Database session.

    Returns:
        The newly created user profile.

    Raises:
        HTTPException: If the username or email is already taken.
    """
    try:
        return create_user(db, user_in)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/login",
    summary="Log in and retrieve a JWT token",
)
def login(
    credentials: UserLogin,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    """Authenticate with username and password to get a bearer token.

    Args:
        credentials: User login credentials.
        db: Database session.

    Returns:
        A JWT access token and token type.

    Raises:
        HTTPException: If the credentials are invalid or user inactive.
    """
    user = authenticate_user(db, credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user profile",
)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the profile data of the currently authenticated user.

    Args:
        current_user: Current authenticated user.

    Returns:
        The current user profile.
    """
    return current_user
