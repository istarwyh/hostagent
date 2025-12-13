"""
ReAct agent from scratch using LangGraph, following:
https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/

Prerequisites:
  pip install -U langgraph langchain-openai

This example uses Moonshot AI (Kimi) API with OpenAI-compatible interface.
Set OPENAI_API_KEY to your Moonshot API key when prompted at runtime.
"""
from __future__ import annotations

import os
import json
import getpass
from typing import Annotated, Sequence, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END


# ---------- Setup: ensure OPENAI_API_KEY exists ----------

def _set_env(var: str) -> None:
    if not os.environ.get(var):
        # Prompt only in interactive terminals
        try:
            os.environ[var] = getpass.getpass(f"{var}: ")
        except Exception:
            raise RuntimeError(f"Environment variable {var} not set")


# ---------- Define graph state ----------

class AgentState(TypedDict):
    """The state of the agent.

    messages is a list of LangChain BaseMessage. add_messages is a reducer.
    """

    # See https://langchain-ai.github.io/langgraph/concepts/low_level/#reducers
    messages: Annotated[Sequence[BaseMessage], add_messages]


# ---------- Define model and tools ----------

model = ChatOpenAI(base_url="https://api.moonshot.cn/v1", model="kimi-k2-turbo-preview")


@tool
def get_weather(location: str):
    """Call to get the weather from a specific location."""
    # Placeholder implementation
    if any(city in location.lower() for city in ["sf", "san francisco"]):
        return "It's sunny in San Francisco, but you better look out if you're a Gemini 😈."
    else:
        return f"I am not sure what the weather is in {location}"


tools = [get_weather]
model = model.bind_tools(tools)

# For quick lookup by name in the tool node
tools_by_name = {tool_.name: tool_ for tool_ in tools}


# ---------- Define nodes and edges ----------

def tool_node(state: AgentState):
    """A simplified Tool node that executes tool calls from the last AI message."""
    outputs: list[ToolMessage] = []
    last = state["messages"][-1]
    # Gracefully handle when there are no tool calls
    tool_calls = getattr(last, "tool_calls", None) or []
    for tool_call in tool_calls:
        name = tool_call["name"]
        args = tool_call["args"]

        # Check if tool exists
        if name not in tools_by_name:
            outputs.append(
                ToolMessage(
                    content=f"Error: Tool '{name}' not found",
                    name=name,
                    tool_call_id=tool_call["id"],
                )
            )
            continue

        tool_result = tools_by_name[name].invoke(args)
        outputs.append(
            ToolMessage(
                content=str(tool_result),
                name=name,
                tool_call_id=tool_call["id"],
            )
        )
    return {"messages": outputs}


def call_model(state: AgentState, config: RunnableConfig):
    """Call the chat model with a system prompt and current messages."""
    system_prompt = SystemMessage(
        content=(
            "You are a helpful AI assistant, please respond to the user's query to the best of your ability!"
        )
    )
    response: AIMessage = model.invoke([system_prompt] + list(state["messages"]), config)
    # Return as list so LangGraph appends to existing messages
    return {"messages": [response]}


def should_continue(state: AgentState):
    """Conditional edge: if last AI message included any tool calls, continue to tools."""
    last_message = state["messages"][-1]
    if not getattr(last_message, "tool_calls", None):
        return "end"
    else:
        return "continue"


# ---------- Define and compile the graph ----------

workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

# Entry point
workflow.set_entry_point("agent")

# Conditional edges from agent
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",
        "end": END,
    },
)

# Cycle back from tools to agent
workflow.add_edge("tools", "agent")

# Compile the graph
graph = workflow.compile()


# ---------- Demo / Usage ----------

def print_stream(stream):
    """Helper to pretty-print streamed values."""
    for s in stream:
        message = s["messages"][-1]
        print(message)

def _maybe_show_graph_png():
    try:
        from IPython.display import Image, display  # type: ignore

        display(Image(graph.get_graph().draw_mermaid_png()))
    except Exception:
        # Optional visualization requires extra deps
        pass


if __name__ == "__main__":
    _set_env("OPENAI_API_KEY")
    _maybe_show_graph_png()

    inputs = {"messages": [("user", "what is the weather in sf")]}

    print_stream(graph.stream(inputs, stream_mode="values"))
