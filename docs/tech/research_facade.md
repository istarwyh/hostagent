# Research Agent API

符合 LangGraph 标准的 Research Agent API，提供完整的流式、同步和异步调用能力。

## 功能特性

✅ **流式响应** - 使用 Server-Sent Events (SSE) 实时返回 agent 执行过程
✅ **状态持久化** - 使用 checkpointer 保存会话状态
✅ **多种调用方式** - 支持同步调用、事件流、状态更新流
✅ **会话管理** - 基于 thread_id 的多轮对话支持
✅ **错误处理** - 完善的异常处理和错误返回

## 快速开始

### 1. 安装依赖

```bash
pip install fastapi uvicorn httpx
```

### 2. 启动 API 服务

```bash
# 方式一：直接运行
python src/facade/research_agent_api.py

# 方式二：使用 uvicorn
uvicorn src.facade.research_agent_api:app --reload --host 0.0.0.0 --port 8000
```

### 3. 访问 API 文档

浏览器打开：`http://localhost:8000/docs`

## API 端点

### 健康检查
```http
GET /health
```

### 同步调用
```http
POST /research/invoke
Content-Type: application/json

{
  "query": "你的研究问题",
  "thread_id": "可选的会话ID"
}
```

### 事件流（推荐用于实时反馈）
```http
POST /research/stream
Content-Type: application/json

{
  "query": "你的研究问题",
  "thread_id": "可选的会话ID"
}
```

返回格式：Server-Sent Events (SSE)

### 状态更新流
```http
POST /research/stream-updates
Content-Type: application/json

{
  "query": "你的研究问题",
  "thread_id": "可选的会话ID"
}
```

### 查询会话状态
```http
GET /research/state/{thread_id}
```

## 使用示例

### Python 客户端

```python
from src.facade.research_agent_client_example import ResearchAgentClient
import asyncio

async def main():
    client = ResearchAgentClient("http://localhost:8000")

    # 同步调用
    result = await client.invoke(
        query="What are the latest AI trends?",
        thread_id="my-session-1"
    )
    print(result)

    # 流式调用
    async for event in client.stream_events(
        query="Explain quantum computing",
        thread_id="my-session-2"
    ):
        print(event)

asyncio.run(main())
```

### cURL 示例

```bash
# 同步调用
curl -X POST http://localhost:8000/research/invoke \
  -H "Content-Type: application/json" \
  -d '{"query": "What is LangGraph?"}'

# 流式调用
curl -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain agent architectures"}' \
  --no-buffer
```

### JavaScript 示例

```javascript
// 同步调用
const response = await fetch('http://localhost:8000/research/invoke', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: 'What is LangGraph?',
    thread_id: 'web-session-1'
  })
});
const result = await response.json();

// 流式调用（使用 EventSource）
const eventSource = new EventSource(
  'http://localhost:8000/research/stream?' +
  new URLSearchParams({
    query: 'Explain AI agents',
    thread_id: 'web-session-2'
  })
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);

  if (data.event === 'done') {
    eventSource.close();
  }
};
```

## 架构设计

```
┌─────────────────┐
│   Client App    │
└────────┬────────┘
         │ HTTP/SSE
         ▼
┌─────────────────────────┐
│   FastAPI Facade        │
│  (research_agent_api)   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   LangGraph Agent       │
│  (research_agent.py)    │
├─────────────────────────┤
│ • Checkpointer          │
│ • State Management      │
│ • Sub-agents            │
└─────────────────────────┘
```

## LangGraph 最佳实践

### 1. 状态持久化
使用 `MemorySaver` checkpointer 保存会话状态：
```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = base_agent.compile(checkpointer=checkpointer)
```

### 2. 会话管理
通过 `thread_id` 实现多轮对话：
```python
config = {
    "configurable": {
        "thread_id": "user-specific-id"
    }
}
```

### 3. 流式响应
使用 `astream_events` 获取实时执行过程：
```python
async for event in agent.astream_events(input, config, version="v2"):
    yield event
```

### 4. 错误处理
优雅处理 agent 执行失败：
```python
try:
    result = await agent.ainvoke(input, config)
except Exception as e:
    logger.error(f"Agent error: {e}")
    raise HTTPException(status_code=500, detail=str(e))
```

## 生产环境部署

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY ../../src/facade .

RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "src.facade.research_agent_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 性能优化
- 使用 `gunicorn` + `uvicorn workers` 提高并发
- 配置 Redis checkpointer 替代 MemorySaver
- 添加限流和缓存机制
- 启用 CORS 和认证

### 监控
- 添加 Prometheus metrics
- 集成日志聚合（ELK/Loki）
- 配置健康检查和告警

## 常见问题

**Q: 如何保存会话历史？**
A: 使用 `thread_id` 参数，同一个 thread_id 会保持会话状态。

**Q: 如何处理长时间运行的查询？**
A: 使用流式端点 `/research/stream`，可以实时获取进度。

**Q: 如何扩展到多个 agent？**
A: 参考此模板，为每个 agent 创建独立的 API 文件，或使用路由分组。

**Q: 生产环境推荐使用什么 checkpointer？**
A: 推荐使用 `PostgresSaver` 或 `RedisSaver` 替代 `MemorySaver`。

## 文件结构

```
src/facade/
├── research_agent_api.py              # API 主文件
├── research_agent_client_example.py   # 客户端示例
└── README.md                          # 本文档
```

## 参考资料

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Server-Sent Events 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)
