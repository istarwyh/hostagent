"""PR acceptance: actual HTTP contracts and persisted channel boundaries."""

from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from deepagents.audit_tool_node import SimpleAuditToolNode
from deepagents.middleware.filesystem import _create_file_data
from deepagents.state import DeepAgentState
from src.app.agent_config import AgentConfig
from src.app.agent_initializer import registry
from src.facade.langgraph_api.main import app
from src.facade.langgraph_api.routers.threads import _thread_agents
from src.repository.checkpointer import checkpointer
from src.service.langgraph_api.assistant_service import user_assistants


def test_dynamic_system_protection_and_user_management():
    identifier = str(uuid4())
    with TestClient(app) as client:
        # Register after startup: discovery must stay dynamic.
        registry.register(AgentConfig(identifier, "Late registration", "test", [], ""))
        try:
            system = client.get(f"/assistants/{identifier}").json()
            assert system["graph_id"] == identifier
            assert system["metadata"]["created_by"] == "system"
            for method in ("patch", "delete"):
                kwargs = {"json": {"name": "changed"}} if method == "patch" else {}
                assert (
                    getattr(client, method)(f"/assistants/{identifier}", **kwargs).status_code
                    == 403
                )
            assert client.get(f"/assistants/{identifier}").json()["name"] == "Late registration"
            response = client.post(
                "/assistants",
                json={
                    "graph_id": identifier,
                    "name": "User",
                    "metadata": {"created_by": "system", "project": "acceptance"},
                },
            )
            assert response.status_code == 200
            assistant = response.json()
            user_id = assistant["assistant_id"]
            try:
                assert assistant["metadata"]["created_by"] == "user"
                response = client.patch(
                    f"/assistants/{user_id}",
                    json={
                        "name": "Renamed",
                        "metadata": {"created_by": "system", "project": "updated"},
                    },
                )
                assert response.status_code == 200
                assert response.json()["metadata"] == {"created_by": "user", "project": "updated"}
                found = client.post(
                    "/assistants/search",
                    json={"graph_id": identifier, "metadata": {"created_by": "system"}},
                ).json()
                assert [a["assistant_id"] for a in found] == [identifier]
                assert client.get(f"/assistants/{user_id}").json()["name"] == "Renamed"
                assert client.delete(f"/assistants/{user_id}").status_code == 200
                assert client.get(f"/assistants/{user_id}").status_code == 404
            finally:
                user_assistants.pop(user_id, None)
        finally:
            registry._configs.pop(identifier, None)


@pytest.mark.parametrize("bound_graph", [False, True])
def test_actual_checkpoint_state_history_channels_and_thread_isolation(bound_graph):
    graph = StateGraph(DeepAgentState)
    graph.add_node("reply", lambda state: {"messages": [AIMessage(content="answer")]})
    graph.add_edge(START, "reply")
    graph.add_edge("reply", END)
    graph = graph.compile(checkpointer=checkpointer)
    thread_id, other_id = str(uuid4()), str(uuid4())
    todo = {"content": "separate task", "status": "pending"}
    config = {"configurable": {"thread_id": thread_id}}
    graph.invoke(
        {
            "messages": [HumanMessage(content="question")],
            "todos": [todo],
            "files": {"/report.txt": _create_file_data("first\nsecond\n")},
        },
        config,
    )
    graph.invoke(
        {"messages": [HumanMessage(content="other thread")], "todos": [], "files": {}},
        {"configurable": {"thread_id": other_id}},
    )
    if bound_graph:
        _thread_agents[thread_id] = graph
    try:
        with TestClient(app) as client:
            response = client.get(f"/threads/{thread_id}/state")
            assert response.status_code == 200
            state = response.json()
            assert state["checkpoint"]["thread_id"] == thread_id
            assert state["checkpoint"]["checkpoint_id"] == state["checkpoint_id"]
            assert state["tasks"] == []
            assert "parent_checkpoint" in state
            values = state["values"]
            assert values["todos"] == [todo]
            assert values["files"] == {"/report.txt": "first\nsecond\n"}
            assert [m["content"] for m in values["messages"]] == ["question", "answer"]
            assert [m["type"] for m in values["messages"]] == ["human", "ai"]
            assert "/report.txt" not in values
            assert not any(k.startswith(("__", "branch:", "start:")) for k in values)
            historical = client.get(
                f"/threads/{thread_id}/state", params={"checkpoint_id": state["checkpoint_id"]}
            )
            assert historical.json()["values"] == values
            history = client.post(f"/threads/{thread_id}/history", json={"limit": 10})
            assert history.status_code == 200
            assert history.json()[0]["values"] == values
            other = client.get(f"/threads/{other_id}/state").json()["values"]
            assert other["files"] == {} and other["todos"] == []
            assert other["messages"][0]["content"] == "other thread"
    finally:
        _thread_agents.pop(thread_id, None)
        checkpointer.delete_thread(thread_id)
        checkpointer.delete_thread(other_id)


def test_legacy_audit_parallel_summary_records(tmp_path):
    node = SimpleAuditToolNode([], audit_dir=str(tmp_path))

    def write(index):
        return node._write_audit_log(
            "local",
            str(index),
            {"payload": "x" * 20000},
            "ok",
            None,
            1,
            str(tmp_path / f"{index}.json"),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write, range(40)))
    entries = [
        json.loads(line) for line in next(tmp_path.glob("summary_*.jsonl")).read_text().splitlines()
    ]
    assert len(entries) == 40
    assert {entry["tool_call_id"] for entry in entries} == {str(i) for i in range(40)}


def test_learning_example_missing_key_fails_without_prompt(monkeypatch):
    import sys
    from unittest.mock import MagicMock

    monkeypatch.setattr("langchain_openai.ChatOpenAI", lambda **kwargs: MagicMock())
    from src.test.learn.react_agent_from_scratch import _set_env

    monkeypatch.delenv("HOSTAGENT_TEST_MISSING_KEY", raising=False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(RuntimeError, match="no TTY"):
        _set_env("HOSTAGENT_TEST_MISSING_KEY")
