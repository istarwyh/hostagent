# Python 项目日志查看与测试指南

## 目录
- [日志系统概述](#日志系统概述)
- [日志配置](#日志配置)
- [查看日志](#查看日志)
- [测试指南](#测试指南)
- [调试技巧](#调试技巧)
- [最佳实践](#最佳实践)

## 日志系统概述

本项目使用统一的日志配置工具 (`backend/src/util/logger.py`)，提供：
- **自动文件输出**：日志自动保存到 `logs/` 目录
- **多种日志文件**：app.log（全部）、error.log（错误）、daily.log（按日期）
- **结构化日志**：JSON 格式日志便于 AI 自动分析
- **自动轮转**：按大小和日期自动轮转，无需手动清理
- **统一格式**：所有模块使用一致的日志格式

日志主要用于：
- 追踪应用程序运行状态
- 调试和排查问题
- 监控 Agent 执行流程
- 记录工具调用和 API 请求
- **便于 AI 自动调试和查询**

### 日志文件位置

所有日志文件统一存储在项目根目录的 `logs/` 目录下：

```
logs/
├── app.log              # 所有日志（按大小轮转，10MB）
├── error.log            # 仅错误日志
├── daily.log            # 按日期轮转的日志
├── daily.log.2024-12-13 # 历史日志
├── structured/          # JSON 格式日志（便于 AI 解析）
│   └── structured.jsonl
└── README.md            # 日志说明文档
```

### 主要日志输出位置

代码中的日志记录：
- `backend/src/deepagents/graph.py` - Agent 构建过程
- `backend/src/facade/research_agent_api.py` - API 请求和错误
- `backend/src/service/research_agent/research_agent.py` - Research Agent 初始化
- `backend/src/util/logger.py` - 统一日志配置工具

## 日志配置

### 推荐配置（使用统一日志工具）

**新代码请使用此方式**，日志会自动输出到 `logs/` 目录：

```python
from src.util.logger import setup_logger

# 创建 logger（自动输出到文件和控制台）
logger = setup_logger(__name__)

# 使用 logger
logger.info("应用启动")
logger.error("发生错误", exc_info=True)
```

这种方式提供：
- 自动输出到 `logs/app.log`、`logs/error.log`、`logs/daily.log`
- 控制台同步显示
- 统一的日志格式
- 自动轮转，无需手动清理

### 自定义配置

根据需要自定义日志行为：

```python
from src.util.logger import setup_logger
import logging
from pathlib import Path

# 自定义日志目录
logger = setup_logger(
    __name__,
    log_dir=Path("custom_logs"),  # 自定义目录
    level=logging.DEBUG,           # 日志级别
    detailed=True                  # 详细格式（包含文件名和行号）
)

# 仅输出到控制台（不写文件）
logger = setup_logger(__name__, file_output=False)

# 仅输出到文件（不显示在控制台）
logger = setup_logger(__name__, console=False)
```

### 全局初始化（可选）

在应用启动时配置全局日志：

```python
from src.util.logger import init_logging
import logging

# 在 main 函数或应用入口调用一次
init_logging(
    log_dir=Path("logs"),
    level=logging.INFO,
    detailed=False
)

# 之后所有模块都使用统一配置
import logging
logger = logging.getLogger(__name__)
logger.info("使用全局配置")
```

### 结构化日志（便于 AI 解析）

输出 JSON 格式日志，方便程序化分析：

```python
from src.util.logger import StructuredLogger

logger = StructuredLogger(__name__)

# 记录带上下文的结构化日志
logger.log(
    "INFO",
    "用户登录",
    user_id="12345",
    ip="192.168.1.1",
    action="login"
)

# 输出到 logs/structured/structured.jsonl
# {"timestamp": "2024-12-14T15:30:45", "level": "INFO", ...}
```

### 旧的配置方式（兼容）

如果需要使用标准 logging 模块：

```python
import logging

# 配置日志级别
logging.basicConfig(level=logging.INFO)

# 创建模块级别的 logger
logger = logging.getLogger(__name__)
```

**注意**：旧方式不会自动输出到文件，推荐使用 `setup_logger`。

### 日志级别说明

```python
# 从低到高的日志级别
logging.DEBUG     # 详细的调试信息
logging.INFO      # 一般信息（默认级别）
logging.WARNING   # 警告信息
logging.ERROR     # 错误信息
logging.CRITICAL  # 严重错误
```

### 自定义日志配置

如需更详细的日志输出，可以在项目入口处配置：

```python
import logging

# 配置更详细的日志格式
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 级别
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

示例输出：
```
2024-12-14 15:30:45 - deepagents.graph - INFO - Building agent with instructions: Research the topic...
```

## 查看日志

### 方式一：FastAPI + Uvicorn 运行

使用启动脚本运行 Research Agent API：

```bash
# 启动服务
./conf/start_research_agent_api.sh
```

日志会直接输出到终端：
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:deepagents.graph:_agent_builder called with model=None
INFO:deepagents.graph:No model specified, using default model
INFO:research_agent:Creating research agent...
INFO:research_agent:research agent created successfully
```

查看 API 请求日志：
```bash
# 发送测试请求
curl -X POST http://localhost:8000/research/invoke \
  -H "Content-Type: application/json" \
  -d '{"query": "测试查询"}'

# 终端会显示
INFO:research_agent_api:Request received: query=测试查询
ERROR:research_agent_api:Error in invoke_research: ...  # 如果有错误
```

### 方式二：LangGraph 部署方式

使用 LangGraph CLI 运行：

```bash
# 1. 初始化环境
cd examples/research
./init_langgraph.sh
source .venv/bin/activate

# 2. 启动 LangGraph 开发服务器
langgraph dev
```

LangGraph 日志输出：
```
Starting LangGraph API server...
INFO:     Started server process [67890]
INFO:     Waiting for application startup.
INFO:deepagents.graph:_agent_builder called with model=gpt-4
INFO:research_agent:Creating research agent...
Ready. Listening on http://127.0.0.1:2024
```

访问 LangGraph Studio UI 查看详细日志：
- 打开 http://127.0.0.1:2024
- 查看 Agent 执行流程和每个节点的日志

### 方式三：直接运行 Python 脚本

```bash
cd backend
source .venv/bin/activate

# 设置日志级别环境变量（可选）
export PYTHONUNBUFFERED=1  # 禁用输出缓冲，实时显示日志

# 运行测试脚本
python -m src.test.test_env_connectivity
```

### 方式四：查看日志文件（推荐用于 AI 调试）

日志自动保存在 `logs/` 目录，可以随时查看：

```bash
# 查看最新的完整日志
tail -f logs/app.log

# 查看错误日志
tail -f logs/error.log

# 查看今天的日志
cat logs/daily.log

# 查看昨天的日志
cat logs/daily.log.2024-12-13
```

#### AI 自动查询日志示例

**1. 查找特定时间的错误**
```bash
grep "2024-12-14 15:" logs/app.log | grep ERROR
```

**2. 统计错误类型**
```bash
grep ERROR logs/error.log | cut -d'-' -f4 | sort | uniq -c | sort -rn
```

**3. 查找特定模块的日志**
```bash
grep "research_agent" logs/app.log
```

**4. 解析结构化 JSON 日志**
```python
import json

# 读取并解析 JSON 日志
with open('logs/structured/structured.jsonl') as f:
    for line in f:
        log = json.loads(line)
        if log['level'] == 'ERROR':
            print(f"{log['timestamp']}: {log['message']}")
            if 'exception' in log:
                print(f"  Exception: {log['exception']}")
```

**5. 查找最近 10 分钟的日志**
```bash
# macOS/Linux
find logs/ -name "app.log" -mmin -10 -exec tail {} \;
```

**6. 按关键词搜索**
```bash
# 搜索包含 "Agent" 或 "error" 的日志
grep -i "agent\|error" logs/app.log
```

**7. 导出某个时间段的日志供 AI 分析**
```bash
# 导出今天下午 3 点的所有日志
grep "2024-12-14 15:" logs/app.log > today_15h.log

# 或使用 sed
sed -n '/2024-12-14 15:00/,/2024-12-14 16:00/p' logs/app.log > timerange.log
```

#### 使用 Python 脚本查询日志

```python
from pathlib import Path
import json
from datetime import datetime, timedelta

def analyze_recent_errors(hours=1):
    """分析最近几小时的错误"""
    log_file = Path("logs/error.log")
    cutoff_time = datetime.now() - timedelta(hours=hours)

    errors = []
    with open(log_file) as f:
        for line in f:
            # 解析时间戳
            try:
                timestamp_str = line.split(' - ')[0]
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                if timestamp >= cutoff_time:
                    errors.append(line.strip())
            except:
                continue

    return errors

# 使用示例
recent_errors = analyze_recent_errors(hours=1)
print(f"最近 1 小时发现 {len(recent_errors)} 个错误")
for error in recent_errors:
    print(error)
```

#### JSON 日志高级分析

```python
import json
from pathlib import Path
from collections import Counter

def analyze_json_logs():
    """分析结构化 JSON 日志"""
    log_file = Path("logs/structured/structured.jsonl")

    if not log_file.exists():
        print("结构化日志文件不存在")
        return

    levels = []
    modules = []
    errors = []

    with open(log_file) as f:
        for line in f:
            try:
                log = json.loads(line)
                levels.append(log['level'])
                modules.append(log['logger'])

                if log['level'] == 'ERROR':
                    errors.append({
                        'time': log['timestamp'],
                        'module': log['logger'],
                        'message': log['message']
                    })
            except json.JSONDecodeError:
                continue

    print("日志级别分布:")
    for level, count in Counter(levels).most_common():
        print(f"  {level}: {count}")

    print("\n最活跃的模块:")
    for module, count in Counter(modules).most_common(5):
        print(f"  {module}: {count}")

    print(f"\n错误详情 ({len(errors)} 个):")
    for error in errors[-5:]:  # 最近 5 个错误
        print(f"  [{error['time']}] {error['module']}: {error['message']}")

# 使用
analyze_json_logs()
```

## 测试指南

### 测试目录结构

```
backend/src/test/
├── test_env_connectivity.py      # 环境连接测试
├── integration/                   # 集成测试
│   └── redis_example_usage.py
└── learn/                         # 学习示例
    └── react_agent_from_scratch.py
```

### 编写测试文件

遵循项目原则：**拒绝 mock 测试**，使用真实的集成测试。

示例测试文件 `test_example.py`：

```python
import sys
import logging

# 配置测试日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_feature():
    """测试某个功能"""
    logger.info("开始测试功能")

    try:
        # 执行测试逻辑
        result = some_function()

        logger.info(f"测试结果: {result}")
        assert result is not None, "结果不应为 None"

        logger.info("测试通过")

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        test_feature()
        print("✓ 所有测试通过")
    except Exception as e:
        print(f"✗ 测试失败: {e}", file=sys.stderr)
        sys.exit(1)
```

### 运行测试

```bash
cd backend
source .venv/bin/activate

# 运行单个测试
python -m src.test.test_example

# 运行所有测试（如果有 pytest）
pytest src/test/ -v

# 查看详细日志
python -m src.test.test_example 2>&1 | tee test.log
```

### 测试 Agent 功能

```python
import logging
from src.deepagents.graph import create_deep_agent
from langchain_core.tools import tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@tool
def sample_tool(query: str) -> str:
    """示例工具"""
    logger.info(f"工具被调用: query={query}")
    return f"处理结果: {query}"


def test_agent():
    """测试 Agent 创建和执行"""
    logger.info("创建测试 Agent")

    agent = create_deep_agent(
        tools=[sample_tool],
        instructions="你是一个测试助手"
    )

    logger.info("调用 Agent")
    result = agent.invoke({
        "messages": [{"role": "user", "content": "测试消息"}]
    })

    logger.info(f"Agent 响应: {result}")
    return result


if __name__ == "__main__":
    test_agent()
```

## 调试技巧

### 1. 增加日志详细程度

在调试时临时修改日志级别：

```python
# 在文件开头添加
import logging
logging.basicConfig(level=logging.DEBUG)

# 或者只针对特定模块
logging.getLogger('deepagents.graph').setLevel(logging.DEBUG)
```

### 2. 查看完整错误堆栈

```python
try:
    risky_operation()
except Exception as e:
    logger.error("操作失败", exc_info=True)  # exc_info=True 会输出完整堆栈
    # 或使用
    logger.exception("操作失败")  # 自动包含 exc_info=True
```

### 3. 临时调试输出

```python
# 在关键位置添加调试日志
logger.debug(f"变量值: model={model}, tools={tools}")
logger.debug(f"执行到此处，状态: {state}")
```

### 4. 使用 Python 调试器

```python
# 在需要调试的位置插入断点
import pdb; pdb.set_trace()

# 或使用 ipdb（需要安装：pip install ipdb）
import ipdb; ipdb.set_trace()
```

### 5. 查看 LangGraph 执行流程

启用 LangGraph 的详细日志：

```python
# 在创建 agent 后
agent = create_deep_agent(...)

# 查看 graph 结构
print(agent.get_graph().draw_ascii())

# 使用 verbose 模式执行
result = agent.invoke(
    {"messages": [...]},
    {"configurable": {"thread_id": "test"}},
)
```

### 6. 日志文件输出

将日志同时输出到文件：

```python
import logging
from logging.handlers import RotatingFileHandler

# 创建文件 handler
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)

# 创建控制台 handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 配置格式
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 配置 root logger
logging.root.setLevel(logging.DEBUG)
logging.root.addHandler(file_handler)
logging.root.addHandler(console_handler)
```

## 最佳实践

### 1. 日志级别使用规范

```python
# INFO - 记录正常流程
logger.info("Agent 创建成功")
logger.info(f"处理请求: query={query}")

# DEBUG - 详细调试信息（仅开发环境）
logger.debug(f"中间状态: state={state}")
logger.debug(f"工具参数: args={args}")

# WARNING - 可恢复的异常情况
logger.warning(f"API 响应慢: {duration}s")
logger.warning("使用默认配置")

# ERROR - 错误但程序可继续
logger.error(f"工具调用失败: {e}")

# CRITICAL - 严重错误，程序无法继续
logger.critical("无法连接数据库")
```

### 2. 遵循项目原则

根据 CLAUDE.md 的开发原则：

- **拒绝一个函数超过 30 行**：如果日志太多导致函数过长，考虑拆分函数
- **高内聚、低耦合**：日志记录应该在合适的层级，避免重复
- **避免硬编码字符串**：使用常量定义日志消息模板

```python
# 不好的做法
logger.info("Creating research agent...")

# 好的做法 - 使用常量
LOG_MSG_AGENT_CREATE = "Creating %s agent"
logger.info(LOG_MSG_AGENT_CREATE, "research")
```

### 3. 敏感信息处理

```python
# 不要记录敏感信息
logger.info(f"API Key: {api_key}")  # ❌ 错误

# 部分脱敏
logger.info(f"API Key: {api_key[:8]}...")  # ✓ 正确
```

### 4. 性能考虑

```python
# 避免在循环中频繁记录
for item in large_list:
    logger.debug(f"Processing {item}")  # ❌ 可能影响性能

# 改为批量记录或采样
if len(large_list) > 100:
    logger.info(f"批量处理 {len(large_list)} 条记录")
```

### 5. 测试中的日志

```python
def test_with_logging():
    """测试时记录关键信息"""
    logger.info("=" * 50)
    logger.info("测试开始: test_with_logging")
    logger.info("=" * 50)

    try:
        # 测试逻辑
        result = perform_test()
        logger.info(f"测试结果: {result}")
        assert result.success

    except Exception as e:
        logger.error("测试失败", exc_info=True)
        raise
    finally:
        logger.info("测试结束")
```

## 常见问题排查

### 问题 1：看不到日志输出

**解决方案**：
```bash
# 确保设置了正确的日志级别
export PYTHONUNBUFFERED=1

# 检查代码中的配置
logging.basicConfig(level=logging.INFO)  # 不是 WARNING 或 ERROR
```

### 问题 2：日志格式不清晰

**解决方案**：
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
```

### 问题 3：日志太多难以查找

**解决方案**：
```bash
# 使用 grep 过滤
python app.py 2>&1 | grep "ERROR"

# 或重定向到文件后查看
python app.py > app.log 2>&1
tail -f app.log | grep "research_agent"
```

### 问题 4：LangGraph 日志看不到自定义日志

**解决方案**：
LangGraph 有自己的日志系统，确保：
```python
# 在 langgraph.json 或环境变量中配置
LANGSMITH_TRACING=true  # 启用追踪
```

## 总结

- 使用标准 `logging` 模块，配置清晰的格式
- 开发时使用 `DEBUG`，生产环境使用 `INFO` 或 `WARNING`
- 测试遵循项目原则：真实测试，拒绝 mock
- 关键位置记录日志，便于调试和追踪
- 敏感信息要脱敏，避免泄露

## 相关文档

- Python logging 文档: https://docs.python.org/3/library/logging.html
- LangGraph 调试: https://langchain-ai.github.io/langgraph/
- 项目开发原则: /CLAUDE.md
