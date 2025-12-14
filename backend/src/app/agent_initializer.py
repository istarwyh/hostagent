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
    Initialize all agent configurations and instances.

    This function imports domain service modules and calls their registration functions.
    Each domain service is responsible for creating and registering its own agents.
    """
    logger.info("Initializing agent pool...")

    # Import and register research agent
    from src.service.research_agent import research_agent

    research_agent.register_to_agent_pool(registry, agent_pool)

    # Future agents can be registered here by importing their modules:
    # from src.service.code_agent import code_agent
    # code_agent.register_to_agent_pool(registry, agent_pool)

    # Preload any singleton agents that weren't registered via register_instance()
    # (This is now a fallback mechanism)
    agent_pool.preload_singletons()

    logger.info("Agent pool initialization completed")


# Initialize agents on module import (application startup)
initialize_agents()
