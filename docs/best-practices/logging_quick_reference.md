# 日志系统快速参考

## 快速开始

```python
# 在任何模块中使用
from src.util.logger import setup_logger

logger = setup_logger(__name__)
logger.info("开始执行任务")
logger.error("发生错误", exc_info=True)
```

日志自动保存到：
- `logs/app.log` - 所有日志
- `logs/error.log` - 仅错误
- `logs/daily.log` - 按日期轮转

## 常用命令

### 实时查看日志
```bash
tail -f logs/app.log          # 查看所有日志
tail -f logs/error.log         # 仅查看错误
```

### 搜索日志
```bash
grep "ERROR" logs/app.log      # 查找错误
grep "research_agent" logs/app.log  # 查找特定模块
grep "2024-12-14 15:" logs/app.log  # 查找特定时间
```

### AI 分析日志
```python
# 读取 JSON 格式日志
import json
with open('logs/structured/structured.jsonl') as f:
    for line in f:
        log = json.loads(line)
        if log['level'] == 'ERROR':
            print(log)
```

## 日志级别

```python
logger.debug("调试信息")      # 开发环境
logger.info("正常信息")       # 默认级别
logger.warning("警告信息")    # 可恢复的问题
logger.error("错误信息")      # 错误但可继续
logger.critical("严重错误")   # 无法继续
```

## 高级用法

### 结构化日志（便于 AI 解析）
```python
from src.util.logger import StructuredLogger

logger = StructuredLogger(__name__)
logger.log("INFO", "用户操作", user_id="123", action="login")
# 输出到 logs/structured/structured.jsonl
```

### 自定义日志目录
```python
from pathlib import Path

logger = setup_logger(__name__, log_dir=Path("custom_logs"))
```

### 详细格式（含文件名和行号）
```python
logger = setup_logger(__name__, detailed=True)
```

## 文档链接

- 完整文档: `docs/best-practices/python_logging_testing_guide.md`
- 日志工具: `backend/src/util/logger.py`
- 使用示例: `backend/src/util/logger_example.py`
- 日志目录说明: `logs/README.md`

## 常见问题

**Q: 看不到日志输出？**
```python
# 确保使用了正确的导入
from src.util.logger import setup_logger
logger = setup_logger(__name__)  # 不是 logging.getLogger()
```

**Q: 如何只输出到文件不显示在控制台？**
```python
logger = setup_logger(__name__, console=False)
```

**Q: 日志文件在哪里？**
```bash
ls logs/
# app.log, error.log, daily.log, structured/
```

**Q: 如何清理旧日志？**
日志会自动轮转，无需手动清理。如需归档：
```bash
mv logs/*.log.* logs/archived/
```

## 最佳实践

1. 新代码统一使用 `setup_logger(__name__)`
2. 关键操作记录 INFO 日志
3. 错误必须记录，使用 `exc_info=True` 包含堆栈
4. 避免在循环中大量记录日志
5. 敏感信息（API Key）不要记录到日志
