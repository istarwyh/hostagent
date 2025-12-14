#!/usr/bin/env bash
set -euo pipefail

# Start Research Agent API server
# This script starts the FastAPI server for the Research Agent

# Get the project root directory (parent of conf/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "=== Starting Research Agent API Server ==="
echo "Project root: $PROJECT_ROOT"
echo "Backend dir: $BACKEND_DIR"

# Check if backend directory exists
if [ ! -d "$BACKEND_DIR" ]; then
  echo "ERROR: Backend directory not found at $BACKEND_DIR"
  exit 1
fi

# Check if virtual environment exists in backend directory
if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "ERROR: Virtual environment not found at $BACKEND_DIR/.venv"
  echo "Please create a virtual environment first:"
  echo "  cd $BACKEND_DIR"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -e ."
  exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$BACKEND_DIR/.venv/bin/activate"

# Check if required packages are installed
if ! python -c "import fastapi" 2>/dev/null; then
  echo "ERROR: FastAPI not installed. Please run:"
  echo "  cd $BACKEND_DIR"
  echo "  source .venv/bin/activate"
  echo "  pip install -e ."
  exit 1
fi

# Change to backend directory and set Python path
cd "$BACKEND_DIR"
export PYTHONPATH="$BACKEND_DIR:${PYTHONPATH:-}"

# Start the server
echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop the server"
echo ""

python -m uvicorn src.facade.research_agent_api:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload
