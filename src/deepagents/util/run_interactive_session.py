from typing import Callable, List, Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.utils import from_env
from deepagents.util.handle_interactive_loop import build_initial_state, interactive_loop
from deepagents.util.handle_user_input import print_banner
from deepagents.model import get_default_model
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.state import CompiledStateGraph
from typing import Dict


async def run_interactive_session(
        agent_id: str,
        agentBuilder: Callable[[List[Any], str, BaseLanguageModel, List[Any]], CompiledStateGraph],
        instructions: str,
        subagents: List[Any]
) -> None:
    """Run an interactive terminal session for the product health report agent.

    Args:
        agent_id: The agent ID for MCP configuration
        agentBuilder: Function to build the agent
        instructions: System instructions for the agent
        subagents: List of subagents to use
    """
    llm = get_default_model()
    mcp_server_configs = _get_mcp_server_configs(agent_id)
    print(f"正在连接 {len(mcp_server_configs)} 个 MCP 服务器...")

    persisted_state = build_initial_state()
    default_tools = []

    mcp_client = MultiServerMCPClient(mcp_server_configs)
    loaded_tools = default_tools[:]
    for tool in await mcp_client.get_tools():
        tool.description = f"Powered by '{tool.name}'.\n{tool.description}"
        loaded_tools.append(tool)
        
    agent = agentBuilder(loaded_tools, instructions, llm, subagents)
    await interactive_loop(agent, persisted_state)


def _get_mcp_server_configs(agent_id: str) -> Dict[str, Any]:
   
    return {
        "mcpadvisor": {
            "transport":"stdio",
            "command":"npx",
            "args":["-y","@xiaohui-wang/mcpadvisor"],
            "env":{}
        },
        # "tavily": {
        #     "transport":"stdio",
        #     "command": "npx",
        #     "args": [
        #         "-y",
        #         "tavily-mcp@0.2.3"
        #     ],
        #     "env": { 
        #         "TAVILY_API_KEY": from_env("TAVILY_API_KEY")
        #     }
        # }
    }