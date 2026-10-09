# 前端 Subgraph 流式渲染完整技术分析

**版本**: 1.0  
**日期**: 2025-12-22  
**状态**: 已实现

---

## 目录

1. [核心发现](#核心发现)
2. [数据流完整链路](#数据流完整链路)
3. [关键数据结构](#关键数据结构)
4. [SDK 内部机制](#sdk-内部机制)
5. [前端渲染逻辑](#前端渲染逻辑)
6. [SubAgent 的生命周期](#subagent-的生命周期)
7. [为什么中间步骤会消失](#为什么中间步骤会消失)
8. [完整示例](#完整示例)

---

## 核心发现

### 关键事实

当前前端**已经支持**看到 SubAgent 的中间执行步骤，但这些步骤在渲染完成后会消失，只留下 SubAgent 卡片。

**数据流路径**：
```
后端 SSE 流
  ↓ event: messages|tools (SubAgent 中间步骤)
  ↓ event: updates|tools (SubAgent 节点更新)
  ↓ event: values (完整状态快照)
SDK StreamManager
  ↓ 实时累积 messages
  ↓ 实时更新 values
前端 ChatInterface
  ↓ 从 messages 提取 toolCalls
  ↓ 渲染 SubAgent 中间步骤
  ↓ values 事件覆盖 messages
  ↓ 只留下 SubAgent 卡片
```

---

## 数据流完整链路

### 1. 后端 SSE 事件序列

当 SubAgent 执行时，后端会发送以下事件序列：

```
event: metadata
data: {"run_id": "...", "thread_id": "..."}

# 根图调用 task 工具（启动 SubAgent）
event: messages
data: [
  {
    "type": "ai",
    "content": "",
    "tool_calls": [{
      "id": "call_123",
      "name": "task",
      "args": {
        "subagent_type": "research_agent",
        "description": "Search for information"
      }
    }]
  },
  {"thread_id": "...", "langgraph_step": 1, ...}
]

# SubAgent 内部的流式消息（关键！）
event: messages|tools
data: [
  {
    "type": "ai",
    "content": "I'll search for that information...",
    "id": "msg_sub_1"
  },
  {"thread_id": "...", "langgraph_step": 2, "langgraph_node": "research_node", ...}
]

event: messages|tools
data: [
  {
    "type": "AIMessageChunk",
    "content": "Based",
    "id": "msg_sub_1"
  },
  {"thread_id": "...", "langgraph_step": 2, ...}
]

event: messages|tools
data: [
  {
    "type": "AIMessageChunk",
    "content": " on",
    "id": "msg_sub_1"
  },
  {"thread_id": "...", "langgraph_step": 2, ...}
]

# SubAgent 内部的工具调用
event: messages|tools
data: [
  {
    "type": "ai",
    "content": "",
    "tool_calls": [{
      "id": "call_456",
      "name": "web_search",
      "args": {"query": "..."}
    }],
    "id": "msg_sub_2"
  },
  {"thread_id": "...", "langgraph_step": 3, ...}
]

# SubAgent 工具执行结果
event: messages|tools
data: [
  {
    "type": "tool",
    "content": "Search results: ...",
    "tool_call_id": "call_456",
    "id": "msg_sub_3"
  },
  {"thread_id": "...", "langgraph_step": 4, ...}
]

# SubAgent 完成后的 tool 消息（返回给根图）
event: messages
data: [
  {
    "type": "tool",
    "content": "Research completed. Found: ...",
    "tool_call_id": "call_123",
    "id": "msg_tool_result"
  },
  {"thread_id": "...", "langgraph_step": 5, ...}
]

# 完整状态快照（覆盖之前的流式消息）
event: values
data: {
  "messages": [
    {"type": "human", "content": "user query", "id": "msg_0"},
    {
      "type": "ai",
      "content": "",
      "tool_calls": [{
        "id": "call_123",
        "name": "task",
        "args": {"subagent_type": "research_agent", ...}
      }],
      "id": "msg_1"
    },
    {
      "type": "tool",
      "content": "Research completed. Found: ...",
      "tool_call_id": "call_123",
      "id": "msg_tool_result"
    }
  ],
  "todos": [...],
  "files": {...}
}

event: end
data: {}
```

**关键观察**：
- `event: messages|tools` - SubAgent 内部的流式消息（**会实时渲染**）
- `event: values` - 完整状态快照（**会覆盖之前的流式消息**）

---

### 2. SDK StreamManager 处理逻辑

**文件**: `@langchain/langgraph-sdk/dist/ui/manager.js`

```javascript
// 第 78-122 行：处理每个 SSE 事件
for await (const { event, data } of run) {
  // 提取 subgraph 路径
  const namespace = event.includes("|")
    ? event.split("|").slice(1)
    : void 0;

  // 处理 messages 事件（包括 messages|tools）
  if (this.matchEventType("messages", event, data)) {
    const [serialized, metadata] = data;
    const messageId = this.messages.add(serialized, metadata);

    // 实时更新 stream.messages
    this.setStreamValues((streamValues) => {
      const values = {
        ...options.initialValues,
        ...streamValues
      };
      const messages = options.getMessages(values).slice();
      const { chunk, index } = this.messages.get(messageId, messages.length) ?? {};

      if (!chunk || index == null) return values;

      if (chunk.getType() === "remove")
        messages.splice(index, 1);
      else
        messages[index] = toMessageDict(chunk);

      return options.setMessages(values, messages);
    });
  }

  // 处理 values 事件（覆盖之前的流式消息）
  if (event === "values") {
    if ("__interrupt__" in data) {
      this.setStreamValues((prev) => ({
        ...prev,
        ...data
      }));
    } else {
      this.setStreamValues(data);  // ← 直接覆盖！
    }
  }
}
```

**关键机制**：
1. **`matchEventType("messages", event, data)`**：
   - 匹配 `event === "messages"` 或 `event.startsWith("messages|")`
   - 所以 `messages|tools` 会被处理

2. **`MessageTupleManager.add()`**：
   - 累积消息 chunks（支持 token-by-token 流式）
   - 为每个消息分配唯一 ID

3. **`setStreamValues()`**：
   - 更新 `stream.values` 和 `stream.messages`
   - `values` 事件会**直接覆盖**之前的流式消息

---

### 3. 前端消费逻辑

**文件**: `frontend/src/app/components/ChatInterface.tsx`

```typescript
// 第 114-216 行：处理消息和工具调用
const processedMessages = useMemo(() => {
  const messageMap = new Map<
    string,
    { message: Message; toolCalls: ToolCall[] }
  >();

  // 遍历所有消息
  messages.forEach((message: Message) => {
    if (message.type === "ai") {
      // 提取工具调用
      const toolCallsInMessage = [];
      if (message.additional_kwargs?.tool_calls) {
        toolCallsInMessage.push(...message.additional_kwargs.tool_calls);
      } else if (message.tool_calls) {
        toolCallsInMessage.push(...message.tool_calls);
      }

      // 转换为 ToolCall 对象
      const toolCallsWithStatus = toolCallsInMessage.map((toolCall) => ({
        id: toolCall.id || `tool-${Math.random()}`,
        name: toolCall.function?.name || toolCall.name || "unknown",
        args: toolCall.function?.arguments || toolCall.args || {},
        status: interrupt ? "interrupted" : "pending",
      }));

      messageMap.set(message.id!, {
        message,
        toolCalls: toolCallsWithStatus,
      });
    } else if (message.type === "tool") {
      // 更新工具调用结果
      const toolCallId = message.tool_call_id;
      for (const [, data] of messageMap.entries()) {
        const toolCallIndex = data.toolCalls.findIndex(
          (tc) => tc.id === toolCallId
        );
        if (toolCallIndex !== -1) {
          data.toolCalls[toolCallIndex] = {
            ...data.toolCalls[toolCallIndex],
            status: "completed",
            result: extractStringFromMessageContent(message),
          };
          break;
        }
      }
    }
  });

  return Array.from(messageMap.values());
}, [messages, interrupt]);
```

**关键逻辑**：
- 从 `stream.messages` 提取所有 AI 消息的 `tool_calls`
- 从 `tool` 类型消息提取工具执行结果
- 构建 `ToolCall[]` 数组传递给 `ChatMessage` 组件

---

### 4. SubAgent 识别与渲染

**文件**: `frontend/src/app/components/ChatMessage.tsx`

```typescript
// 第 48-71 行：识别 SubAgent
const subAgents = useMemo(() => {
  return toolCalls
    .filter((toolCall: ToolCall) => {
      return (
        toolCall.name === "task" &&
        toolCall.args["subagent_type"] &&
        toolCall.args["subagent_type"] !== "" &&
        toolCall.args["subagent_type"] !== null
      );
    })
    .map((toolCall: ToolCall) => {
      const subagentType = toolCall.args["subagent_type"] as string;
      return {
        id: toolCall.id,
        name: toolCall.name,
        subAgentName: subagentType,
        input: toolCall.args,
        output: toolCall.result ? { result: toolCall.result } : undefined,
        status: toolCall.status,
      } as SubAgent;
    });
}, [toolCalls]);

// 第 150-193 行：渲染 SubAgent 卡片
{!isUser && subAgents.length > 0 && (
  <div className="flex w-fit max-w-full flex-col gap-4">
    {subAgents.map((subAgent) => (
      <div key={subAgent.id} className="flex w-full flex-col gap-2">
        <SubAgentIndicator
          subAgent={subAgent}
          onClick={() => toggleSubAgent(subAgent.id)}
          isExpanded={isSubAgentExpanded(subAgent.id)}
        />
        {isSubAgentExpanded(subAgent.id) && (
          <div className="w-full max-w-full">
            <div className="bg-surface border-border-light rounded-md border p-4">
              <h4>Input</h4>
              <MarkdownContent
                content={extractSubAgentContent(subAgent.input)}
              />

              {subAgent.output && (
                <>
                  <h4>Output</h4>
                  <MarkdownContent
                    content={extractSubAgentContent(subAgent.output)}
                  />
                </>
              )}
            </div>
          </div>
        )}
      </div>
    ))}
  </div>
)}
```

**识别逻辑**：
- 过滤 `toolCall.name === "task"` 且有 `subagent_type` 参数
- 从 `toolCall.args` 提取 SubAgent 输入
- 从 `toolCall.result` 提取 SubAgent 输出

---

## 关键数据结构

### 1. Message 类型

```typescript
interface Message {
  id?: string;
  type: "human" | "ai" | "tool" | "system";
  content: string | ContentBlock[];
  name?: string;
  additional_kwargs?: {
    tool_calls?: Array<{
      id?: string;
      function?: { name?: string; arguments?: unknown };
      name?: string;
      type?: string;
    }>;
  };
  tool_calls?: Array<{
    id?: string;
    name?: string;
    args?: unknown;
  }>;
  tool_call_id?: string;  // 用于 tool 类型消息
  response_metadata?: Record<string, any>;
}
```

### 2. ToolCall 类型

```typescript
interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: "pending" | "completed" | "error" | "interrupted";
}
```

### 3. SubAgent 类型

```typescript
interface SubAgent {
  id: string;
  name: string;
  subAgentName: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: "pending" | "active" | "completed" | "error";
}
```

### 4. StateType 类型

```typescript
type StateType = {
  messages: Message[];
  todos: TodoItem[];
  files: Record<string, string>;
  email?: {
    id?: string;
    subject?: string;
    page_content?: string;
  };
  ui?: any;
};
```

---

## SDK 内部机制

### 1. MessageTupleManager

**文件**: `@langchain/langgraph-sdk/dist/ui/messages.js`

```javascript
class MessageTupleManager {
  chunks = {};

  add(serialized, metadata) {
    // 规范化消息类型
    if (serialized.type.endsWith("MessageChunk")) {
      serialized.type = serialized.type.slice(0, -12).toLowerCase();
    }

    const message = tryCoerceMessageLikeToMessage(serialized);
    const chunk = tryConvertToChunk(message);
    const { id } = chunk ?? message;

    if (!id) {
      console.warn("No message ID found for chunk, ignoring in state", serialized);
      return null;
    }

    // 累积 chunks（支持 token-by-token 流式）
    this.chunks[id] ??= {};
    this.chunks[id].metadata = metadata ?? this.chunks[id].metadata;

    if (chunk) {
      const prev = this.chunks[id].chunk;
      this.chunks[id].chunk =
        (isBaseMessageChunk(prev) ? prev : null)?.concat(chunk) ?? chunk;
    } else {
      this.chunks[id].chunk = message;
    }

    return id;
  }

  get(id, defaultIndex) {
    if (id == null || this.chunks[id] == null) return null;
    if (defaultIndex != null) this.chunks[id].index ??= defaultIndex;
    return this.chunks[id];
  }

  clear() {
    this.chunks = {};
  }
}
```

**关键特性**：
- 为每个消息维护独立的 chunk 累积器
- 支持 `AIMessageChunk` 的 `concat()` 操作（token-by-token 流式）
- 自动分配消息索引（用于插入到 `messages` 数组）

### 2. StreamManager 事件匹配

```javascript
matchEventType = (expected, actual, _data) => {
  return expected === actual || actual.startsWith(`${expected}|`);
};
```

**匹配规则**：
- `matchEventType("messages", "messages", data)` → `true`
- `matchEventType("messages", "messages|tools", data)` → `true`
- `matchEventType("messages", "updates", data)` → `false`

**这意味着**：
- `messages|tools` 事件会被当作 `messages` 事件处理
- SubAgent 内部的流式消息会实时累积到 `stream.messages`

---

## SubAgent 的生命周期

### 阶段 1: 根图调用 task 工具

```
event: messages
data: [
  {
    "type": "ai",
    "tool_calls": [{
      "id": "call_123",
      "name": "task",
      "args": {"subagent_type": "research_agent", ...}
    }]
  },
  {...}
]
```

**前端状态**：
- `stream.messages` 包含一条 AI 消息，带有 `task` 工具调用
- `ChatMessage` 组件识别出 SubAgent，渲染 `SubAgentIndicator`
- SubAgent 状态：`pending`

---

### 阶段 2: SubAgent 内部执行（流式消息）

```
event: messages|tools
data: [{"type": "ai", "content": "I'll search...", "id": "msg_sub_1"}, {...}]

event: messages|tools
data: [{"type": "AIMessageChunk", "content": "Based", "id": "msg_sub_1"}, {...}]

event: messages|tools
data: [{"type": "AIMessageChunk", "content": " on", "id": "msg_sub_1"}, {...}]
```

**前端状态**：
- SDK 的 `MessageTupleManager` 累积 `msg_sub_1` 的 chunks
- `stream.messages` 实时更新，包含 SubAgent 内部的消息
- `ChatInterface` 渲染这些消息（**用户可以看到 SubAgent 的中间步骤**）
- SubAgent 状态：`active`

**用户看到的**：
```
[AI Message] (SubAgent 内部)
I'll search for that information...Based on the search results...
```

---

### 阶段 3: SubAgent 内部工具调用

```
event: messages|tools
data: [
  {
    "type": "ai",
    "tool_calls": [{"id": "call_456", "name": "web_search", ...}],
    "id": "msg_sub_2"
  },
  {...}
]

event: messages|tools
data: [
  {
    "type": "tool",
    "content": "Search results: ...",
    "tool_call_id": "call_456",
    "id": "msg_sub_3"
  },
  {...}
]
```

**前端状态**：
- `stream.messages` 包含 SubAgent 内部的工具调用和结果
- `ChatInterface` 渲染 `ToolCallBox`（**用户可以看到 SubAgent 调用的工具**）

**用户看到的**：
```
[AI Message] (SubAgent 内部)
I'll search for that information...

[Tool Call: web_search]
Query: "..."
Result: "Search results: ..."
```

---

### 阶段 4: SubAgent 完成，返回结果

```
event: messages
data: [
  {
    "type": "tool",
    "content": "Research completed. Found: ...",
    "tool_call_id": "call_123",
    "id": "msg_tool_result"
  },
  {...}
]
```

**前端状态**：
- `stream.messages` 添加 `tool` 类型消息
- `ChatInterface` 更新 `call_123` 的状态为 `completed`
- SubAgent 的 `output` 被填充
- SubAgent 状态：`completed`

---

### 阶段 5: values 事件覆盖流式消息

```
event: values
data: {
  "messages": [
    {"type": "human", "content": "user query", "id": "msg_0"},
    {
      "type": "ai",
      "tool_calls": [{
        "id": "call_123",
        "name": "task",
        "args": {"subagent_type": "research_agent", ...}
      }],
      "id": "msg_1"
    },
    {
      "type": "tool",
      "content": "Research completed. Found: ...",
      "tool_call_id": "call_123",
      "id": "msg_tool_result"
    }
  ],
  ...
}
```

**前端状态**：
- SDK 的 `setStreamValues(data)` **直接覆盖** `stream.values`
- `stream.messages` 被替换为 `values.messages`（**不包含 SubAgent 内部的流式消息**）
- `ChatInterface` 重新渲染，只显示最终状态
- SubAgent 的中间步骤消失，只留下 SubAgent 卡片

**用户看到的**：
```
[SubAgent: research_agent]
Input: "Search for information"
Output: "Research completed. Found: ..."
```

---

## 为什么中间步骤会消失

### 根本原因

SDK 的 `StreamManager` 在处理 `values` 事件时，会**直接覆盖**之前累积的流式消息：

```javascript
// manager.js 第 98-102 行
if (event === "values") {
  if ("__interrupt__" in data) {
    this.setStreamValues((prev) => ({
      ...prev,
      ...data
    }));
  } else {
    this.setStreamValues(data);  // ← 直接覆盖，不合并！
  }
}
```

### 设计意图

这是 LangGraph SDK 的**有意设计**：
1. **流式阶段**：`messages|subgraph_path` 事件提供实时反馈
2. **快照阶段**：`values` 事件提供最终状态（用于持久化和历史回放）

**优点**：
- 避免状态不一致（流式消息 vs 最终状态）
- 简化历史记录（只保存最终状态）
- 减少内存占用（不需要保留所有中间消息）

**缺点**：
- 用户无法回看 SubAgent 的中间步骤
- 调试困难（无法看到 SubAgent 内部的详细执行过程）

---

## 完整示例

### 用户视角的时间线

**T0: 用户发送消息**
```
User: "Research the latest AI trends"
```

**T1: 根图决定调用 SubAgent**
```
[AI Message]
(empty content, tool_calls: [task])

[SubAgent: research_agent] (pending)
Input: "Research the latest AI trends"
```

**T2-T5: SubAgent 执行中（流式渲染）**
```
[AI Message]
(empty content, tool_calls: [task])

[AI Message] (SubAgent 内部) ← 实时流式渲染
I'll search for the latest AI trends...

[Tool Call: web_search] ← 实时显示
Query: "latest AI trends 2025"
Result: "Found 10 articles..."

[AI Message] (SubAgent 内部) ← 继续流式渲染
Based on the search results, the top AI trends are...
```

**T6: values 事件到达（覆盖流式消息）**
```
[AI Message]
(empty content, tool_calls: [task])

[SubAgent: research_agent] (completed) ← 只剩下卡片
Input: "Research the latest AI trends"
Output: "Top AI trends: 1. Generative AI, 2. Multimodal models..."
```

---

## 数据结构对比

### 流式阶段的 stream.messages

```typescript
[
  {
    id: "msg_0",
    type: "human",
    content: "Research the latest AI trends"
  },
  {
    id: "msg_1",
    type: "ai",
    content: "",
    tool_calls: [{
      id: "call_123",
      name: "task",
      args: { subagent_type: "research_agent", ... }
    }]
  },
  // SubAgent 内部的流式消息（来自 messages|tools 事件）
  {
    id: "msg_sub_1",
    type: "ai",
    content: "I'll search for the latest AI trends..."
  },
  {
    id: "msg_sub_2",
    type: "ai",
    content: "",
    tool_calls: [{
      id: "call_456",
      name: "web_search",
      args: { query: "latest AI trends 2025" }
    }]
  },
  {
    id: "msg_sub_3",
    type: "tool",
    content: "Found 10 articles...",
    tool_call_id: "call_456"
  },
  {
    id: "msg_sub_4",
    type: "ai",
    content: "Based on the search results, the top AI trends are..."
  },
  // SubAgent 返回给根图的结果
  {
    id: "msg_tool_result",
    type: "tool",
    content: "Top AI trends: 1. Generative AI, 2. Multimodal models...",
    tool_call_id: "call_123"
  }
]
```

### 快照阶段的 stream.messages（values 事件后）

```typescript
[
  {
    id: "msg_0",
    type: "human",
    content: "Research the latest AI trends"
  },
  {
    id: "msg_1",
    type: "ai",
    content: "",
    tool_calls: [{
      id: "call_123",
      name: "task",
      args: { subagent_type: "research_agent", ... }
    }]
  },
  // SubAgent 内部的流式消息全部消失！
  {
    id: "msg_tool_result",
    type: "tool",
    content: "Top AI trends: 1. Generative AI, 2. Multimodal models...",
    tool_call_id: "call_123"
  }
]
```

---

## 总结

### 当前实现的能力

✅ **已支持**：
1. SubAgent 的中间执行步骤**可以实时渲染**（通过 `messages|tools` 事件）
2. SubAgent 内部的工具调用**可以实时显示**（通过 `ToolCallBox`）
3. SubAgent 的流式消息**支持 token-by-token 渲染**（通过 `MessageTupleManager`）
4. SubAgent 的最终结果**会保留在 SubAgent 卡片中**（通过 `values` 事件）

### 当前实现的限制

❌ **不支持**：
1. SubAgent 的中间步骤**无法回看**（被 `values` 事件覆盖）
2. 无法在 SubAgent 卡片中**展示执行历史**
3. 无法**持久化** SubAgent 的中间步骤到历史记录

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│  后端 SSE 流                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ event: messages (根图调用 task)                     │   │
│  │ event: messages|tools (SubAgent 流式消息) ← 实时!   │   │
│  │ event: messages|tools (SubAgent 工具调用) ← 实时!   │   │
│  │ event: messages (SubAgent 返回结果)                 │   │
│  │ event: values (完整状态快照) ← 覆盖!                │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  SDK StreamManager                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ matchEventType("messages", "messages|tools") → true │   │
│  │ MessageTupleManager.add() → 累积 chunks            │   │
│  │ setStreamValues() → 更新 stream.messages           │   │
│  │ values 事件 → setStreamValues(data) ← 直接覆盖!    │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  useChat Hook                                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ stream.messages (实时更新)                          │   │
│  │ stream.values (被 values 事件覆盖)                  │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  ChatInterface                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ processedMessages = useMemo(() => {                 │   │
│  │   messages.forEach((message) => {                   │   │
│  │     if (message.type === "ai") {                    │   │
│  │       提取 tool_calls → ToolCall[]                  │   │
│  │     }                                                │   │
│  │     if (message.type === "tool") {                  │   │
│  │       更新 toolCall.result                          │   │
│  │     }                                                │   │
│  │   })                                                 │   │
│  │ }, [messages])                                      │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  ChatMessage                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ const subAgents = useMemo(() => {                   │   │
│  │   return toolCalls                                   │   │
│  │     .filter(tc => tc.name === "task")               │   │
│  │     .map(tc => ({                                    │   │
│  │       subAgentName: tc.args.subagent_type,          │   │
│  │       input: tc.args,                                │   │
│  │       output: tc.result,                             │   │
│  │       status: tc.status                              │   │
│  │     }))                                              │   │
│  │ }, [toolCalls])                                     │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  SubAgent 渲染                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 流式阶段（messages|tools 事件）：                   │   │
│  │   - 显示 SubAgent 内部的 AI 消息                    │   │
│  │   - 显示 SubAgent 内部的工具调用                    │   │
│  │   - 支持 token-by-token 流式渲染                    │   │
│  │                                                      │   │
│  │ 快照阶段（values 事件后）：                         │   │
│  │   - 只显示 SubAgent 卡片                            │   │
│  │   - Input: tc.args                                  │   │
│  │   - Output: tc.result                               │   │
│  │   - 中间步骤消失                                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 参考资料

- 后端实现：`backend/src/service/langgraph_api/run_service.py`
- SDK 源码：`@langchain/langgraph-sdk/dist/ui/manager.js`
- 前端组件：`frontend/src/app/components/ChatInterface.tsx`
- 前端组件：`frontend/src/app/components/ChatMessage.tsx`
- 最佳实践：`docs/best-practices/streaming-events-design.md`
