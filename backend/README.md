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
- Virtual environment tool (venv)

### Installation

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

### API Services

#### Starting the Research Agent API

```bash
# From the project root
../conf/start_research_agent_api.sh

# Or manually from backend directory
source .venv/bin/activate
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
python -m uvicorn src.facade.research_agent_api:app --reload
```

The API will be available at `http://localhost:8000` with endpoints:
- `GET /health` - Health check
- `POST /research/invoke` - Synchronous research invocation
- `POST /research/stream` - SSE streaming research endpoint

## Architecture

### Deep Agent Components

1. **Planning Tool** (`write_todos`): Task list management for complex workflows
2. **Sub-agents**: Spawn specialized agents for subtasks or context isolation
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
    instructions="Your custom instructions...",
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
