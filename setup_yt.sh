#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

echo "[*] Installing yt-dlp into Python environment..."
source /root/rumble-uploader/venv/bin/activate
pip install yt-dlp -U

# Install ffmpeg for video/audio merging if not installed
apt update -y && apt install -y ffmpeg

chmod +x "$DIR/start_yt.sh"

# Create Desktop Shortcut
DESKTOP_DIR="/root/Desktop"
mkdir -p "$DESKTOP_DIR"

cat <<EOF > "$DESKTOP_DIR/YT_Downloader.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=YT Video Downloader
Comment=Download YouTube Channel Videos
Exec=bash -c "cd '$DIR' && source /root/rumble-uploader/venv/bin/activate && python3 gui.py"
Icon=video-x-generic
Terminal=true
StartupNotify=true
EOF

chmod +x "$DESKTOP_DIR/YT_Downloader.desktop"

echo "=========================================================="
echo " [OK] YT Video Downloader Installed on VPS Desktop! "
echo "=========================================================="
