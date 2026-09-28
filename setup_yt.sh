#!/bin/bash
set -e

# ==========================================================
# YouTube Video Downloader - Safe VPS / RDP Setup Script
# Completely isolated: Uses its own dedicated virtual environment
# Zero impact on existing web software or other RDP tools.
# ==========================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "=========================================================="
echo " [*] Setting up YouTube Video Downloader on VPS / RDP..."
echo "=========================================================="

# 1. Ensure required system packages (Tkinter for GUI, FFmpeg, venv)
echo "[*] Checking system dependencies..."
apt update -y
apt install -y python3-tk python3-venv ffmpeg

# 2. Create isolated Python virtual environment (No conflict with other apps)
if [ ! -d "$DIR/venv" ]; then
    echo "[*] Creating dedicated virtual environment..."
    python3 -m venv "$DIR/venv"
fi

echo "[*] Activating virtual environment & installing requirements..."
source "$DIR/venv/bin/activate"
pip install --upgrade pip
pip install -r "$DIR/requirements.txt"

# 3. Make start script executable
chmod +x "$DIR/start_yt.sh"

# 4. Create Desktop Shortcut on RDP Desktop
DESKTOP_DIR="$HOME/Desktop"
if [ ! -d "$DESKTOP_DIR" ] && [ -d "/root/Desktop" ]; then
    DESKTOP_DIR="/root/Desktop"
fi
mkdir -p "$DESKTOP_DIR"

cat <<EOF > "$DESKTOP_DIR/YT_Downloader.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=YT Video Downloader
Comment=Download YouTube Channel / Playlist / Single Videos
Exec=bash -c "cd '$DIR' && source '$DIR/venv/bin/activate' && python3 main.py"
Icon=video-x-generic
Terminal=false
StartupNotify=true
EOF

chmod +x "$DESKTOP_DIR/YT_Downloader.desktop"

echo "=========================================================="
echo " [OK] YouTube Video Downloader is ready on RDP Desktop!"
echo " Double-click 'YT Video Downloader' icon on Desktop to run."
echo "=========================================================="
