"""
Assistants Router

Provides endpoints for managing assistants compatible with LangGraph SDK.
Dynamically discovers system agents from agent_registry and manages user-created assistants.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.model.assistant import (
    Assistant,
    AssistantCreateRequest,
    AssistantMetadata,
    AssistantSearchRequest,
    AssistantUpdateRequest,
)
from src.service.langgraph_api.assistant_service import get_all_assistants, user_assistants
from src.util.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.post("/search")
async def search_assistants(request: AssistantSearchRequest = None):
    """
    Search for assistants.

    Returns list of assistants matching the search criteria.
    System agents are automatically discovered from agent_registry.
    Frontend SDK expects at least one assistant with metadata.created_by === "system".
    """
    logger.info("Searching assistants")

    assistants = list(get_all_assistants().values())

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
    """
    Get assistant by ID.

    Supports both system agents (from agent_registry) and user-created assistants.
    """
    logger.info(f"Getting assistant: {assistant_id}")

    assistants = get_all_assistants()
    if assistant_id not in assistants:
        raise HTTPException(status_code=404, detail="Assistant not found")

    return assistants[assistant_id].model_dump()


@router.post("")
async def create_assistant(request: AssistantCreateRequest):
    """
    Create a new user-defined assistant.

    System agents from agent_registry cannot be created via API (they are auto-discovered).
    This endpoint creates user-defined assistants with custom configurations.
    """
    from uuid import uuid4

    assistant_id = str(uuid4())
    assistant = Assistant(
        assistant_id=assistant_id,
        graph_id=request.graph_id,
        name=request.name or f"Assistant-{assistant_id[:8]}",
        config=request.config,
        metadata=AssistantMetadata(**{"created_by": "user", **request.metadata}),
    )

    user_assistants[assistant_id] = assistant
    logger.info(f"Created user assistant: {assistant_id}")

    return assistant.model_dump()


@router.patch("/{assistant_id}")
async def update_assistant(assistant_id: str, request: AssistantUpdateRequest):
    """
    Update an existing user-created assistant.

    System agents from agent_registry are read-only and cannot be modified via API.
    """
    # Only allow updating user-created assistants
    if assistant_id not in user_assistants:
        assistants = get_all_assistants()
        if assistant_id in assistants:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify system agents. System agents are managed via agent_registry.",
            )
        raise HTTPException(status_code=404, detail="Assistant not found")

    assistant = user_assistants[assistant_id]

    if request.name is not None:
        assistant.name = request.name
    if request.config is not None:
        assistant.config.update(request.config)
    if request.metadata is not None:
        for key, value in request.metadata.items():
            setattr(assistant.metadata, key, value)

    assistant.updated_at = datetime.utcnow()
    logger.info(f"Updated user assistant: {assistant_id}")

    return assistant.model_dump()


@router.delete("/{assistant_id}")
async def delete_assistant(assistant_id: str):
    """
    Delete a user-created assistant.

    System agents from agent_registry cannot be deleted via API.
    """
    # Only allow deleting user-created assistants
    if assistant_id not in user_assistants:
        assistants = get_all_assistants()
        if assistant_id in assistants:
            raise HTTPException(
                status_code=403,
                detail="Cannot delete system agents. System agents are managed via agent_registry.",
            )
        raise HTTPException(status_code=404, detail="Assistant not found")

    del user_assistants[assistant_id]
    logger.info(f"Deleted user assistant: {assistant_id}")

    return {"status": "deleted", "assistant_id": assistant_id}
