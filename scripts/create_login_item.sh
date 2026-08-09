#!/bin/bash
# Creates a macOS Login Item app using AppleScript that starts SENTINEL
# on login without using launchd at all.
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
APP_PATH="$HOME/Applications/SENTINEL.app"

mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Write the launcher script
cat > "$APP_PATH/Contents/MacOS/SENTINEL" << LAUNCHER
#!/bin/bash
exec "$VENV_PYTHON" "$PROJECT_DIR/scripts/start_daemon.py"
LAUNCHER

chmod +x "$APP_PATH/Contents/MacOS/SENTINEL"

# Write Info.plist
cat > "$APP_PATH/Contents/Info.plist" << 'INFOPLIST'
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>SENTINEL</string>
    <key>CFBundleIdentifier</key><string>com.sentinel.osint</string>
    <key>CFBundleName</key><string>SENTINEL</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleVersion</key><string>1.0</string>
    <key>LSBackgroundOnly</key><true/>
    <key>LSUIElement</key><true/>
</dict>
</plist>
INFOPLIST

echo ""
echo "SENTINEL.app created at: $APP_PATH"
echo ""
echo "Now add it to Login Items:"
echo "  System Settings → General → Login Items → + → choose SENTINEL.app"
echo "  (it's in ~/Applications/)"
echo ""
echo "To start it RIGHT NOW without waiting for login:"
echo "  open '$APP_PATH'"
echo ""
echo "To stop it:"
echo "  pkill -f 'python run.py'"
echo "  pkill -f 'http.server 8080'"
