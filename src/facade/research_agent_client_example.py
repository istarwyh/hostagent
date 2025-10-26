"""
Example client for Research Agent API.
Demonstrates how to use sync, async, and streaming endpoints.
"""

import asyncio
import httpx
import json
from typing import AsyncIterator


class ResearchAgentClient:
    """Client for interacting with Research Agent API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def invoke(self, query: str, thread_id: str = None) -> dict:
        """
        Synchronous invocation - waits for complete result.

        Args:
            query: The research query
            thread_id: Optional thread ID for conversation continuity

        Returns:
            Complete research result
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.post(
                f"{self.base_url}/research/invoke",
                json={"query": query, "thread_id": thread_id},
                timeout=300.0  # 5 minutes timeout
            )
            response.raise_for_status()
            return response.json()

    async def stream_events(self, query: str, thread_id: str = None) -> AsyncIterator[dict]:
        """
        Stream events from agent execution.

        Args:
            query: The research query
            thread_id: Optional thread ID for conversation continuity

        Yields:
            Event dictionaries as they occur
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/research/stream",
                json={"query": query, "thread_id": thread_id},
                timeout=300.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        try:
                            event = json.loads(data)
                            yield event
                        except json.JSONDecodeError:
                            continue

    async def stream_updates(self, query: str, thread_id: str = None) -> AsyncIterator[dict]:
        """
        Stream state updates from agent.

        Args:
            query: The research query
            thread_id: Optional thread ID for conversation continuity

        Yields:
            State update dictionaries
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/research/stream-updates",
                json={"query": query, "thread_id": thread_id},
                timeout=300.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        try:
                            event = json.loads(data)
                            yield event
                        except json.JSONDecodeError:
                            continue

    async def get_state(self, thread_id: str) -> dict:
        """
        Get current state for a thread.

        Args:
            thread_id: Thread ID to query

        Returns:
            Current state dictionary
        """
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(
                f"{self.base_url}/research/state/{thread_id}",
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> dict:
        """Check API health."""
        async with httpx.AsyncClient(trust_env=False) as client:
            response = await client.get(f"{self.base_url}/health", timeout=10.0)
            response.raise_for_status()
            return response.json()


# Example usage
async def example_sync_invocation():
    """Example: Synchronous invocation."""
    print("=== Sync Invocation Example ===")
    client = ResearchAgentClient()

    result = await client.invoke(
        query="你好，我是晓灰！",
        thread_id="example-thread-1"
    )

    print(f"Result: {json.dumps(result, indent=2)}")


async def example_streaming():
    """Example: Streaming events."""
    print("\n=== Streaming Example ===")
    client = ResearchAgentClient()

    async for event in client.stream_events(
        query="你好，我是晓灰！",
        thread_id="example-thread-2"
    ):
        if event["event"] == "done":
            print("Stream completed!")
            break
        elif event["event"] == "error":
            print(f"Error: {event['data']}")
            break
        else:
            print(f"Event: {event['event']}")


async def example_state_updates():
    """Example: Streaming state updates."""
    print("\n=== State Updates Example ===")
    client = ResearchAgentClient()

    async for update in client.stream_updates(
        query="你好，我是晓灰！",
        thread_id="example-thread-3"
    ):
        if update["event"] == "done":
            print("Updates completed!")
            break
        elif update["event"] == "error":
            print(f"Error: {update['data']}")
            break
        else:
            print(f"Update: {json.dumps(update['data'], indent=2, default=str)}")


async def example_get_state():
    """Example: Get state for a thread."""
    print("\n=== Get State Example ===")
    client = ResearchAgentClient()

    state = await client.get_state(thread_id="example-thread-1")
    print(f"State: {json.dumps(state, indent=2, default=str)}")


async def example_health_check():
    """Example: Health check."""
    print("\n=== Health Check Example ===")
    client = ResearchAgentClient()

    health = await client.health_check()
    print(f"Health: {json.dumps(health, indent=2)}")


async def main():
    """Run all examples."""
    try:
        await example_health_check()
        await example_sync_invocation()
        await example_streaming()
        await example_state_updates()
        await example_get_state()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
