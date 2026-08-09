#!/bin/bash
# Run this after dropping in updated project files (e.g. after unzipping a
# new version ON TOP of this folder with `unzip -o`). It does NOT touch your
# .env, sentinel.db, or logs — those aren't part of the update package.
# Schema changes (new columns/tables) are applied automatically the next
# time the backend starts, so there's no need to delete the database.
#
# Self-healing: if the venv or .env got wiped out somehow (e.g. the whole
# project folder was deleted and re-unzipped instead of overwritten in
# place), this rebuilds them automatically instead of erroring out.
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
VENV_PIP="$VENV_DIR/bin/pip"
BACKEND_PLIST="$HOME/Library/LaunchAgents/com.sentinel.backend.plist"
FRONTEND_PLIST="$HOME/Library/LaunchAgents/com.sentinel.frontend.plist"

if [ ! -x "$VENV_PIP" ]; then
  echo "venv not found — rebuilding it now (this happens once, takes ~30s)..."
  python3 -m venv "$VENV_DIR"
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "backend/.env not found — creating it from .env.example."
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo ""
  echo "IMPORTANT: your API key is NOT in this new .env file — it has to be added again."
  echo "Opening it now so you can paste your key back in..."
  open -e "$BACKEND_DIR/.env" 2>/dev/null || true
  echo "Press Enter once you've pasted your key back in and saved the file."
  read -r _
fi

echo "Refreshing dependencies (safe no-op if nothing changed)..."
"$VENV_PIP" install -q -r "$BACKEND_DIR/requirements.txt"

if [ -f "$BACKEND_PLIST" ] && [ -f "$FRONTEND_PLIST" ]; then
  echo "Restarting background services..."
  launchctl unload "$BACKEND_PLIST" 2>/dev/null || true
  launchctl unload "$FRONTEND_PLIST" 2>/dev/null || true
  launchctl load "$BACKEND_PLIST"
  launchctl load "$FRONTEND_PLIST"
  echo ""
  echo "Done. Any schema changes will be applied automatically on this startup —"
  echo "check logs/backend.log if you want to confirm ('Migration: added column ...' lines)."
  echo "Dashboard: http://localhost:8080"
else
  echo ""
  echo "Background services aren't installed yet — registering them now..."
  "$PROJECT_DIR/scripts/install_background_service.sh"
fi
