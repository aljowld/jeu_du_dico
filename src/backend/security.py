"""Security utilities for password hashing and verification."""

import bcrypt


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

