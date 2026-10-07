"""
Threads Router

Provides endpoints for managing threads compatible with LangGraph SDK.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.facade.langgraph_api.run_dependencies import prepare_run_agent
from src.model.run import RunStreamRequest
from src.model.thread import (
    Thread,
    ThreadHistoryRequest,
    ThreadSearchRequest,
    ThreadState,
    ThreadStateUpdateRequest,
)
from src.repository.checkpointer import checkpointer
from src.service.langgraph_api.run_service import execute_stream_run
from src.service.langgraph_api.serialization import serialize_snapshot, serialize_state
from src.util.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/threads", tags=["threads"])

# In-memory thread registry
_threads: dict[str, Thread] = {}
# In-memory checkpointer lifetime matches these compiled graph bindings.
_thread_agents: dict[str, Any] = {}


def _extract_values_from_checkpoint(checkpoint: dict) -> dict:
    """Keep v1 channel names; never flatten custom dict state or internal channels."""
    channels = checkpoint.get("channel_values", {}) or {}
    return serialize_state(
        {
            key: value
            for key, value in channels.items()
            if not key.startswith(("__", "branch:", "start:"))
        }
    )


@router.post("")
async def create_thread(metadata: Optional[dict] = None):
    """Create a new thread."""
    thread_id = str(uuid4())
    thread = Thread(
        thread_id=thread_id,
        metadata=metadata or {},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    _threads[thread_id] = thread
    logger.info(f"Created thread: {thread_id}")
    return thread.model_dump()


@router.post("/search")
async def search_threads(request: ThreadSearchRequest = None):
    """
    Search for threads.

    Returns threads from both in-memory registry and checkpointer.
    """
    logger.info("Searching threads")

    # Get threads from checkpointer
    thread_ids_from_checkpointer = set()
    try:
        all_tuples = list(checkpointer.list(None))
        for t in all_tuples:
            config = t.config or {}
            configurable = config.get("configurable", {})
            tid = configurable.get("thread_id")
            if tid:
                thread_ids_from_checkpointer.add(tid)
    except Exception as e:
        logger.warning(f"Failed to list checkpoints: {e}")

    # Merge with in-memory threads
    all_thread_ids = set(_threads.keys()) | thread_ids_from_checkpointer

    threads = []
    for tid in all_thread_ids:
        if tid in _threads:
            threads.append(_threads[tid])
        else:
            thread = Thread(
                thread_id=tid,
                metadata={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            _threads[tid] = thread
            threads.append(thread)

    if request and request.status:
        threads = [t for t in threads if t.status == request.status]

    offset = request.offset if request else 0
    limit = request.limit if request else 10

    return [t.model_dump() for t in threads[offset : offset + limit]]


@router.get("/{thread_id}")
async def get_thread(thread_id: str):
    """Get thread by ID."""
    logger.info(f"Getting thread: {thread_id}")

    if thread_id in _threads:
        return _threads[thread_id].model_dump()

    # Check if thread exists in checkpointer
    try:
        tuples = list(checkpointer.list({"configurable": {"thread_id": thread_id}}))
        if tuples:
            thread = Thread(
                thread_id=thread_id,
                metadata={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            _threads[thread_id] = thread
            return thread.model_dump()
    except Exception as e:
        logger.warning(f"Failed to check checkpointer: {e}")

    raise HTTPException(status_code=404, detail="Thread not found")


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread."""
    if thread_id in _threads:
        del _threads[thread_id]
        _thread_agents.pop(thread_id, None)
        logger.info(f"Deleted thread: {thread_id}")
        return {"status": "deleted", "thread_id": thread_id}

    raise HTTPException(status_code=404, detail="Thread not found")


@router.get("/{thread_id}/state")
async def get_thread_state(thread_id: str, checkpoint_id: Optional[str] = None):
    """Get current state for a thread."""
    logger.info(f"Getting state for thread: {thread_id}")

    config = {"configurable": {"thread_id": thread_id}}
    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id

    try:
        if thread_id in _thread_agents:
            return serialize_snapshot(await _thread_agents[thread_id].aget_state(config))
        tuples = list(checkpointer.list(config, limit=1))
        if not tuples:
            return ThreadState(
                values={},
                next=[],
                checkpoint_id=None,
                metadata={"thread_id": thread_id},
            ).model_dump()

        latest = tuples[0]
        values = _extract_values_from_checkpoint(latest.checkpoint)

        return ThreadState(
            values=values,
            next=[],
            checkpoint_id=latest.checkpoint.get("id"),
            created_at=latest.checkpoint.get("ts"),
            metadata={"thread_id": thread_id},
        ).model_dump()
    except Exception as e:
        logger.error(f"Failed to get thread state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read thread state") from e


@router.post("/{thread_id}/state")
async def update_thread_state(thread_id: str, request: ThreadStateUpdateRequest):
    """Update thread state."""
    logger.info(f"Updating state for thread: {thread_id}")

    raise HTTPException(status_code=501, detail="Thread state updates are not implemented")


@router.api_route("/{thread_id}/history", methods=["GET", "POST"])
async def get_thread_history(
    thread_id: str,
    request: Optional[ThreadHistoryRequest] = None,
):
    """
    Get thread history.

    Returns list of checkpoints for the thread, grouped by step.
    For each step, only the checkpoint with the most messages is returned.
    """
    logger.info(f"Getting history for thread: {thread_id}")

    limit = request.limit if request else 10

    try:
        if thread_id in _thread_agents:
            config = {"configurable": {"thread_id": thread_id}}
            return [
                serialize_snapshot(snapshot)
                async for snapshot in _thread_agents[thread_id].aget_state_history(
                    config, limit=limit
                )
            ]

        tuples = list(
            checkpointer.list(
                {"configurable": {"thread_id": thread_id}},
                limit=limit * 2,  # Get more to handle grouping
            )
        )

        if not tuples:
            return []

        # Group by step, keep checkpoint with most messages
        grouped: dict[int, list] = {}
        for t in tuples:
            step_metadata = t.metadata or {}
            step = (
                getattr(step_metadata, "step", 0)
                if hasattr(step_metadata, "step")
                else step_metadata.get("step", 0)
            )
            grouped.setdefault(step, []).append(t)

        history: list[dict[str, Any]] = []
        for step in sorted(grouped.keys()):
            candidates = grouped[step]
            best = max(
                candidates,
                key=lambda t: len(
                    _extract_values_from_checkpoint(t.checkpoint).get("messages", [])
                ),
            )

            # values: messages/todos/files 等，来自 checkpoint.channel_values
            values = _extract_values_from_checkpoint(best.checkpoint)

            # 构造符合 LangGraph ThreadState.checkpoint 结构的 checkpoint 字段
            config = (best.config or {}).get("configurable", {})
            checkpoint = {
                "thread_id": config.get("thread_id", thread_id),
                "checkpoint_ns": config.get("checkpoint_ns", ""),
                "checkpoint_id": config.get("checkpoint_id") or best.checkpoint.get("id"),
                "checkpoint_map": None,
            }

            # parent_checkpoint：当前场景可为空，占位即可满足 SDK 类型
            parent_config = getattr(best, "parent_config", None) or {}
            parent_conf_cfg = (
                parent_config.get("configurable") if isinstance(parent_config, dict) else None
            )
            parent_checkpoint: Optional[dict[str, Any]]
            if parent_conf_cfg:
                parent_checkpoint = {
                    "thread_id": parent_conf_cfg.get("thread_id", thread_id),
                    "checkpoint_ns": parent_conf_cfg.get("checkpoint_ns", ""),
                    "checkpoint_id": parent_conf_cfg.get("checkpoint_id"),
                    "checkpoint_map": None,
                }
            else:
                parent_checkpoint = None

            # 合并 metadata：保留原有信息并补充 thread_id / step
            best_metadata = best.metadata or {}
            metadata: dict[str, Any]
            if isinstance(best_metadata, dict):
                metadata = {**best_metadata}
            else:
                # 对象形式时，退化为只有 step/thread_id
                metadata = {}
            metadata.setdefault("thread_id", thread_id)
            metadata.setdefault("step", step)

            history.append(
                {
                    "values": values,
                    "next": [],
                    "checkpoint": checkpoint,
                    "metadata": metadata,
                    "created_at": best.checkpoint.get("ts"),
                    "parent_checkpoint": parent_checkpoint,
                    "tasks": [],
                }
            )

        return history[:limit]
    except Exception as e:
        logger.error(f"Failed to get thread history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to read thread history") from e


@router.post("/{thread_id}/runs/stream")
async def stream_run(thread_id: str, request: RunStreamRequest):
    """
    Execute a streaming run for a thread.

    This is the core endpoint for agent execution with SSE streaming.
    """
    logger.info(f"Starting stream run for thread: {thread_id}")

    agent, run_config = await prepare_run_agent(request.assistant_id, request.config)
    if request.checkpoint:
        checkpoint = request.checkpoint
        if checkpoint.get("thread_id", thread_id) != thread_id:
            raise HTTPException(status_code=422, detail="Checkpoint belongs to another thread")
        run_config["configurable"].update(
            {
                key: checkpoint[key]
                for key in ("checkpoint_id", "checkpoint_ns")
                if key in checkpoint
            }
        )
    _thread_agents[thread_id] = agent
    # Ensure thread exists
    if thread_id not in _threads:
        _threads[thread_id] = Thread(
            thread_id=thread_id,
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def event_generator():
        async for event in execute_stream_run(
            thread_id=thread_id,
            assistant_id=request.assistant_id,
            input_data=request.input,
            stream_mode=request.stream_mode,
            stream_subgraphs=request.stream_subgraphs,
            config=run_config,
            agent=agent,
            command=request.command.model_dump(exclude_unset=True) if request.command else None,
            interrupt_before=request.interrupt_before,
            interrupt_after=request.interrupt_after,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
