# LangGraph API 契约与日常校验

> 结合 `@langchain/langgraph-sdk` 前端 client 的实际行为，对后端接口的契约要求和日常校验方法做一个独立梳理，作为开发/Code Review/CI 的参考基线。

---

## 1. 范围与目标

本契约主要覆盖：

- **Assistants**：`/assistants/search`, `/assistants/{id}`
- **Threads**：`/threads`, `/threads/search`, `/threads/{id}`, `/threads/{id}/state`, `/threads/{id}/history`
- **Runs**：`/threads/{id}/runs/stream`, `/runs/stream`

并强调：

- 以 SDK 类型定义为单一真源（TS Schema → JSON 结构 → Pydantic）
- 把“契约正确”当作 **自动化测试的一部分**，而不是等 UI 异常再排查

---

## 2. Assistants 契约

### 2.1 SDK 行为

前端使用 `@langchain/langgraph-sdk` 时，典型流程是：

- 启动时：

  ```ts
  const assistants = await client.assistants.search({
    graphId: config.assistantId,
    limit: 100,
  });
  const defaultAssistant = assistants.find(
    (assistant) => assistant.metadata?.["created_by"] === "system",
  );
  ```

- 如果找不到 `created_by === "system"` 的 assistant，会抛出 `"No default assistant found"`。

### 2.2 后端接口要求

#### 2.2.1 `POST /assistants/search`

- 请求体（约定）：

  ```json
  {
    "graph_id": "researchAgent",
    "limit": 100,
    "metadata": {}
  }
  ```

- 响应：`Assistant[]`，字段对齐 SDK `schema.Assistant`：

  ```json
  {
    "assistant_id": "researchAgent",
    "graph_id": "researchAgent",
    "name": "Research Agent",
    "config": {},
    "metadata": {"created_by": "system"},
    "created_at": "2025-12-14T...",
    "updated_at": "2025-12-14T...",
    "version": 1
  }
  ```

- 强约束：

  - **至少**返回一个 `metadata.created_by === "system"` 的默认 assistant。
  - 该默认 assistant 的 `graph_id` 必须与前端配置的 `assistantId` 一致（本项目为 `researchAgent`）。

#### 2.2.2 `GET /assistants/{id}`

- 必须返回完整 `Assistant` 对象，字段与搜索返回一致。

---

## 3. Threads 契约

### 3.1 SDK 行为（State / History）

- `client.threads.getState(threadId, checkpoint?) -> Promise<ThreadState>`
- `client.threads.getHistory(threadId, opts) -> Promise<ThreadState[]>`
- React `useStream` / `useThreadHistory`：
  - 内部使用 `ThreadState[]` 来构建：
    - `stream.history`（扁平历史）
    - `branchTree`（分支树）
    - `threadHead`（当前最新状态）

> 结论：**后端 `state`/`history` 返回的每一项，都必须是完整的 `ThreadState` 结构**。

### 3.2 ThreadState 结构

根据 SDK `schema.ThreadState`，后端需要返回：

```ts
interface ThreadState<ValuesType = Record<string, unknown> | Record<string, unknown>[]> {
  values: ValuesType;              // 会话状态：messages/todos/files...
  next: string[];                  // 下一步节点，暂无可返回 []
  checkpoint: {
    thread_id: string;
    checkpoint_ns: string;
    checkpoint_id: string | null;
    checkpoint_map: Record<string, unknown> | null;
  };
  metadata: Record<string, unknown>;
  created_at: string | null;
  parent_checkpoint: {
    thread_id: string;
    checkpoint_ns: string;
    checkpoint_id: string | null;
    checkpoint_map: Record<string, unknown> | null;
  } | null;
  tasks: any[];                    // 当前可返回 []
}
```

### 3.3 `GET /threads/{id}/state`

- 响应必须是单个 `ThreadState`：

  ```json
  {
    "values": {"messages": [...], "todos": [], "files": {}},
    "next": [],
    "checkpoint": {
      "thread_id": "...",
      "checkpoint_ns": "",
      "checkpoint_id": "...",
      "checkpoint_map": null
    },
    "metadata": {"thread_id": "...", "step": 1, "source": "loop"},
    "created_at": "2025-12-14T...",
    "parent_checkpoint": null,
    "tasks": []
  }
  ```

### 3.4 `POST /threads/{id}/history`

- 请求体（SDK 默认）：

  ```json
  {
    "limit": 10,
    "before": null,
    "checkpoint": null,
    "metadata": null
  }
  ```

- 响应：`ThreadState[]`，即上面结构的数组。

- 关键点：

  - **不要返回自定义结构**（如 `checkpoint_id` 顶层字段），而是返回完整 `ThreadState`。
  - `checkpoint` / `parent_checkpoint` 应从 `CheckpointTuple.config.configurable` / `parent_config.configurable` 派生。
  - `values` 通过统一的 `_extract_values_from_checkpoint` 从 `checkpoint.channel_values` 中提取。

---

## 4. Runs / Streaming 契约

### 4.1 SDK 行为

- `client.runs.stream(threadId, assistantId, payload)`
- React `useStream`：
  - 负责管理 `messages`/`values` 流式更新
  - 依赖 SSE 事件类型：`metadata` / `updates` / `values` / `messages` / `end` / `error`

### 4.2 StreamMode 完整类型定义

根据 `@langchain/langgraph-sdk/dist/types.stream.d.ts`，SDK 支持以下 StreamMode：

```ts
type StreamMode = "values" | "messages" | "updates" | "events" | "debug"
                | "tasks" | "checkpoints" | "custom" | "messages-tuple";
```

每种模式对应的 SSE 事件 `data` 结构如下：

#### 4.2.1 `values` 模式

```ts
type ValuesStreamEvent<StateType> = {
  event: "values";
  data: StateType;  // 完整的状态快照
};
```

示例：

```json
event: values
data: {"messages": [...], "todos": [], "files": {}}
```

#### 4.2.2 `messages` / `messages-tuple` 模式

```ts
type MessagesTupleStreamEvent = {
  event: "messages";
  data: [message: Message, config: MessageTupleMetadata];
};

type MessageTupleMetadata = {
  tags: string[];
  [key: string]: unknown;
};
```

**关键点**：`data[0]` 必须是完整的 `Message` 对象，不能是字符串 repr。

示例：

```json
event: messages
data: [
  {
    "id": "run-xxx-0",
    "type": "AIMessageChunk",
    "content": "如果你",
    "name": null,
    "additional_kwargs": {},
    "response_metadata": {},
    "tool_calls": []
  },
  {
    "tags": [],
    "langgraph_step": 1,
    "langgraph_node": "agent"
  }
]
```

#### 4.2.3 `updates` 模式

```ts
type UpdatesStreamEvent<UpdateType> = {
  event: "updates";
  data: {
    [node: string]: UpdateType;  // 节点名 -> 更新内容
  };
};
```

示例：

```json
event: updates
data: {"agent": {"messages": [...]}}
```

#### 4.2.4 `tasks` 模式

```ts
// 任务创建事件
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

// 任务结果事件
type TasksStreamResultEvent<UpdateType> = {
  event: "tasks";
  data: {
    id: string;
    name: string;
    interrupts: Interrupt[];
    result: [string, UpdateType][];  // [节点名, 更新内容][]
  };
};

// 任务错误事件
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

示例（结果事件）：

```json
event: tasks
data: {
  "id": "run-xxx-1",
  "name": "agent",
  "interrupts": [],
  "result": [["agent", {"messages": [...]}]]
}
```

#### 4.2.5 `checkpoints` 模式

```ts
type CheckpointsStreamEvent<StateType> = {
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

示例：

```json
event: checkpoints
data: {
  "values": {"messages": [...]},
  "next": [],
  "config": {"configurable": {"thread_id": "...", "checkpoint_id": null}},
  "metadata": {"source": "loop", "step": 1, "writes": null},
  "tasks": []
}
```

#### 4.2.6 `debug` 模式

```ts
type DebugStreamEvent = {
  event: "debug";
  data: unknown;  // 任意调试信息
};
```

#### 4.2.7 `events` 模式

```ts
type EventsStreamEvent = {
  event: "events";
  data: {
    event: "on_chat_model_start" | "on_llm_stream" | "on_chain_end" | ...;
    name: string;
    tags: string[];
    run_id: string;
    metadata: Record<string, unknown>;
    parent_ids: string[];
    data: unknown;
  };
};
```

#### 4.2.8 `custom` 模式

```ts
type CustomStreamEvent<T> = {
  event: "custom";
  data: T;  // 自定义数据，透传
};
```

#### 4.2.9 通用事件类型

除了上述模式特定事件，还有以下通用事件：

```ts
// 元数据事件（流开始时发送）
type MetadataStreamEvent = {
  event: "metadata";
  data: { run_id: string; thread_id: string; };
};

// 错误事件
type ErrorStreamEvent = {
  event: "error";
  data: { error: string; message: string; };
};

// 结束事件
// event: "end", data: {}
```

### 4.3 `POST /threads/{thread_id}/runs/stream`

- 请求体（示例）：

  ```json
  {
    "assistant_id": "researchAgent",
    "input": {
      "messages": [
        {"role": "user", "content": "你好"}
      ]
    },
    "stream_mode": ["messages", "updates"],
    "config": {"configurable": {"thread_id": "..."}}
  }
  ```

- 响应：SSE 流，事件格式取决于 `stream_mode`：

  ```text
  event: metadata
  data: {"run_id": "...", "thread_id": "..."}

  event: messages
  data: [{"id": "...", "type": "AIMessageChunk", "content": "如"}, {"tags": []}]

  event: messages
  data: [{"id": "...", "type": "AIMessageChunk", "content": "果"}, {"tags": []}]

  event: end
  data: {}
  ```

### 4.4 后端实现要点

1. **模式映射**：SDK 的 `stream_mode` 需要映射到 LangGraph agent 的实际模式：
   - `messages` / `messages-tuple` → agent `stream_mode="messages"`
   - `values` → agent `stream_mode="values"`
   - `updates` / `tasks` / `checkpoints` → agent `stream_mode="updates"`

2. **数据序列化**：每种模式的 `data` 结构必须严格符合 SDK 类型定义：
   - `messages` 模式：`[Message dict, metadata dict]`
   - `updates` 模式：`{node_name: update_dict}`
   - `tasks` 模式：`{id, name, interrupts, result/input/error}`
   - `checkpoints` 模式：`{values, next, config, metadata, tasks}`

3. **错误处理**：异常时发送 `event: error`，`data` 包含 `error` 和 `message` 字段

---

## 5. 日常契约校验方式

不要等到 UI 异常才发现协议不匹配，应在 **开发 / 预发布 / CI 阶段** 就自动校验：

1. 后端是否启动且无严重错误
2. 关键端点是否可用
3. 返回 JSON 是否满足 SDK 类型约束

### 5.1 手工快速校验（开发时）

- Assistants：

  ```bash
  curl -s -X POST http://localhost:2024/assistants/search \
    -H "Content-Type: application/json" \
    -d '{"graph_id": "researchAgent", "limit": 100}' | jq
  ```

  检查：

  - 返回数组不为空
  - 存在 `metadata.created_by == "system"` 的元素

- Threads + Streaming + History：

  见 `docs/tech/202512/check_langgraph_contract.py` 中的步骤。

### 5.2 自动化校验脚本

本目录中提供 `check_langgraph_contract.py`，用于在开发/CI 中自动校验：

- `/ok` 健康检查
- `/assistants/search` 默认 assistant 契约
- `/threads` + `/threads/{id}/runs/stream` 基本流式调用
- `/threads/{id}/history` 返回结构是否是 `ThreadState[]`

推荐：

- 本地开发：

  ```bash
  cd backend
  source .venv/bin/activate
  python ../docs/tech/202512/check_langgraph_contract.py --base-url http://localhost:2024
  ```

- CI 中：

  - 在启动后端服务后，作为一个独立的校验步骤执行；
  - 任何断言失败都应视为构建失败，提前暴露契约问题。

---

## 6. 后续扩展建议

1. 如未来引入 `/crons`、`/items` 等 LangGraph 其他能力，也应按同样方式：
   - 先看 SDK 类型定义
   - 再设计后端 Pydantic / JSON Schema
   - 最后补自动化校验
2. 可以考虑把 `check_langgraph_contract.py` 中的断言拆成 pytest 测试，用 `requests`/`httpx` + `pydantic` 进行强类型校验。
