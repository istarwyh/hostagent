"""Shared assistant definitions used by management and run APIs."""

from datetime import datetime

from src.app.agent_initializer import registry
from src.model.assistant import Assistant, AssistantMetadata

# User-created assistants (not from agent_registry)
user_assistants: dict[str, Assistant] = {}


def _build_assistant_from_agent_config(agent_id: str) -> Assistant:
    """
    Convert AgentConfig from registry to Assistant model.

    System agents are automatically discovered from agent_registry,
    eliminating the need to manually maintain assistant configurations.
    """
    config = registry.get_config(agent_id)
    return Assistant(
        assistant_id=config.agent_id,
        graph_id=config.agent_id,
        name=config.name,
        config={"scope": config.scope, "recursion_limit": config.recursion_limit},
        metadata=AssistantMetadata(created_by="system"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        version=1,
    )


def get_all_assistants() -> dict[str, Assistant]:
    """
    Get all assistants (system agents + user-created assistants).

    System agents are dynamically loaded from agent_registry,
    ensuring consistency with available agent implementations.
    """
    # System agents from registry
    system_assistants = {
        agent_id: _build_assistant_from_agent_config(agent_id)
        for agent_id in registry.get_agent_ids()
    }

    # Merge with user-created assistants
    return {**system_assistants, **user_assistants}
