#!/usr/bin/env bash
set -euo pipefail

# One-click initializer for examples/research
# - Creates local .venv (Python venv)
# - Installs requirements (with langgraph-cli pinned)
# - Verifies CLI resolution and versions

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

PY_BIN="${PY_BIN:-python3}"

echo "[1/5] Creating venv at $HERE/.venv (if not exists)"
if [ ! -d .venv ]; then
  "$PY_BIN" -m venv .venv
fi

echo "[2/5] Activating venv"
# shellcheck disable=SC1091
source ./.venv/bin/activate

# Ensure pip is up-to-date to avoid resolver quirks
echo "[3/5] Upgrading pip and installing requirements"
python -m pip install --upgrade pip
python -m pip install --requirement requirements.txt

# Install the local package in editable mode so code changes under src/ are picked up immediately
echo "[3.5/5] Installing local package in editable mode (-e ../..)"
python -m pip install -e ../..

# Optional: reinstall explicitly if you want to force pinned version resolution
# python -m pip install --upgrade "langgraph-cli[inmem]==0.4.4"

# Clear shell command hash to avoid stale resolution
hash -r || true

echo "[4/5] Verifying CLI resolution"
echo "python: $(python -c 'import sys; print(sys.executable)')"
echo "langgraph path: $(command -v langgraph || true)"

set +e
LG_VER=$(langgraph --version 2>/dev/null)
LG_WHICH=$(command -v langgraph 2>/dev/null)
set -e

echo "[5/5] langgraph --version => ${LG_VER:-<not found>}"

# Sanity checks
if [[ -z "${LG_WHICH:-}" ]]; then
  echo "ERROR: langgraph not found on PATH after install." >&2
  echo "Hint: Ensure this script is run from examples/research and that .venv/bin is active." >&2
  exit 1
fi

# Expect version to be 0.4.x as pinned
if [[ "$LG_VER" != *"0.4."* ]]; then
  echo "WARNING: Detected langgraph version is not 0.4.x: $LG_VER" >&2
  echo "It may be influenced by another env or PATH. Current path: $PATH" >&2
  echo "Resolution: run '. ./.venv/bin/activate' and re-run this script, or call ./.venv/bin/langgraph directly." >&2
else
  echo "OK: langgraph resolved to $LG_VER at $LG_WHICH"
fi

echo "Done. To use this environment now, run:"
echo "  source ./.venv/bin/activate"
echo "Then run your commands, e.g.:"
echo "  langgraph --version"
