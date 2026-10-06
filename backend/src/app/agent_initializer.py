"""
Agent Initializer

Application startup initialization for agent pool.
Imports and registers all domain service agents.
"""

from src.app.agent_pool import AgentPool
from src.app.agent_registry import AgentRegistry
from src.repository.checkpointer import checkpointer
from src.util.logger import setup_logger

logger = setup_logger(__name__)

# Global registry and pool instances
registry = AgentRegistry()
agent_pool = AgentPool(registry, checkpointer)


def initialize_agents():
    """
    Register agent configurations without requiring provider credentials.

    This function imports domain service modules and calls their registration functions.
    Each domain service is responsible for creating and registering its own agents.
    """
    logger.info("Initializing agent pool...")

    # Import and register research agent
    from src.service.research_agent import research_agent

    if not registry.has_agent(research_agent.AGENT_ID):
        research_agent.register_to_agent_pool(registry, agent_pool)

    # Future agents can be registered here by importing their modules:
    # from src.service.code_agent import code_agent
    # code_agent.register_to_agent_pool(registry, agent_pool)

    logger.info("Agent configurations registered; instances are created on first use")
