# CLAUDE.md

## 应用知识
- 应用如何启动、测试、查看日志: docs/best_practice/e2e_testing_guide.md
- 工具类在: backend/src/util
- 对象类在: backend/src/model
- 以前的技术方案在: docs/tech

**Monorepo Structure**: This project contains both a Python backend (deepagents library) and a Next.js frontend UI (deep-agents-ui) for interacting with deployed agents.

### Project Structure

- `backend/`: Backend Python application
  - `src/deepagents/`: Core library implementation
    - `graph.py`: Main agent creation functions (`create_deep_agent`, `async_create_deep_agent`)
    - `prompts.py`: Built-in system prompts that guide agent behavior
    - `tools.py`: Built-in tools (todos, virtual file system)
    - `sub_agent.py`: Sub-agent spawning and management
    - `state.py`: LangGraph state schema (`DeepAgentState`)
    - `interrupt.py`: Human-in-the-loop interrupt handling
    - `audit_tool_node.py`: Tool execution auditing
  - `src/service/`: Service layer with specific agent implementations
  - `src/facade/`: FastAPI endpoints exposing agents as APIs
  - `src/client/`: Client libraries (e.g., Redis client)
  - `src/test/`: Test files
- `frontend/`: Next.js frontend UI application (deep-agents-ui)
  - `src/app/`: Next.js app router pages and components
  - `src/components/`: Reusable UI components
  - `src/providers/`: React context providers (Client, Chat)
  - `src/lib/`: Utilities and configuration
  - `package.json`: Frontend dependencies and scripts
- `examples/research/`: Complete research agent example with LangGraph deployment
- `docs/`: Documentation

## Common Development Commands

### Full Stack Setup

For the complete development experience with UI:

```bash
# Terminal 1 - Backend/LangGraph API
cd examples/research
./init_langgraph.sh  # First time only
source .venv/bin/activate
langgraph dev  # Runs on http://127.0.0.1:2024

# Terminal 2 - Frontend UI
cd frontend
yarn install  # First time only
yarn dev  # Runs on http://localhost:3000
```

Configure the UI at http://localhost:3000 with:
- Deployment URL: `http://127.0.0.1:2024`
- Assistant ID: `researchAgent`

### Backend Setup and Installation

```bash
# Navigate to backend directory
cd backend

# Install dependencies using uv (recommended)
uv venv  # Create virtual environment
source .venv/bin/activate  # On macOS/Linux (optional with uv)
uv pip install -e ".[dev]"  # Install all dependencies including dev tools

# Alternative: using standard pip
# python3 -m venv .venv
# source .venv/bin/activate
# pip install -e .
```

## 开发原则
理解 程序 = 算法 + 数据结构, 编程的核心是控制数据的流动。
理解 高内聚、低耦合，代码短期最重要是能跑，长期最重要人能看。
拒绝过度设计。
拒绝 mock 测试。
拒绝一个函数超过 30行。
尽量不使用硬编码字符串，使用内聚的常量或者枚举。

## AI 工作原则
**端到端测试验证**: 完成代码开发后，你必须自己完成完整的端到端测试验证，包括：
1. 启动应用
2. 检查启动日志，确保没有错误
3. 验证相关接口功能，确保符合预期
4. 只有在所有测试通过后，才交给用户进行最终验证

不要仅完成代码编写就认为任务结束，必须自己验证代码确实能正常运行。

## 最重要的原则
有任何不清楚的，随时提问。
