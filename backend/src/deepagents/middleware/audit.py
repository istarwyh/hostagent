"""Per-tool audit logging for the LangChain v1 middleware pipeline."""

import asyncio
import dataclasses
import json
import logging
import os
import re
import sys
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphInterrupt
from langgraph.types import Command
from pydantic import BaseModel

from deepagents.workspace_dir import get_workspace_dir_name

logger = logging.getLogger(__name__)
_SUMMARY_LOCK = threading.Lock()
ToolResult = ToolMessage | Command[Any]


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return str(value)


def _lock_summary(stream: TextIO, *, unlock: bool = False) -> None:
    """Lock the summary across worker processes as well as threads."""
    if sys.platform == "win32":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK if unlock else msvcrt.LK_LOCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN if unlock else fcntl.LOCK_EX)


class ToolAuditMiddleware(AgentMiddleware):
    """Record tool inputs/outcomes without modifying their values or exceptions.

    Place this last in the middleware list to observe the actual request after
    outer middleware has transformed it, including individual retry attempts.
    Audit persistence is best-effort: a disk failure must not change execution.
    """

    def __init__(self, audit_dir: str | os.PathLike[str] | None = None) -> None:
        self.audit_dir = (
            Path(audit_dir)
            if audit_dir is not None
            else Path(get_workspace_dir_name()) / "audit_logs"
        )

    def wrap_tool_call(
        self, request: ToolCallRequest, handler: Callable[[ToolCallRequest], ToolResult]
    ) -> ToolResult:
        started = time.perf_counter()
        result = None
        error = None
        try:
            result = handler(request)
            return result
        except BaseException as exc:
            error = exc
            raise
        finally:
            self._record(request, result, error, (time.perf_counter() - started) * 1000)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolResult]],
    ) -> ToolResult:
        started = time.perf_counter()
        result = None
        error = None
        try:
            result = await handler(request)
            return result
        except BaseException as exc:
            error = exc
            raise
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            try:
                await asyncio.to_thread(self._record, request, result, error, elapsed_ms)
            except Exception:
                logger.warning("Unable to schedule tool audit write", exc_info=True)

    def _record(
        self,
        request: ToolCallRequest,
        result: ToolResult | None,
        error: BaseException | None,
        elapsed_ms: float,
    ) -> None:
        try:
            record = self._make_record(request, result, error, elapsed_ms)
            self._write_record(record)
        except Exception:
            logger.warning("Unable to persist tool audit record", exc_info=True)

    @staticmethod
    def _make_record(
        request: ToolCallRequest,
        result: ToolResult | None,
        error: BaseException | None,
        elapsed_ms: float,
    ) -> dict[str, Any]:
        output = result.content if isinstance(result, ToolMessage) else result
        interrupted = isinstance(error, GraphInterrupt)
        error_message = str(error) if error is not None and not interrupted else None
        if isinstance(result, ToolMessage) and result.status == "error":
            error_message = output if isinstance(output, str) else json.dumps(output)
        config = request.runtime.config if request.runtime is not None else {}
        return {
            "audit_id": uuid.uuid4().hex,
            "tool_call_id": request.tool_call.get("id"),
            "tool_name": request.tool_call["name"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "execution_time_ms": elapsed_ms,
            "input": request.tool_call.get("args", {}),
            "output": output,
            "error": error_message,
            "status": (
                "interrupted"
                if interrupted
                else "failed" if error_message is not None else "success"
            ),
            "thread_id": config.get("configurable", {}).get("thread_id"),
            "run_id": config.get("run_id"),
        }

    def _write_record(self, record: dict[str, Any]) -> None:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        tool_slug = re.sub(r"[^a-zA-Z0-9_-]", "_", record["tool_name"])[:64] or "tool"
        timestamp = datetime.fromisoformat(record["timestamp"])
        filename = f"{timestamp:%H%M%S%f}_{tool_slug}_{record['audit_id']}.json"
        content = json.dumps(record, ensure_ascii=False, default=_json_default)
        with (self.audit_dir / filename).open("x", encoding="utf-8") as stream:
            stream.write(content)
        summary = self.audit_dir / f"summary_{timestamp:%Y%m%d}.jsonl"
        with _SUMMARY_LOCK, summary.open("a", encoding="utf-8") as stream:
            _lock_summary(stream)
            try:
                stream.write(content + "\n")
                stream.flush()
            finally:
                _lock_summary(stream, unlock=True)
