import time
from typing import Any, Dict, List, Optional

from langgraph.graph.state import CompiledStateGraph

from deepagents.util.agent_streamer import AgentStreamer


async def local_async_streaming(
    agent: CompiledStateGraph, input_data: Optional[Dict[str, Any]] = None
):
    """异步流式处理示例"""
    start_time = time.time()
    streamer = AgentStreamer(agent)
    step_counter = 0
    previous_todos = []
    last_result = None

    try:
        async for result in streamer.stream_with_progress(input_data):
            last_result = result
            if result["type"] == "step":
                step_counter += 1
                print(f"\n🔄 步骤 {step_counter} - 节点: {get_node_name(result)}")

                content = result.get("data", {})
                await preview_content_async(content, previous_todos)

            elif result["type"] == "error":
                print(f"❌ 错误: {result['error']}")
                break

        elapsed = time.time() - start_time
        print(f"\n✅ 异步流式执行完成，共处理 {step_counter} 个步骤")
        print(f"⏰ 总耗时: {elapsed:.2f} 秒")
        await pretty_print_last_result_async(last_result)

        return last_result

    except Exception as e:
        print(f"❌ 异步流式处理出现错误: {e}")
        import traceback

        traceback.print_exc()
        return None


def get_node_name(result: Dict[str, Any]) -> str:
    """从结果中提取节点名称"""
    data = result.get("data", {})
    if isinstance(data, dict) and data:
        return list(data.keys())[0]
    return "unknown"


async def preview_content_async(content: Dict[str, Any], previous_todos: List[Dict[str, Any]]):
    """异步预览内容 - 复用sync_stream_preview的逻辑"""
    for node, state in content.items():
        if isinstance(state, dict):
            # 处理待办事项变化 - 复用原有逻辑
            if state.get("todos"):
                current_todos = state["todos"]
                await handle_todos_async(current_todos, previous_todos)
                previous_todos.clear()
                previous_todos.extend(current_todos)

            # 处理消息信息 - 复用原有逻辑
            await preview_message_async(state)

            # 处理文件信息 - 复用原有逻辑
            if state.get("files"):
                await handle_files_async(state["files"])


async def handle_todos_async(
    current_todos: List[Dict[str, Any]], previous_todos: List[Dict[str, Any]]
):
    """异步处理待办事项变化 - 复用sync_stream_preview的逻辑"""
    pending = [t for t in current_todos if t.get("status") == "pending"]
    in_progress = [t for t in current_todos if t.get("status") == "in_progress"]
    completed = [t for t in current_todos if t.get("status") == "completed"]

    print(
        f"   📋 待办状态: 待处理({len(pending)}) | 进行中({len(in_progress)}) | 已完成({len(completed)})"
    )

    # 检测新增的待办事项
    if len(current_todos) > len(previous_todos):
        new_todos = current_todos[len(previous_todos) :]
        for todo in new_todos:
            status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(
                todo.get("status"), "❓"
            )
            print(f"   ➕ todo: {status_emoji} {todo.get('content', 'N/A')}")

    # 检测状态变化的待办事项
    for i, todo in enumerate(current_todos):
        if i < len(previous_todos):
            old_status = previous_todos[i].get("status")
            new_status = todo.get("status")
            if old_status != new_status:
                status_emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(
                    new_status, "❓"
                )
                print(
                    f"   🔄 状态变更: {status_emoji} {todo.get('content', 'N/A')[:50]}... ({old_status} → {new_status})"
                )


async def preview_message_async(state: Dict[str, Any]):
    """异步预览消息 - 复用sync_stream_preview的逻辑"""
    # 处理消息信息
    if state.get("messages"):
        messages = state["messages"]
        if messages:
            last_message = messages[-1]

            content = getattr(last_message, "content", "")
            tool_calls = getattr(last_message, "tool_calls", None)
            response_metadata = getattr(last_message, "response_metadata", None)
            usage_metadata = getattr(last_message, "usage_metadata", None)

            show_progress_message = content[:300]
            if len(show_progress_message) < 1 and tool_calls:
                show_progress_message = (
                    tool_calls[0]["name"]
                    if isinstance(tool_calls[0], dict)
                    else getattr(tool_calls[0], "name", "unknown")
                )
            print(f"   💬 最新消息: {show_progress_message}...")

            # 显示工具调用
            if tool_calls:
                print(f"   🔧 工具调用: {len(tool_calls)} 个")
                for tool_call in tool_calls[:2]:  # 只显示前2个
                    if isinstance(tool_call, dict):
                        tool_name = tool_call["name"]
                    else:
                        tool_name = getattr(tool_call, "name", "unknown")
                    print(f"      🛠️  {tool_name}")

            # 显示 Token 使用情况
            if usage_metadata:
                input_tokens = usage_metadata.get("input_tokens", 0)
                output_tokens = usage_metadata.get("output_tokens", 0)
                total_tokens = usage_metadata.get("total_tokens", 0)
                input_token_details = usage_metadata.get("input_token_details", {})
                cache_read = input_token_details.get("cache_read", 0) if input_token_details else 0

                print(f"   📊 Token 输入: {input_tokens} 个")
                print(f"   📊 Token 输出: {output_tokens} 个")
                print(f"   📊 Token 使用: {total_tokens} 个")
                print(f"           📊 cached_read 缓存: {cache_read} 个")


async def handle_files_async(files: Dict[str, Any]):
    """异步处理文件信息 - 复用sync_stream_preview的逻辑"""
    print(f"   📁 文件操作: {len(files)} 个文件")
    for filename in list(files.keys())[-2:]:  # 显示最后2个文件
        file_size = len(files[filename]) if isinstance(files[filename], str) else 0
        print(f"      📄 {filename} ({file_size} 字符)")


async def pretty_print_last_result_async(last_result: Optional[Dict[str, Any]]):
    """异步打印最后结果 - 复用sync_stream_preview的逻辑"""
    print("\n📝 最后运行结果摘要：")
    if not last_result:
        print("  [无结果]")
        return

    # 只处理 type=step 且有 data/agent/messages
    if last_result.get("type") == "step":
        data = last_result.get("data", {})
        agent = data.get("agent") if isinstance(data, dict) else None
        if agent and isinstance(agent, dict):
            messages = agent.get("messages")
            if messages and isinstance(messages, list):
                last_msg = messages[-1]
                # 兼容 AIMessage/content 结构
                msg_content = getattr(last_msg, "content", None)
                if msg_content:
                    print("\n------ AI回复内容 ------\n")
                    print(msg_content)
                    print("\n----------------------\n")
                else:
                    print("[未找到AI回复内容]")
            else:
                print("[未找到messages]")
        else:
            print("[未找到agent]")

        # 可选：展示token用量
        if agent and isinstance(agent, dict) and agent.get("messages"):
            last_msg = agent["messages"][-1]
            response_metadata = getattr(last_msg, "response_metadata", None)
            if response_metadata and isinstance(response_metadata, dict):
                token_usage = response_metadata.get("token_usage")
                if token_usage:
                    print(f"\n📊 Token 统计: 总用量 {token_usage.get('total_tokens', 0)} 个")
    else:
        print(f"[结果类型: {last_result.get('type', 'unknown')}]")
