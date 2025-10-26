"""
FastAPI facade for Research Agent following LangGraph best practices.

Provides:
- Streaming endpoints with SSE
- Sync and async invocation
- State persistence with checkpointing
- Thread-based session management
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncIterator, Any
import json
import logging
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import StreamMode

from src.service.research_agent.research_agent import agent as base_agent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Research Agent API",
    description="LangGraph-based Research Agent with streaming and state management",
    version="1.0.0"
)
research_agent = base_agent


# Request/Response Models
class ResearchRequest(BaseModel):
    """Request model for research queries."""
    query: str = Field(..., description="The research query to process")
    thread_id: Optional[str] = Field(None, description="Thread ID for conversation continuity")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the latest developments in quantum computing?",
                "thread_id": "user-123"
            }
        }


class ResearchResponse(BaseModel):
    """Response model for completed research."""
    result: Any
    thread_id: str
    status: str = "completed"


class StreamEvent(BaseModel):
    """Stream event model."""
    event: str
    data: Any
    thread_id: str


# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "research-agent"}


@app.post("/research/invoke", response_model=ResearchResponse)
async def invoke_research(request: ResearchRequest):
    """
    Synchronous research invocation.
    Returns final result after agent completes.
    """
    thread_id = request.thread_id or str(uuid4())

    try:
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        result = await research_agent.ainvoke(
            {"messages": [{"role": "user", "content": request.query}]},
            config=config
        )

        return ResearchResponse(
            result=result,
            thread_id=thread_id,
            status="completed"
        )

    except Exception as e:
        logger.error(f"Error in invoke_research: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/research/stream")
async def stream_research(request: ResearchRequest):
    """
    Streaming research endpoint with Server-Sent Events.
    Returns real-time agent execution events.
    """
    thread_id = request.thread_id or str(uuid4())

    async def event_generator() -> AsyncIterator[str]:
        try:
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            async for event in research_agent.astream_events(
                {"messages": [{"role": "user", "content": request.query}]},
                config=config,
                version="v2"
            ):
                # Format as SSE
                event_data = {
                    "event": event.get("event", "unknown"),
                    "data": event.get("data", {}),
                    "thread_id": thread_id
                }
                yield f"data: {json.dumps(event_data, default=str)}\n\n"

            # Send completion event
            yield f"data: {json.dumps({'event': 'done', 'thread_id': thread_id})}\n\n"

        except Exception as e:
            logger.error(f"Error in stream_research: {str(e)}")
            error_event = {
                "event": "error",
                "data": {"error": str(e)},
                "thread_id": thread_id
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/research/stream-updates")
async def stream_updates(request: ResearchRequest):
    """
    Stream agent state updates.
    Returns state changes as they occur.
    """
    thread_id = request.thread_id or str(uuid4())

    async def update_generator() -> AsyncIterator[str]:
        try:
            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            async for chunk in research_agent.astream(
                {"messages": [{"role": "user", "content": request.query}]},
                config=config,
                stream_mode="updates"
            ):
                event_data = {
                    "event": "update",
                    "data": chunk,
                    "thread_id": thread_id
                }
                yield f"data: {json.dumps(event_data, default=str)}\n\n"

            yield f"data: {json.dumps({'event': 'done', 'thread_id': thread_id})}\n\n"

        except Exception as e:
            logger.error(f"Error in stream_updates: {str(e)}")
            error_event = {
                "event": "error",
                "data": {"error": str(e)},
                "thread_id": thread_id
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        update_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/research/state/{thread_id}")
async def get_state(thread_id: str):
    """
    Get current state for a thread.
    Useful for checking agent status.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = await research_agent.aget_state(config)

        return {
            "thread_id": thread_id,
            "state": state.values if state else None,
            "next_steps": state.next if state else []
        }

    except Exception as e:
        logger.error(f"Error getting state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Research Agent API",
        "version": "1.0.0",
        "endpoints": {
            "invoke": "/research/invoke",
            "stream": "/research/stream",
            "stream_updates": "/research/stream-updates",
            "get_state": "/research/state/{thread_id}",
            "health": "/health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
