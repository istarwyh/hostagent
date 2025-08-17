from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from deepagents.util.async_stream_preview import local_async_streaming
from deepagents.util.handle_user_input import read_user_input
from deepagents.util.agent_streamer import AgentStreamer

def build_initial_state():
    return {"messages": [], "files": {}, "todos": []}


async def interactive_loop(agent: CompiledStateGraph, persisted_state: dict):
    while True:
        try:
            user_input = await read_user_input("You> ")
        except (EOFError, KeyboardInterrupt):
            print("\n👋 退出。")
            break

        if not user_input or not user_input.strip():
            continue

        cmd = user_input.strip().lower()
        if cmd in {"/exit", "exit", "quit", "q"}:
            print("👋 已退出会话。")
            break
        if cmd in {"/reset", "reset"}:
            persisted_state.clear()
            persisted_state.update(build_initial_state())
            print("🔄 会话已重置。")
            continue

        # Build input with persisted state and new user message
        agent_input = {
            "messages": list(persisted_state.get("messages", [])) + [
                HumanMessage(content=user_input)
            ],
            "files": dict(persisted_state.get("files", {})),
            "todos": list(persisted_state.get("todos", [])),
        }

        # Stream this turn and update state
        last_result = await local_async_streaming(agent, agent_input)
        try:
            _update_state_from_last_result(persisted_state, last_result)
        except Exception as e:
            print(f"⚠️ 更新会话状态失败: {e}")


def _update_state_from_last_result(persisted_state: dict, last_result: dict):
    if not last_result or not isinstance(last_result, dict):
        return
    if last_result.get("type") != "step":
        return
    data = last_result.get("data", {}) or {}
    agent_state = data.get("agent") if isinstance(data, dict) else None
    if not isinstance(agent_state, dict):
        return
    if agent_state.get("messages"):
        persisted_state["messages"] = agent_state["messages"]
    if agent_state.get("files") is not None:
        persisted_state["files"] = agent_state.get("files", {})
    if agent_state.get("todos") is not None:
        persisted_state["todos"] = agent_state.get("todos", [])