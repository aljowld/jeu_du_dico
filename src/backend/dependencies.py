"""Dependencies for FastAPI endpoints."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.backend.database import get_db
from src.backend.models import User
from src.backend.security import decode_access_token
from src.backend.user_service import get_user_by_username

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Retrieve the currently authenticated user from the Bearer token.

    Args:
        token: JWT bearer token extracted from request header.
        db: Database session.

    Returns:
        The authenticated User model instance.

    Raises:
        HTTPException: If the token is missing, invalid, or user is not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    username: str | None = payload.get("sub")
    if username is None:
        raise credentials_exception

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise credentials_exception

    return user
