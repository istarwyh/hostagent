import logging
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_core.tools import ToolException, tool
from requests.exceptions import RequestException
from tavily import TavilyClient
from tavily.errors import (
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    TimeoutError,
    UsageLimitExceededError,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


@tool
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> dict:
    """Run a web search"""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise ToolException("Web search is unavailable: configure TAVILY_API_KEY")
    if not query.strip() or not 1 <= max_results <= 20:
        raise ToolException("Provide a non-empty query and max_results between 1 and 20")
    try:
        return TavilyClient(api_key=api_key).search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
            timeout=15,
        )
    except (
        RequestException,
        BadRequestError,
        ForbiddenError,
        InvalidAPIKeyError,
        TimeoutError,
        UsageLimitExceededError,
    ) as error:
        logger.warning("Web search failed (%s)", type(error).__name__)
        raise ToolException("Web search provider is unavailable; try again later") from error


internet_search.handle_tool_error = True
