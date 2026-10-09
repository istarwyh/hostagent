# Streaming Messages 契约对齐与反思

> 本文档记录在实现 LangGraph API 流式 messages 支持过程中的契约对齐问题、根因分析与举一反三的改进建议。

---

## 1. 问题现象

### 1.1 用户报告

在前端 UI 中发送消息后：

- AI 回复**不是逐 token 流式显示**，而是在流结束后"一次性闪现"
- 后端日志显示 `agent.astream(..., stream_mode="messages")` 确实逐 chunk 输出（共 766 个 chunk）
- curl 测试后端 `/threads/{id}/runs/stream` 也能看到多条 `event: messages`

**矛盾点**：后端明明在流式发送，前端却表现为"批量渲染"。

### 1.2 初步排查

- 后端 `execute_stream_run` 中对 `stream_mode=["messages"]` 的处理：
  - 正确选择了 `agent.astream(..., stream_mode="messages")`
  - SSE 事件类型也是 `event: messages`
- 但 `data` 字段的结构有问题：
  - 我们发的是：`["content='如果你' additional_kwargs=... id='...'", {...metadata...}]`
  - SDK 期望的是：`[{Message对象}, {MessageTupleMetadata}]`

---

## 2. SDK 契约定义

### 2.1 MessagesTupleStreamEvent

根据 `@langchain/langgraph-sdk/dist/types.stream.d.ts`：

```ts
type MessagesTupleStreamEvent = {
  event: "messages";
  data: [message: Message, config: MessageTupleMetadata];
};
```

其中 `Message` 是一个完整的对象，包含：

```ts
interface Message {
  id: string;
  type: "human" | "ai" | "tool" | "system";
  content: string | ContentBlock[];
  name?: string;
  additional_kwargs?: Record<string, any>;
  response_metadata?: Record<string, any>;
  tool_calls?: ToolCall[];
  // ... 等等
}
```

### 2.2 StreamMessagesHandler 行为

在 `@langchain/langgraph/dist/pregel/messages.js` 中：

```js
this.streamFn([
  meta[0],
  "messages",
  [message, meta[1]]  // 这里的 message 是 BaseMessage 或 AIMessageChunk 对象
]);
```

前端 SDK 的 `useStream` 在消费 `event: messages` 时，会：

1. 解析 `data[0]` 为 `Message` 对象
2. 根据 `message.id` 做增量合并（逐 token 追加到同一条消息）
3. 触发 UI 重新渲染

如果 `data[0]` 不是标准 Message 对象（例如是字符串 repr），SDK 的消息聚合逻辑会失败，导致：

- 前端无法正确追踪同一条消息的多个 chunk
- 最终只能通过 `history` 一次性重建完整消息

---

## 3. 根因分析：为什么最初没有对齐这条契约

### 3.1 设计阶段的盲区

#### 3.1.1 把"能跑通"当成"契约正确"

在最初实现时：

- 我们验证了 `/threads/{id}/runs/stream` 能返回 SSE
- 用 curl 看到了 `event: updates` / `event: messages`
- 前端也能收到事件，没有报错

**但忽略了**：

- `data` 字段的**内部结构**是否严格符合 SDK 类型定义
- 前端"能收到"不等于"能正确解析和使用"

#### 3.1.2 只看 LangGraph 文档，没看 SDK 源码

技术方案主要参考了：

- LangGraph 官方文档（关于 `agent.astream` 的 `stream_mode` 参数）
- 自己对"流式"的理解（逐 chunk yield）

**但没有系统性地**：

- 去 `@langchain/langgraph-sdk` 的 TypeScript 类型定义中，逐个确认每种 `StreamMode` 对应的 `data` 结构
- 去 SDK 的 React hooks 实现中，看 `useStream` 如何消费这些事件

结果就是：

- 我们知道要发 `event: messages`
- 但不知道 `data` 必须是 `[Message, metadata]` 而不是 `[repr字符串, metadata]`

#### 3.1.3 缺少"以 SDK 为单一真源"的设计原则

在方案中虽然提到了"兼容 SDK"，但实际执行时：

- 后端模型设计主要基于 LangGraph Python 侧的 `CheckpointTuple` / `StateSnapshot`
- 返回 JSON 结构是"看着差不多就行"，而不是"严格对照 SDK 的 TS 类型逐字段映射"

**缺少的环节**：

- 一个明确的"SDK 类型 → Python Pydantic / dict"的映射表
- 一个在设计阶段就执行的"契约校验清单"

### 3.2 测试阶段的盲区

#### 3.2.1 只做了"后端自测"，没做"SDK 集成测试"

我们的测试路径：

- 用 Python 直接调 `agent.astream`，看是否逐 chunk → ✅
- 用 curl 调 `/threads/{id}/runs/stream`，看是否有多条 SSE → ✅

**但没有**：

- 用 SDK 的 `client.runs.stream` 去调，然后检查返回的事件能否被 `useStream` 正确解析
- 在真实 UI 中观察"逐 token 流式渲染"是否生效

结果：

- 后端层面一切正常
- 但前后端集成时，UI 行为异常（一次性出现）

#### 3.2.2 E2E 测试用例设计不够"贴近真实使用"

虽然方案里提到了"启动后通过 curl 验证"，但：

- 没有明确写出"用前端 UI 发消息，观察是否逐 token 显示"这一关键场景
- 没有把"messages 流式体验"作为验收标准

---

## 4. 修复方案

### 4.1 后端改动

在 `execute_stream_run` 中：

```python
async for chunk in agent.astream(
    input_data or {},
    config=run_config,
    stream_mode=mode_for_agent,
):
    # messages 模式下，LangGraph 返回形如 (MessageLike, metadata) 的二元组，
    # 而 SDK 期望 SSE data 对应 MessagesTupleStreamEvent：
    #   data: [message: Message, config: MessageTupleMetadata]
    # 因此这里需要显式序列化第一个元素为标准 Message dict。
    if event_type == "messages" and isinstance(chunk, (list, tuple)) and len(chunk) == 2:
        message_like, meta = chunk
        message_dict = _serialize_message(message_like)
        serialized = [message_dict, meta]
    else:
        serialized = (
            serialize_state(chunk) if isinstance(chunk, dict) else chunk
        )

    yield format_sse_event(event_type, serialized)
```

关键点：

- `_serialize_message` 把 LangChain 的 `AIMessageChunk` 转成标准 dict：
  - `type: "AIMessageChunk"` / `"ai"`
  - `content: str`
  - `id: str`
  - `additional_kwargs: dict`
  - `response_metadata: dict`
  - 等等
- 这样前端 SDK 能正确解析 `data[0]` 为 `Message`，并按 `id` 聚合多个 chunk

### 4.2 验证方式

- curl 测试：

  ```bash
  curl -N -X POST "http://localhost:2024/threads/{id}/runs/stream" \
    -H "Content-Type: application/json" \
    -d '{"assistant_id":"researchAgent","input":{"messages":[...]},"stream_mode":["messages"]}'
  ```

  确认每条 `event: messages` 的 `data` 是：

  ```json
  [
    {"content": "如果你", "type": "AIMessageChunk", "id": "run--...", ...},
    {"thread_id": "...", "langgraph_step": 1, ...}
  ]
  ```

- 前端 UI 测试：
  - 发送一条较长问题
  - 观察 AI 回复是否逐 token 滚动显示
  - DevTools Network 中检查 SSE 流的 `data` 结构

---

## 5. 举一反三：其他可能存在的 SDK 契约盲区

基于这次经验，我们可以系统性地排查以下几类潜在问题：

### 5.1 其他 StreamMode 的 data 结构

除了 `messages`，SDK 还支持：

- `"updates"` → `UpdatesStreamEvent`
- `"values"` → `ValuesStreamEvent`
- `"debug"` → `DebugStreamEvent`
- `"custom"` → `CustomStreamEvent`
- `"tasks"` → `TasksStreamEvent`
- `"checkpoints"` → `CheckpointsStreamEvent`

**潜在问题**：

- 我们目前只实现了 `updates` 和 `messages`
- 如果前端请求 `stream_mode: ["values"]` 或 `["debug"]`，后端能否返回符合 SDK 期望的结构？

**建议**：

- 在 `langgraph-api-contract-checklist.md` 中，为每种 `StreamMode` 补充：
  - SDK 类型定义（来自 `types.stream.d.ts`）
  - 后端应返回的 JSON 示例
  - 契约校验脚本中的断言

### 5.2 Interrupt / Command 相关契约

SDK 支持：

- `stream.submit(null, { command: { goto: "__end__" } })`
- `stream.submit(null, { command: { resume: value } })`
- `stream.interrupt` 字段

**潜在问题**：

- 后端的 `/threads/{id}/runs/stream` 是否正确处理 `command` 参数？
- `interrupt_before` / `interrupt_after` 是否按 SDK 预期工作？
- 返回的 `ThreadState.tasks` 字段是否包含正确的 interrupt 信息？

**建议**：

- 补充 interrupt 场景的 E2E 测试：
  - 设置 `interruptBefore: ["tools"]`
  - 发送消息触发工具调用
  - 验证流是否在工具前暂停
  - 验证 `stream.interrupt` 是否非空
  - 调用 `resumeInterrupt` 继续执行

### 5.3 Subgraphs / Nested Agents

**调研结果**：当前不支持子图流式输出。

**SDK 支持情况**：
- `useStream` hook 支持 `streamSubgraphs?: boolean` 配置（默认 `false`）
- 前端代码中未启用此功能：`useChat` hook 没有设置 `streamSubgraphs: true`
- 子图事件使用特殊的 `AsSubgraph<TEvent>` 类型格式：
  ```ts
  type AsSubgraph<TEvent extends {
    id?: string;
    event: string;
    data: unknown;
  }> = {
    id?: TEvent["id"];
    event: TEvent["event"] | `${TEvent["event"]}|${string}`;
    data: TEvent["data"];
  };
  ```

**当前实现状态**：
- ❌ 前端未启用 `streamSubgraphs` 配置
- ❌ 后端未实现子图事件流式输出
- ❌ 没有 `SubgraphValuesStreamEvent`、`SubgraphUpdatesStreamEvent` 等事件处理

**潜在问题**：
- 如果 Agent 调用子图（sub-agents），这些子图的执行过程无法被前端实时观察
- 用户无法看到嵌套 Agent 的执行状态和消息流

**建议**：
- 在 `useChat` hook 中添加 `streamSubgraphs: true` 配置
- 后端 `execute_stream_run` 需要处理来自子图的事件，并按 SDK 的 `AsSubgraph` 格式包装
- 在契约文档中明确标注当前不支持子图流式输出的限制

### 5.4 Metadata / Config 字段的完整性

**调研结果**：部分支持，但可能不完整。

**SDK 期望的字段**：
- `MessageTupleMetadata` 应包含：
  - `langgraph_step`
  - `langgraph_node`
  - `langgraph_triggers`
  - `langgraph_path`
  - `langgraph_checkpoint_ns`
  - `checkpoint_ns`
  - 等等

**当前实现状态**：
- ✅ 后端确实传递 LangGraph 内部的 metadata（包括上述字段）
- ✅ 前端 SDK 能收到这些字段
- ❓ 字段完整性和命名是否与 SDK 期望完全一致？

**潜在问题**：
- LangGraph 内部 metadata 字段可能与 SDK 期望的字段有细微差异
- 某些字段缺失可能导致前端 SDK 的某些功能（如分支树构建、消息溯源）失效

**建议**：
- 在契约文档中列出 `MessageTupleMetadata` 的必需字段清单
- 在 SSE 发送前做字段完整性校验，确保关键字段存在
- 如有字段缺失，考虑在后端补充或转换

### 5.5 Checkpoint 结构的细节

**调研结果**：已实现基本支持，但 `checkpoint_map` 字段使用待确认。

**SDK 的 `Checkpoint` 类型定义**：
```ts
interface Checkpoint {
  thread_id: string;
  checkpoint_ns: string;
  checkpoint_id: string | null;
  checkpoint_map: Record<string, unknown> | null;
}
```

**当前实现状态**：
- ✅ 在 `/threads/{id}/history` 中已对齐基本结构
- ✅ 在 `/threads/{id}/runs/stream` 的 `checkpoint` 参数处理中也对齐了
- ❓ `checkpoint_map` 字段当前设置为 `null`，其语义和用途待确认

**潜在问题**：
- `checkpoint_map` 字段的用途是什么？LangGraph Cloud 是否使用它？
- 如果需要填充 `checkpoint_map`，当前实现可能不完整

**建议**：
- 查阅 LangGraph Cloud 或官方示例，确认 `checkpoint_map` 的用途
- 如暂时用不到，可以保持 `null`，但要在文档中说明
- 考虑在契约脚本中添加 checkpoint 结构校验

### 5.6 Error Handling & Retry

**调研结果**：已实现基本支持，但可能需要完善错误信息格式。

**SDK 支持**：
- `ErrorStreamEvent`：`{ event: "error", data: { error: string, message: string } }`
- `onError` callback
- 自动重连（`reconnectOnMount`）

**当前实现状态**：
- ✅ 后端在 `execute_stream_run` 的 `except` 块中发送 `event: error`
- ✅ 包含 `error` 和 `message` 字段
- ❓ 错误信息是否足够详细（是否需要 `code`, `stack` 等字段？）

**潜在问题**：
- SDK 可能期望更详细的错误信息格式
- 重连机制是否在前端正确配置和处理

**建议**：
- 在契约脚本中故意触发错误用例，验证错误事件的格式
- 检查前端的 `onError` callback 是否正确处理错误事件
- 如需要，扩展错误信息包含更多诊断字段

### 5.7 Thread / Run 生命周期管理

**调研结果**：Thread 状态管理基本实现，但可能需要完善。

**SDK 期望的状态**：
- `ThreadStatus`: `"idle"` / `"busy"` / `"interrupted"` / `"error"`
- `RunStatus`: `"pending"` / `"running"` / `"success"` / `"error"` / `"timeout"` / `"interrupted"`

**当前实现状态**：
- ✅ `/threads/{id}` 返回的 `status` 字段反映线程状态
- ❓ 是否有完整的状态机管理（idle → busy → idle 的转换）
- ❓ 流结束时是否正确更新状态
- ❓ interrupt 状态是否正确维护

**潜在问题**：
- 线程状态可能没有随 run 生命周期正确更新
- interrupt 后的状态转换逻辑可能不完整

**建议**：
- 在 checkpointer 或 run_service 中维护线程状态
- 在契约脚本中验证状态转换的正确性
- 确保 interrupt 和 resume 操作正确更新状态

### 5.8 其他 StreamMode 的 data 结构支持

**调研结果**：已实现 `updates`、`values`、`tasks`、`checkpoints`，但 `debug`、`custom`、`events` 待完善。

**SDK 支持的完整 StreamMode**：
- `"values"`: `ValuesStreamEvent<StateType>` ✅ 已实现
- `"messages"`: `MessagesTupleStreamEvent` ✅ 已实现
- `"messages-tuple"`: `MessagesTupleStreamEvent` ✅ 已实现
- `"updates"`: `UpdatesStreamEvent<UpdateType>` ✅ 已实现
- `"tasks"`: `TasksStreamEvent` ✅ 已实现
- `"checkpoints"`: `CheckpointsStreamEvent<StateType>` ✅ 已实现
- `"debug"`: `DebugStreamEvent` ❓ 待验证
- `"custom"`: `CustomStreamEvent<T>` ❓ 待验证
- `"events"`: `EventsStreamEvent` ❓ 待验证

**当前实现状态**：
- ✅ 后端已支持所有模式的 SSE 事件生成
- ✅ `_serialize_chunk_for_mode` 函数处理不同模式的序列化
- ❓ `debug`、`custom`、`events` 模式的数据结构是否完全符合 SDK 期望？

**潜在问题**：
- 前端可能从未请求过 `debug`、`custom`、`events` 模式
- 这些模式的 `data` 结构可能与 SDK 期望有细微差异

**建议**：
- 在契约脚本中添加对所有 StreamMode 的测试用例
- 验证每种模式的事件数据结构是否符合 SDK 类型定义

---

## 5.9 Interrupt / Command 相关契约

**调研结果**：基本支持，但可能不完整。

**SDK 支持的 Command**：
- `stream.submit(null, { command: { goto: "__end__" } })`
- `stream.submit(null, { command: { resume: value } })`
- `interruptBefore` / `interruptAfter` 配置
- `stream.interrupt` 字段

**当前实现状态**：
- ✅ 前端 `useChat` 中有 `interruptBefore: ["tools"]` 和 `interruptAfter` 的使用
- ✅ 后端接受 `command` 参数
- ❓ interrupt 后的状态管理和 resume 逻辑是否完整

**潜在问题**：
- interrupt 后的线程状态转换
- resume 命令的处理逻辑
- interrupt 信息的持久化

**建议**：
- 添加完整的 interrupt E2E 测试用例
- 验证 interrupt 和 resume 的状态转换
- 确保 interrupt 信息正确传递给前端

---

### 6.1 设计阶段

1. **以 SDK 类型定义为单一真源**
   - 在设计任何新接口前，先去 `@langchain/langgraph-sdk/dist/*.d.ts` 找到对应的 TS 类型
   - 逐字段列出 Python 侧的 Pydantic 模型或 dict 结构
   - 在技术方案中明确写出"类型映射表"

2. **为每个资源建立契约清单**
   - 参考 `langgraph-api-contract-checklist.md`
   - 每个 endpoint 都要有：
     - SDK 调用方式
     - 请求体 / 响应体的 JSON Schema
     - 业务约束（如"至少一个 system assistant"）

3. **在 Code Review 中检查契约对齐**
   - PR 描述中必须包含"对照了哪个 SDK 类型"
   - Reviewer 重点检查返回 JSON 的字段完整性

### 6.2 实现阶段

1. **优先实现契约校验脚本**
   - 在写业务逻辑前，先写好 `check_langgraph_contract.py` 的对应测试用例
   - 用 TDD 的方式驱动实现

2. **用 Pydantic 强制类型校验**
   - 虽然当前很多地方用 `dict` 返回，但可以考虑：
     - 定义完整的 `ThreadStateResponse(BaseModel)`
     - 在 FastAPI 路由中用 `response_model=ThreadStateResponse`
     - 这样 Pydantic 会自动校验返回 JSON 的结构

3. **日志中记录关键字段**
   - 在发送 SSE 前，log 一下 `event` 和 `data` 的类型
   - 方便排查"为什么前端收到的结构不对"

### 6.3 测试阶段

1. **集成测试必须用 SDK client**
   - 不能只用 curl / httpx
   - 要用 `@langchain/langgraph-sdk` 的 JS/TS client 去调
   - 或者用 Python 版的 `langgraph-sdk`（如果有）

2. **E2E 测试必须覆盖真实 UI 场景**
   - "发消息后逐 token 显示"
   - "刷新页面后历史还原"
   - "interrupt 后能 resume"
   - 等等

3. **在 CI 中强制执行契约校验**
   - `check_langgraph_contract.py` 作为 CI 的一个 step
   - 任何契约不匹配都应导致构建失败

### 6.4 文档阶段

1. **技术方案中补充"SDK 契约"专门章节**
   - 已在 `self-hosted-langgraph-api-guide.md` 中补充
   - 后续新功能也要同步更新

2. **维护一个"已知限制"清单**
   - 例如"当前不支持 streamSubgraphs"
   - 避免用户踩坑

---

## 7. 总结

### 7.1 这次问题的本质

- **表象**：AI 回复不是流式显示
- **直接原因**：`event: messages` 的 `data` 结构不符合 SDK 的 `MessagesTupleStreamEvent`
- **根本原因**：设计和测试阶段，没有把"SDK 类型定义"当作强约束，而是凭经验"差不多就行"

### 7.2 举一反三的价值

通过这次反思，我们识别出了至少 7 类潜在的契约盲区：

1. 其他 StreamMode 的 data 结构
2. Interrupt / Command 相关契约
3. Subgraphs / Nested Agents
4. Metadata / Config 字段完整性
5. Checkpoint 结构细节
6. Error Handling & Retry
7. Thread / Run 生命周期管理

这些都应该在后续迭代中逐一排查和补齐。

### 7.3 长期改进方向

- **Contract-First Design**：先定义契约（基于 SDK 类型），再写实现
- **Automated Contract Testing**：把契约校验作为 CI 的强制步骤
- **Living Documentation**：技术方案和契约清单要随代码演进同步更新

通过这些措施，可以系统性地避免"后端能跑，前端不能用"的集成问题。
