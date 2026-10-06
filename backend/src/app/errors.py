"""Application errors safe to expose to API clients."""


class AgentUnavailableError(RuntimeError):
    """An agent cannot run because its provider is not configured."""
