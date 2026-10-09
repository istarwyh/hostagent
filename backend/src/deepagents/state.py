"""Shared v1 state for local tools and application-level graph tests."""

from langchain.agents.middleware.todo import PlanningState

from deepagents.middleware.filesystem import FilesystemState


class DeepAgentState(FilesystemState, PlanningState):
    """Combine upstream filesystem and todo reducers without changing their schemas."""
