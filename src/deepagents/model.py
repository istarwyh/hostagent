from langchain_anthropic import ChatAnthropic
from deepagents.util.env_utils import from_env
from langchain_openai import ChatOpenAI 
import logging
logger = logging.getLogger(__name__)

def get_default_model():
    provider = from_env(["MODEL_PROVIDER", "LLM_PROVIDER"], default="OPENAI").lower()
    logger.info(f"Using model provider: {provider}")
    if provider.startswith("anthropic"):
        return get_anthropic_model()
    return get_openai_model()

def get_anthropic_model():
    model_name = from_env([
        "ANTHROPIC_MODEL_NAME",
        "ANTHROPIC_MODEL",
    ], default="claude-3-7-sonnet-latest")
    # Output tokens budget; Anthropic models typically support <= 8k output tokens.
    # Allow override via env, but clamp to a safe range to avoid invalid requests.
    max_tokens_str = from_env(["ANTHROPIC_MAX_TOKENS"], default="4096")
    try:
        max_tokens = int(max_tokens_str)
    except ValueError:
        max_tokens = 4096
    # Clamp to [1, 8192]
    max_tokens = max(1, min(8192, max_tokens))
    logger.info(f"Initializing Anthropic model: {model_name} with max_tokens={max_tokens}")
    return ChatAnthropic(model=model_name, max_tokens=max_tokens)

def get_openai_model():
    model_name = from_env(
        ["OPENAI_MODEL_NAME", "OPENAI_MODEL", "OPENAI_CHAT_MODEL"],
        default="gpt-4o-mini",
    )
    return ChatOpenAI(model=model_name)
