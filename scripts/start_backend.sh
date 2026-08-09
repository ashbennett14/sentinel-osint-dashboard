#!/bin/bash
# Wrapper script for launchd — sets up the environment properly before
# starting the backend. Running Python directly from launchd can fail
# silently due to missing PATH, missing HOME, or other env differences
# vs. an interactive terminal session. This wrapper sources the correct
# environment explicitly, then starts the backend.

set -e

# Resolve project root relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"

# Set environment variables the backend needs
export PATH="$BACKEND_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
export PYTHONUNBUFFERED=1

# Load .env file if present so environment variables are available
if [ -f "$BACKEND_DIR/.env" ]; then
    set -a
    source "$BACKEND_DIR/.env"
    set +a
fi

# Run the backend
cd "$BACKEND_DIR"
exec "$VENV_PYTHON" run.py
