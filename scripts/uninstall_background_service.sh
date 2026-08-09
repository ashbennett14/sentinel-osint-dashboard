#!/bin/bash
# Stops and removes the SENTINEL background services installed by
# install_background_service.sh.
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
BACKEND_PLIST="$LAUNCH_AGENTS/com.sentinel.backend.plist"
FRONTEND_PLIST="$LAUNCH_AGENTS/com.sentinel.frontend.plist"

launchctl unload "$BACKEND_PLIST" 2>/dev/null || true
launchctl unload "$FRONTEND_PLIST" 2>/dev/null || true
rm -f "$BACKEND_PLIST" "$FRONTEND_PLIST"

echo "SENTINEL background services stopped and removed."
echo "(Your project files, database, and .env are untouched.)"
