"""
Runs Router

Provides endpoints for stateless run execution compatible with LangGraph SDK.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.model.run import RunStreamRequest
from src.service.langgraph_api.run_service import execute_stream_run
from src.util.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/stream")
async def stream_run(request: RunStreamRequest):
    """
    Execute a stateless streaming run.

    Creates a temporary thread for execution if no thread_id is provided.
    """
    from uuid import uuid4

    thread_id = str(uuid4())
    logger.info(f"Starting stateless stream run with temp thread: {thread_id}")

    async def event_generator():
        async for event in execute_stream_run(
            thread_id=thread_id,
            assistant_id=request.assistant_id,
            input_data=request.input,
            stream_mode=request.stream_mode,
            stream_subgraphs=request.stream_subgraphs,
            config=request.config,
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
