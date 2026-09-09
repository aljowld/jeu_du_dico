"""Security utilities for password hashing and verification."""

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-insecure-jwt-secret-key-change-in-production")
ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def hash_password(password: str) -> str:
    """Hash a clear-text password using bcrypt.

    Args:
        password: Plain-text password to hash.

    Returns:
        The hashed password string.
    """
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a hashed password.

    Args:
        plain_password: The plain-text password to verify.
        hashed_password: The stored hashed password.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a new JWT access token.

    Args:
        data: Payload data to encode in the token.
        expires_delta: Optional custom expiration duration.

    Returns:
        Encoded JWT token as a string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.

    Args:
        token: JWT string to decode.

    Returns:
        Decoded payload dictionary, or None if invalid or expired.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
