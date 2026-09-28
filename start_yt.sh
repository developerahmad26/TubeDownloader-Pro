#!/bin/bash
# ==========================================================
# TubeDownloader Pro - Safe Auto-Healing Launcher for VPS / RDP
# ==========================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Sudo detection for non-root users
SUDO=""
if [ "$EUID" -ne 0 ] && which sudo >/dev/null 2>&1; then
    SUDO="sudo"
fi

echo "=========================================================="
echo " [*] Initializing TubeDownloader Pro on VPS / RDP..."
echo "=========================================================="

# 1. Automatically sync with latest GitHub code (Conflict-free reset)
echo "[*] Checking for latest updates from GitHub..."
git remote set-url origin https://github.com/developerahmad26/TubeDownloader-Pro.git 2>/dev/null || true
git fetch origin main --quiet 2>/dev/null && git reset --hard origin/main --quiet 2>/dev/null || true

# 2. Check and ensure system Tkinter and venv packages are installed
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo "[!] Tkinter not found! Installing system GUI packages (python3-tk, python3-venv)..."
    $SUDO apt-get update -y 2>/dev/null || true
    $SUDO apt-get install -y python3-tk python3-venv python3-pip ffmpeg 2>/dev/null || true
fi

# 3. Ensure dedicated virtual environment exists
if [ ! -d "$DIR/venv" ]; then
    echo "[*] Creating dedicated virtual environment at $DIR/venv..."
    python3 -m venv "$DIR/venv" 2>/dev/null || true
fi

# 4. Determine Python and Pip executables
if [ -f "$DIR/venv/bin/python" ]; then
    PYTHON_BIN="$DIR/venv/bin/python"
    PIP_BIN="$DIR/venv/bin/pip"
else
    PYTHON_BIN="python3"
    PIP_BIN="pip3"
fi

# 5. Verify & install Python requirements
if ! "$PYTHON_BIN" -c "import yt_dlp, customtkinter, PIL, mutagen" 2>/dev/null; then
    echo "[*] Installing missing dependencies into virtual environment..."
    "$PIP_BIN" install --upgrade pip --quiet 2>/dev/null || true
    "$PIP_BIN" install -r "$DIR/requirements.txt" --quiet 2>/dev/null || true
else
    # Keep yt-dlp updated to bypass latest YouTube bot detection patches
    "$PIP_BIN" install --upgrade yt-dlp --quiet 2>/dev/null || true
fi

# 6. Ensure Deno or Node.js (>=22) & xclip are available for YouTube JS challenge & RDP clipboard
NODE_MAJOR=0
if which node >/dev/null 2>&1; then
    NODE_MAJOR=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
fi

if [ "$NODE_MAJOR" -lt 22 ] && ! which deno >/dev/null 2>&1 && [ ! -f "$DIR/deno" ] && [ ! -f "$HOME/.deno/bin/deno" ]; then
    curl -fsSL https://github.com/denoland/deno/releases/download/v2.4.2/deno-x86_64-unknown-linux-gnu.zip -o "$DIR/deno.zip" 2>/dev/null && unzip -qo "$DIR/deno.zip" -d "$DIR" 2>/dev/null && chmod +x "$DIR/deno" 2>/dev/null && rm -f "$DIR/deno.zip" || true
    if [ ! -f "$DIR/deno" ]; then
        curl -fsSL https://deno.land/install.sh | sh 2>/dev/null || true
    fi
fi

[ -f "$DIR/deno" ] && export PATH="$DIR:$PATH"
[ -f "$HOME/.deno/bin/deno" ] && export PATH="$HOME/.deno/bin:$PATH"
which xclip >/dev/null 2>&1 || ($SUDO apt-get install -y xclip --quiet 2>/dev/null || true)

# 7. Auto-detect GUI Display if not set
if [ -z "$DISPLAY" ]; then
    for xsock in /tmp/.X11-unix/X*; do
        if [ -e "$xsock" ]; then
            disp_num=$(basename "$xsock" | sed 's/X//')
            export DISPLAY=":${disp_num}.0"
            echo "[*] Auto-detected DISPLAY=$DISPLAY"
            break
        fi
    done
fi

# 8. Launch application with full logging
LOG_FILE="$DIR/vps_run.log"
echo "[*] Starting TubeDownloader Pro (DISPLAY=${DISPLAY:-'NOT SET'})..."
echo "=========================================================="

"$PYTHON_BIN" main.py 2>&1 | tee "$LOG_FILE"
EXIT_STATUS=${PIPESTATUS[0]}

if [ $EXIT_STATUS -ne 0 ]; then
    echo ""
    echo "=========================================================="
    echo "❌ [ERROR] TubeDownloader Pro exited with code: $EXIT_STATUS"
    echo "📌 Log file saved to: $LOG_FILE"
    echo "=========================================================="
    if [ -t 0 ] || [ -n "$SSH_TTY" ]; then
        read -p "Press Enter to exit..."
    fi
fi
