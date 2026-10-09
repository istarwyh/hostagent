# Logs Directory

本目录用于存储应用运行日志，便于调试、监控和 AI 自动分析。

## 目录结构

```
logs/
├── app.log              # 主应用日志（按大小轮转）
├── app.log.1            # 轮转的历史日志
├── app.log.2
├── error.log            # 错误日志（仅 ERROR 及以上级别）
├── error.log.1
├── daily.log            # 按日期轮转的日志
├── daily.log.2024-12-13 # 历史日志（按日期）
├── structured/          # 结构化 JSON 日志（便于 AI 解析）
│   └── structured.jsonl
└── archived/            # 归档的日志（可选）
```

## 日志文件说明

### app.log
- 包含所有级别的日志（INFO 及以上）
- 按大小轮转（默认 10MB）
- 保留最近 5 个文件

### error.log
- 仅包含 ERROR 和 CRITICAL 级别的日志
- 用于快速定位错误
- 按大小轮转（默认 10MB）

### daily.log
- 按天轮转的完整日志
- 每天午夜自动创建新文件
- 保留最近 7 天

### structured/structured.jsonl
- JSON Lines 格式的结构化日志
- 每行一个 JSON 对象
- 便于程序化解析和 AI 分析
- 包含完整的上下文信息（模块、函数、行号等）

## 日志格式

### 标准格式
```
2024-12-14 15:30:45 - module.name - INFO - 日志消息
```

### 详细格式
```
2024-12-14 15:30:45 - module.name - INFO - [file.py:123] - 日志消息
```

### JSON 格式（structured.jsonl）
```json
{
  "timestamp": "2024-12-14T15:30:45.123456",
  "level": "INFO",
  "logger": "deepagents.graph",
  "module": "graph",
  "function": "create_deep_agent",
  "line": 38,
  "message": "Creating research agent"
}
```

## AI 查询日志示例

### 查找错误日志
```bash
cat logs/error.log | grep "Exception"
```

### 查询特定时间段
```bash
grep "2024-12-14 15:" logs/app.log
```

### 解析 JSON 日志
```python
import json
with open('logs/structured/structured.jsonl') as f:
    for line in f:
        log = json.loads(line)
        if log['level'] == 'ERROR':
            print(log)
```

### 统计错误类型
```bash
grep ERROR logs/error.log | cut -d'-' -f4 | sort | uniq -c
```

## 日志清理

日志文件会自动轮转，不需要手动清理。如需归档：

```bash
# 归档一个月前的日志
find logs/ -name "*.log.*" -mtime +30 -exec mv {} logs/archived/ \;
```

## 注意事项

- 日志文件已添加到 .gitignore，不会被提交到版本控制
- 生产环境建议使用 WARNING 或 ERROR 级别
- 定期检查日志目录大小，避免占用过多磁盘空间
- 敏感信息（API Key、密码等）不应出现在日志中
