"""Offline end-to-end checks of the v1 graph through the real API boundary."""

import asyncio
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import Field

from deepagents import create_deep_agent
from deepagents.middleware.filesystem import _create_file_data
from deepagents.state import DeepAgentState
from src.app.agent_config import AgentConfig
from src.app.agent_initializer import agent_pool, registry
from src.facade.langgraph_api.main import app
from src.repository.checkpointer import checkpointer
from src.service.langgraph_api.serialization import normalize_input, serialize_state


class ScriptModel(BaseChatModel):
    """Deterministic local tool-calling model; never opens a provider connection."""

    responses: list[AIMessage] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "local-script"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        index = sum(isinstance(message, AIMessage) for message in messages)
        message = self.responses[min(index, len(self.responses) - 1)]
        return ChatResult(generations=[ChatGeneration(message=message.model_copy(deep=True))])


def calls(*tools):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": str(uuid4())} for name, args in tools],
    )


def parse_events(response):
    assert response.status_code == 200, response.text
    return [
        (lines[0][7:], json.loads(lines[1][6:]))
        for block in response.text.strip().split("\n\n")
        if (lines := block.splitlines())
    ]


@pytest.fixture
def api():
    identifiers = []
    with TestClient(app, raise_server_exceptions=False) as client:

        def register(graph):
            identifier = str(uuid4())
            registry.register(AgentConfig(identifier, "v1 local", "test", [], ""))
            agent_pool.register_instance(identifier, graph)
            identifiers.append(identifier)
            return identifier

        yield client, register
    for identifier in identifiers:
        registry._configs.pop(identifier, None)
        agent_pool._singletons.pop(identifier, None)


@pytest.mark.parametrize("is_async", [False, True])
def test_v1_todos_and_file_tools_preserve_reducers(is_async, tmp_path):
    model = ScriptModel(
        responses=[
            calls(
                ("write_todos", {"todos": [{"content": "write report", "status": "in_progress"}]})
            ),
            calls(("write_file", {"file_path": "/report.txt", "content": "first\nsecond"})),
            calls(
                (
                    "edit_file",
                    {"file_path": "/report.txt", "old_string": "first", "new_string": "updated"},
                )
            ),
            calls(("read_file", {"file_path": "/report.txt"})),
            AIMessage(content="done"),
        ]
    )
    graph = create_deep_agent(model=model, tools=[], audit_dir=str(tmp_path))
    state = {"messages": [{"role": "user", "content": "write report"}]}
    result = asyncio.run(graph.ainvoke(state)) if is_async else graph.invoke(state)
    assert result["todos"][0]["content"] == "write report"
    assert result["files"]["/report.txt"]["content"] == ["updated", "second"]
    assert "created_at" in result["files"]["/report.txt"]
    assert result["messages"][-1].content == "done"
    assert len(list(tmp_path.glob("*.json"))) == 4


def test_v1_file_state_stream_history_and_input_compatibility(api):
    client, register = api
    model = ScriptModel(
        responses=[
            calls(("read_file", {"file_path": "/input.txt"})),
            calls(("write_file", {"file_path": "/result.txt", "content": "one\ntwo"})),
            AIMessage(content="done"),
        ]
    )
    identifier = register(create_deep_agent(model=model, tools=[], checkpointer=checkpointer))
    thread_id = str(uuid4())
    response = client.post(
        f"/threads/{thread_id}/runs/stream",
        json={
            "assistant_id": identifier,
            "input": {
                "messages": [{"role": "user", "content": "write file"}],
                "files": {"input.txt": "original"},
            },
            "stream_mode": ["values", "updates", "checkpoints"],
        },
    )
    events = parse_events(response)
    assert events[-1][0] == "end", response.text
    assert all(not (name == "error") for name, _ in events)
    values = [value for name, value in events if name == "values"]
    assert values[-1]["files"]["/result.txt"] == "one\ntwo"
    assert values[-1]["files"]["/input.txt"] == "original"
    checkpoints = [value for name, value in events if name == "checkpoints"]
    assert checkpoints[-1]["values"]["files"]["/result.txt"] == "one\ntwo"
    state = client.get(f"/threads/{thread_id}/state").json()
    assert state["values"]["files"]["/result.txt"] == "one\ntwo"
    history = client.post(f"/threads/{thread_id}/history", json={"limit": 10}).json()
    assert history[0]["values"]["files"]["/result.txt"] == "one\ntwo"
    assert not any(k.startswith("branch:") for k in state["values"])


@pytest.mark.parametrize("decision", ["approve", "edit", "reject"])
def test_v1_hitl_http_resume_preserves_all_ordered_decisions(api, decision):
    client, register = api
    executed = []

    @tool
    def record(value: str) -> str:
        """Record a local value after human review."""
        executed.append(value)
        return value

    model = ScriptModel(
        responses=[
            calls(("record", {"value": "first"}), ("record", {"value": "second"})),
            AIMessage(content="done"),
        ]
    )
    graph = create_deep_agent(
        model=model, tools=[record], checkpointer=checkpointer, interrupt_on={"record": True}
    )
    identifier = register(graph)
    thread_id = str(uuid4())
    path = f"/threads/{thread_id}/runs/stream"
    events = parse_events(
        client.post(
            path,
            json={
                "assistant_id": identifier,
                "input": {"messages": [{"role": "user", "content": "record"}]},
                "stream_mode": ["updates", "values"],
            },
        )
    )
    interruptions = [
        value["__interrupt__"]
        for _, value in events
        if isinstance(value, dict) and "__interrupt__" in value
    ]
    assert interruptions, events
    assert len(interruptions[0][0]["value"]["action_requests"]) == 2
    assert executed == []
    state = client.get(f"/threads/{thread_id}/state").json()
    assert state["tasks"][0]["interrupts"][0]["value"]["action_requests"]
    second = {"type": decision}
    if decision == "edit":
        second["edited_action"] = {"name": "record", "args": {"value": "edited"}}
    if decision == "reject":
        second["message"] = "skip second"
    events = parse_events(
        client.post(
            path,
            json={
                "assistant_id": identifier,
                "command": {"resume": {"decisions": [{"type": "approve"}, second]}},
                "stream_mode": ["updates", "values"],
            },
        )
    )
    assert not any(name == "error" for name, _ in events), events
    assert sorted(executed) == sorted(
        ["first"] + ([] if decision == "reject" else ["edited" if decision == "edit" else "second"])
    )
    assert not client.get(f"/threads/{thread_id}/state").json()["next"]


def test_async_compiled_subagents_keep_parent_todos_and_merge_files():
    observed = []

    async def respond(state):
        description = state["messages"][0].content
        observed.append(
            {
                "description": description,
                "todos": state.get("todos"),
                "count": len(state["messages"]),
            }
        )
        return {
            "messages": [AIMessage(content=f"done {description}")],
            "files": {f"/{description}.txt": _create_file_data(description)},
            "todos": [{"content": "sub-only", "status": "completed"}],
        }

    builder = StateGraph(DeepAgentState)
    builder.add_node("respond", respond)
    builder.add_edge(START, "respond")
    builder.add_edge("respond", END)
    model = ScriptModel(
        responses=[
            calls(("write_todos", {"todos": [{"content": "parent", "status": "pending"}]})),
            calls(
                ("task", {"description": "first", "subagent_type": "local"}),
                ("task", {"description": "second", "subagent_type": "local"}),
            ),
            AIMessage(content="done"),
        ]
    )
    graph = create_deep_agent(
        model=model,
        tools=[],
        subagents=[
            {"name": "local", "description": "local async graph", "runnable": builder.compile()}
        ],
    )
    result = asyncio.run(
        graph.ainvoke(
            {
                "messages": [{"role": "user", "content": "delegate"}],
                "todos": [{"content": "parent", "status": "pending"}],
            }
        )
    )
    assert set(result["files"]) == {"/first.txt", "/second.txt"}
    assert result["todos"] == [{"content": "parent", "status": "pending"}]
    assert all(x["todos"] is None and x["count"] == 1 for x in observed)
    assert len(result["messages"]) == 7


def test_serializer_keeps_custom_channels_and_filters_no_user_data():
    state = {
        "files": {"/a": _create_file_data("line\nend")},
        "email": {"subject": "hello"},
        "todos": [],
    }
    result = serialize_state(state)
    assert result["files"]["/a"] == "line\nend"
    assert result["email"] == {"subject": "hello"}
    assert normalize_input({"files": {"a": "x"}})["files"]["/a"]["content"] == ["x"]


def test_research_registry_uses_v1_subagent_definitions(monkeypatch):
    from src.app.agent_pool import AgentPool
    from src.app.agent_registry import AgentRegistry
    from src.service.research_agent import research_agent

    local_registry = AgentRegistry()
    pool = AgentPool(local_registry, InMemorySaver())
    research_agent.register_to_agent_pool(local_registry, pool)
    local_registry.get_config("researchAgent").model = ScriptModel(
        responses=[AIMessage(content="done")]
    )
    graph = pool.get_agent("researchAgent")
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "hello"}]},
        config={"configurable": {"thread_id": "research-local"}},
    )
    assert result["messages"][-1].content == "done"
    assert "tools" in graph.nodes and "model" in graph.nodes


def test_long_line_file_round_trip_is_byte_preserving():
    original = json.dumps({"payload": "a" * 2200}) + "\n"
    result = serialize_state(normalize_input({"files": {"data.json": original}}))
    assert result["files"]["/data.json"] == original
    assert json.loads(result["files"]["/data.json"])["payload"] == "a" * 2200


@pytest.mark.parametrize("workers", [1, 2])
def test_subagent_hitl_resume_by_id_never_repeats_completed_tools(api, workers):
    client, register = api
    executed = []

    @tool
    def effect(value: str) -> str:
        """Record a completed local side effect."""
        executed.append(value)
        return value

    @tool
    def approve_effect(value: str) -> str:
        """Record a local side effect after approval."""
        executed.append(value)
        return value

    subagents = []
    tasks = []
    for index in range(workers):
        name = f"worker-{index}"
        subagents.append(
            {
                "name": name,
                "description": name,
                "system_prompt": "local",
                "tools": [effect, approve_effect],
                "interrupt_on": {"approve_effect": True},
                "model": ScriptModel(
                    responses=[
                        calls(("effect", {"value": f"before-{index}"})),
                        calls(("approve_effect", {"value": f"after-{index}"})),
                        AIMessage(content="done"),
                    ]
                ),
            }
        )
        tasks.append(("task", {"description": name, "subagent_type": name}))
    graph = create_deep_agent(
        model=ScriptModel(responses=[calls(*tasks), AIMessage(content="done")]),
        tools=[],
        subagents=subagents,
        checkpointer=checkpointer,
    )
    identifier = register(graph)
    path = f"/threads/{uuid4()}/runs/stream"
    events = parse_events(
        client.post(
            path,
            json={
                "assistant_id": identifier,
                "input": {"messages": [{"role": "user", "content": "delegate"}]},
                "stream_mode": ["updates", "values"],
            },
        )
    )
    interrupts = [
        interrupt
        for _, value in events
        if isinstance(value, dict)
        for interrupt in value.get("__interrupt__", [])
    ]
    interrupts = list({interrupt["id"]: interrupt for interrupt in interrupts}.values())
    assert len(interrupts) == workers, events
    assert len({interrupt["id"] for interrupt in interrupts}) == workers
    assert sorted(executed) == [f"before-{index}" for index in range(workers)]
    resume = {interrupt["id"]: {"decisions": [{"type": "approve"}]} for interrupt in interrupts}
    events = parse_events(
        client.post(
            path,
            json={
                "assistant_id": identifier,
                "command": {"resume": resume},
                "stream_mode": ["updates", "values"],
            },
        )
    )
    assert not any(name == "error" for name, _ in events), events
    assert sorted(executed) == sorted(
        [f"{step}-{index}" for index in range(workers) for step in ("before", "after")]
    )


@pytest.mark.parametrize("large", [False, True])
@pytest.mark.parametrize("is_async", [False, True])
def test_filesystem_and_audit_preserve_command_control_and_original_updates(
    tmp_path, large, is_async
):
    from langchain.agents.middleware.types import ToolCallRequest
    from langchain.tools import ToolRuntime
    from langchain_core.messages import ToolMessage
    from langgraph.types import Command

    from deepagents.middleware.audit import ToolAuditMiddleware
    from deepagents.middleware.filesystem import FilesystemMiddleware

    @tool
    def handoff() -> str:
        """Represent a tool handoff."""
        return "not called"

    content = "large" * 100 if large else "short"
    files = {"/original": _create_file_data("original")}
    command = Command(
        graph=Command.PARENT,
        goto="__end__",
        resume="resume-value",
        update={"messages": [ToolMessage(content, tool_call_id="handoff")], "files": files},
    )
    runtime = ToolRuntime(
        state={},
        context=None,
        config={},
        tool_call_id="handoff",
        store=None,
        stream_writer=lambda _: None,
    )
    request = ToolCallRequest(
        tool_call={"name": "handoff", "args": {}, "id": "handoff", "type": "tool_call"},
        tool=handoff,
        state={},
        runtime=runtime,
    )
    filesystem = FilesystemMiddleware(tool_token_limit_before_evict=10)
    audit = ToolAuditMiddleware(tmp_path)
    if is_async:

        async def original(_):
            return command

        async def audited(req):
            return await audit.awrap_tool_call(req, original)

        result = asyncio.run(filesystem.awrap_tool_call(request, audited))
    else:
        result = filesystem.wrap_tool_call(
            request, lambda req: audit.wrap_tool_call(req, lambda _: command)
        )
    assert (
        result.graph == command.graph
        and result.goto == command.goto
        and result.resume == command.resume
    )
    assert files.keys() == {"/original"}
    assert command.update["messages"][0].content == content
    assert bool("/large_tool_results/handoff" in result.update["files"]) is large
    if not large:
        assert result is command


def test_custom_subagent_audit_observes_transformed_tool_arguments(tmp_path):
    from langchain.agents.middleware import AgentMiddleware

    executed = []

    @tool
    def record(value: str) -> str:
        """Record a transformed local argument."""
        executed.append(value)
        return value

    class Rewrite(AgentMiddleware):
        def wrap_tool_call(self, request, handler):
            changed = {**request.tool_call, "args": {"value": "actual"}}
            return handler(request.override(tool_call=changed))

    child_model = ScriptModel(
        responses=[calls(("record", {"value": "original"})), AIMessage(content="done")]
    )
    parent_model = ScriptModel(
        responses=[
            calls(("task", {"description": "work", "subagent_type": "local"})),
            AIMessage(content="done"),
        ]
    )
    graph = create_deep_agent(
        model=parent_model,
        tools=[],
        audit_dir=str(tmp_path),
        subagents=[
            {
                "name": "local",
                "description": "local",
                "system_prompt": "local",
                "tools": [record],
                "model": child_model,
                "middleware": [Rewrite()],
            }
        ],
    )
    graph.invoke({"messages": [{"role": "user", "content": "work"}]})
    assert executed == ["actual"]
    records = [json.loads(path.read_text()) for path in tmp_path.glob("*.json")]
    record_audits = [entry for entry in records if entry["tool_name"] == "record"]
    assert len(record_audits) == 1 and record_audits[0]["input"] == {"value": "actual"}
