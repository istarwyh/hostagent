"""LangGraph API 契约校验脚本

在开发 / CI 阶段运行，用于提前发现后端与 `@langchain/langgraph-sdk`
之间的协议不匹配问题。

用法示例：

  cd backend
  source .venv/bin/activate
  python ../docs/tech/202512/check_langgraph_contract.py \
    --base-url http://localhost:2024
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Dict, List

import requests


@dataclass
class ThreadStateContract:
  """最小 ThreadState 结构契约，用于运行期校验。"""

  values: Dict[str, Any]
  next: List[str]
  checkpoint: Dict[str, Any]
  metadata: Dict[str, Any]
  created_at: str | None
  parent_checkpoint: Dict[str, Any] | None
  tasks: List[Any]

  @classmethod
  def validate(cls, obj: Dict[str, Any]) -> None:
    """抛异常而不是返回 bool，便于在 CI 中快速失败。"""

    if not isinstance(obj, dict):
      raise AssertionError("ThreadState must be an object")

    for field in [
      "values",
      "next",
      "checkpoint",
      "metadata",
      "created_at",
      "parent_checkpoint",
      "tasks",
    ]:
      if field not in obj:
        raise AssertionError(f"ThreadState missing field: {field}")

    if not isinstance(obj["values"], dict):
      raise AssertionError("ThreadState.values must be a dict")
    if not isinstance(obj["next"], list):
      raise AssertionError("ThreadState.next must be a list")
    if not isinstance(obj["checkpoint"], dict):
      raise AssertionError("ThreadState.checkpoint must be a dict")
    if not isinstance(obj["metadata"], dict):
      raise AssertionError("ThreadState.metadata must be a dict")
    if obj["created_at"] is not None and not isinstance(
      obj["created_at"], str,
    ):
      raise AssertionError("ThreadState.created_at must be str | None")
    if obj["parent_checkpoint"] is not None and not isinstance(
      obj["parent_checkpoint"], dict,
    ):
      raise AssertionError("ThreadState.parent_checkpoint must be dict | None")
    if not isinstance(obj["tasks"], list):
      raise AssertionError("ThreadState.tasks must be a list")

    cp = obj["checkpoint"]
    for f in ["thread_id", "checkpoint_ns", "checkpoint_id", "checkpoint_map"]:
      if f not in cp:
        raise AssertionError(f"checkpoint missing field: {f}")


def _request_json(base_url: str, method: str, path: str, **kwargs: Any) -> Any:
  url = f"{base_url.rstrip('/')}{path}"
  resp = requests.request(method, url, timeout=30, **kwargs)
  try:
    resp.raise_for_status()
  except Exception as exc:  # pragma: no cover - 简单脚本
    raise SystemExit(f"Request failed {method} {url}: {exc}\nBody: {resp.text}") from exc
  if "application/json" in resp.headers.get("Content-Type", ""):
    return resp.json()
  return resp.text


def check_health(base_url: str) -> None:
  data = _request_json(base_url, "GET", "/ok")
  assert isinstance(data, dict), "health response must be JSON object"
  assert data.get("status") == "ok", "health status must be 'ok'"


def check_assistants(base_url: str) -> None:
  payload = {"graph_id": "researchAgent", "limit": 100}
  data = _request_json(
    base_url,
    "POST",
    "/assistants/search",
    json=payload,
    headers={"Content-Type": "application/json"},
  )
  assert isinstance(data, list), "assistants.search must return a list"
  assert data, "assistants.search must return at least one assistant"

  system_assistants = [
    a for a in data if a.get("metadata", {}).get("created_by") == "system"
  ]
  assert (
    system_assistants
  ), "must have at least one assistant with metadata.created_by == 'system'"

  for a in system_assistants:
    assert (
      a.get("graph_id") == "researchAgent"
    ), "default system assistant.graph_id must equal 'researchAgent'"


def check_thread_stream_and_history(base_url: str) -> None:
  # 1) 创建线程
  thread = _request_json(
    base_url,
    "POST",
    "/threads",
    json={},
    headers={"Content-Type": "application/json"},
  )
  assert isinstance(thread, dict), "threads.create must return an object"
  thread_id = thread.get("thread_id")
  assert isinstance(thread_id, str) and thread_id, "thread_id must be non-empty string"

  # 2) 触发一次流式运行
  stream_payload = {
    "assistant_id": "researchAgent",
    "input": {"messages": [{"role": "user", "content": "契约自检 ping"}]},
    "stream_mode": ["updates"],
  }
  # 这里只验证 HTTP 层是否 2xx，不完全消费 SSE 流内容
  url = f"{base_url.rstrip('/')}/threads/{thread_id}/runs/stream"
  resp = requests.post(
    url,
    json=stream_payload,
    headers={"Content-Type": "application/json"},
    timeout=60,
    stream=True,
  )
  try:
    resp.raise_for_status()
  except Exception as exc:  # pragma: no cover
    raise SystemExit(f"stream_run failed: {exc}\nBody: {resp.text}") from exc

  # 简单消费几行，避免阻塞
  for _ in range(3):
    _ = resp.raw.readline()

  # 3) 拉取 history，并校验结构
  history = _request_json(
    base_url,
    "POST",
    f"/threads/{thread_id}/history",
    json={"limit": 10},
    headers={"Content-Type": "application/json"},
  )
  assert isinstance(history, list), "threads.history must return a list"
  assert (
    history
  ), "threads.history must return at least one ThreadState after streaming run"

  for idx, state in enumerate(history):
    try:
      ThreadStateContract.validate(state)
    except AssertionError as exc:  # pragma: no cover
      pretty = json.dumps(state, ensure_ascii=False, indent=2)
      raise SystemExit(
        f"Invalid ThreadState at index {idx}: {exc}\nObject: {pretty}"
      ) from exc


def main() -> None:
  parser = argparse.ArgumentParser(
    description="Check LangGraph API contract against SDK expectations.",
  )
  parser.add_argument(
    "--base-url",
    default="http://localhost:2024",
    help="Base URL of the LangGraph-compatible backend.",
  )
  args = parser.parse_args()

  base_url = args.base_url
  print(f"[check] base_url = {base_url}")

  print("[check] health ...", end=" ")
  check_health(base_url)
  print("OK")

  print("[check] assistants ...", end=" ")
  check_assistants(base_url)
  print("OK")

  print("[check] thread stream + history ...", end=" ")
  check_thread_stream_and_history(base_url)
  print("OK")

  print("All LangGraph API contract checks passed.")


if __name__ == "__main__":  # pragma: no cover
  main()
