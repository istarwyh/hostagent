"""Exercise API contracts with real in-memory LangGraph graphs and no provider keys."""

import asyncio
import json
from typing import TypedDict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from deepagents.audit_tool_node import SimpleAuditToolNode
from deepagents.middleware.subagents import _create_task_tool
from deepagents.model import get_default_model
from deepagents.state import DeepAgentState
from src.app.agent_config import AgentConfig
from src.app.agent_initializer import agent_pool, registry
from src.facade.langgraph_api.main import app
from src.repository.checkpointer import checkpointer
from src.service.research_agent.research_agent_tools import internet_search


class CounterState(TypedDict):
    """Small local graph state for HTTP and SSE integration tests."""

    value: int
    tag: str
    thread_id: str


def increment(state: CounterState, config: RunnableConfig):
    """Return state and the config actually received by a graph node."""
    return {
        "value": state["value"] + 1,
        "tag": config["configurable"].get("tag", "default"),
        "thread_id": config["configurable"]["thread_id"],
    }


def fail(state: CounterState):
    """Raise an internal error whose details must not reach the client."""
    raise RuntimeError("private-provider-details")


@pytest.fixture
def client(monkeypatch):
    """Start the actual API with provider configuration absent."""
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "TAVILY_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    with TestClient(app, raise_server_exceptions=False) as api:
        yield api


@pytest.fixture
def graph_id():
    """Register a real compiled graph, independent of an external LLM."""
    identifiers = []

    def register(node=increment):
        identifier = str(uuid4())
        graph = StateGraph(CounterState)
        graph.add_node("counter", node)
        graph.add_edge(START, "counter")
        graph.add_edge("counter", END)
        registry.register(AgentConfig(identifier, "Local counter", "API test", [], ""))
        agent_pool.register_instance(identifier, graph.compile(checkpointer=checkpointer))
        identifiers.append(identifier)
        return identifier

    yield register
    for identifier in identifiers:
        registry._configs.pop(identifier, None)
        agent_pool._singletons.pop(identifier, None)


def events(response):
    """Parse the actual SSE response, preserving order and payloads."""
    result = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        result.append(
            (lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: ")))
        )
    return result


def test_server_starts_without_keys(client):
    """Liveness and assistant discovery work without constructing an LLM."""
    assert client.get("/ok").json() == {"status": "ok"}
    assistants = client.post("/assistants/search", json={}).json()
    assert any(a["assistant_id"] == "researchAgent" for a in assistants)


@pytest.mark.parametrize("path", ["/runs/stream", "/threads/test/runs/stream"])
def test_unknown_assistant_returns_404_before_sse(client, path):
    response = client.post(path, json={"assistant_id": "missing"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Assistant not found"}
    assert "text/event-stream" not in response.headers["content-type"]


@pytest.mark.parametrize("path", ["/runs/stream", "/threads/test/runs/stream"])
def test_unconfigured_model_returns_503_before_sse(client, path):
    response = client.post(path, json={"assistant_id": "researchAgent"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_invalid_stream_mode_returns_422(client):
    response = client.post(
        "/runs/stream",
        json={
            "assistant_id": "researchAgent",
            "stream_mode": ["invalid"],
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "config",
    [
        {"configurable": "invalid"},
        {"recursion_limit": 0},
        {"recursion_limit": True},
    ],
)
def test_invalid_graph_configuration_returns_422(client, config):
    response = client.post(
        "/runs/stream",
        json={
            "assistant_id": "researchAgent",
            "config": config,
        },
    )
    assert response.status_code == 422
    response = client.post("/assistants", json={"graph_id": "researchAgent", "config": config})
    assert response.status_code == 422


def test_unimplemented_state_update_does_not_claim_success(client):
    response = client.post("/threads/test/state", json={"values": {"value": 1}})
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"]


def test_missing_search_key_is_an_actionable_tool_error(client):
    result = internet_search.invoke({"query": "API verification"})
    assert result == "Web search is unavailable: configure TAVILY_API_KEY"


def test_json_assistant_create_update_and_run(client, graph_id):
    identifier = graph_id()
    response = client.post(
        "/assistants",
        json={
            "graph_id": identifier,
            "name": "Custom Research",
            "config": {"configurable": {"tag": "assistant"}},
            "metadata": {"created_by": "user", "project": "verification"},
        },
    )
    assert response.status_code == 200
    assistant = response.json()
    assert assistant["graph_id"] == identifier
    assert assistant["name"] == "Custom Research"
    assert assistant["metadata"]["project"] == "verification"
    assistant_id = assistant["assistant_id"]
    patched = client.patch(
        f"/assistants/{assistant_id}",
        json={
            "name": "Renamed",
            "config": {"configurable": {"tag": "updated"}},
        },
    )
    assert patched.status_code == 200
    assert client.get(f"/assistants/{assistant_id}").json()["name"] == "Renamed"
    payload = {"assistant_id": assistant_id, "input": {"value": 1}, "stream_mode": ["values"]}
    data = events(client.post("/threads/owned-thread/runs/stream", json=payload))
    values = [value for name, value in data if name == "values"]
    assert values[-1]["tag"] == "updated"
    payload["config"] = {"configurable": {"tag": "run", "thread_id": "injected"}}
    data = events(client.post("/threads/owned-thread/runs/stream", json=payload))
    values = [value for name, value in data if name == "values"]
    assert values[-1]["tag"] == "run"
    assert values[-1]["thread_id"] == "owned-thread"
    assert data[-1] == ("end", {})
    assert client.delete(f"/assistants/{assistant_id}").status_code == 200


@pytest.mark.parametrize("path", ["/runs/stream", "/threads/mixed/runs/stream"])
def test_mixed_modes_keep_values_and_updates_distinct(client, graph_id, path):
    response = client.post(
        path,
        json={
            "assistant_id": graph_id(),
            "input": {"value": 2},
            "stream_mode": ["values", "updates"],
        },
    )
    assert response.status_code == 200
    data = events(response)
    values = [value for name, value in data if name == "values"]
    updates = [value for name, value in data if name == "updates"]
    assert len(values) == 2
    assert len(updates) == 1
    assert values[-1]["value"] == 3
    assert updates[0]["counter"]["value"] == 3
    assert data[-1] == ("end", {})


def test_runtime_failure_sends_safe_sse_error(client, graph_id):
    response = client.post(
        "/runs/stream",
        json={
            "assistant_id": graph_id(fail),
            "input": {"value": 1},
        },
    )
    assert response.status_code == 200
    data = events(response)
    assert data[0][0] == "metadata"
    assert data[-1][0] == "error"
    assert data[-1][1]["error"] == "RunError"
    assert data[-1][1]["run_id"] == data[0][1]["run_id"]
    assert "private-provider-details" not in response.text


def test_thread_create_fetch_delete_and_missing(client):
    response = client.post("/threads", json={"project": "verification"})
    assert response.status_code == 200
    thread_id = response.json()["thread_id"]
    assert client.get(f"/threads/{thread_id}").status_code == 200
    assert client.delete(f"/threads/{thread_id}").status_code == 200
    assert client.get(f"/threads/{thread_id}").status_code == 404


@pytest.mark.parametrize("is_async", [False, True])
def test_failing_tool_preserves_original_error_and_writes_audit(tmp_path, is_async):
    """The audit finally block must not replace a failed tool's exception."""

    @tool
    def explode() -> str:
        """Raise a deliberate error to exercise the audit failure path."""
        raise ValueError("deliberate-tool-failure")

    node = SimpleAuditToolNode([explode], audit_dir=str(tmp_path), handle_tool_errors=False)
    graph = StateGraph(DeepAgentState)
    graph.add_node("tools", node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile()
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "explode", "args": {}, "id": "failure-test"},
                ],
            )
        ]
    }
    with pytest.raises(ValueError, match="deliberate-tool-failure"):
        if is_async:
            asyncio.run(compiled.ainvoke(state))
        else:
            compiled.invoke(state)
    audits = list(tmp_path.glob("*.json"))
    assert len(audits) == 1
    audit = json.loads(audits[0].read_text())
    assert "deliberate-tool-failure" in str(audit)


def test_async_subagent_runs_an_async_only_graph(monkeypatch):
    """An async graph requires ainvoke; invoke cannot execute its node."""
    monkeypatch.setenv("OPENAI_API_KEY", "inspection-placeholder")

    async def respond(state):
        return {"messages": [AIMessage(content="Local subagent completed")]}

    graph = StateGraph(DeepAgentState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    task = _create_task_tool(
        default_tools=[],
        subagents=[{"name": "local", "description": "local graph", "runnable": graph.compile()}],
        default_model=get_default_model(),
        default_middleware=[],
        default_interrupt_on=None,
        general_purpose_agent=False,
    )
    result = asyncio.run(
        task.ainvoke(
            {
                "description": "verification",
                "subagent_type": "local",
                "runtime": ToolRuntime(
                    state={"messages": []},
                    context=None,
                    config={},
                    tool_call_id="verify",
                    store=None,
                    stream_writer=lambda _: None,
                ),
            }
        )
    )
    assert result.update["messages"][0].content == "Local subagent completed"
