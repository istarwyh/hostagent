"""Optional live model smoke test; never runs during ordinary offline validation."""

import os
import sys

import pytest
from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam


def _live_test_enabled() -> bool:
    return os.getenv("HOSTAGENT_RUN_LIVE_TESTS") == "1" and bool(os.getenv("OPENAI_API_KEY"))


@pytest.mark.integration
def test_chat() -> None:
    if not _live_test_enabled():
        pytest.skip("Set HOSTAGENT_RUN_LIVE_TESTS=1 and OPENAI_API_KEY to opt into a live call")
    model = os.getenv("OPENAI_MODEL_NAME", "kimi-k2-turbo-preview")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.moonshot.cn/v1")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url.rstrip("/"))
    response = client.chat.completions.create(
        model=model,
        messages=[
            ChatCompletionSystemMessageParam(role="system", content="You are a concise assistant."),
            ChatCompletionUserMessageParam(role="user", content="Reply with the single word: pong"),
        ],
        max_tokens=5,
        temperature=0,
    )
    content = response.choices[0].message.content if response.choices else None
    assert content and content.strip().lower() == "pong"
    print("Connectivity OK")


if __name__ == "__main__":
    if not _live_test_enabled():
        print(
            "Live test disabled: configure OPENAI_API_KEY and explicitly set HOSTAGENT_RUN_LIVE_TESTS=1",
            file=sys.stderr,
        )
        sys.exit(2)
    try:
        test_chat()
    except Exception as error:
        print(
            f"Connectivity failed ({type(error).__name__}); provider details omitted",
            file=sys.stderr,
        )
        sys.exit(1)
