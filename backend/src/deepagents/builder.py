from typing import Any, Optional

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel
from typing_extensions import NotRequired, TypedDict

from deepagents.graph import async_create_deep_agent, create_deep_agent
from deepagents.sub_agent import SubAgent


class SerializableSubAgent(TypedDict):
    name: str
    description: str
    prompt: str
    tools: NotRequired[list[str]]
    # Optional per-subagent model: can be either a model instance OR dict settings
    model: NotRequired[dict[str, Any]]


def create_configurable_agent(
    default_instructions: str,
    default_sub_agents: list[SerializableSubAgent],
    tools,
    agent_config: Optional[dict] = None,
    **kwargs,
):
    tools = [t if isinstance(t, BaseTool) else tool(t) for t in tools]
    tool_names = [t.name for t in tools]

    class AgentConfig(BaseModel):
        instructions: str = default_instructions
        subagents: list[SerializableSubAgent] = default_sub_agents
        tools: list[str] = tool_names

    def build_agent(config: Optional[dict] = None):
        if config is not None:
            config = config.get("configurable", {})
        else:
            config = {}
        config_fields = {k: v for k, v in config.items() if k in ["instructions", "subagents"]}
        config = AgentConfig(**config_fields)
        return create_deep_agent(
            instructions=config.instructions,
            tools=[t for t in tools if t.name in config.tools],
            subagents=config.subagents,
            config_schema=AgentConfig,
            **kwargs,
        ).with_config(agent_config or {})

    return build_agent


def async_create_configurable_agent(
    default_instructions: str,
    default_sub_agents: list[SerializableSubAgent],
    tools,
    agent_config: Optional[dict] = None,
    **kwargs,
):
    tools = [t if isinstance(t, BaseTool) else tool(t) for t in tools]
    tool_names = [t.name for t in tools]

    class AgentConfig(BaseModel):
        instructions: str = default_instructions
        subagents: list[SerializableSubAgent] = default_sub_agents
        tools: list[str] = tool_names

    def build_agent(config: Optional[dict] = None):
        if config is not None:
            config = config.get("configurable", {})
        else:
            config = {}
        config_fields = {k: v for k, v in config.items() if k in ["instructions", "subagents"]}
        config = AgentConfig(**config_fields)
        return async_create_deep_agent(
            instructions=config.instructions,
            tools=[t for t in tools if t.name in config.tools],
            subagents=config.subagents,
            config_schema=AgentConfig,
            **kwargs,
        ).with_config(agent_config or {"recursion_limit": 1000})

    return build_agent
