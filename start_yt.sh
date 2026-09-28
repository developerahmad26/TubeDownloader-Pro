#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# 1. Automatically sync with latest GitHub code (Conflict-free reset)
git fetch origin main --quiet 2>/dev/null && git reset --hard origin/main --quiet 2>/dev/null || true

# 2. Activate dedicated virtual environment
if [ -d "$DIR/venv" ]; then
    source "$DIR/venv/bin/activate"
fi

# 3. Keep yt-dlp updated to bypass latest YouTube bot detection patches
pip install --upgrade yt-dlp --quiet 2>/dev/null || true

# 4. Ensure Node.js / Deno & xclip are installed for YouTube JS challenge & RDP clipboard
if ! which node >/dev/null 2>&1 && ! which deno >/dev/null 2>&1 && ! which nodejs >/dev/null 2>&1; then
    apt update -y --quiet 2>/dev/null || true
    apt install -y nodejs xclip --quiet 2>/dev/null || true
fi
[ -f /usr/bin/nodejs ] && [ ! -f /usr/bin/node ] && ln -s /usr/bin/nodejs /usr/bin/node 2>/dev/null || true
which xclip >/dev/null 2>&1 || (apt install -y xclip --quiet 2>/dev/null || true)

# 5. Launch application
python3 main.py
