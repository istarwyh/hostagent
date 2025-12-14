"""
日志工具使用示例

展示如何在项目中使用统一的日志配置
"""

import logging
from pathlib import Path

from src.util.logger import StructuredLogger, init_logging, setup_logger


def example_basic_usage():
    """基本使用示例"""
    # 创建 logger
    logger = setup_logger(__name__)

    # 记录不同级别的日志
    logger.debug("这是调试信息")
    logger.info("应用启动成功")
    logger.warning("配置文件未找到，使用默认配置")
    logger.error("数据库连接失败")
    logger.critical("系统内存不足")


def example_custom_log_dir():
    """自定义日志目录"""
    logger = setup_logger(__name__, log_dir=Path("custom_logs"), level=logging.DEBUG)
    logger.info("日志将输出到 custom_logs 目录")


def example_detailed_format():
    """使用详细格式（包含文件名和行号）"""
    logger = setup_logger(__name__, detailed=True)
    logger.info("这条日志会显示文件名和行号")


def example_console_only():
    """仅输出到控制台"""
    logger = setup_logger(__name__, file_output=False)
    logger.info("这条日志只会显示在控制台")


def example_file_only():
    """仅输出到文件"""
    logger = setup_logger(__name__, console=False)
    logger.info("这条日志只会写入文件")


def example_global_init():
    """全局初始化（在应用启动时调用一次）"""
    # 初始化全局日志配置
    init_logging(log_dir=Path("logs"), level=logging.INFO, detailed=False)

    # 之后所有模块都可以直接使用
    logger = logging.getLogger(__name__)
    logger.info("使用全局配置的日志")


def example_structured_logging():
    """结构化日志（JSON 格式，便于 AI 解析）"""
    logger = StructuredLogger(__name__)

    # 记录带上下文的日志
    logger.log("INFO", "用户登录", user_id="12345", ip="192.168.1.1", action="login")

    logger.log(
        "ERROR", "API 调用失败", endpoint="/api/users", status_code=500, error="Connection timeout"
    )


def example_exception_logging():
    """异常日志记录"""
    logger = setup_logger(__name__)

    try:
        result = 1 / 0
    except Exception as e:
        # 方法1：使用 exc_info=True
        logger.error("计算错误", exc_info=True)

        # 方法2：使用 exception（自动包含 exc_info）
        logger.exception("计算错误")


def example_agent_usage():
    """在 Agent 中使用日志"""
    logger = setup_logger(__name__)

    # Agent 初始化
    logger.info("初始化 Research Agent")

    # 工具调用
    logger.info("调用搜索工具", extra={"query": "Python logging", "tool": "internet_search"})

    # Agent 响应
    logger.info("Agent 响应完成", extra={"tokens": 1500, "duration": 2.3})


def example_api_request_logging():
    """API 请求日志"""
    logger = setup_logger(__name__)

    # 请求开始
    logger.info(
        "API 请求", extra={"method": "POST", "endpoint": "/research/invoke", "thread_id": "abc123"}
    )

    # 请求完成
    logger.info("API 响应", extra={"status": 200, "duration_ms": 1234, "thread_id": "abc123"})

    # 错误情况
    logger.error(
        "API 错误",
        extra={"status": 500, "error": "Database connection failed", "thread_id": "abc123"},
    )


if __name__ == "__main__":
    print("日志工具使用示例")
    print("=" * 50)

    print("\n1. 基本使用")
    example_basic_usage()

    print("\n2. 自定义日志目录")
    example_custom_log_dir()

    print("\n3. 详细格式")
    example_detailed_format()

    print("\n4. 结构化日志")
    example_structured_logging()

    print("\n5. 异常日志")
    example_exception_logging()

    print("\n" + "=" * 50)
    print("查看日志文件:")
    print("  - logs/app.log        # 所有日志")
    print("  - logs/error.log      # 仅错误")
    print("  - logs/daily.log      # 按日期")
    print("  - logs/structured/structured.jsonl  # JSON 格式")
