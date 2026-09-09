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


class UserRead(UserBase):
    """Schema for returning user data to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime

