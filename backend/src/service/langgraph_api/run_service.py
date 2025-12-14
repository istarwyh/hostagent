"""
Run Service

Provides streaming execution service for LangGraph API.
"""

import json
from typing import Any, AsyncIterator, Optional
from uuid import uuid4

from src.repository.checkpointer import checkpointer
from src.util.logger import setup_logger

logger = setup_logger(__name__)


def format_sse_event(event_type: str, data: dict) -> str:
    """Format data as SSE event."""
    json_data = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"


def _serialize_message(msg: Any) -> dict:
    """Serialize a LangChain message to dict."""
    if hasattr(msg, "model_dump"):
        return msg.model_dump()
    if hasattr(msg, "dict"):
        return msg.dict()
    if isinstance(msg, dict):
        return msg
    return {
        "type": getattr(msg, "type", "unknown"),
        "content": getattr(msg, "content", str(msg)),
        "id": getattr(msg, "id", str(uuid4())),
        "additional_kwargs": getattr(msg, "additional_kwargs", {}),
        "response_metadata": getattr(msg, "response_metadata", {}),
    }


def serialize_state(state: dict) -> dict:
    """Serialize agent state to JSON-compatible dict."""
    result = {}
    for key, value in state.items():
        if key == "messages" and isinstance(value, list):
            result[key] = [_serialize_message(m) for m in value]
        elif hasattr(value, "model_dump"):
            result[key] = value.model_dump()
        else:
            result[key] = value
    return result


def _get_agent(assistant_id: str):
    """Get agent instance by assistant ID."""
    from src.deepagents.graph import create_deep_agent
    from src.service.research_agent.research_agent_prompt import (
        critique_sub_agent,
        research_instructions,
        sub_research_prompt,
    )
    from src.service.research_agent.research_agent_tools import internet_search

    research_sub_agent = {
        "name": "research-agent",
        "description": "Used to research more in depth questions.",
        "prompt": sub_research_prompt,
        "tools": ["internet_search"],
    }

    logger.info(f"Creating agent for assistant: {assistant_id}")
    agent = create_deep_agent(
        tools=[internet_search],
        instructions=research_instructions,
        subagents=[critique_sub_agent, research_sub_agent],
        checkpointer=checkpointer,
    ).with_config({"recursion_limit": 1000})

    return agent


async def execute_stream_run(
    thread_id: str,
    assistant_id: str,
    input_data: Optional[dict] = None,
    stream_mode: Optional[list[str]] = None,
    config: Optional[dict] = None,
) -> AsyncIterator[str]:
    """
    Execute a streaming run and yield SSE events.

    Args:
        thread_id: Thread ID for the conversation
        assistant_id: Assistant ID to use
        input_data: Input data containing messages
        stream_mode: Stream modes to use (updates, values, messages)
        config: Additional configuration

    Yields:
        SSE formatted events
    """
    run_id = str(uuid4())
    logger.info(f"Executing stream run: {run_id} for thread: {thread_id}")

    # Send metadata event
    yield format_sse_event("metadata", {"run_id": run_id})

    try:
        agent = _get_agent(assistant_id)

        run_config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        if config:
            run_config.update(config)

        # Determine stream mode
        mode = "updates"
        if stream_mode and len(stream_mode) > 0:
            mode = stream_mode[0]

        async for chunk in agent.astream(
            input_data or {},
            config=run_config,
            stream_mode=mode,
        ):
            serialized = serialize_state(chunk) if isinstance(chunk, dict) else chunk
            yield format_sse_event(mode, serialized)

        # Send end event
        yield format_sse_event("end", {})
        logger.info(f"Stream run completed: {run_id}")

    except Exception as e:
        logger.error(f"Stream run failed: {run_id}", exc_info=True)
        yield format_sse_event("error", {"message": str(e), "code": "EXECUTION_ERROR"})
