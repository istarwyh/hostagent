# DeepAgents Backend

This directory contains the backend implementation of the deepagents library - a Python package that implements "deep agents" with planning, sub-agent spawning, and virtual file systems built on LangGraph.

## Project Structure

```
backend/
├── src/
│   ├── deepagents/          # Core library implementation
│   │   ├── graph.py         # Main agent creation functions
│   │   ├── prompts.py       # Built-in system prompts
│   │   ├── tools.py         # Built-in tools (todos, virtual FS)
│   │   ├── sub_agent.py     # Sub-agent spawning
│   │   ├── state.py         # LangGraph state schema
│   │   ├── interrupt.py     # Human-in-the-loop handling
│   │   └── ...
│   ├── service/             # Service layer implementations
│   ├── facade/              # FastAPI endpoints
│   ├── client/              # Client libraries (Redis, etc.)
│   └── test/                # Test files
├── pyproject.toml           # Python project configuration
└── .env                     # Environment variables (not in git)
```

## Setup

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Installation

**Using uv (recommended)**:
```bash
# From the backend directory
cd backend

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On macOS/Linux (optional with uv)
uv pip install -e ".[dev]"  # Install all dependencies including dev tools
```

**Using pip (alternative)**:
```bash
# From the backend directory
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or on Windows:
# .venv\Scripts\activate

# Install the package in editable mode
pip install -e .
```

### Environment Variables

Create a `.env` file in the backend directory with:

```bash
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here
TAVILY_API_KEY=your_tavily_key_here  # For research agent
```

The API starts and exposes liveness, assistant discovery, and thread management
without provider keys. Agent instances are created on first use. A run without
the selected model provider's key returns HTTP 503 before SSE starts; unknown
assistants return 404 and invalid stream modes return 422. Web search requires
`TAVILY_API_KEY`, uses a 15-second timeout, and reports provider failures as tool
errors. Execution failures after streaming starts produce an `error` SSE event
with a run ID; internal exception details remain in server logs.

Run the local API regression suite without credentials or external services:

```bash
pytest src/test/test_api_errors.py
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest src/test/test_env_connectivity.py

# Run with verbose output
pytest -v

# Run specific test directory
pytest src/test/unit/
```

### Code Structure

- **Core Library** (`src/deepagents/`): The main deepagents package that can be installed via pip
- **Service Layer** (`src/service/`): Business logic and agent implementations
- **Facade Layer** (`src/facade/`): FastAPI REST API endpoints
- **Client Layer** (`src/client/`): External service clients (Redis, etc.)

### Start the API

From `backend/`, run `.venv/bin/python -m uvicorn src.facade.langgraph_api.main:app --port 2024`.
The health endpoint is `GET /ok`; assistant discovery is `POST /assistants/search`.
Start the frontend separately with `cd frontend && yarn dev` from the repository root.

## LangChain v1 migration

The core follows upstream master 8907f04: `create_agent` plus todo, filesystem,
subagent, summarization, prompt caching, patch-tool-call and human-review middleware.
Both `invoke` and `ainvoke` use the same compiled graph. Domain agents register
configuration at startup and construct provider clients only on the first run.
Registry subagents use `system_prompt`, actual tool objects, and `runnable` for a
precompiled subagent; `instructions` remains the application AgentConfig field.

Internally files retain upstream FileData metadata and reducers. The API converts
contents to the frontend's text-file contract in streams, thread state and history.
Human-review decisions travel through `command.resume`; complete decision batches
keep action order, including repeated calls to the same tool. State/history include
real pending tasks so interrupted threads can reconnect. Thread state updates are
still explicitly unsupported (HTTP 501), rather than pretending to save edits.

Set `HOSTAGENT_AUDIT_DIR` (or AgentConfig.extra_config.audit_dir) to opt into v1
per-tool auditing for the main agent and its subagents. Logs contain tool inputs and
outputs: choose local access/retention accordingly. Auditing preserves tool results
and exceptions, uses unique filenames and serialized summary writes, and is off
when no directory is configured. The old SimpleAuditToolNode remains for the
existing learning/integration examples; production uses middleware.

Run offline regression checks without provider credentials:

```bash
.venv/bin/python -m pytest src/test/test_api_errors.py src/test/test_logging_system.py src/test/test_v1_migration.py src/test/test_audit_middleware.py
# Upstream local middleware tests only instantiate an Anthropic client; no API call:
ANTHROPIC_API_KEY=local-construction-placeholder OPENAI_API_KEY=local-construction-placeholder .venv/bin/python -m pytest tests/test_middleware.py
```

`tests/integration_tests/` retains upstream live-model tests, which require actual
provider access and are not part of the offline suite. The local migration suite
uses deterministic chat models with real create_agent graphs, HTTP routes, tools,
checkpoints, and interrupts. It does not verify external LLM, Tavily or Redis service
availability. This experiment is run from its complete checkout; standalone wheel
or repository-external import validation is outside its scope.

The monorepo uses `backend/pyproject.toml` for setup; the upstream root-only uv.lock
was not carried over because it does not describe these API/development dependencies.

## Architecture

### Deep Agent Components

1. **Planning Tool** (`write_todos`): Task list management for complex workflows
2. **Sub-agents**: Spawn specialized agents through SubAgentMiddleware
3. **Virtual File System**: Mock filesystem using LangGraph state (no disk I/O)
4. **System Prompt**: Detailed instructions in `src/deepagents/prompts.py`

### Model Configuration

Default model: `claude-sonnet-4-20250514` (configured in `src/deepagents/model.py`)

Custom models can be passed to `create_deep_agent()` or configured per-subagent.

## Common Tasks

### Adding a New Tool

1. Define your tool function in the appropriate module
2. Pass it to `create_deep_agent(tools=[your_tool])`

### Creating a Custom Agent

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    tools=[your_tools],
    system_prompt="Your custom instructions...",
    model="claude-sonnet-4-20250514",  # optional
    subagents=[...],  # optional
)
```

### Debugging

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Documentation

For full documentation, see:
- Main README: `../README.md`
- Examples: `../examples/`
- Technical docs: `../docs/tech/`

## Troubleshooting

### Import Errors

If you encounter import errors, ensure:
1. You're in the activated virtual environment
2. The package is installed: `pip install -e .`
3. PYTHONPATH is set correctly for development

### API Connection Issues

Test connectivity with:
```bash
python src/test/test_env_connectivity.py
```
