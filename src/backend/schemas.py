"""Pydantic schemas for data validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Shared attributes for user schemas."""

    username: str = Field(min_length=3, max_length=50, description="User public display name.")
    email: EmailStr = Field(description="User email address.")


class UserCreate(UserBase):
    """Schema for creating a new user account."""

    password: str = Field(min_length=8, max_length=128, description="User plain-text password.")


class UserLogin(BaseModel):
    """Schema for user credentials during login."""

    username: str = Field(description="Username or email.")
    password: str = Field(description="User plain-text password.")


class UserRead(UserBase):
    """Schema for returning user data to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """Schema representing an authentication token."""

    access_token: str
    token_type: str = Field(default="bearer")


class TokenPayload(BaseModel):
    """Schema representing the decoded JWT payload."""

    sub: str | None = None
