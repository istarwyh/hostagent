---
trigger: always_on
---
# CLAUDE.md

项目开发指南和 AI 辅助编程最佳实践。

## 应用架构

**Monorepo 结构**：全栈应用，包含 Python 后端（deepagents 库 + 领域服务）和 Next.js 前端 UI。

### 核心概念

- **工具类**：`backend/src/util` - 通用工具函数
- **数据模型**：`backend/src/model` - Pydantic 模型定义
- **技术方案文档**：`docs/tech` - 架构决策和实现方案

### 目录结构

```
backend/                          # Python 后端
├── src/
│   ├── deepagents/              # 核心 Agent 框架
│   │   ├── graph.py             # Agent 创建函数（create_deep_agent）
│   │   ├── prompts.py           # 内置系统提示词
│   │   ├── tools.py             # 内置工具（todos, 虚拟文件系统）
│   │   ├── sub_agent.py         # 子 Agent 管理
│   │   ├── state.py             # LangGraph 状态模式（DeepAgentState）
│   │   ├── interrupt.py         # 人机交互中断处理
│   │   └── audit_tool_node.py   # 工具执行审计
│   ├── app/                     # 应用层（Agent 注册和生命周期管理）
│   │   ├── agent_registry.py   # Agent 配置注册表
│   │   ├── agent_pool.py        # Agent 实例池
│   │   ├── agent_config.py      # Agent 配置模型
│   │   └── agent_initializer.py # 启动初始化
│   ├── service/                 # 领域服务层（具体 Agent 实现）
│   │   └── research_agent/      # 研究型 Agent
│   ├── facade/                  # API 网关层（FastAPI 端点）
│   │   └── langgraph_api/       # LangGraph SDK 兼容 API
│   ├── repository/              # 数据持久层（checkpointer 等）
│   ├── client/                  # 外部客户端（Redis 等）
│   ├── model/                   # 数据模型（Pydantic）
│   └── util/                    # 通用工具
│
frontend/                         # Next.js 前端
├── src/
│   ├── app/                     # App Router 页面
│   ├── components/              # 可复用组件
│   ├── providers/               # React Context（Client, Chat）
│   └── lib/                     # 工具和配置
│
docs/                            # 文档
└── tech/                        # 技术方案和架构决策
```

### 架构原则

- **分层清晰**：
  - `facade` → `app` → `service` → `deepagents` → `repository`
  - 依赖方向单向，不反向依赖
- **配置与实例分离**：
  - `agent_registry` 管理配置（what to create）
  - `agent_pool` 管理实例（when to create）
- **契约先行**：
  - API 实现必须严格遵循 SDK 类型定义
  - 数据结构对齐优先于功能实现

## 常用开发命令

### 快速启动

```bash
# 开发环境一键启动（推荐）
./conf/start_dev.sh

# 或者分别启动后端和前端
```

### 后端开发

```bash
cd backend

# 安装依赖（使用 uv，推荐）
uv venv                          # 创建虚拟环境
source .venv/bin/activate        # 激活虚拟环境（macOS/Linux）
uv pip install -e ".[dev]"       # 安装开发依赖

# 启动后端 API（开发模式，热重载）
uvicorn src.facade.langgraph_api.main:app --reload --port 2024

# 运行测试
pytest

# 代码格式化和检查（pre-commit）
pre-commit run --all-files
```

### 前端开发

```bash
cd frontend

# 安装依赖
yarn install

# 启动开发服务器
yarn dev                         # 运行在 http://localhost:3000

# 构建生产版本
yarn build
```

### 配置前端连接后端

访问 http://localhost:3000，配置：
- **Deployment URL**: `http://localhost:2024`
- **Assistant ID**: `researchAgent`

### 查看日志

```bash
# 后端日志（如果后台运行）
tail -f /tmp/backend.log

# 前端日志（终端输出）
# 直接在运行 yarn dev 的终端查看
```

## 开发原则

### 核心理念

- **程序 = 算法 + 数据结构**：编程的核心是控制数据的流动
- **高内聚、低耦合**：
  - 短期：代码能跑
  - 长期：人能看懂
- **单一数据源原则（Single Source of Truth）**：
  - 例：`agent_registry` 是所有 Agent 配置的唯一数据源
  - 例：SDK 类型定义是 API 契约的唯一数据源
  - 避免在多处维护相同信息

### 代码质量标准

- **拒绝硬编码**：使用常量、枚举或配置文件
- **拒绝过度设计**：只解决当前问题，不预设未来需求
- **拒绝 mock 测试**：优先集成测试和端到端测试
- **函数长度限制**：单个函数不超过 30 行
- **命名清晰**：函数名、变量名要自解释，减少注释需求

## AI 工作原则

### 必须完成端到端验证

代码开发后，必须自己完成完整验证，包括：

1. **启动应用**：使用实际启动命令，不能只写代码
2. **检查启动日志**：确保无错误、无警告
3. **验证接口功能**：
   - 使用 curl 或实际前端测试 API
   - 验证返回数据结构符合预期
   - 测试正常流程和异常流程
4. **确认集成正确**：检查日志中的相关信息
5. **只有全部通过后才交给用户最终验证**

**禁止行为**：
- 写完代码就认为任务完成
- 依赖用户进行基本测试
- 假设代码能运行而不实际验证

### 工作流程建议

1. **理解需求**：先提问澄清，避免返工
2. **使用 TodoWrite**：分解任务，跟踪进度
3. **先读后写**：修改代码前必须先读取文件
4. **分步验证**：每完成一个功能点就验证
5. **查阅文档**：遇到不确定的 API 契约，查看 `docs/tech` 下的文档

## 最重要的原则

**有任何不清楚的，随时提问。**

不确定时宁愿多问一句，也不要基于假设实现错误的方案。
