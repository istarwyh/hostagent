#!/usr/bin/env bash
set -euo pipefail

# Start Development Environment
# This script starts both frontend and backend in debug mode

# Get the project root directory (parent of conf/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOGS_DIR="$PROJECT_ROOT/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_PORT=2024
FRONTEND_PORT=3000
LOG_LEVEL="DEBUG"

# PIDs for cleanup
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo -e "\n${YELLOW}=== Shutting down services ===${NC}"

  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Stopping backend (PID: $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Stopping frontend (PID: $FRONTEND_PID)..."
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  # Kill any remaining processes on the ports
  lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
  lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true

  echo -e "${GREEN}Cleanup complete${NC}"
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

print_banner() {
  echo -e "${BLUE}"
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║           HostAgent Development Environment                  ║"
  echo "║                                                              ║"
  echo "║  Backend:  http://localhost:$BACKEND_PORT (LangGraph API)         ║"
  echo "║  Frontend: http://localhost:$FRONTEND_PORT (Next.js)               ║"
  echo "║                                                              ║"
  echo "║  Press Ctrl+C to stop all services                           ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

check_prerequisites() {
  echo -e "${YELLOW}=== Checking prerequisites ===${NC}"

  # Check backend directory
  if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}ERROR: Backend directory not found at $BACKEND_DIR${NC}"
    exit 1
  fi

  # Check frontend directory
  if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}ERROR: Frontend directory not found at $FRONTEND_DIR${NC}"
    exit 1
  fi

  # Check backend virtual environment
  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo -e "${RED}ERROR: Backend virtual environment not found${NC}"
    echo "Please create it first:"
    echo "  cd $BACKEND_DIR"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -e ."
    exit 1
  fi

  # Check frontend node_modules
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    (cd "$FRONTEND_DIR" && yarn install)
  fi

  # Create logs directory
  mkdir -p "$LOGS_DIR"

  echo -e "${GREEN}Prerequisites check passed${NC}"
}

start_backend() {
  echo -e "${YELLOW}=== Starting Backend (Debug Mode) ===${NC}"

  # Activate virtual environment and start backend
  (
    source "$BACKEND_DIR/.venv/bin/activate"
    cd "$BACKEND_DIR"
    export PYTHONPATH="$BACKEND_DIR:${PYTHONPATH:-}"
    export LOG_LEVEL="$LOG_LEVEL"

    python -m uvicorn src.facade.langgraph_api.main:app \
      --host 0.0.0.0 \
      --port $BACKEND_PORT \
      --reload \
      --log-level debug \
      2>&1 | tee "$LOGS_DIR/backend.log"
  ) &
  BACKEND_PID=$!

  echo -e "${GREEN}Backend started (PID: $BACKEND_PID)${NC}"

  # Wait for backend to be ready
  echo "Waiting for backend to be ready..."
  for i in {1..30}; do
    if curl -s "http://localhost:$BACKEND_PORT/ok" > /dev/null 2>&1; then
      echo -e "${GREEN}Backend is ready!${NC}"
      return 0
    fi
    sleep 1
  done

  echo -e "${RED}Backend failed to start within 30 seconds${NC}"
  exit 1
}

start_frontend() {
  echo -e "${YELLOW}=== Starting Frontend (Debug Mode) ===${NC}"

  (
    cd "$FRONTEND_DIR"

    # Set debug environment variables
    export NODE_ENV="development"
    export DEBUG="*"

    yarn dev 2>&1 | tee "$LOGS_DIR/frontend.log"
  ) &
  FRONTEND_PID=$!

  echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"

  # Wait for frontend to be ready
  echo "Waiting for frontend to be ready..."
  for i in {1..60}; do
    if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
      echo -e "${GREEN}Frontend is ready!${NC}"
      return 0
    fi
    sleep 1
  done

  echo -e "${YELLOW}Frontend may still be compiling...${NC}"
}

main() {
  print_banner
  check_prerequisites

  echo ""
  start_backend

  echo ""
  start_frontend

  echo ""
  echo -e "${GREEN}=== All services started ===${NC}"
  echo -e "Backend logs:  ${BLUE}$LOGS_DIR/backend.log${NC}"
  echo -e "Frontend logs: ${BLUE}$LOGS_DIR/frontend.log${NC}"
  echo ""
  echo -e "${YELLOW}Configure frontend settings:${NC}"
  echo "  - Deployment URL: http://localhost:$BACKEND_PORT"
  echo "  - Assistant ID: researchAgent"
  echo ""

  # Keep script running and wait for child processes
  wait
}

main "$@"
