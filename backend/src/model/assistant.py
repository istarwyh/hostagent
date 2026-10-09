"""Assistant-related Pydantic models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.model.config import GraphConfig


class AssistantMetadata(BaseModel):
    """Metadata for an assistant."""

    model_config = ConfigDict(extra="allow")
    created_by: str = "system"


class Assistant(BaseModel):
    """Assistant model compatible with LangGraph SDK."""

    assistant_id: str
    graph_id: str = "agent"
    name: str
    config: dict = Field(default_factory=dict)
    metadata: AssistantMetadata = Field(default_factory=AssistantMetadata)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1


class AssistantSearchRequest(BaseModel):
    """Request model for searching assistants."""

    graph_id: Optional[str] = None
    metadata: Optional[dict] = None
    limit: int = 10
    offset: int = 0


class AssistantCreateRequest(BaseModel):
    """JSON request body for creating a user assistant."""

    graph_id: str = Field(default="agent", min_length=1)
    name: Optional[str] = Field(default=None, min_length=1)
    config: GraphConfig = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class AssistantUpdateRequest(BaseModel):
    """JSON request body for updating a user assistant."""

    name: Optional[str] = Field(default=None, min_length=1)
    config: Optional[GraphConfig] = None
    metadata: Optional[dict] = None
