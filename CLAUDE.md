# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is **deepagents**, a Python package that implements "deep agents" - LLM agents that can plan, spawn sub-agents, use a virtual file system, and handle complex multi-step tasks. The architecture is inspired by Claude Code and built on LangGraph.

## Project Structure

- `src/deepagents/`: Core library implementation
  - `graph.py`: Main agent creation functions (`create_deep_agent`, `async_create_deep_agent`)
  - `prompts.py`: Built-in system prompts that guide agent behavior
  - `tools.py`: Built-in tools (todos, virtual file system)
  - `sub_agent.py`: Sub-agent spawning and management
  - `state.py`: LangGraph state schema (`DeepAgentState`)
  - `interrupt.py`: Human-in-the-loop interrupt handling
  - `audit_tool_node.py`: Tool execution auditing

- `src/service/`: Service layer with specific agent implementations
- `src/facade/`: FastAPI endpoints exposing agents as APIs
- `src/client/`: Client libraries (e.g., Redis client)
- `examples/research/`: Complete research agent example with LangGraph deployment
- `src/test/`: Test files
- `docs/`: Documentation

## Common Development Commands

### Setup and Installation

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -e .

# For the research example specifically:
cd examples/research
./init_langgraph.sh
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest src/test/test_env_connectivity.py

# Run with verbose output
pytest -v
```

### Running the Research Agent Example

```bash
# Option 1: Via LangGraph (from examples/research/)
cd examples/research
source .venv/bin/activate
langgraph dev  # Starts LangGraph Studio

# Option 2: Via FastAPI (from project root)
./conf/start_research_agent_api.sh
# Server runs at http://localhost:8000
# Endpoints: /health, /research/invoke, /research/stream
```

### Testing API Connectivity

```bash
# Test OpenAI-compatible API connectivity (Moonshot/Kimi example)
python src/test/test_env_connectivity.py
```

## Key Architecture Concepts

### Deep Agent Pattern

A "deep agent" combines four components to handle complex tasks:

1. **Planning Tool** (`write_todos`): Allows agents to create task lists to stay organized across long-running tasks
2. **Sub-agents**: Spawning specialized agents for subtasks or context isolation
3. **Virtual File System**: Mock filesystem using LangGraph state (no actual file I/O)
4. **Detailed System Prompt**: Comprehensive instructions in `prompts.py` guide agent behavior

### Agent Creation

The main entry points are `create_deep_agent()` (sync) and `async_create_deep_agent()` (async):

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    tools=[your_tools],           # Custom tools
    instructions="...",            # Task-specific instructions
    model="claude-sonnet-4-20250514",  # Optional, defaults to Claude Sonnet
    subagents=[...],              # Optional custom sub-agents
    builtin_tools=[...],          # Optional: restrict built-in tools
    interrupt_config={...},       # Optional: human-in-the-loop
)
```

The agent is a LangGraph graph that can be invoked, streamed, and deployed.

### Built-in Tools

All deep agents have access to:
- `write_todos`: Task list management
- `write_file`, `read_file`, `edit_file`, `ls`: Virtual filesystem operations
- `Task` tool: Spawns sub-agents

The virtual filesystem exists only in LangGraph state (the `files` key), not on disk.

### Sub-agents

Two types of sub-agents:

1. **SubAgent**: Defined via dict with `name`, `description`, `prompt`, optional `tools` and `model_settings`
2. **CustomSubAgent**: Pre-built LangGraph graph with `name`, `description`, `graph`

Sub-agents provide "context quarantine" - keeping specialized work separate from main agent context.

### State Management

The `DeepAgentState` schema includes:
- `messages`: Conversation history
- `files`: Virtual filesystem (dict mapping filenames to content)
- Additional fields as needed by custom implementations

Access files after agent execution:
```python
result = agent.invoke({"messages": [...]})
final_files = result["files"]
```

### Human-in-the-Loop

Configure tools requiring approval via `interrupt_config`:
```python
agent = create_deep_agent(
    tools=[...],
    instructions="...",
    interrupt_config={
        "tool_name": True,  # Enable all interrupt options
        # OR fine-grained:
        "other_tool": {
            "allow_accept": True,
            "allow_edit": True,
            "allow_respond": True,
            "allow_ignore": False,
        }
    }
)
```

Requires a checkpointer (default is `MemorySaver`).

## Model Configuration

### Default Model

By default, agents use `claude-sonnet-4-20250514` (configured in `src/deepagents/model.py`).

### Custom Models

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="gpt-4",
    api_key="...",
    base_url="...",
)
agent = create_deep_agent(tools, instructions, model=model)
```

### Per-Subagent Models

Subagents can override the default model:
```python
subagent = {
    "name": "fast-agent",
    "description": "Quick analysis agent",
    "prompt": "...",
    "model_settings": {
        "model": "claude-3-5-haiku-20241022",
        "temperature": 0,
        "max_tokens": 8192
    }
}
```

## Testing Architecture

Test structure:
- Unit tests: `src/test/unit/`
- Integration tests: `src/test/integration/`
- Learning/exploratory tests: `src/test/learn/`

Test files use standard pytest conventions (`test_*.py`).

## Environment Variables

The `.env` file (gitignored) contains API keys:
- `TAVILY_API_KEY`: For the research agent's internet search
- `ANTHROPIC_API_KEY`: For Claude models
- `OPENAI_API_KEY`: For OpenAI models or compatible APIs

## Deployment

### LangGraph Platform

The research example includes `langgraph.json` for LangGraph deployment:
```json
{
  "dependencies": ["."],
  "graphs": {
    "researchAgent": "./research_agent.py:agent"
  },
  "env": ".env"
}
```

Deploy with: `langgraph deploy` or run locally with `langgraph dev`

### FastAPI Service

The facade layer (`src/facade/research_agent_api.py`) provides:
- `/health`: Health check
- `/research/invoke`: Synchronous invocation
- `/research/stream`: SSE streaming endpoint

Start via: `./conf/start_research_agent_api.sh`

## Research Agent Example

The complete example in `examples/research/research_agent.py` demonstrates:
- Internet search tool (Tavily)
- Two custom sub-agents: `research-agent` (focused research) and `critique-agent` (report review)
- Virtual file system usage (storing research in `question.txt` and `final_report.md`)
- Multi-step workflow: plan → research → draft → critique → revise → finalize

The agent automatically:
1. Breaks down complex research questions
2. Spawns parallel research sub-agents for different subtopics
3. Synthesizes findings into a structured markdown report
4. Self-critiques and improves the report
5. Formats output with proper citations

## Debugging and Logging

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

The codebase uses Python's standard logging throughout (`logger.info()`, etc.).

## Common Pitfalls

1. **Async vs Sync**: Use `async_create_deep_agent` when passing async tools (especially MCP tools)
2. **File System**: The virtual filesystem is in-memory only; files don't persist to disk
3. **Context Limits**: Deep agents can accumulate large context; use sub-agents to quarantine
4. **Interrupts**: Human-in-the-loop requires a checkpointer and currently only supports one interrupt at a time
5. **Model Settings**: Sub-agent `model_settings` can be either a dict of settings OR a model instance, but dict is preferred for serialization
