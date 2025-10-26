import logging

from dotenv import load_dotenv

from src.deepagents.graph import create_deep_agent
from src.service.research_agent.research_agent_prompt import sub_research_prompt, research_instructions, \
    critique_sub_agent
from src.service.research_agent.research_agent_tools import internet_search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

research_sub_agent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions. Only give this researcher one topic at a time. Do not pass multiple sub questions to this researcher. Instead, you should break down a large topic into the necessary components, and then call multiple research agents in parallel, one for each sub question.",
    "prompt": sub_research_prompt,
    "tools": ["internet_search"],
}

# Create the agent
logger.info("Creating research agent...")
agent = create_deep_agent(
    tools=[internet_search],
    instructions=research_instructions,
    subagents=[critique_sub_agent, research_sub_agent],
).with_config({"recursion_limit": 1000})
logger.info("research agent created successfully")
