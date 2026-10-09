"""Immutable prompt composition for current LangChain v1 ModelRequest objects."""

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import SystemMessage


def append_system_prompt(request: ModelRequest, prompt: str) -> ModelRequest:
    message = request.system_message
    content = message.content if message else ""
    if isinstance(content, list):
        content = [*content, {"type": "text", "text": prompt}]
    else:
        content = f"{content}\n\n{prompt}" if content else prompt
    updated = (
        message.model_copy(update={"content": content})
        if message
        else SystemMessage(content=content)
    )
    return request.override(system_message=updated)
