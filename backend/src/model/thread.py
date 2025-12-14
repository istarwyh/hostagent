"""Thread-related Pydantic models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Thread(BaseModel):
    """Thread model compatible with LangGraph SDK."""

    thread_id: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "idle"
    values: dict = Field(default_factory=dict)


class ThreadState(BaseModel):
    """Thread state model."""

    values: dict = Field(default_factory=dict)
    next: list[str] = Field(default_factory=list)
    checkpoint_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class ThreadSearchRequest(BaseModel):
    """Request model for searching threads."""

    metadata: Optional[dict] = None
    status: Optional[str] = None
    limit: int = 10
    offset: int = 0


class ThreadStateUpdateRequest(BaseModel):
    """Request model for updating thread state."""

    values: dict
    as_node: Optional[str] = None
    checkpoint_id: Optional[str] = None


class ThreadHistoryRequest(BaseModel):
    """Request model for getting thread history."""

    limit: int = 10
    before: Optional[str] = None
    checkpoint_id: Optional[str] = None
