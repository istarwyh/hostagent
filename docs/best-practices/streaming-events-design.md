# LangGraph 流式事件设计指南

本文档详细说明后端如何将 LangGraph Agent 的流式输出包装成符合 `@langchain/langgraph-sdk` 契约的 SSE 事件。

## 设计思路

### 核心理念

后端流式服务的本质是一个 **协议适配层**：

```
LangGraph Agent.astream() → 协议适配层 → SDK 契约事件 → 前端消费
```

1. **Agent 输出**：LangGraph Agent 通过 `astream()` 方法产生原始 chunk
2. **协议适配**：后端根据请求的 `stream_mode` 将 chunk 转换为 SDK 期望的数据结构
3. **SSE 封装**：将转换后的数据封装为 Server-Sent Events 格式
4. **前端消费**：SDK 的 `useStream` 等 hook 按契约解析事件

事件类型	SSE event	触发时机
MetadataStreamEvent	metadata	流开始时首发
ValuesStreamEvent	values	每步完成后的完整状态
MessagesTupleStreamEvent	messages	逐 token 流式输出
UpdatesStreamEvent	updates	节点执行后的增量更新
TasksStreamEvent	tasks	任务创建/结果/错误
CheckpointsStreamEvent	checkpoints	完整检查点信息
EventsStreamEvent	events	LangChain 回调事件
DebugStreamEvent	debug	详细调试信息
CustomStreamEvent	custom	节点自定义数据
ErrorStreamEvent	error	执行异常
EndStreamEvent	end	流正常结束

### 关键设计决策

| 决策点 | 方案 | 原因 |
|--------|------|------|
| Agent 调用次数 | 单次调用，多模式输出 | 避免重复执行，提高效率 |
| 模式优先级 | messages > values > debug > updates | 选择最详细的模式作为 primary mode |
| 事件名映射 | `messages-tuple` → `event: "messages"` | SDK 契约要求，非直接透传 |
| 数据序列化 | 统一使用 `_json_safe` | 确保所有输出可 JSON 序列化 |

---

## StreamMode 完整类型定义

根据 `@langchain/langgraph-sdk/dist/types.stream.d.ts`，SDK 支持以下 StreamMode：

```typescript
type StreamMode = "values" | "messages" | "updates" | "events" | "debug"
                | "tasks" | "checkpoints" | "custom" | "messages-tuple";
```

---

## 事件类型详解

### 1. MetadataStreamEvent（元数据事件）

**触发时机**：流开始时首先发送

**SSE 格式**：
```
event: metadata
data: {"run_id": "uuid", "thread_id": "uuid"}
```

**SDK 类型定义**：
```typescript
type MetadataStreamEvent = {
  id?: string;
  event: "metadata";
  data: {
    run_id: string;
    thread_id: string;
  };
};
```

**后端实现**：
```python
yield format_sse_event("metadata", {"run_id": run_id, "thread_id": thread_id})
```

---

### 2. ValuesStreamEvent（状态快照事件）

**触发时机**：`stream_mode` 包含 `"values"` 时，每个步骤完成后发送完整状态

**SSE 格式**：
```
event: values
data: {"messages": [...], "todos": [...], "files": {...}}
```

**SDK 类型定义**：
```typescript
type ValuesStreamEvent<StateType> = {
  id?: string;
  event: "values";
  data: StateType;  // 完整的 agent state
};
```

**data 结构示例**（DeepAgentState）：
```json
{
  "messages": [
    {"type": "human", "content": "hello", "id": "msg-1", ...},
    {"type": "ai", "content": "Hi!", "id": "msg-2", ...}
  ],
  "todos": [
    {"content": "Task 1", "status": "completed"},
    {"content": "Task 2", "status": "in_progress"}
  ],
  "files": {
    "/path/to/file.txt": "file content"
  }
}
```

**后端实现**：
```python
if sdk_mode == "values":
    if agent_mode == "messages":
        return None  # 无法从 message chunks 派生完整状态
    return serialize_state(chunk) if isinstance(chunk, dict) else chunk
```

---

### 3. MessagesTupleStreamEvent（消息流事件）

**触发时机**：`stream_mode` 包含 `"messages"` 或 `"messages-tuple"` 时，逐 token 流式输出

**SSE 格式**：
```
event: messages
data: [{"type": "AIMessageChunk", "content": "Hello", ...}, {"thread_id": "...", "langgraph_step": 1, ...}]
```

**⚠️ 重要契约**：无论请求的是 `"messages"` 还是 `"messages-tuple"`，SSE 事件名**必须**是 `"messages"`

**SDK 类型定义**：
```typescript
type MessagesTupleStreamEvent = {
  event: "messages";  // 注意：不是 "messages-tuple"
  data: [message: Message, config: MessageTupleMetadata];
};

type MessageTupleMetadata = {
  tags: string[];
  [key: string]: unknown;  // 包含 thread_id, langgraph_step, langgraph_node 等
};
```

**data 结构示例**：
```json
[
  {
    "type": "AIMessageChunk",
    "content": "I'll",
    "id": "lc_run--xxx",
    "tool_calls": [],
    "additional_kwargs": {},
    "response_metadata": {"model_provider": "openai"}
  },
  {
    "thread_id": "uuid",
    "langgraph_step": 1,
    "langgraph_node": "agent",
    "langgraph_triggers": ["branch:to:agent"],
    "ls_provider": "openai",
    "ls_model_name": "gpt-4"
  }
]
```

**后端实现**：
```python
if sdk_mode in ("messages", "messages-tuple"):
    if agent_mode != "messages":
        return None
    if isinstance(chunk, (list, tuple)) and len(chunk) == 2:
        message_like, meta = chunk
        return [_serialize_message(message_like), meta]
    return [_serialize_message(chunk), {"tags": []}]

# SSE 事件名映射
event_type = "messages" if sdk_mode in ("messages", "messages-tuple") else sdk_mode
```

---

### 4. UpdatesStreamEvent（增量更新事件）

**触发时机**：`stream_mode` 包含 `"updates"` 时，每个节点执行后发送该节点的输出

**SSE 格式**：
```
event: updates
data: {"agent": {"messages": [...]}}
```

**SDK 类型定义**：
```typescript
type UpdatesStreamEvent<UpdateType> = {
  id?: string;
  event: "updates";
  data: {
    [node: string]: UpdateType;  // 节点名 → 该节点的输出
  };
};
```

**data 结构示例**：
```json
{
  "agent": {
    "messages": [
      {
        "type": "ai",
        "content": "I'll help you with that.",
        "tool_calls": [{"name": "search", "args": {...}}]
      }
    ]
  }
}
```

**后端实现**：
```python
if sdk_mode == "updates":
    if agent_mode == "messages":
        return None
    if isinstance(chunk, dict):
        return {k: serialize_state(v) if isinstance(v, dict) else v for k, v in chunk.items()}
    return chunk
```

---

### 5. TasksStreamEvent（任务事件）

**触发时机**：`stream_mode` 包含 `"tasks"` 时，报告任务创建、结果或错误

**SSE 格式**：
```
event: tasks
data: {"id": "task-1", "name": "agent", "interrupts": [], "result": [...]}
```

**SDK 类型定义**：
```typescript
// 任务创建
type TasksStreamCreateEvent<StateType> = {
  event: "tasks";
  data: {
    id: string;
    name: string;
    interrupts: Interrupt[];
    input: StateType;
    triggers: string[];
  };
};

// 任务结果
type TasksStreamResultEvent<UpdateType> = {
  event: "tasks";
  data: {
    id: string;
    name: string;
    interrupts: Interrupt[];
    result: [string, UpdateType][];  // [节点名, 输出][]
  };
};

// 任务错误
type TasksStreamErrorEvent = {
  event: "tasks";
  data: {
    id: string;
    name: string;
    interrupts: Interrupt[];
    error: string;
  };
};
```

**后端实现**：
```python
def _build_tasks_event_data(task_id, node_name, state, is_result=False, error=None):
    base = {"id": task_id, "name": node_name, "interrupts": []}
    if error:
        base["error"] = error
    elif is_result:
        base["result"] = [[node_name, serialize_state(state)]]
    else:
        base["input"] = serialize_state(state)
        base["triggers"] = []
    return base
```

---

### 6. CheckpointsStreamEvent（检查点事件）

**触发时机**：`stream_mode` 包含 `"checkpoints"` 时，发送完整的检查点信息

**SSE 格式**：
```
event: checkpoints
data: {"values": {...}, "next": [], "config": {...}, "metadata": {...}, "tasks": []}
```

**SDK 类型定义**：
```typescript
type CheckpointsStreamEvent<StateType> = {
  id?: string;
  event: "checkpoints";
  data: {
    values: StateType;
    next: string[];
    config: Config;
    metadata: Metadata;
    tasks: ThreadTask[];
  };
};
```

**data 结构示例**：
```json
{
  "values": {"messages": [...], "todos": [...], "files": {...}},
  "next": [],
  "config": {
    "configurable": {
      "thread_id": "uuid",
      "checkpoint_id": "checkpoint-uuid"
    }
  },
  "metadata": {
    "source": "loop",
    "step": 3,
    "writes": null
  },
  "tasks": []
}
```

**后端实现**：
```python
def _build_checkpoint_event_data(thread_id, state, step=0):
    return {
        "values": serialize_state(state),
        "next": [],
        "config": {"configurable": {"thread_id": thread_id, "checkpoint_id": None}},
        "metadata": {"source": "loop", "step": step, "writes": None},
        "tasks": [],
    }
```

---

### 7. EventsStreamEvent（执行事件）

**触发时机**：`stream_mode` 包含 `"events"` 时，发送 LangChain 回调事件

**SSE 格式**：
```
event: events
data: {"event": "on_chat_model_stream", "name": "ChatOpenAI", "run_id": "...", ...}
```

**SDK 类型定义**：
```typescript
type EventsStreamEvent = {
  id?: string;
  event: "events";
  data: {
    event: `on_${"chat_model" | "llm" | "chain" | "tool" | "retriever" | "prompt"}_${"start" | "stream" | "end"}` | string;
    name: string;
    tags: string[];
    run_id: string;
    metadata: Record<string, unknown>;
    parent_ids: string[];
    data: unknown;
  };
};
```

**后端实现**：
```python
def _build_events_event_data(event_name, node_name, run_id, data):
    return {
        "event": event_name,
        "name": node_name,
        "tags": [],
        "run_id": run_id,
        "metadata": {},
        "parent_ids": [],
        "data": data,
    }
```

---

### 8. DebugStreamEvent（调试事件）

**触发时机**：`stream_mode` 包含 `"debug"` 时，发送详细调试信息

**SSE 格式**：
```
event: debug
data: {...}
```

**SDK 类型定义**：
```typescript
type DebugStreamEvent = {
  id?: string;
  event: "debug";
  data: unknown;  // 任意调试数据
};
```

**后端实现**：
```python
if sdk_mode == "debug":
    if isinstance(chunk, dict):
        return serialize_state(chunk)
    return chunk
```

---

### 9. CustomStreamEvent（自定义事件）

**触发时机**：`stream_mode` 包含 `"custom"` 时，发送节点内部自定义数据

**SSE 格式**：
```
event: custom
data: {...}
```

**SDK 类型定义**：
```typescript
type CustomStreamEvent<T> = {
  event: "custom";
  data: T;  // 任意自定义数据
};
```

**后端实现**：
```python
if sdk_mode == "custom":
    if isinstance(chunk, dict):
        return serialize_state(chunk)
    return chunk
```

---

### 10. ErrorStreamEvent（错误事件）

**触发时机**：执行过程中发生异常

**SSE 格式**：
```
event: error
data: {"error": "ValueError", "message": "Something went wrong"}
```

**SDK 类型定义**：
```typescript
type ErrorStreamEvent = {
  id?: string;
  event: "error";
  data: {
    error: string;   // 错误类型名
    message: string; // 错误消息
  };
};
```

**后端实现**：
```python
except Exception as e:
    yield format_sse_event("error", {"error": type(e).__name__, "message": str(e)})
```

---

### 11. EndStreamEvent（结束事件）

**触发时机**：流正常结束

**SSE 格式**：
```
event: end
data: {}
```

**后端实现**：
```python
yield format_sse_event("end", {})
```

---

## 实现架构

### 核心函数

```
execute_stream_run()
├── format_sse_event()           # SSE 格式化
├── STREAM_MODE_MAPPING          # SDK mode → agent mode 映射表
└── _serialize_chunk_for_mode()  # 按 SDK 模式序列化
    ├── _serialize_message()     # 消息序列化
    ├── serialize_state()        # 状态序列化
    ├── _build_checkpoint_event_data()
    ├── _build_tasks_event_data()
    └── _build_events_event_data()
```

### 模式映射与多模式透传

**关键设计**：前端请求的 `stream_mode` 列表**直接透传**给 `agent.astream()`，不再选择单一 primary mode。

```python
# 1. 前端请求的 SDK stream_mode 列表
requested_modes = ["messages-tuple", "values", "tasks"]

# 2. 映射到 agent 侧的 stream_mode（去重）
agent_modes = sorted({STREAM_MODE_MAPPING[m] for m in requested_modes})
# 结果：["messages", "updates", "values"]

# 3. 按 (agent_mode, chunk) 逐个生成 SSE 事件
async for agent_mode, chunk in agent.astream(
    input_data,
    config=run_config,
    stream_mode=agent_modes,  # 多模式列表
):
    for sdk_mode in requested_modes:
        serialized = _serialize_chunk_for_mode(
            chunk=chunk,
            sdk_mode=sdk_mode,
            agent_mode=agent_mode,  # 真实的 agent 返回模式
            ...
        )
        if serialized is not None:
            yield format_sse_event(event_type, serialized)
```

**模式映射表**：

| SDK stream_mode | Agent stream_mode | SSE event type | 说明 |
|-----------------|-------------------|----------------|------|
| `values` | `values` | `values` | 完整状态快照 |
| `messages` | `messages` | `messages` | 消息流（token 级） |
| `messages-tuple` | `messages` | `messages` ⚠️ | 消息流（SDK 契约要求 event: "messages"） |
| `updates` | `updates` | `updates` | 增量更新 |
| `tasks` | `updates` | `tasks` | 从 updates 派生 |
| `checkpoints` | `values` | `checkpoints` | 从 values 派生 |
| `debug` | `debug` | `debug` | 调试信息 |
| `events` | `events` | `events` | 执行事件 |
| `custom` | `custom` | `custom` | 自定义数据 |

**优势**：
- ✓ 语义清晰：agent 返回什么就是什么，不再「派生」或「猜测」
- ✓ 效率高：单次 agent 执行，多模式输出
- ✓ 灵活性强：支持任意组合的 stream_mode 请求

---

## 常见问题与解决方案

### 问题 1：前端不显示流式消息

**症状**：SSE 有数据输出，但前端 `stream.messages` 不更新

**原因**：`stream_mode: "messages-tuple"` 时，后端发送 `event: messages-tuple`，但 SDK 期望 `event: messages`

**解决**：
```python
event_type = "messages" if sdk_mode in ("messages", "messages-tuple") else sdk_mode
yield format_sse_event(event_type, serialized)
```

### 问题 2：history/state 返回的 values 缺少 todos/files

**症状**：`/threads/{id}/history` 返回的 `values` 只有 `messages`

**原因**：`_extract_values_from_checkpoint` 没有按 channel 名区分处理

**解决**：显式检查 `channel_name == "todos"` / `"files"` 并分别处理

### 问题 3：JSON 序列化错误

**症状**：`ValueError: 'Send' object is not iterable`

**原因**：LangGraph 内部对象（如 `Send`）直接传给 FastAPI encoder

**解决**：使用 `_json_safe()` 递归转换所有值为 JSON-safe 类型

---

## 前端消费示例

```typescript
import { useStream } from "@langchain/langgraph-sdk/react";

export type StateType = {
  messages: Message[];
  todos: TodoItem[];
  files: Record<string, string>;
};

const stream = useStream<StateType>({
  assistantId: "researchAgent",
  client: client,
  threadId: threadId,
  // SDK 会自动处理各种事件类型
});

// 访问状态
const messages = stream.messages;           // 从 messages 事件累积
const todos = stream.values.todos ?? [];    // 从 values 事件获取
const files = stream.values.files ?? {};    // 从 values 事件获取
const isLoading = stream.isLoading;         // 流状态
const interrupt = stream.interrupt;         // 中断信息
```

---

## 参考资料

- SDK 类型定义：`@langchain/langgraph-sdk/dist/types.stream.d.ts`
- 后端实现：`backend/src/service/langgraph_api/run_service.py`
- LangGraph 文档：https://langchain-ai.github.io/langgraph/
