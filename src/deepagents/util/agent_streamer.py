import asyncio
from typing import AsyncIterator, Dict, Any, Iterator
import traceback


class AgentStreamer:
    """Agent 流式输出处理器"""

    def __init__(self, agent):
        self.agent = agent

    async def stream_with_progress(self, input_data: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        流式执行 agent 并输出中间过程

        Args:
            input_data: 输入数据，包含 messages 等

        Yields:
            Dict: 包含步骤信息、状态更新等的字典
        """
        try:
            # 使用 astream 方法进行流式处理
            async for chunk in self.agent.astream(input_data):
                # 输出当前步骤信息
                yield {
                    "type": "step",
                    "data": chunk,
                    "timestamp": asyncio.get_event_loop().time()
                }

        except Exception as e:
            # Print full traceback to help diagnose issues like "'str' object has no attribute 'model_dump'"
            traceback.print_exc()
            yield {
                "type": "error",
                "error": str(e),
                "exception_type": e.__class__.__name__,
                "timestamp": asyncio.get_event_loop().time()
            }

    def stream_sync(self, input_data: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        同步流式执行 agent

        Args:
            input_data: 输入数据

        Yields:
            Dict: 步骤信息
        """
        try:
            # 使用 stream 方法进行同步流式处理
            for chunk in self.agent.stream(input_data):
                yield {
                    "type": "step",
                    "data": chunk,
                    "node": list(chunk.keys())[0] if chunk else "unknown",
                    "content": chunk
                }
        except Exception as e:
            yield {
                "type": "error",
                "error": str(e)
            }

    def invoke_with_callbacks(self, input_data: Dict[str, Any], callbacks=None):
        """
        使用回调函数执行 agent，获取中间过程

        Args:
            input_data: 输入数据
            callbacks: 回调函数列表

        Returns:
            执行结果
        """
        config = {"callbacks": callbacks} if callbacks else {}
        return self.agent.invoke(input_data, config=config)