"""
Assistants Router

Provides endpoints for managing assistants compatible with LangGraph SDK.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.model.assistant import Assistant, AssistantMetadata, AssistantSearchRequest
from src.util.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/assistants", tags=["assistants"])

# Default assistant configuration
# Note: graph_id should match what frontend uses as assistantId for search
DEFAULT_ASSISTANT = Assistant(
    assistant_id="researchAgent",
    graph_id="researchAgent",
    name="Research Agent",
    config={},
    metadata=AssistantMetadata(created_by="system"),
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow(),
    version=1,
)

# In-memory assistant registry
_assistants: dict[str, Assistant] = {DEFAULT_ASSISTANT.assistant_id: DEFAULT_ASSISTANT}


@router.post("/search")
async def search_assistants(request: AssistantSearchRequest = None):
    """
    Search for assistants.

    Returns list of assistants matching the search criteria.
    Frontend SDK expects at least one assistant with metadata.created_by === "system".
    """
    logger.info("Searching assistants")

    assistants = list(_assistants.values())

    if request and request.graph_id:
        assistants = [a for a in assistants if a.graph_id == request.graph_id]

    if request and request.metadata:
        for key, value in request.metadata.items():
            assistants = [a for a in assistants if getattr(a.metadata, key, None) == value]

    offset = request.offset if request else 0
    limit = request.limit if request else 10

    return [a.model_dump() for a in assistants[offset : offset + limit]]


@router.get("/{assistant_id}")
async def get_assistant(assistant_id: str):
    """Get assistant by ID."""
    logger.info(f"Getting assistant: {assistant_id}")

    if assistant_id not in _assistants:
        raise HTTPException(status_code=404, detail="Assistant not found")

    return _assistants[assistant_id].model_dump()


@router.post("")
async def create_assistant(
    graph_id: str = "agent",
    name: Optional[str] = None,
    config: Optional[dict] = None,
    metadata: Optional[dict] = None,
):
    """Create a new assistant."""
    from uuid import uuid4

    assistant_id = str(uuid4())
    assistant = Assistant(
        assistant_id=assistant_id,
        graph_id=graph_id,
        name=name or f"Assistant-{assistant_id[:8]}",
        config=config or {},
        metadata=AssistantMetadata(**(metadata or {})),
    )

    _assistants[assistant_id] = assistant
    logger.info(f"Created assistant: {assistant_id}")

    return assistant.model_dump()


@router.patch("/{assistant_id}")
async def update_assistant(
    assistant_id: str,
    name: Optional[str] = None,
    config: Optional[dict] = None,
    metadata: Optional[dict] = None,
):
    """Update an existing assistant."""
    if assistant_id not in _assistants:
        raise HTTPException(status_code=404, detail="Assistant not found")

    assistant = _assistants[assistant_id]

    if name:
        assistant.name = name
    if config:
        assistant.config.update(config)
    if metadata:
        for key, value in metadata.items():
            setattr(assistant.metadata, key, value)

    assistant.updated_at = datetime.utcnow()
    logger.info(f"Updated assistant: {assistant_id}")

    return assistant.model_dump()


@router.delete("/{assistant_id}")
async def delete_assistant(assistant_id: str):
    """Delete an assistant."""
    if assistant_id not in _assistants:
        raise HTTPException(status_code=404, detail="Assistant not found")

    del _assistants[assistant_id]
    logger.info(f"Deleted assistant: {assistant_id}")

    return {"status": "deleted", "assistant_id": assistant_id}
