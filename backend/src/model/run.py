"""Run-related Pydantic models."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class StreamMode(str, Enum):
    """Stream mode options."""

    UPDATES = "updates"
    VALUES = "values"
    MESSAGES = "messages"
    DEBUG = "debug"


class EventType(str, Enum):
    """SSE event types."""

    METADATA = "metadata"
    UPDATES = "updates"
    VALUES = "values"
    MESSAGES = "messages"
    END = "end"
    ERROR = "error"


class RunStreamRequest(BaseModel):
    """Request model for streaming runs."""

    assistant_id: str
    input: Optional[dict] = None
    stream_mode: list[str] = Field(default_factory=lambda: ["updates"])
    config: Optional[dict] = None
    metadata: Optional[dict] = None
    interrupt_before: Optional[list[str]] = None
    interrupt_after: Optional[list[str]] = None
    multitask_strategy: Optional[str] = None


class StreamEvent(BaseModel):
    """Stream event model."""

    event: str
    data: Any
    run_id: Optional[str] = None
