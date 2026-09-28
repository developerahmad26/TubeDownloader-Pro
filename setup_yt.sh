#!/bin/bash
# ==========================================================
# TubeDownloader Pro - Safe VPS / RDP Setup Script
# Completely isolated: Uses its own dedicated virtual environment
# Zero impact on existing web software or other RDP tools.
# ==========================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=========================================================="
echo " [*] Setting up TubeDownloader Pro on VPS / RDP..."
echo "=========================================================="

SUDO=""
if [ "$EUID" -ne 0 ] && which sudo >/dev/null 2>&1; then
    SUDO="sudo"
fi

# 1. Ensure required system packages (Tkinter for GUI, FFmpeg, venv, Node.js, xclip for clipboard, unzip)
echo "[*] Checking system dependencies..."
$SUDO apt-get update -y || true
$SUDO apt-get install -y python3-tk python3-venv python3-pip ffmpeg nodejs xclip unzip || true

# 2. Create isolated Python virtual environment (No conflict with other apps)
if [ ! -d "$DIR/venv" ]; then
    echo "[*] Creating dedicated virtual environment at $DIR/venv..."
    python3 -m venv "$DIR/venv" || true
fi

# 3. Determine Python and Pip
if [ -f "$DIR/venv/bin/python" ]; then
    PYTHON_BIN="$DIR/venv/bin/python"
    PIP_BIN="$DIR/venv/bin/pip"
else
    PYTHON_BIN="python3"
    PIP_BIN="pip3"
fi

echo "[*] Installing requirements into isolated virtual environment..."
"$PIP_BIN" install --upgrade pip --quiet || true
"$PIP_BIN" install -r "$DIR/requirements.txt" || true

# Ensure git remote is updated to TubeDownloader-Pro
git remote set-url origin https://github.com/developerahmad26/TubeDownloader-Pro.git 2>/dev/null || true

# 4. Make all scripts executable
chmod +x "$DIR"/*.sh 2>/dev/null || true

# 5. Create Desktop Shortcut on RDP Desktop
DESKTOP_DIR="$HOME/Desktop"
if [ ! -d "$DESKTOP_DIR" ] && [ -d "/root/Desktop" ]; then
    DESKTOP_DIR="/root/Desktop"
fi
mkdir -p "$DESKTOP_DIR"

ICON_PATH="$DIR/assets/icon.png"
[ ! -f "$ICON_PATH" ] && ICON_PATH="video-x-generic"

cat <<EOF > "$DESKTOP_DIR/TubeDownloader_Pro.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=TubeDownloader Pro
Comment=Download YouTube Channel / Playlist / Single Videos
Exec=bash -c "cd '$DIR' && ./start.sh"
Icon=$ICON_PATH
Terminal=true
StartupNotify=true
Categories=AudioVideo;Network;
EOF

chmod +x "$DESKTOP_DIR/TubeDownloader_Pro.desktop"
which gio >/dev/null 2>&1 && gio set "$DESKTOP_DIR/TubeDownloader_Pro.desktop" metadata::trusted true 2>/dev/null || true

# Clean up old legacy shortcuts if present
rm -f "$DESKTOP_DIR/YT_Downloader.desktop" 2>/dev/null || true

echo "=========================================================="
echo " [OK] TubeDownloader Pro is ready on your RDP Desktop!"
echo " Double-click 'TubeDownloader Pro' icon on Desktop to run."
echo " Or run in terminal: ./start_yt.sh"
echo "=========================================================="
