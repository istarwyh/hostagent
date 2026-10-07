"""Translate LangChain v1 state into the experiment's SDK/UI wire contract."""

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from deepagents.middleware.filesystem import _create_file_data, _validate_path


def json_safe(value: Any) -> Any:
    """Preserve structured interrupts and messages instead of stringifying them."""
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return json_safe(value.model_dump())
    if is_dataclass(value) and not isinstance(value, type):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


def serialize_state(state: dict) -> dict:
    """Keep public channel boundaries and render v1 FileData as text for the UI."""
    result = json_safe(state)
    if isinstance(state.get("files"), dict):
        result["files"] = {
            path: (
                "\n".join(data["content"])
                if isinstance(data, dict) and isinstance(data.get("content"), list)
                else data
            )
            for path, data in result["files"].items()
        }
    return result


def normalize_input(state: dict | None) -> dict | None:
    """Accept existing UI string files while keeping v1 data inside the graph."""
    if state is None:
        return None
    result = dict(state)
    if isinstance(state.get("files"), dict):
        result["files"] = {
            _validate_path(path): _create_file_data(value) if isinstance(value, str) else value
            for path, value in state["files"].items()
        }
    return result


def serialize_snapshot(snapshot: Any) -> dict:
    """Serialize real graph state, including pending HITL tasks after reconnect."""
    configurable = (snapshot.config or {}).get("configurable", {})
    parent = (snapshot.parent_config or {}).get("configurable")
    return {
        "values": serialize_state(snapshot.values),
        "next": list(snapshot.next),
        "checkpoint": json_safe(configurable),
        "checkpoint_id": configurable.get("checkpoint_id"),
        "parent_checkpoint": json_safe(parent),
        "created_at": snapshot.created_at,
        "metadata": json_safe(snapshot.metadata or {}),
        "tasks": [
            {
                "id": task.id,
                "name": task.name,
                "error": None if task.error is None else "Task execution failed",
                "interrupts": json_safe(task.interrupts),
                "state": None,
            }
            for task in snapshot.tasks
        ],
    }
