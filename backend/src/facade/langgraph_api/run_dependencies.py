"""Validate run prerequisites before committing SSE response headers."""

from fastapi import HTTPException

from src.app.agent_initializer import agent_pool, registry
from src.service.langgraph_api.assistant_service import get_all_assistants


async def prepare_run_agent(assistant_id: str, config: dict | None):
    """Resolve system or user assistants and validate the configured graph."""
    assistant = get_all_assistants().get(assistant_id)
    if assistant is None:
        raise HTTPException(status_code=404, detail="Assistant not found")
    graph_id = assistant.graph_id
    if not registry.has_agent(graph_id):
        raise HTTPException(status_code=422, detail="Assistant graph is not available")
    run_config = {**assistant.config, **(config or {})}
    run_config["configurable"] = {
        **assistant.config.get("configurable", {}),
        **(config or {}).get("configurable", {}),
    }
    return agent_pool.get_agent(graph_id), run_config
