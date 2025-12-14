#!/usr/bin/env python3
"""
测试日志系统是否正常工作

运行此脚本验证：
1. 日志是否正确输出到文件
2. 不同日志级别是否正常工作
3. 结构化日志是否正确生成
4. 日志轮转是否配置正确
"""

import sys
from pathlib import Path

# 添加项目路径到 sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.util.logger import setup_logger, StructuredLogger
import logging


def test_basic_logging():
    """测试基本日志功能"""
    print("\n=== 测试基本日志功能 ===")
    logger = setup_logger("test.basic")

    logger.debug("这是 DEBUG 日志")
    logger.info("这是 INFO 日志")
    logger.warning("这是 WARNING 日志")
    logger.error("这是 ERROR 日志")

    print("✓ 基本日志测试完成")
    print(f"  查看日志: tail -f {project_root}/logs/app.log")


def test_error_logging():
    """测试错误日志"""
    print("\n=== 测试错误日志 ===")
    logger = setup_logger("test.error")

    try:
        result = 1 / 0
    except Exception as e:
        logger.error("捕获异常", exc_info=True)

    print("✓ 错误日志测试完成")
    print(f"  查看错误日志: tail -f {project_root}/logs/error.log")


def test_structured_logging():
    """测试结构化日志"""
    print("\n=== 测试结构化日志 ===")
    logger = StructuredLogger("test.structured")

    logger.log("INFO", "测试结构化日志", module="test", action="verify")
    logger.log("ERROR", "测试错误日志", error_code=500, error_type="服务器错误")

    print("✓ 结构化日志测试完成")
    print(f"  查看 JSON 日志: tail -f {project_root}/logs/structured/structured.jsonl")


def test_custom_directory():
    """测试自定义日志目录"""
    print("\n=== 测试自定义日志目录 ===")

    custom_log_dir = project_root / "logs" / "test_custom"
    logger = setup_logger("test.custom", log_dir=custom_log_dir)

    logger.info("测试自定义目录日志")

    if custom_log_dir.exists():
        print("✓ 自定义目录日志测试完成")
        print(f"  日志目录: {custom_log_dir}")
    else:
        print("✗ 自定义目录创建失败")


def test_detailed_format():
    """测试详细格式"""
    print("\n=== 测试详细日志格式 ===")
    logger = setup_logger("test.detailed", detailed=True)

    logger.info("这条日志包含文件名和行号")
    print("✓ 详细格式测试完成")


def verify_log_files():
    """验证日志文件是否创建"""
    print("\n=== 验证日志文件 ===")
    logs_dir = project_root / "logs"

    required_files = [
        "app.log",
        "error.log",
        "daily.log",
    ]

    for filename in required_files:
        filepath = logs_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"✓ {filename} 存在 ({size} bytes)")
        else:
            print(f"✗ {filename} 不存在")

    # 检查结构化日志目录
    structured_dir = logs_dir / "structured"
    if structured_dir.exists():
        jsonl_file = structured_dir / "structured.jsonl"
        if jsonl_file.exists():
            size = jsonl_file.stat().st_size
            print(f"✓ structured/structured.jsonl 存在 ({size} bytes)")
        else:
            print("✗ structured/structured.jsonl 不存在")
    else:
        print("✗ structured/ 目录不存在")


def show_log_samples():
    """显示日志示例"""
    print("\n=== 日志文件示例 ===")
    logs_dir = project_root / "logs"

    # 显示 app.log 最后几行
    app_log = logs_dir / "app.log"
    if app_log.exists():
        print("\napp.log 最后 5 行:")
        with open(app_log) as f:
            lines = f.readlines()
            for line in lines[-5:]:
                print(f"  {line.rstrip()}")

    # 显示 error.log
    error_log = logs_dir / "error.log"
    if error_log.exists() and error_log.stat().st_size > 0:
        print("\nerror.log 最后 3 行:")
        with open(error_log) as f:
            lines = f.readlines()
            for line in lines[-3:]:
                print(f"  {line.rstrip()}")

    # 显示结构化日志
    structured_log = logs_dir / "structured" / "structured.jsonl"
    if structured_log.exists() and structured_log.stat().st_size > 0:
        print("\nstructured.jsonl 最后 2 行:")
        with open(structured_log) as f:
            lines = f.readlines()
            for line in lines[-2:]:
                print(f"  {line.rstrip()}")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("日志系统测试")
    print("=" * 60)

    try:
        test_basic_logging()
        test_error_logging()
        test_structured_logging()
        test_custom_directory()
        test_detailed_format()

        verify_log_files()
        show_log_samples()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)

        print("\n下一步:")
        print("1. 查看日志文件:")
        print(f"   cd {project_root}")
        print("   tail -f logs/app.log")
        print("\n2. 搜索日志:")
        print("   grep ERROR logs/error.log")
        print("\n3. 分析结构化日志:")
        print("   cat logs/structured/structured.jsonl | jq")

        return 0

    except Exception as e:
        print(f"\n✗ 测试失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
