# Subgraphs Streaming 实现指南

**版本**: 1.0  
**日期**: 2025-12-21  
**状态**: 已实现并验证

## 目录

1. [概述](#概述)
2. [核心概念](#核心概念)
3. [架构设计](#架构设计)
4. [数据流](#数据流)
5. [实现细节](#实现细节)
6. [验证方案](#验证方案)
7. [常见问题](#常见问题)

---

## 概述

本文档详细记录了在自托管 LangGraph API 中实现 **Subgraphs Streaming** 支持的完整技术方案。该功能使客户端能够接收来自嵌套 Agent（子图）的流式事件，并通过 `event|subgraph_path` 格式的事件名称来区分不同子图层级的输出。

### 目标

- ✅ 后端支持 `stream_subgraphs` 请求参数
- ✅ 后端透传 `subgraphs=True` 给 LangGraph 的 `agent.astream`
- ✅ 后端输出 `event|subgraph_path` 格式的 SSE 事件
- ✅ 前端 `useChat` 钩子传递 `streamSubgraphs: true`
- ✅ 完整的 E2E 验证和契约测试

---

## 核心概念

### 什么是 Subgraphs Streaming？

在 LangGraph 中，一个图可以包含多个子图（nested agents）。当启用 `subgraphs=True` 时，`agent.astream()` 会返回来自所有层级（包括子图）的流式输出，并用 **namespace** 标识每个输出的来源。

### 数据结构对齐

#### SDK 期望的事件格式

```typescript
// 来自根图的事件
{
  event: "updates",
  data: { node_name: update_data }
}

// 来自子图的事件（带路径后缀）
{
  event: "updates|subgraph_name",
  data: { node_name: update_data }
}

// 多层嵌套的事件
{
  event: "updates|parent_subgraph/child_subgraph",
  data: { node_name: update_data }
}
```

#### LangGraph 返回的结构

当 `subgraphs=True` 时，`agent.astream()` 返回两种形式的数据：

**形式 1: 普通输出（来自根图）**
```python
(agent_mode: str, chunk: Any)
```

**形式 2: 子图输出**
```python
# 两种可能的结构
# 结构 A: ((namespace_tuple), (agent_mode, chunk))
# 结构 B: (namespace_tuple, agent_mode, chunk)

# 其中 namespace_tuple 是一个元组，如：
# ("subgraph_name",)
# ("parent", "child")
```

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────────┐
│         Frontend (React + Next.js)          │
│  useChat hook → stream.submit({             │
│    streamSubgraphs: true                    │
│  })                                         │
└────────────────┬────────────────────────────┘
                 │ HTTP POST /threads/{id}/runs/stream
                 │ + stream_subgraphs: true
                 ▼
┌─────────────────────────────────────────────┐
│    FastAPI Router (threads.py / runs.py)    │
│  - 接收 stream_subgraphs 参数               │
│  - 透传给 execute_stream_run()              │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│  Run Service (run_service.py)               │
│  execute_stream_run(                        │
│    stream_subgraphs=True                    │
│  )                                          │
│  - 调用 agent.astream(...,                  │
│      subgraphs=stream_subgraphs)            │
│  - 解包 namespace 和 chunk                  │
│  - 生成 event|subgraph_path SSE 事件       │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│    LangGraph Agent (agent.astream)          │
│  - 返回 (agent_mode, chunk) 或             │
│    (namespace, agent_mode, chunk)           │
└─────────────────────────────────────────────┘
```

### 请求/响应流

#### 请求模型

```python
class RunStreamRequest(BaseModel):
    assistant_id: str
    input: Optional[dict] = None
    stream_mode: list[str] = Field(default_factory=lambda: ["updates"])
    config: Optional[dict] = None
    metadata: Optional[dict] = None
    interrupt_before: Optional[list[str]] = None
    interrupt_after: Optional[list[str]] = None
    multitask_strategy: Optional[str] = None
    stream_subgraphs: bool = False  # ← 新增字段
```

#### 响应（SSE 流）

```
event: metadata
data: {"run_id": "...", "thread_id": "..."}

event: updates
data: {"node_a": {...}}

event: updates|subgraph_name
data: {"node_b": {...}}

event: updates|parent/child
data: {"node_c": {...}}

event: end
data: {}
```

---

## 数据流

### 完整的请求-处理-响应流程

```
1. 前端发起请求
   ┌─────────────────────────────────────────┐
   │ POST /threads/{thread_id}/runs/stream   │
   │ {                                       │
   │   "assistant_id": "researchAgent",      │
   │   "input": {...},                       │
   │   "stream_mode": ["updates"],           │
   │   "stream_subgraphs": true  ← 关键参数 │
   │ }                                       │
   └─────────────────────────────────────────┘
                    │
                    ▼
2. FastAPI 路由层处理
   ┌─────────────────────────────────────────┐
   │ @router.post("/{thread_id}/runs/stream")│
   │ async def stream_run(                   │
   │   request: RunStreamRequest              │
   │ ):                                      │
   │   # request.stream_subgraphs = true     │
   │   async for event in execute_stream_run(│
   │     stream_subgraphs=request.stream_... │
   │   ):                                    │
   │     yield event                         │
   └─────────────────────────────────────────┘
                    │
                    ▼
3. 服务层处理
   ┌─────────────────────────────────────────┐
   │ async def execute_stream_run(           │
   │   stream_subgraphs: bool = False        │
   │ ):                                      │
   │   async for agent_chunk in              │
   │     agent.astream(                      │
   │       stream_mode=agent_modes,          │
   │       subgraphs=stream_subgraphs        │
   │     ):                                  │
   │       # 解包 agent_chunk                │
   │       if stream_subgraphs:              │
   │         # 处理 namespace 形式           │
   │       else:                             │
   │         # 处理普通 (mode, chunk) 形式   │
   └─────────────────────────────────────────┘
                    │
                    ▼
4. 解包逻辑（关键）
   ┌─────────────────────────────────────────┐
   │ 检查 agent_chunk 结构：                 │
   │                                         │
   │ if stream_subgraphs and isinstance(...):│
   │   if len == 2 and nested tuple:         │
   │     # 形式 A: ((ns), (mode, chunk))    │
   │     namespace, (mode, chunk) = ...      │
   │   elif len == 3 and tuple[0] is tuple: │
   │     # 形式 B: (ns, mode, chunk)        │
   │     namespace, mode, chunk = ...        │
   │   else:                                 │
   │     # 回退为普通处理                    │
   │     mode, chunk = ...                   │
   │ else:                                   │
   │   # 不启用 subgraphs，普通处理          │
   │   mode, chunk = ...                     │
   └─────────────────────────────────────────┘
                    │
                    ▼
5. 生成 SSE 事件
   ┌─────────────────────────────────────────┐
   │ subgraph_path = _format_subgraph_path(  │
   │   namespace                             │
   │ )                                       │
   │ # ("subgraph_name",) → "subgraph_name"  │
   │ # ("parent", "child") → "parent/child"  │
   │                                         │
   │ event_type = _with_subgraph_suffix(     │
   │   "updates", subgraph_path              │
   │ )                                       │
   │ # "" → "updates"                        │
   │ # "subgraph_name" → "updates|subgraph_n│
   │                                         │
   │ yield format_sse_event(                 │
   │   event_type, serialized_data           │
   │ )                                       │
   └─────────────────────────────────────────┘
                    │
                    ▼
6. 前端接收 SSE 事件
   ┌─────────────────────────────────────────┐
   │ event: updates                          │
   │ data: {...}                             │
   │                                         │
   │ event: updates|subgraph_name            │
   │ data: {...}                             │
   │                                         │
   │ event: end                              │
   │ data: {}                                │
   └─────────────────────────────────────────┘
```

---

## 实现细节

### 1. 后端数据模型更新

**文件**: `backend/src/model/run.py`

```python
class RunStreamRequest(BaseModel):
    """Request model for streaming runs."""

    assistant_id: str
    input: Optional[dict] = None
    stream_mode: list[str] = Field(default_factory=lambda: ["updates"])
    config: Optional[dict] = None
    metadata: Optional[dict] = None
    interrupt_before: Optional[list[str]] = None
    interrupt_after: Optional[list[str]] = None
    multitask_strategy: Optional[str] = None
    stream_subgraphs: bool = False  # ← 新增
```

### 2. FastAPI 路由层透传

**文件**: `backend/src/facade/langgraph_api/routers/threads.py`

```python
@router.post("/{thread_id}/runs/stream")
async def stream_run(
    thread_id: str,
    request: RunStreamRequest,
):
    """Stream run for a specific thread."""
    async for event in execute_stream_run(
        thread_id=thread_id,
        assistant_id=request.assistant_id,
        input_data=request.input,
        stream_mode=request.stream_mode,
        stream_subgraphs=request.stream_subgraphs,  # ← 透传
        config=request.config,
    ):
        yield event
```

**文件**: `backend/src/facade/langgraph_api/routers/runs.py`

```python
@router.post("/stream")
async def stream_run(request: RunStreamRequest):
    """Stream run without thread context."""
    async for event in execute_stream_run(
        thread_id=str(uuid4()),
        assistant_id=request.assistant_id,
        input_data=request.input,
        stream_mode=request.stream_mode,
        stream_subgraphs=request.stream_subgraphs,  # ← 透传
        config=request.config,
    ):
        yield event
```

### 3. 服务层核心逻辑

**文件**: `backend/src/service/langgraph_api/run_service.py`

#### 3.1 辅助函数

```python
def _format_subgraph_path(namespace: Any) -> str:
    """
    将 LangGraph namespace 元组转换为路径字符串。

    示例:
      ("subgraph_name",) → "subgraph_name"
      ("parent", "child") → "parent/child"
      None → ""
    """
    if isinstance(namespace, (list, tuple)):
        parts = [str(p) for p in namespace if str(p)]
        return "/".join(parts)
    if namespace is None:
        return ""
    return str(namespace)


def _with_subgraph_suffix(event_type: str, subgraph_path: str) -> str:
    """
    为事件类型添加子图路径后缀。

    示例:
      ("updates", "") → "updates"
      ("updates", "subgraph_name") → "updates|subgraph_name"
      ("messages", "parent/child") → "messages|parent/child"
    """
    if not subgraph_path:
        return event_type
    return f"{event_type}|{subgraph_path}"
```

#### 3.2 主流程

```python
async def execute_stream_run(
    thread_id: str,
    assistant_id: str,
    input_data: Optional[dict] = None,
    stream_mode: Optional[list[str]] = None,
    stream_subgraphs: bool = False,  # ← 新增参数
    config: Optional[dict] = None,
) -> AsyncIterator[str]:
    """
    执行流式运行并输出 SSE 事件。

    当 stream_subgraphs=True 时，支持来自子图的事件，
    并用 event|subgraph_path 格式标识。
    """
    run_id = str(uuid4())

    # 发送元数据事件
    yield format_sse_event("metadata", {"run_id": run_id, "thread_id": thread_id})

    try:
        agent = agent_pool.get_agent(assistant_id)

        run_config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        if config:
            run_config.update(config)

        requested_modes = stream_mode or ["updates"]
        agent_modes = sorted({STREAM_MODE_MAPPING[m] for m in requested_modes})

        step = 0

        # 关键：透传 subgraphs 参数给 agent.astream
        async for agent_chunk in agent.astream(
            input_data or {},
            config=run_config,
            stream_mode=agent_modes,
            subgraphs=stream_subgraphs,  # ← 关键参数
        ):
            agent_mode: str
            chunk: Any
            subgraph_path = ""

            # 解包逻辑：兼容 subgraphs 的多种返回形式
            if stream_subgraphs and isinstance(agent_chunk, (list, tuple)):
                # 形式 A: ((namespace_tuple), (agent_mode, chunk))
                if (
                    len(agent_chunk) == 2
                    and isinstance(agent_chunk[0], (list, tuple))
                    and isinstance(agent_chunk[1], (list, tuple))
                ):
                    namespace, payload = agent_chunk
                    subgraph_path = _format_subgraph_path(namespace)
                    agent_mode, chunk = payload
                # 形式 B: (namespace_tuple, agent_mode, chunk)
                elif (
                    len(agent_chunk) == 3
                    and isinstance(agent_chunk[0], (list, tuple))
                    and isinstance(agent_chunk[1], str)
                ):
                    namespace, agent_mode, chunk = agent_chunk
                    subgraph_path = _format_subgraph_path(namespace)
                else:
                    # 回退为普通处理
                    agent_mode, chunk = agent_chunk
            else:
                # 不启用 subgraphs，普通处理
                agent_mode, chunk = agent_chunk

            step += 1

            # 为每个请求的 SDK 模式生成事件
            for sdk_mode in requested_modes:
                serialized = _serialize_chunk_for_mode(
                    chunk=chunk,
                    sdk_mode=sdk_mode,
                    agent_mode=agent_mode,
                    thread_id=thread_id,
                    run_id=run_id,
                    step=step,
                )
                if serialized is not None:
                    # SDK 约定：event 名称规范化
                    event_type = (
                        "messages" if sdk_mode in ("messages", "messages-tuple") else sdk_mode
                    )
                    # 添加子图路径后缀
                    yield format_sse_event(
                        _with_subgraph_suffix(event_type, subgraph_path),
                        serialized,
                    )

        # 发送结束事件
        yield format_sse_event("end", {})
        logger.info(f"Stream run completed: {run_id}")

    except Exception as e:
        logger.error(f"Stream run failed: {run_id}", exc_info=True)
        yield format_sse_event("error", {"error": type(e).__name__, "message": str(e)})
```

### 4. 前端集成

**文件**: `frontend/src/app/hooks/useChat.ts`

```typescript
const sendMessage = useCallback(
  (content: string) => {
    const newMessage: Message = { id: uuidv4(), type: "human", content };
    stream.submit(
      { messages: [newMessage] },
      {
        optimisticValues: (prev) => ({
          messages: [...(prev.messages ?? []), newMessage],
        }),
        config: { ...(activeAssistant?.config ?? {}), recursion_limit: 100 },
        streamSubgraphs: true,  // ← 启用子图流
      }
    );
    onHistoryRevalidate?.();
  },
  [stream, activeAssistant?.config, onHistoryRevalidate]
);

const runSingleStep = useCallback(
  (nodeId: string) => {
    stream.submit(
      { command: { type: "step", node_id: nodeId } },
      {
        streamSubgraphs: true,  // ← 启用子图流
      }
    );
  },
  [stream]
);

const continueStream = useCallback(() => {
  stream.submit(
    { command: { type: "continue" } },
    {
      streamSubgraphs: true,  // ← 启用子图流
    }
  );
}, [stream]);
```

---

## 验证方案

### 1. 单元测试

创建测试用例验证解包逻辑：

```python
def test_format_subgraph_path():
    assert _format_subgraph_path(("subgraph",)) == "subgraph"
    assert _format_subgraph_path(("parent", "child")) == "parent/child"
    assert _format_subgraph_path(None) == ""
    assert _format_subgraph_path([]) == ""

def test_with_subgraph_suffix():
    assert _with_subgraph_suffix("updates", "") == "updates"
    assert _with_subgraph_suffix("updates", "subgraph") == "updates|subgraph"
    assert _with_subgraph_suffix("messages", "parent/child") == "messages|parent/child"
```

### 2. 契约测试脚本

**文件**: `docs/tech/202512/check_langgraph_contract.py`

```python
def check_thread_stream_and_history(base_url: str) -> None:
    # 创建线程
    thread = _request_json(base_url, "POST", "/threads", json={})
    thread_id = thread.get("thread_id")

    # 发起带 stream_subgraphs=true 的流式请求
    stream_payload = {
        "assistant_id": "researchAgent",
        "input": {"messages": [{"role": "user", "content": "test"}]},
        "stream_mode": ["updates"],
        "stream_subgraphs": True,  # ← 关键
    }

    resp = requests.post(
        f"{base_url}/threads/{thread_id}/runs/stream",
        json=stream_payload,
        stream=True,
    )

    # 验证 SSE 流中至少出现一个子图事件
    saw_subgraph_event = False
    for _ in range(80):
        line = resp.raw.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="ignore")
        if decoded.startswith("event:") and "|" in decoded:
            saw_subgraph_event = True
            break

    assert saw_subgraph_event, "Expected at least one subgraph-suffixed SSE event"
```

### 3. E2E 验证步骤

1. **启动后端**
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn src.facade.langgraph_api.main:app --reload --port 2024
   ```

2. **启动前端**
   ```bash
   cd frontend
   yarn dev
   ```

3. **运行契约脚本**
   ```bash
   cd backend
   python ../docs/tech/202512/check_langgraph_contract.py --base-url http://localhost:2024
   ```

4. **手动测试**
   - 打开浏览器访问 `http://localhost:3000`
   - 发送一条消息
   - 在浏览器开发者工具的 Network 标签中检查 SSE 流
   - 验证是否出现 `event: updates|...` 格式的事件

---

## 常见问题

### Q1: 为什么需要兼容两种 namespace 形式？

**A**: LangGraph 的不同版本或不同配置可能返回不同的结构。通过兼容两种形式，我们确保在版本升级或配置变化时不会立即崩溃，而是有一个优雅的回退机制。

### Q2: 如果 `stream_subgraphs=False` 会怎样？

**A**: 后端会跳过 namespace 解包逻辑，直接按 `(agent_mode, chunk)` 处理，行为与之前完全一致，保证向后兼容。

### Q3: 子图路径的格式是什么？

**A**: 使用 `/` 作为分隔符，从根到叶的路径。例如：
- `subgraph_name` - 一级子图
- `parent/child` - 二级子图
- `parent/child/grandchild` - 三级子图

### Q4: 前端如何处理子图事件？

**A**: `@langchain/langgraph-sdk` 的 `useStream` 钩子会自动解析 `event|path` 格式，并将其映射到 `AsSubgraph<T>` 类型。前端代码无需特殊处理，只需确保传递 `streamSubgraphs: true`。

### Q5: 如果 Agent 没有子图会怎样？

**A**: 所有事件的 `subgraph_path` 都会是空字符串，事件名称保持原样（如 `updates`），完全透明。

### Q6: 性能影响如何？

**A**: 启用 `subgraphs=True` 会增加 LangGraph 的处理开销（需要追踪所有层级的输出），但对网络和序列化的影响很小。建议仅在需要时启用。

---

## 总结

本实现通过以下关键步骤实现了完整的 Subgraphs Streaming 支持：

1. **数据模型层**：扩展 `RunStreamRequest` 添加 `stream_subgraphs` 字段
2. **路由层**：透传参数到服务层
3. **服务层**：
   - 透传 `subgraphs` 参数给 LangGraph
   - 兼容多种 namespace 返回形式
   - 生成 `event|subgraph_path` 格式的 SSE 事件
4. **前端层**：在所有 `stream.submit` 调用中传递 `streamSubgraphs: true`
5. **验证**：通过契约脚本和 E2E 测试确保功能正确性

整个实现保持了向后兼容性，当 `stream_subgraphs=False` 时行为完全不变。
