"""Run-related Pydantic models."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from src.model.config import GraphConfig


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


class RunCommand(BaseModel):
    """SDK control command, including human approval decisions."""

    resume: Any = None
    update: Optional[dict] = None
    goto: Optional[str | list[str]] = None


class RunStreamRequest(BaseModel):
    """Request model for streaming runs."""

    assistant_id: str = Field(min_length=1)
    input: Optional[dict] = None
    command: Optional[RunCommand] = None
    checkpoint: Optional[dict] = None
    stream_mode: list[StreamMode] = Field(default_factory=lambda: [StreamMode.UPDATES])
    stream_subgraphs: bool = False
    config: Optional[GraphConfig] = None
    metadata: Optional[dict] = None
    interrupt_before: Optional[list[str]] = None
    interrupt_after: Optional[list[str]] = None
    multitask_strategy: Optional[str] = None

    @model_validator(mode="after")
    def validate_input_or_command(self):
        if self.input is not None and self.command is not None:
            raise ValueError("Provide input or command, not both")
        return self


class StreamEvent(BaseModel):
    """Stream event model."""

    event: str
    data: Any
    run_id: Optional[str] = None
