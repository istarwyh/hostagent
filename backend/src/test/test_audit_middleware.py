"""Exercise audit middleware with real tool requests and compiled v1 agents."""

import asyncio
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from deepagents.middleware.audit import ToolAuditMiddleware


@tool
def echo(value: str) -> str:
    """Return the input unchanged."""
    return value


class ScriptedToolModel(FakeMessagesListChatModel):
    """Deterministic local model capable of participating in create_agent."""

    def bind_tools(self, tools, **kwargs):
        return self


def _request(selected_tool=echo, call_id="call-1", args=None):
    runtime = ToolRuntime(
        state={},
        context=None,
        config={"configurable": {"thread_id": "thread-1"}, "run_id": "run-1"},
        stream_writer=lambda value: None,
        tool_call_id=call_id,
        store=None,
    )
    return ToolCallRequest(
        tool_call={
            "name": selected_tool.name,
            "args": {"value": "unchanged"} if args is None else args,
            "id": call_id,
            "type": "tool_call",
        },
        tool=selected_tool,
        state={},
        runtime=runtime,
    )


def _invoke(middleware, request, use_async=False):
    if use_async:
        return asyncio.run(
            middleware.awrap_tool_call(request, lambda req: req.tool.ainvoke(req.tool_call))
        )
    return middleware.wrap_tool_call(request, lambda req: req.tool.invoke(req.tool_call))


def _records(directory):
    return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))]


def _assert_summary(directory, expected):
    summary = list(directory.glob("summary_*.jsonl"))
    assert len(summary) == 1
    records = [json.loads(line) for line in summary[0].read_text().splitlines()]
    assert len(records) == len(expected)
    assert {row["audit_id"] for row in records} == {row["audit_id"] for row in expected}
    assert all(row in expected for row in records)


def _agent(directory, tool_calls):
    model = ScriptedToolModel(
        responses=[AIMessage(content="", tool_calls=tool_calls), AIMessage(content="done")]
    )
    return create_agent(model, [echo], middleware=[ToolAuditMiddleware(directory)])


@pytest.mark.parametrize("use_async", [False, True])
def test_compiled_agent_audits_each_tool_call_without_changing_outputs(tmp_path, use_async):
    calls = [
        {"name": "echo", "args": {"value": value}, "id": f"call-{value}"}
        for value in ("first", "second")
    ]
    agent = _agent(tmp_path, calls)
    inputs = {"messages": [HumanMessage(content="Run both tools")]}
    result = asyncio.run(agent.ainvoke(inputs)) if use_async else agent.invoke(inputs)
    outputs = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert [message.content for message in outputs] == ["first", "second"]
    assert [message.tool_call_id for message in outputs] == ["call-first", "call-second"]
    records = _records(tmp_path)
    assert len(records) == 2
    assert {row["tool_name"] for row in records} == {"echo"}
    assert {row["tool_call_id"] for row in records} == {"call-first", "call-second"}
    assert all(row["output"] == row["input"]["value"] for row in records)
    assert all(row["status"] == "success" and row["error"] is None for row in records)
    assert all(row["execution_time_ms"] >= 0 for row in records)
    _assert_summary(tmp_path, records)


@pytest.mark.parametrize("use_async", [False, True])
def test_handled_tool_validation_error_is_a_failed_audit(tmp_path, use_async):
    agent = _agent(tmp_path, [{"name": "echo", "args": {}, "id": "invalid-call"}])
    inputs = {"messages": [HumanMessage(content="Run invalid tool")]}
    result = asyncio.run(agent.ainvoke(inputs)) if use_async else agent.invoke(inputs)
    message = next(item for item in result["messages"] if isinstance(item, ToolMessage))
    record = _records(tmp_path)[0]
    assert message.status == "error"
    assert record["status"] == "failed"
    assert record["error"] == record["output"] == message.content
    assert record["tool_call_id"] == "invalid-call"


@pytest.mark.parametrize("use_async", [False, True])
@pytest.mark.parametrize("disk_available", [False, True])
def test_tool_exception_is_preserved_even_when_audit_directory_is_unwritable(
    tmp_path, use_async, disk_available, caplog
):
    error = ValueError("original tool failure")

    @tool
    def fail() -> str:
        """Raise the original exception."""
        raise error

    directory = tmp_path / "audit"
    if not disk_available:
        directory.write_text("a file cannot be used as an audit directory")
    with pytest.raises(ValueError) as raised:
        _invoke(ToolAuditMiddleware(directory), _request(fail, args={}), use_async)
    assert raised.value is error
    if disk_available:
        record = _records(directory)[0]
        assert record["error"] == "original tool failure"
        assert record["status"] == "failed" and record["output"] is None
    else:
        assert "Unable to persist tool audit record" in caplog.text


@pytest.mark.parametrize("use_async", [False, True])
def test_audit_failure_does_not_change_successful_tool_result(tmp_path, use_async, caplog):
    directory = tmp_path / "audit"
    directory.write_text("not a directory")
    result = _invoke(ToolAuditMiddleware(directory), _request(), use_async)
    assert result.content == "unchanged"
    assert result.tool_call_id == "call-1"
    assert "Unable to persist tool audit record" in caplog.text


@pytest.mark.parametrize("use_async", [False, True])
def test_command_and_message_artifact_are_preserved(tmp_path, use_async):
    message = ToolMessage(content="unchanged", tool_call_id="call-1", artifact={"value": 42})
    command = Command(update={"messages": [message], "counter": 1})

    @tool
    def update_state() -> Command:
        """Return an explicit graph state update."""
        return command

    result = _invoke(ToolAuditMiddleware(tmp_path), _request(update_state, args={}), use_async)
    assert result is command
    assert result.update["messages"][0] is message
    assert message.content == "unchanged" and message.artifact == {"value": 42}
    record = _records(tmp_path)[0]
    assert record["output"]["update"]["counter"] == 1
    assert record["output"]["update"]["messages"][0]["artifact"] == {"value": 42}
    assert record["thread_id"] == "thread-1" and record["run_id"] == "run-1"


def test_filenames_are_safe_and_unique_even_for_identical_call_ids(tmp_path):
    @tool("../../../unsafe/tool")
    def unsafe_name(value: str) -> str:
        """Exercise an unsafe-looking tool name."""
        return value

    middleware = ToolAuditMiddleware(tmp_path)
    for _ in range(3):
        _invoke(middleware, _request(unsafe_name, call_id="../../same-call"))
    records = _records(tmp_path)
    assert len(records) == 3
    assert all(row["tool_name"] == "../../../unsafe/tool" for row in records)
    assert all(row["tool_call_id"] == "../../same-call" for row in records)
    assert len({row["audit_id"] for row in records}) == 3
    _assert_summary(tmp_path, records)


def _concurrent_call(arguments):
    directory, index = arguments
    request = _request(call_id=f"call-{index}", args={"value": "并发" * 8192})
    return _invoke(ToolAuditMiddleware(directory), request).tool_call_id


@pytest.mark.parametrize("executor_type", [ThreadPoolExecutor, ProcessPoolExecutor])
def test_summary_is_safe_across_middleware_instances_and_workers(tmp_path, executor_type):
    options = {"max_workers": 4}
    if executor_type is ProcessPoolExecutor:
        options["mp_context"] = multiprocessing.get_context("spawn")
    with executor_type(**options) as executor:
        results = list(executor.map(_concurrent_call, [(str(tmp_path), i) for i in range(24)]))
    assert len(set(results)) == 24
    records = _records(tmp_path)
    assert len(records) == 24
    assert {row["tool_call_id"] for row in records} == set(results)
    _assert_summary(tmp_path, records)


def test_concurrent_async_tools_append_complete_summary_records(tmp_path):
    async def run_tools():
        return await asyncio.gather(
            *[
                ToolAuditMiddleware(tmp_path).awrap_tool_call(
                    _request(call_id=f"call-{index}"), lambda req: req.tool.ainvoke(req.tool_call)
                )
                for index in range(24)
            ]
        )

    results = asyncio.run(run_tools())
    records = _records(tmp_path)
    assert len(records) == len(results) == 24
    assert {row["tool_call_id"] for row in records} == {item.tool_call_id for item in results}
    _assert_summary(tmp_path, records)


def test_async_cancellation_is_preserved_and_audited(tmp_path):
    cancellation = asyncio.CancelledError()

    @tool
    async def cancelled_tool() -> str:
        """Cancel tool execution."""
        raise cancellation

    with pytest.raises(asyncio.CancelledError) as raised:
        _invoke(ToolAuditMiddleware(tmp_path), _request(cancelled_tool, args={}), use_async=True)
    assert raised.value is cancellation
    record = _records(tmp_path)[0]
    assert record["status"] == "failed"
    assert record["error"] == ""
    assert record["output"] is None
