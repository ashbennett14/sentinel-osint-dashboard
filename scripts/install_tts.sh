#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TTS_ENV="$PROJECT_DIR/backend/tts-venv"

if ! command -v python3.12 >/dev/null 2>&1; then
  echo "Python 3.12 is required for the local neural voice." >&2
  exit 1
fi

python3.12 -m venv "$TTS_ENV"
"$TTS_ENV/bin/python" -m pip install --upgrade pip
"$TTS_ENV/bin/python" -m pip install -r "$PROJECT_DIR/backend/tts-requirements.txt"
echo "Local neural voice installed. Model weights download automatically on first use."
