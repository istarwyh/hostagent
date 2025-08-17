from langchain_anthropic import ChatAnthropic
from deepagents.util.env_utils import from_env
from langchain_openai import ChatOpenAI 

def get_default_model():
    provider = from_env(["MODEL_PROVIDER", "LLM_PROVIDER"], default="OPENAI").lower()
    if provider.startswith("ANTHROPIC"):
        return get_anthropic_model()
    return get_openai_model()

def get_anthropic_model():
    model_name = from_env(["ANTHROPIC_MODEL_NAME"], default="claude-sonnet-4-20250514")
    print(model_name)
    return ChatAnthropic(model_name=model_name, max_tokens=64000)

def get_openai_model():
    model_name = from_env(
        ["OPENAI_MODEL_NAME", "OPENAI_MODEL", "OPENAI_CHAT_MODEL"],
        default="gpt-4o-mini",
    )
    print(model_name)
    return ChatOpenAI(model=model_name)
