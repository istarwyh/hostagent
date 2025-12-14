from dotenv import load_dotenv

from src.app.agent_config import AgentConfig
from src.app.agent_pool import AgentPool
from src.app.agent_registry import AgentRegistry
from src.deepagents.graph import create_deep_agent
from src.repository.checkpointer import checkpointer
from src.service.research_agent.research_agent_prompt import (
    critique_sub_agent,
    research_instructions,
    sub_research_prompt,
)
from src.service.research_agent.research_agent_tools import internet_search
from src.util.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# Agent configuration
AGENT_ID = "researchAgent"
AGENT_NAME = "Research Agent"
AGENT_DESCRIPTION = "Research agent for in-depth question answering"

research_sub_agent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions. Only give this researcher one topic at a time. Do not pass multiple sub questions to this researcher. Instead, you should break down a large topic into the necessary components, and then call multiple research agents in parallel, one for each sub question.",
    "prompt": sub_research_prompt,
    "tools": ["internet_search"],
}

# Create the agent instance (module-level singleton)
logger.info(f"Creating {AGENT_NAME}...")
agent = create_deep_agent(
    tools=[internet_search],
    instructions=research_instructions,
    subagents=[critique_sub_agent, research_sub_agent],
    checkpointer=checkpointer,
).with_config({"recursion_limit": 1000})
logger.info(f"{AGENT_NAME} created successfully")


def register_to_agent_pool(registry: AgentRegistry, pool: AgentPool) -> None:
    """
    Register this agent to the global agent pool.

    This function should be called during application initialization.

    Args:
        registry: Global agent registry
        pool: Global agent pool
    """
    # Register configuration
    config = AgentConfig(
        agent_id=AGENT_ID,
        name=AGENT_NAME,
        description=AGENT_DESCRIPTION,
        tools=[internet_search],
        instructions=research_instructions,
        subagents=[critique_sub_agent, research_sub_agent],
        scope="singleton",
        recursion_limit=1000,
    )
    registry.register(config)

    # Register the pre-created agent instance
    pool.register_instance(AGENT_ID, agent)
    logger.info(f"{AGENT_NAME} registered to agent pool")
