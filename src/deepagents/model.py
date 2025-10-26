from langchain_anthropic import ChatAnthropic
from langchain_core.utils import from_env
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger(__name__)


def get_default_model():
    provider = from_env(["OPENAI_BASE_URL", "ANTHROPIC_BASE_URL"], default="https://api.moonshot.cn/v1")().lower()
    logger.info(f"Using model provider url: {provider}")
    if "anthropic" in provider:
        return get_anthropic_model()
    return get_openai_model()


def get_anthropic_model():
    model_name = from_env(["ANTHROPIC_MODEL_NAME"], default="claude-3-7-sonnet-latest")()
    return ChatAnthropic(model_name=model_name, timeout=60000, stop=None)


def get_openai_model():
    model_name = from_env(["OPENAI_MODEL_NAME"], default="kimi-k2-turbo-preview")()
    return ChatOpenAI(model=model_name)
