import asyncio
def print_banner(tools_count: int, tools_added_count: int):
    print(f"成功加载 {tools_count} 个工具， {tools_added_count}  MCP 工具")
    
    
async def read_user_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)
    