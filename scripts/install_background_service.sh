#!/bin/bash
# Installs SENTINEL as a background service on macOS using launchd, so it
# starts automatically at login and keeps running without a Terminal
# window open. Run this ONCE after your normal setup (venv created,
# dependencies installed, .env configured).
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

if [ ! -x "$VENV_PYTHON" ]; then
  echo "Could not find $VENV_PYTHON"
  echo "Run the normal setup first (create the venv + pip install) before installing the background service."
  exit 1
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "Warning: $BACKEND_DIR/.env not found. The backend will start but won't be able to"
  echo "generate synopses/briefs until you create it (cp .env.example .env and add your API key)."
fi

mkdir -p "$LOG_DIR"
mkdir -p "$LAUNCH_AGENTS"

BACKEND_PLIST="$LAUNCH_AGENTS/com.sentinel.backend.plist"
FRONTEND_PLIST="$LAUNCH_AGENTS/com.sentinel.frontend.plist"

cat > "$BACKEND_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.sentinel.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PYTHON</string>
        <string>run.py</string>
    </array>
    <key>WorkingDirectory</key><string>$BACKEND_DIR</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$LOG_DIR/backend.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/backend.err.log</string>
</dict>
</plist>
PLIST

cat > "$FRONTEND_PLIST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.sentinel.frontend</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_PYTHON</string>
        <string>-m</string>
        <string>http.server</string>
        <string>8080</string>
    </array>
    <key>WorkingDirectory</key><string>$FRONTEND_DIR</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>$LOG_DIR/frontend.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/frontend.err.log</string>
</dict>
</plist>
PLIST

# Unload first in case this is a re-install, then load fresh.
launchctl unload "$BACKEND_PLIST" 2>/dev/null || true
launchctl unload "$FRONTEND_PLIST" 2>/dev/null || true
launchctl load "$BACKEND_PLIST"
launchctl load "$FRONTEND_PLIST"

echo ""
echo "Installed. SENTINEL will now:"
echo "  - start automatically whenever you log in to this Mac"
echo "  - keep running in the background (no Terminal window needed)"
echo "  - restart itself automatically if it crashes"
echo ""
echo "Open the dashboard any time at: http://localhost:8080"
echo "Logs are in: $LOG_DIR"
echo ""
echo "To stop/remove the background service later, run: scripts/uninstall_background_service.sh"
