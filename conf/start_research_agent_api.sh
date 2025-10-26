#!/usr/bin/env bash
set -euo pipefail

# Start Research Agent API server
# This script starts the FastAPI server for the Research Agent

# Get the project root directory (parent of conf/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Starting Research Agent API Server ==="
echo "Project root: $PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d .venv ]; then
  echo "ERROR: Virtual environment not found at $PROJECT_ROOT/.venv"
  echo "Please create a virtual environment first:"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Check if required packages are installed
if ! python -c "import fastapi" 2>/dev/null; then
  echo "ERROR: FastAPI not installed. Please run:"
  echo "  source .venv/bin/activate"
  echo "  pip install fastapi uvicorn"
  exit 1
fi

# Set Python path to include project root
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# Start the server
echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

python -m uvicorn src.facade.research_agent_api:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
