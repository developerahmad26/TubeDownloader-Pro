#!/bin/bash
# ==========================================================
# TubeDownloader Pro - VPS Automatic Migration & Rename Script
# ==========================================================

echo "=========================================================="
echo " [*] TubeDownloader Pro VPS Migration Engine"
echo "=========================================================="

NEW_NAME="TubeDownloader-Pro"
REPO_URL="https://github.com/developerahmad26/TubeDownloader-Pro.git"

# Detect target parent directory
TARGET_PARENT="/root"
[ ! -d "/root" ] && TARGET_PARENT="$HOME"

# Check possible legacy directories
POSSIBLE_OLD_DIRS=(
    "$TARGET_PARENT/youtube-video-downloader"
    "$TARGET_PARENT/Youtube Video Downloader"
    "$TARGET_PARENT/Youtube-Video-Downloader"
    "$HOME/youtube-video-downloader"
    "$HOME/Youtube Video Downloader"
    "$HOME/Youtube-Video-Downloader"
)

FOUND_OLD_DIR=""
for d in "${POSSIBLE_OLD_DIRS[@]}"; do
    if [ -d "$d" ]; then
        FOUND_OLD_DIR="$d"
        break
    fi
done

TARGET_DIR="$TARGET_PARENT/$NEW_NAME"

if [ -n "$FOUND_OLD_DIR" ] && [ "$FOUND_OLD_DIR" != "$TARGET_DIR" ]; then
    echo "[*] Found legacy folder: $FOUND_OLD_DIR"
    echo "[*] Migrating and renaming folder to: $TARGET_DIR..."
    mv "$FOUND_OLD_DIR" "$TARGET_DIR"
elif [ -d "$TARGET_DIR" ]; then
    echo "[*] Target directory already exists: $TARGET_DIR"
else
    echo "[*] Cloning fresh TubeDownloader-Pro repository to $TARGET_DIR..."
    git clone "$REPO_URL" "$TARGET_DIR"
fi

cd "$TARGET_DIR" || exit 1

echo "[*] Updating Git Remote to new TubeDownloader-Pro repository..."
git remote set-url origin "$REPO_URL" 2>/dev/null || true
git fetch origin main --quiet 2>/dev/null || true
git reset --hard origin/main --quiet 2>/dev/null || true

echo "[*] Configuring executable permissions..."
chmod +x ./*.sh 2>/dev/null || true

echo "[*] Running setup and refreshing Desktop shortcuts..."
bash ./setup.sh

echo "=========================================================="
echo " [OK] VPS Rebranding & Migration Complete!"
echo " Location: $TARGET_DIR"
echo " You can launch it anytime with: cd '$TARGET_DIR' && ./start.sh"
echo "=========================================================="
