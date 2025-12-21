"""Run-related Pydantic models."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class StreamMode(str, Enum):
    """Stream mode options matching SDK StreamMode type."""

    VALUES = "values"
    MESSAGES = "messages"
    MESSAGES_TUPLE = "messages-tuple"
    UPDATES = "updates"
    EVENTS = "events"
    DEBUG = "debug"
    TASKS = "tasks"
    CHECKPOINTS = "checkpoints"
    CUSTOM = "custom"


class EventType(str, Enum):
    """SSE event types matching SDK stream event types."""

    METADATA = "metadata"
    VALUES = "values"
    MESSAGES = "messages"
    UPDATES = "updates"
    EVENTS = "events"
    DEBUG = "debug"
    TASKS = "tasks"
    CHECKPOINTS = "checkpoints"
    CUSTOM = "custom"
    FEEDBACK = "feedback"
    END = "end"
    ERROR = "error"


class RunStreamRequest(BaseModel):
    """Request model for streaming runs."""

    assistant_id: str
    input: Optional[dict] = None
    stream_mode: list[str] = Field(default_factory=lambda: ["updates"])
    stream_subgraphs: bool = False
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
