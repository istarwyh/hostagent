import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence, Union, Optional, Callable, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from deepagents.workspace_dir import get_workspace_dir_name


class SimpleAuditToolNode(ToolNode):
    """
    带审计功能的工具节点
    
    继承自ToolNode，在执行工具前后记录入参和出参到文件系统
    """

    def __init__(
            self,
            tools: Sequence[Union[BaseTool, Callable, dict[str, Any]]],
            *,
            audit_dir: Optional[str] = None,
            name: str = "tools",
            tags: Optional[list[str]] = None,
            handle_tool_errors: bool = True,
    ):
        """
        初始化审计工具节点
        
        Args:
            tools: 工具列表
            audit_dir: 审计日志目录，默认为 ./audit_logs
            name: 节点名称
            tags: 标签列表
            handle_tool_errors: 是否处理工具错误
        """
        super().__init__(
            tools=tools,
            name=name,
            tags=tags,
            handle_tool_errors=handle_tool_errors
        )

        # 设置审计目录
        self.workspace_dir = get_workspace_dir_name()
        if audit_dir is None:
            audit_dir = os.path.join(self.workspace_dir, "audit_logs")
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def _generate_audit_file_path(self, tool_name: str, tool_call_id: str) -> str:
        """
        提前生成审计文件路径
        
        Args:
            tool_name: 工具名称
            tool_call_id: 工具调用ID
        
        Returns:
            审计日志文件路径
        """
        timestamp = datetime.now()
        filename = f"{timestamp.strftime('%H%M%S')}_{tool_name}.json"
        filepath = str(self.audit_dir) + "/" + filename
        return str(filepath)

    @staticmethod
    def _attach_audit_file_path(result: Any, audit_file_path: str) -> Any:

        """
        通用方法：将审计文件路径附加到结果中
        
        支持多种数据类型：ToolMessage、dict、list、其他对象
        
        Args:
            result: 要附加路径的结果对象
            audit_file_path: 审计文件路径

        Returns:
            附加了审计文件路径的结果对象
        """
        file_path = '当前数据的相对 workspace 的文件路径(即引用路径):'
        audit_file_path = SimpleAuditToolNode.extract_from_workspace(audit_file_path)
        if result is None:
            return result

        if isinstance(result, str):
            result = f"{file_path}{audit_file_path}\n" + str(result)

        return result

    @staticmethod
    def extract_from_workspace(input_string):
        """
        提取从 'workspace' 开始到字符串末尾的子字符串

        参数:
        input_string (str): 输入的完整路径字符串

        返回:
        str: 从 'workspace' 开始到字符串末尾的子字符串，如果没有找到则返回 None
        """
        # 使用正则表达式匹配从 'workspace' 开始到字符串末尾的部分
        pattern = r'workspace.*$'
        match = re.search(pattern, input_string)

        if match:
            return match.group(0)
        else:
            return "暂时没有明确的工作空间路径"

    @staticmethod
    def _write_audit_log(
            tool_name: str,
            tool_call_id: str,
            input_data: Any,
            output_data: Any,
            error: Optional[str] = None,
            execution_time_ms: float = 0,
            audit_file_path: Optional[str] = None
    ) -> str:
        """
        写入审计日志到文件
        
        Args:
            tool_name: 工具名称
            tool_call_id: 工具调用ID
            input_data: 输入参数
            output_data: 输出结果
            error: 错误信息（如果有）
            execution_time_ms: 执行时间（毫秒）
            audit_file_path: 预生成的审计文件路径（可选） 绝对路径
        
        Returns:
            审计日志文件路径
        """
        timestamp = datetime.now()

        # 构建审计记录
        audit_record = {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "timestamp": timestamp.isoformat(),
            "execution_time_ms": execution_time_ms,
            "input": input_data,
            "output": output_data,
            "error": error,
            "status": "failed" if error else "success"
        }

        filepath = Path(audit_file_path)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(audit_record, f, ensure_ascii=False, indent=2, default=str)

        # 同时追加到当天的汇总日志
        summary_file = f"{filepath.parent}/summary_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(audit_record, ensure_ascii=False, default=str) + '\n')

        return str(filepath)
    
    def invoke(
            self,
            input: Union[dict[str, Any], Any],
            config: Optional[dict] = None,
            **kwargs: Any
    ) -> Any:
        """
        执行工具调用并记录审计日志
        
        重写invoke方法以添加审计功能
        """
        import time

        # 提取工具调用信息
        if isinstance(input, list) and len(input) > 0:
            tool_call = input[0]
        elif isinstance(input, dict) and "tool_calls" in input:
            tool_call = input["tool_calls"][0] if input["tool_calls"] else {}
        else:
            tool_call = input if isinstance(input, dict) else {}

        tool_name = tool_call.get("name", "unknown")
        tool_call_id = tool_call.get("id", str(uuid.uuid4())[:8])
        tool_args = tool_call.get("args", {})

        # 提前生成审计文件路径
        audit_file_path = self._generate_audit_file_path(tool_name, tool_call_id)

        # 记录开始时间
        start_time = time.time()
        error_msg = None
        try:
            # 调用父类的invoke方法执行实际的工具
            result = super().invoke(input, config, **kwargs)
            output_content = self._extract_output_content_and_add_audit_path(result, audit_file_path)
            return result
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            # 计算执行时间
            execution_time_ms = (time.time() - start_time) * 1000

            audit_file = self._write_audit_log(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                input_data=tool_args,
                output_data=output_content,
                error=error_msg,
                execution_time_ms=execution_time_ms,
                audit_file_path=audit_file_path
            )

            # 打印审计信息（可选）
            status = "❌ FAILED" if error_msg else "✅ SUCCESS"
            print(f"\n[AUDIT] {status} Tool: {tool_name} | ID: {tool_call_id[:8]} | Time: {execution_time_ms:.2f}ms")
            print(f"[AUDIT] Log saved to: {audit_file}")

    def _extract_output_content_and_add_audit_path(self, result: Any, audit_file_path: Optional[str] = None):
        output_content = None
        if result:
            if isinstance(result, ToolMessage):
                output_content = result.content
                result.content = self._attach_audit_file_path(output_content, audit_file_path)
            elif isinstance(result, dict) and "messages" in result:
                messages = result["messages"]
                if messages and isinstance(messages[0], ToolMessage):
                    output_content = messages[0].content
                    messages[0].content = self._attach_audit_file_path(output_content, audit_file_path)
            else:
                output_content = result
                output_content = self._attach_audit_file_path(output_content, audit_file_path)
        return output_content

    async def ainvoke(
            self,
            input: Union[dict[str, Any], Any],
            config: Optional[dict] = None,
            **kwargs: Any
    ) -> Any:
        """
        异步执行工具调用并记录审计日志
        
        重写ainvoke方法以添加审计功能
        """
        import time

        # 提取工具调用信息
        if isinstance(input, list) and len(input) > 0:
            tool_call = input[0]
        elif isinstance(input, dict) and "tool_calls" in input:
            tool_call = input["tool_calls"][0] if input["tool_calls"] else {}
        else:
            tool_call = input if isinstance(input, dict) else {}

        tool_name = tool_call.get("name", "unknown")
        tool_call_id = tool_call.get("id", str(uuid.uuid4())[:8])
        tool_args = tool_call.get("args", {})

        # 提前生成审计文件路径
        audit_file_path = self._generate_audit_file_path(tool_name, tool_call_id)

        # 记录开始时间
        start_time = time.time()
        error_msg = None
        output_content = None

        try:
            # 调用父类的ainvoke方法执行实际的工具
            result = await super().ainvoke(input, config, **kwargs)
            output_content = self._extract_output_content_and_add_audit_path(result, audit_file_path)
            return result
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            # 计算执行时间
            execution_time_ms = (time.time() - start_time) * 1000
            # 写入审计日志，使用预生成的文件路径
            audit_file = self._write_audit_log(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                input_data=tool_args,
                output_data=output_content,
                error=error_msg,
                execution_time_ms=execution_time_ms,
                audit_file_path=audit_file_path
            )

            # 打印审计信息（可选）
            status = "❌ FAILED" if error_msg else "✅ SUCCESS"
            print(f"\n[AUDIT] {status} Tool: {tool_name} | ID: {tool_call_id[:8]} | Time: {execution_time_ms:.2f}ms")
            print(f"[AUDIT] Log saved to: {audit_file}")
