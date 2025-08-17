from dotenv import load_dotenv
import os
# Load and validate environment variables
def load_and_validate_env() -> None:
    # Try to load variables from a .env file if present
    load_dotenv()
    provider = (
        os.environ.get("MODEL_PROVIDER")
        or os.environ.get("LLM_PROVIDER")
        or "ANTHROPIC"
    ).lower()
    required = ["TAVILY_API_KEY"]
    if provider.startswith("openai"):
        required.append("OPENAI_API_KEY")
    else:
        required.append("ANTHROPIC_API_KEY")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Set them in your shell or a .env file next to this script or at project root."
        )

def from_env(keys: list[str], default: str) -> str:
    for key in keys:
        if os.environ.get(key):
            return os.environ[key]
    return default