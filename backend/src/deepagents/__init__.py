"""HostAgent's upstream LangChain v1 framework."""

from deepagents.graph import create_deep_agent
from deepagents.middleware.subagents import CompiledSubAgent, SubAgent
from deepagents.model import get_default_model

# create_agent graphs provide both invoke and ainvoke.
async_create_deep_agent = create_deep_agent

__all__ = [
    "CompiledSubAgent",
    "SubAgent",
    "create_deep_agent",
    "async_create_deep_agent",
    "get_default_model",
]
