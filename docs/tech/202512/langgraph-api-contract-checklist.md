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

### 4.2 `POST /threads/{thread_id}/runs/stream`

- 请求体（示例）：

  ```json
  {
    "assistant_id": "researchAgent",
    "input": {
      "messages": [
        {"role": "user", "content": "你好"}
      ]
    },
    "stream_mode": ["updates"],
    "config": {"configurable": {"thread_id": "..."}}
  }
  ```

- 响应：SSE 流，事件格式：

  ```text
  event: metadata
  data: {"run_id": "..."}

  event: updates
  data: {"agent": {"messages": [...]}}

  event: end
  data: {}
  ```

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
