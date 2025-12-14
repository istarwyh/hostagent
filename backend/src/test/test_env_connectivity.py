import sys

from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam


def test_chat() -> None:
    model = "kimi-k2-turbo-preview"
    api_key = "sk-GPjbDWRs9RUyIsuvQLoA3HEdsVgayokEPkbUJq5HAKl1RdNb"
    base_url = "https://api.moonshot.cn/v1"

    client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
    resp = client.chat.completions.create(
        model=model,
        messages=[
            ChatCompletionSystemMessageParam(role="system", content="You are a concise assistant."),
            ChatCompletionUserMessageParam(role="user", content="Reply with the single word: pong"),
        ],
        max_tokens=5,
        temperature=0,
    )

    content = resp.choices[0].message.content if resp.choices else None
    print("Connectivity OK")
    print(f"model={model}")
    print(f"base_url={base_url}")
    print(f"sample_reply={content!r}")


if __name__ == "__main__":
    try:
        test_chat()
    except Exception as e:
        print(f"[FAIL] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
