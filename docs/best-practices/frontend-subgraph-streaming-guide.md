# 前端子图流式支持技术分析

**版本**: 1.0  
**日期**: 2025-12-21  
**状态**: 已实现（快照模式）

## 目录

1. [概述](#概述)
2. [核心数据流](#核心数据流)
3. [数据结构](#数据结构)
4. [当前实现机制](#当前实现机制)
5. [渲染流程](#渲染流程)
6. [限制与改进方案](#限制与改进方案)

---

## 概述

前端通过 `@langchain/langgraph-sdk/react` 的 `useStream` 钩子接收后端的 SSE 流式事件，包括来自子图的事件（`event|subgraph_path` 格式）。当前实现采用**快照模式**：每次流更新时，前端重新计算并渲染当前状态的 SubAgent 卡片，中间步骤在执行完成后被 SDK 清理，导致卡片消失。

### 关键特性

- ✅ 实时接收子图事件（`event: updates|subgraph_path`）
- ✅ 流式渲染 SubAgent 的执行过程（input/output/status）
- ✅ 支持多个 SubAgent 的并列展示
- ❌ 不保留执行历史（中间步骤会消失）
- ❌ 无法回溯 SubAgent 的完整执行轨迹

---

## 核心数据流

### 1. 后端 → SDK 层

```
后端 SSE 事件流
├─ event: metadata
│  data: { run_id, thread_id }
│
├─ event: messages
│  data: [Message, MessageTupleMetadata]
│
├─ event: updates
│  data: { node_name: update_data }
│
├─ event: updates|subagent_name
│  data: { node_name: update_data }  ← 子图事件
│
└─ event: end
   data: {}
```

SDK 的 `useStream` 钩子在内部：
- 解析 `event|path` 格式，识别子图事件
- 为每条消息维护 `metadata` 和 `tool_calls` 列表
- 累积 `stream.messages` 和 `stream.values`

### 2. SDK → useChat 层

```typescript
const stream = useStream<StateType>({
  assistantId: activeAssistant?.assistant_id || "",
  client: client ?? undefined,
  reconnectOnMount: true,
  threadId: threadId ?? null,
  fetchStateHistory: true,
});

// 关键属性
stream.messages              // Message[] - 当前对话消息序列
stream.values               // StateType - 完整状态（todos, files, email, ui）
stream.getMessagesMetadata()  // 获取消息元数据（包含 tool_calls）
stream.isLoading            // boolean - 流状态
stream.interrupt            // InterruptData | null - 中断信息
```

### 3. useChat → ChatMessage 层

```typescript
// useChat 返回
return {
  stream,
  messages: stream.messages,
  isLoading: stream.isLoading,
  interrupt: stream.interrupt,
  sendMessage,
  runSingleStep,
  continueStream,
  // ...
};

// ChatMessage 接收
interface ChatMessageProps {
  message: Message;              // 单条消息
  toolCalls: ToolCall[];         // 该消息的工具调用列表
  isLoading?: boolean;
  ui?: any[];
  stream?: any;
  onResumeInterrupt?: (value: any) => void;
}
```

### 4. ChatMessage → SubAgent 渲染层

```
toolCalls: ToolCall[]
  ↓ (过滤: name === "task" && subagent_type)
subAgents: SubAgent[]
  ↓ (useMemo 计算，每次 toolCalls 变化时重新计算)
UI 渲染
  ├─ SubAgentIndicator (名称 + 展开按钮)
  └─ 展开面板
     ├─ Input (MarkdownContent)
     └─ Output (MarkdownContent)
```

---

## 数据结构

### 1. ToolCall（来自 SDK）

```typescript
export interface ToolCall {
  id: string;                                    // 工具调用唯一 ID
  name: string;                                  // "task" | 其他工具名
  args: Record<string, unknown>;                 // 调用参数
  result?: string;                               // 执行结果（可能为空）
  status: "pending" | "completed" | "error" | "interrupted";
}
```

**对于 SubAgent（task 工具调用）**：
```typescript
{
  id: "call-123",
  name: "task",
  args: {
    subagent_type: "research_agent",  // ← 子图类型标识
    prompt: "...",
    // ... 其他参数
  },
  result: "...",                       // 执行结果（逐步填充）
  status: "pending" | "active" | "completed" | "error"
}
```

### 2. SubAgent（前端转换）

```typescript
export interface SubAgent {
  id: string;                                    // toolCall.id
  name: string;                                  // toolCall.name
  subAgentName: string;                          // toolCall.args["subagent_type"]
  input: Record<string, unknown>;                // toolCall.args（当前快照）
  output?: Record<string, unknown>;              // { result: toolCall.result }
  status: "pending" | "active" | "completed" | "error";
}
```

### 3. StateType（完整应用状态）

```typescript
export type StateType = {
  messages: Message[];                           // 对话消息
  todos: TodoItem[];                             // 待办事项
  files: Record<string, string>;                 // 文件系统
  email?: {
    id?: string;
    subject?: string;
    page_content?: string;
  };
  ui?: any;                                      // 自定义 UI 组件
};
```

---

## 当前实现机制

### 1. SubAgent 识别与转换（ChatMessage.tsx）

```typescript
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
      const subagentType = (toolCall.args as Record<string, unknown>)[
        "subagent_type"
      ] as string;
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
```

**关键点**：
- 依赖 `toolCalls` 的变化触发重新计算
- 每次计算都是基于**当前快照**，不保留历史
- 一旦 SDK 从 `toolCalls` 中移除 `task` 调用，SubAgent 卡片立即消失

### 2. 展开/折叠状态管理

```typescript
const [expandedSubAgents, setExpandedSubAgents] = useState<
  Record<string, boolean>
>({});

const isSubAgentExpanded = useCallback(
  (id: string) => expandedSubAgents[id] ?? true,
  [expandedSubAgents]
);

const toggleSubAgent = useCallback((id: string) => {
  setExpandedSubAgents((prev) => ({
    ...prev,
    [id]: prev[id] === undefined ? false : !prev[id],
  }));
}, []);
```

**特点**：
- 本地状态，与 SubAgent 的执行状态独立
- 用户可以手动展开/折叠，不会影响执行流

### 3. 内容提取与渲染

```typescript
// 从 SubAgent.input/output 提取可显示的内容
export function extractSubAgentContent(data: unknown): string {
  if (typeof data === "string") {
    return data;
  }

  if (data && typeof data === "object") {
    const dataObj = data as Record<string, unknown>;

    // 优先级：description > prompt > result > JSON
    if (dataObj.description && typeof dataObj.description === "string") {
      return dataObj.description;
    }
    if (dataObj.prompt && typeof dataObj.prompt === "string") {
      return dataObj.prompt;
    }
    if (dataObj.result && typeof dataObj.result === "string") {
      return dataObj.result;
    }

    return JSON.stringify(data, null, 2);
  }

  return JSON.stringify(data, null, 2);
}
```

---

## 渲染流程

### 完整的渲染周期

```
1. 后端发送 SSE 事件
   event: updates|subagent_name
   data: { node_name: { ... } }
        ↓
2. SDK useStream 接收并处理
   - 解析 event|path
   - 更新 stream.messages 和 metadata
        ↓
3. useChat 组件重新渲染
   - 读取 stream.messages
   - 调用 stream.getMessagesMetadata() 获取 toolCalls
        ↓
4. ChatMessage 组件接收新的 toolCalls
   - 触发 useMemo 重新计算 subAgents
   - 过滤出 task 类型的 toolCall
   - 转换为 SubAgent 对象
        ↓
5. 条件渲染
   if (subAgents.length > 0) {
     subAgents.map(subAgent => (
       <SubAgentIndicator ... />
       {isExpanded && <SubAgentPanel ... />}
     ))
   }
        ↓
6. 用户看到
   - SubAgent 卡片出现
   - Input/Output 逐步填充
   - Status 从 pending → active → completed
        ↓
7. 执行完成后
   - SDK 清理 toolCalls 中的 task 调用
   - subAgents 变成空数组
   - SubAgent 卡片消失
```

### 时间轴示例

```
时间 t0: 后端发送 task toolCall (status: pending)
        前端: 显示 SubAgent 卡片，Input 可见，Output 为空

时间 t1: 后端更新 task toolCall (status: active, result: "...")
        前端: SubAgent 卡片仍显示，Output 开始填充

时间 t2: 后端更新 task toolCall (status: completed, result: "完整结果")
        前端: SubAgent 卡片仍显示，Output 完整显示

时间 t3: SDK 清理 toolCalls（移除 task 调用）
        前端: SubAgent 卡片消失 ← 这就是"闪现就消失"的原因
```

---

## 限制与改进方案

### 当前限制

1. **快照模式**：只保留当前状态，不保留历史
2. **自动清理**：SDK 在执行完成后自动清理 `toolCalls`，导致卡片消失
3. **无执行轨迹**：无法回溯 SubAgent 的完整执行过程
4. **无中间步骤记录**：SubAgent 内部的流式消息无法保留

### 改进方案 A：本地时间线（推荐）

在 `useChat` 或上层组件中维护 SubAgent 执行历史：

```typescript
// 新增类型
export interface SubAgentStep {
  timestamp: number;
  status: "pending" | "active" | "completed" | "error";
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
}

export interface SubAgentTimeline {
  id: string;
  subAgentName: string;
  steps: SubAgentStep[];
  currentStep: SubAgentStep;
}

// 在 useChat 中维护
const [subAgentTimelines, setSubAgentTimelines] = useState<
  Map<string, SubAgentTimeline>
>(new Map());

// 监听 toolCalls 变化
useEffect(() => {
  const currentSubAgents = extractSubAgents(toolCalls);

  currentSubAgents.forEach((subAgent) => {
    setSubAgentTimelines((prev) => {
      const timeline = prev.get(subAgent.id) || {
        id: subAgent.id,
        subAgentName: subAgent.subAgentName,
        steps: [],
        currentStep: null,
      };

      // 追加新的步骤（如果状态变化）
      if (
        !timeline.currentStep ||
        timeline.currentStep.status !== subAgent.status ||
        JSON.stringify(timeline.currentStep.output) !== JSON.stringify(subAgent.output)
      ) {
        timeline.steps.push({
          timestamp: Date.now(),
          status: subAgent.status,
          input: subAgent.input,
          output: subAgent.output,
        });
        timeline.currentStep = timeline.steps[timeline.steps.length - 1];
      }

      return new Map(prev).set(subAgent.id, timeline);
    });
  });
}, [toolCalls]);
```

**优点**：
- 保留完整的执行历史
- 可以显示执行进度和中间步骤
- 不依赖 SDK 的清理逻辑

**缺点**：
- 需要额外的状态管理
- 内存占用增加

### 改进方案 B：扩展 UI 数据结构

在后端的 `StateType` 中添加 SubAgent 历史：

```typescript
export type StateType = {
  messages: Message[];
  todos: TodoItem[];
  files: Record<string, string>;
  email?: { ... };
  ui?: any;

  // 新增：SubAgent 执行历史
  subagentHistory?: {
    [messageId: string]: {
      [subagentId: string]: {
        steps: SubAgentStep[];
        finalOutput: Record<string, unknown>;
      };
    };
  };
};
```

**优点**：
- 历史数据来自后端，更可靠
- 支持跨会话保留历史

**缺点**：
- 需要后端改动
- 增加网络传输量

### 改进方案 C：消息级别的 SubAgent 归档

在 `ChatMessage` 中保留已完成的 SubAgent：

```typescript
// 在 ChatMessage 中
const [archivedSubAgents, setArchivedSubAgents] = useState<SubAgent[]>([]);

useEffect(() => {
  // 当 subAgents 变空时，保存当前的 subAgents 到归档
  if (subAgents.length === 0 && archivedSubAgents.length === 0) {
    // 从某处恢复最后的 subAgents 快照
    // （需要在 subAgents 消失前保存）
  }
}, [subAgents]);

// 渲染时同时显示当前和归档的 SubAgent
return (
  <>
    {/* 当前执行的 SubAgent */}
    {subAgents.map(sa => <SubAgentPanel key={sa.id} subAgent={sa} />)}

    {/* 已完成的 SubAgent（灰显） */}
    {archivedSubAgents.map(sa => (
      <SubAgentPanel key={sa.id} subAgent={sa} isArchived />
    ))}
  </>
);
```

**优点**：
- 改动最小
- 用户可以看到完整的执行过程

**缺点**：
- 需要在 SubAgent 消失前捕获快照
- 时序复杂

---

## 推荐实现路径

### 短期（快速改进）

采用**方案 A 的简化版**：在 `useChat` 中添加一个 `subAgentHistory` 状态，记录每个 SubAgent 的最终状态。

```typescript
const [subAgentHistory, setSubAgentHistory] = useState<
  Map<string, SubAgent>
>(new Map());

// 在 stream 变化时更新
useEffect(() => {
  const currentSubAgents = extractSubAgentsFromMessages(stream.messages);

  currentSubAgents.forEach((subAgent) => {
    if (subAgent.status === "completed" || subAgent.status === "error") {
      setSubAgentHistory((prev) =>
        new Map(prev).set(subAgent.id, subAgent)
      );
    }
  });
}, [stream.messages]);
```

### 中期（完整方案）

实现**方案 A 的完整版**，维护 SubAgent 的完整时间线，支持：
- 显示执行进度
- 回溯中间步骤
- 性能优化（虚拟滚动）

### 长期（架构升级）

与后端协作，实现**方案 B**，在 `StateType` 中原生支持 SubAgent 历史，使得：
- 历史数据持久化
- 支持离线查看
- 支持跨会话对比

---

## 总结

前端当前通过 SDK 的 `useStream` 接收子图事件，采用**快照模式**实时渲染 SubAgent 的执行过程。虽然中间步骤确实在流式显示，但由于 SDK 在执行完成后清理 `toolCalls`，导致卡片消失。

要保留执行历史，需要在前端维护独立的 SubAgent 时间线，或与后端协作在 `StateType` 中原生支持历史数据。推荐先从简化版的本地时间线开始，逐步演进到完整的架构方案。
