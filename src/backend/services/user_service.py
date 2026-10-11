"""Business logic and database operations for user accounts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.core.security import hash_password, verify_password
from src.backend.models.models import User
from src.backend.models.schemas import UserCreate


class UserAlreadyExistsError(Exception):
    """Raised when attempting to create a user that already exists."""


def get_user_by_username(db: Session, username: str) -> User | None:
    """Fetch a user by their username.

    Args:
        db: Active database session.
        username: Username to look for.

    Returns:
        User model instance if found, None otherwise.
    """
    stmt = select(User).where(User.username == username)
    return db.scalars(stmt).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by their email address.

    Args:
        db: Active database session.
        email: Email to look for.

    Returns:
        User model instance if found, None otherwise.
    """
    stmt = select(User).where(User.email == email)
    return db.scalars(stmt).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    """Create and persist a new user in the database.

    Args:
        db: Active database session.
        user_in: Schema containing new user details.

    Returns:
        The newly created User model instance.

    Raises:
        UserAlreadyExistsError: If username or email is already taken.
    """
    if get_user_by_username(db, user_in.username):
        msg = f"A user with username '{user_in.username}' already exists."
        raise UserAlreadyExistsError(msg)

    if get_user_by_email(db, user_in.email):
        msg = f"A user with email '{user_in.email}' already exists."
        raise UserAlreadyExistsError(msg)

    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Authenticate a user using their username and password.

    Args:
        db: Active database session.
        username: The account username.
        password: The plain-text password to check.

    Returns:
        User instance if credentials are valid and account is active, None otherwise.
    """
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
