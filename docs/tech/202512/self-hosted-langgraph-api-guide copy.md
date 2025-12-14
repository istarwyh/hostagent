# 自建 LangGraph API 技术方案

> 从 DeepAgent 实例出发，适配标准 LangGraph UI 层

## 1. 背景与目标

### 1.1 问题场景

你已经有一个基于 `DeepAgent` 框架构建的 Agent 实例（如 `researchAgent`），它能够：

- 接收用户输入并生成响应
- 使用工具（如 `internet_search`）
- 管理子代理（如 `critique-agent`、`research-agent`）
- 通过 LangGraph 的 `MemorySaver` 持久化会话状态

现在你希望复用一套标准的前端 UI（基于 `@langchain/langgraph-sdk`），而不想使用 LangGraph Cloud 托管服务。

### 1.2 核心挑战

前端 SDK 期望连接到一个符合 **LangGraph API 规范** 的后端，包括：

- `/assistants/*` - 管理 Assistant 元信息
- `/threads/*` - 管理会话线程和状态
- `/runs/*` - 执行流式运行

你的 DeepAgent 实例本身不暴露这些 HTTP 端点，因此需要构建一个 **兼容层**。

### 1.3 目标

构建一个自托管的 LangGraph 兼容 API 服务，使得：

1. 前端 SDK 可以无缝连接
2. 会话状态通过 LangGraph 的 checkpointer 持久化
3. 流式输出符合 SSE 协议规范

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                          │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │ useStream   │  │ useThreads  │  │ @langchain/langgraph-sdk    │ │
│  │ (流式交互)  │  │ (线程列表)  │  │ Client                      │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────────┬──────────────┘ │
└─────────┼────────────────┼───────────────────────┼─────────────────┘
          │                │                       │
          ▼                ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LangGraph 兼容 API (FastAPI)                     │
│                         http://localhost:2024                       │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │ /assistants │  │ /threads    │  │ /runs       │  │ /ok       │  │
│  │ /search     │  │ /search     │  │ /stream     │  │ /health   │  │
│  │ /{id}       │  │ /{id}/state │  │             │  │           │  │
│  │             │  │ /{id}/history│ │             │  │           │  │
│  │             │  │ /{id}/runs/ │  │             │  │           │  │
│  │             │  │    stream   │  │             │  │           │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────────┘  │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  Shared MemorySaver                          │  │
│  │                  (checkpointer.py)                           │  │
│  │                                                              │  │
│  │  - 所有 checkpoint 读写的唯一入口                            │  │
│  │  - Agent 和 API 共享同一实例                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                          │                                          │
│                          ▼                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  DeepAgent Instance                          │  │
│  │                  (researchAgent)                             │  │
│  │                                                              │  │
│  │  - create_deep_agent(..., checkpointer=checkpointer)         │  │
│  │  - agent.astream(input, config={"thread_id": ...})           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心设计：共享 Checkpointer

### 3.1 为什么需要共享？

LangGraph 的 checkpointer 是状态持久化的核心：

- **Agent 写入**：每次 `agent.astream()` 执行时，LangGraph 内部会自动调用 `checkpointer.put()` 保存 checkpoint
- **API 读取**：`/threads/{id}/state` 和 `/threads/{id}/history` 需要从 checkpointer 读取状态

如果 Agent 和 API 使用不同的 checkpointer 实例，API 将无法看到 Agent 写入的状态。

### 3.2 实现方式

创建一个全局共享的 checkpointer 模块：

```python
# backend/src/langgraph_api/checkpointer.py

from langgraph.checkpoint.memory import MemorySaver

# 单例：所有模块共享这一个实例
checkpointer = MemorySaver()
```

### 3.3 Agent 使用共享 checkpointer

修改你的 DeepAgent 实例，注入共享的 checkpointer：

```python
# backend/src/service/research_agent/research_agent.py

from src.deepagents.graph import create_deep_agent
from src.langgraph_api.checkpointer import checkpointer  # 引入共享实例

agent = create_deep_agent(
    tools=[internet_search],
    instructions=research_instructions,
    subagents=[critique_sub_agent, research_sub_agent],
    checkpointer=checkpointer,  # 关键：注入共享 checkpointer
).with_config({"recursion_limit": 1000})
```

### 3.4 API 使用同一 checkpointer

在 threads 路由中，直接 import 并使用：

```python
# backend/src/langgraph_api/routers/threads.py

from src.langgraph_api.checkpointer import checkpointer

# 在 /threads/search 中
all_tuples = list(checkpointer.list(None))

# 在 /threads/{id}/state 中
tuples = list(checkpointer.list({"configurable": {"thread_id": thread_id}}))
```

---

## 4. 数据流详解

### 4.1 流式执行数据流

```
用户发送消息
    │
    ▼
POST /threads/{thread_id}/runs/stream
    │
    ├─ request.input = {"messages": [{"role": "user", "content": "..."}]}
    │
    ▼
run_service.execute_stream_run()
    │
    ├─ run_config = {"configurable": {"thread_id": thread_id}}
    │
    ▼
agent.astream(input_data, config=run_config, stream_mode="updates")
    │
    ├─ LangGraph 内部：
    │   1. 执行 agent 节点
    │   2. 调用 checkpointer.put() 保存每个 checkpoint
    │   3. yield chunk (包含 messages, todos, files 等)
    │
    ▼
serialize_state(chunk) → format_sse_event("updates", data)
    │
    ▼
SSE 响应流 → 前端 useStream 消费
```

### 4.2 状态查询数据流

```
前端请求历史
    │
    ▼
POST /threads/{thread_id}/history
    │
    ▼
checkpointer.list({"configurable": {"thread_id": thread_id}})
    │
    ├─ 返回 List[CheckpointTuple]
    │   每个 tuple 包含：
    │   - config: {"configurable": {"thread_id": ..., "checkpoint_id": ...}}
    │   - checkpoint: {"channel_values": {...}, "ts": ..., "id": ...}
    │   - metadata: {"source": "loop", "step": 0, ...}
    │
    ▼
_extract_values_from_checkpoint(checkpoint)
    │
    ├─ 从 channel_values 中提取：
    │   - messages: List[Message]
    │   - todos: List[TodoItem]
    │   - files: Dict[str, str]
    │
    ▼
返回 JSON → 前端 useStream 重建状态
```

---

## 5. 数据结构设计

### 5.1 Checkpoint 内部结构

LangGraph 的 `MemorySaver` 存储的 checkpoint 结构：

```python
CheckpointTuple = {
    "config": {
        "configurable": {
            "thread_id": "uuid-string",
            "checkpoint_id": "uuid-string",
            "checkpoint_ns": ""
        }
    },
    "checkpoint": {
        "v": 1,
        "id": "checkpoint-uuid",
        "ts": "2025-12-14T05:20:22.502275Z",
        "channel_values": {
            # 这里是 agent state 的实际内容
            # 结构取决于你的 StateSchema
        },
        "channel_versions": {...},
        "versions_seen": {...}
    },
    "metadata": {
        "source": "loop",  # 或 "input", "update"
        "step": 0,
        "parents": {}
    },
    "parent_config": {...} | None,
    "pending_writes": [...] | None
}
```

### 5.2 channel_values 的两种形态

根据 agent 的执行阶段，`channel_values` 可能呈现不同结构：

**形态 1：dict 包含 messages**

```python
channel_values = {
    "agent": {
        "messages": [HumanMessage(...), AIMessage(...)],
        "todos": [...],
        "files": {...}
    }
}
```

**形态 2：list-of-messages**

```python
channel_values = {
    "messages": [
        [HumanMessage(...), AIMessage(...)]  # 嵌套列表
    ]
}
```

### 5.3 API 返回的 values 结构

无论 checkpoint 内部是哪种形态，API 都需要返回统一的结构：

```json
{
  "values": {
    "messages": [
      {
        "type": "human",
        "content": "你好",
        "id": "uuid",
        "additional_kwargs": {},
        "response_metadata": {}
      },
      {
        "type": "ai",
        "content": "你好！有什么可以帮助你的？",
        "id": "run--uuid",
        "additional_kwargs": {...},
        "response_metadata": {...},
        "tool_calls": [],
        "usage_metadata": {...}
      }
    ],
    "todos": [...],
    "files": {...}
  }
}
```

### 5.4 Message 类型定义

前端 SDK 期望的 Message 结构（来自 `@langchain/langgraph-sdk`）：

```typescript
interface Message {
  id: string;
  type: "human" | "ai" | "tool" | "system";
  content: string | ContentBlock[];
  name?: string;
  additional_kwargs?: Record<string, any>;
  response_metadata?: Record<string, any>;
  tool_calls?: ToolCall[];
  tool_call_id?: string;  // 仅 tool 类型
}
```

---

## 6. 核心端点实现

### 6.1 端点清单

| 端点 | 方法 | 用途 |
|------|------|------|
| `/ok` | GET | 健康检查 |
| `/assistants/search` | POST | 搜索 Assistant |
| `/assistants/{id}` | GET | 获取 Assistant 详情 |
| `/threads` | POST | 创建线程 |
| `/threads/search` | POST | 搜索线程列表 |
| `/threads/{id}` | GET | 获取线程详情 |
| `/threads/{id}/state` | GET | 获取线程状态 |
| `/threads/{id}/state` | POST | 更新线程状态 |
| `/threads/{id}/history` | GET/POST | 获取线程历史 |
| `/threads/{id}/runs/stream` | POST | 流式执行 |
| `/runs/stream` | POST | 无状态流式执行 |

### 6.2 /threads/{id}/runs/stream 实现

这是最核心的端点，负责流式执行 agent：

```python
@router.post("/{thread_id}/runs/stream")
async def stream_run(thread_id: str, request: RunStreamRequest):
    async def event_generator():
        async for event in execute_stream_run(
            thread_id=thread_id,
            assistant_id=request.assistant_id,
            input_data=request.input,
            stream_mode=request.stream_mode,
            config=request.config,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### 6.3 /threads/{id}/history 实现

从 checkpointer 读取历史，并处理"同一 step 多变体"的情况：

```python
@router.api_route("/{thread_id}/history", methods=["GET", "POST"])
async def get_thread_history(thread_id: str, limit: int = 10):
    tuples = list(
        checkpointer.list({"configurable": {"thread_id": thread_id}}, limit=limit)
    )
    if not tuples:
        raise HTTPException(status_code=404, detail="Thread not found")

    # 按 step 分组，每个 step 只保留消息最完整的 checkpoint
    grouped: Dict[int, List[CheckpointTuple]] = {}
    for t in tuples:
        step = getattr(t.metadata, "step", 0)
        grouped.setdefault(step, []).append(t)

    history = []
    for step in sorted(grouped.keys()):
        candidates = grouped[step]
        # 选择 messages 最多的候选
        best = max(candidates, key=lambda t: len(
            _extract_values_from_checkpoint(t.checkpoint).get("messages", [])
        ))
        values = _extract_values_from_checkpoint(best.checkpoint)
        history.append({
            "checkpoint_id": best.checkpoint.get("id") or f"{thread_id}-{step}",
            "values": values,
            "metadata": {"thread_id": thread_id, "step": step},
            "created_at": best.checkpoint.get("ts"),
        })

    return history
```

### 6.4 _extract_values_from_checkpoint 实现

处理 checkpoint 的多种内部结构：

```python
def _extract_values_from_checkpoint(checkpoint: dict) -> dict:
    values = {}
    channel_values = checkpoint.get("channel_values", {}) or {}

    for node_data in channel_values.values():
        # Case 1: dict 包含 messages
        if isinstance(node_data, dict):
            if "messages" in node_data:
                serialized = [serialize_message(m) for m in node_data["messages"]]
                values.setdefault("messages", []).extend(serialized)
            for key, val in node_data.items():
                if key != "messages":
                    values[key] = val
            continue

        # Case 2: list-of-messages
        if isinstance(node_data, list):
            flat = []
            for item in node_data:
                if isinstance(item, list):
                    flat.extend(item)
                else:
                    flat.append(item)
            if flat and _is_message(flat[0]):
                serialized = [serialize_message(m) for m in flat]
                values.setdefault("messages", []).extend(serialized)

    return values
```

---

## 7. SSE 流式协议

### 7.1 事件格式

```
event: <event_type>
data: <json_payload>

```

注意：每个事件以两个换行符结尾。

### 7.2 事件类型

| 事件类型 | 用途 | 数据结构 |
|----------|------|----------|
| `metadata` | 运行元信息 | `{"run_id": "uuid"}` |
| `updates` | 状态增量更新 | `{"agent": {"messages": [...]}}` |
| `values` | 完整状态快照 | `{"messages": [...], "todos": [...]}` |
| `messages` | 流式消息 token | `[{message}, {metadata}]` |
| `end` | 流结束 | `{}` |
| `error` | 错误 | `{"message": "...", "code": "..."}` |

### 7.3 格式化函数

```python
def format_sse_event(event_type: str, data: dict) -> str:
    json_data = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"
```

---

## 8. 消息序列化

### 8.1 LangChain Message → dict

```python
def serialize_message(msg) -> dict:
    # 优先使用 Pydantic 的序列化方法
    if hasattr(msg, 'model_dump'):
        return msg.model_dump()
    if hasattr(msg, 'dict'):
        return msg.dict()
    if isinstance(msg, dict):
        return msg

    # 手动构造
    return {
        "type": getattr(msg, 'type', 'unknown'),
        "content": getattr(msg, 'content', str(msg)),
        "id": getattr(msg, 'id', str(uuid4())),
        "additional_kwargs": getattr(msg, 'additional_kwargs', {}),
        "response_metadata": getattr(msg, 'response_metadata', {}),
    }
```

### 8.2 State 序列化

```python
def serialize_state(state: dict) -> dict:
    result = {}
    for key, value in state.items():
        if key == "messages" and isinstance(value, list):
            result[key] = [serialize_message(m) for m in value]
        elif hasattr(value, 'model_dump'):
            result[key] = value.model_dump()
        else:
            result[key] = value
    return result
```

---

## 9. 目录结构

```
backend/src/langgraph_api/
├── __init__.py
├── main.py                 # FastAPI 应用入口
├── checkpointer.py         # 共享 MemorySaver 实例
├── models/
│   ├── __init__.py
│   ├── assistant.py        # Assistant 相关 Pydantic 模型
│   ├── thread.py           # Thread 相关 Pydantic 模型
│   └── run.py              # Run 相关 Pydantic 模型
├── routers/
│   ├── __init__.py
│   ├── assistants.py       # /assistants/* 路由
│   ├── threads.py          # /threads/* 路由
│   └── runs.py             # /runs/* 路由
└── services/
    ├── __init__.py
    └── run_service.py      # 流式执行服务
```

---

## 10. 启动与配置

### 10.1 启动后端

```bash
cd backend
source .venv/bin/activate
uvicorn src.langgraph_api.main:app --host 0.0.0.0 --port 2024 --reload
```

### 10.2 前端配置

在前端 UI 中配置：

- **Deployment URL**: `http://localhost:2024`
- **Assistant ID**: `researchAgent`

### 10.3 验证连接

```bash
# 健康检查
curl http://localhost:2024/ok

# 搜索 Assistant
curl -X POST http://localhost:2024/assistants/search \
  -H "Content-Type: application/json" \
  -d '{}'

# 创建线程
curl -X POST http://localhost:2024/threads \
  -H "Content-Type: application/json" \
  -d '{}'

# 流式执行
curl -N http://localhost:2024/threads/<thread_id>/runs/stream \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "researchAgent",
    "input": {"messages": [{"role": "user", "content": "你好"}]},
    "stream_mode": ["updates"]
  }'
```

---

## 11. 常见问题与解决

### 11.1 "No default assistant found"

**原因**：前端期望 `/assistants/search` 返回的 assistant 包含 `metadata.created_by === "system"`。

**解决**：在 assistants 路由中添加：

```python
return [{
    "assistant_id": "researchAgent",
    "metadata": {"created_by": "system"},  # 关键
    ...
}]
```

### 11.2 "消息一闪而过"

**原因**：流式结束后，前端调用 `/threads/{id}/history` 重建状态，但返回的 `values.messages` 结构不正确。

**解决**：
1. 确保 `_extract_values_from_checkpoint` 正确处理 checkpoint 的多种内部结构
2. 对同一 step 的多个 checkpoint，只保留消息最完整的那个
3. 确保 `checkpoint_id` 非空

### 11.3 "HTTP 405 Method Not Allowed"

**原因**：前端 SDK 对某些端点使用 POST，但后端只实现了 GET。

**解决**：使用 `@router.api_route(..., methods=["GET", "POST"])`。

### 11.4 "Thread not found" 但刚刚还在

**原因**：`MemorySaver` 是内存存储，进程重启后数据丢失。

**解决**：
- 开发阶段：接受这个限制
- 生产环境：换用 `PostgresSaver` 或 `RedisSaver`

---

## 12. 扩展：切换到持久化存储

当前方案使用 `MemorySaver`，适合开发测试。生产环境建议切换到持久化存储：

```python
# checkpointer.py

# 方案 1：PostgreSQL
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")

# 方案 2：Redis
from langgraph.checkpoint.redis import RedisSaver
checkpointer = RedisSaver.from_conn_string("redis://...")
```

由于整个方案基于共享 checkpointer 设计，切换存储只需修改这一个文件。

---

## 13. 总结

### 13.1 核心要点

1. **共享 Checkpointer**：Agent 和 API 必须使用同一个 checkpointer 实例
2. **数据结构对齐**：API 返回的 `values.messages` 必须符合前端 SDK 的 `Message` 类型
3. **SSE 协议**：流式响应必须遵循 `event: xxx\ndata: {...}\n\n` 格式
4. **多形态处理**：checkpoint 内部结构可能有多种形态，需要统一处理

### 13.2 实现步骤

1. 创建共享 checkpointer 模块
2. 修改 DeepAgent 实例，注入共享 checkpointer
3. 实现 LangGraph 兼容的 API 端点
4. 处理 checkpoint 到 API 响应的数据转换
5. 验证前端 SDK 连接

### 13.3 适用场景

- 希望自托管 LangGraph 服务
- 已有 DeepAgent 实例，需要适配标准 UI
- 需要完全控制后端逻辑
- 不想依赖 LangGraph Cloud
