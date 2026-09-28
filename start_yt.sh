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

# 4. Ensure Node.js is installed for YouTube JavaScript challenge solving
which node >/dev/null 2>&1 || (apt install -y nodejs --quiet 2>/dev/null || true)

# 5. Launch application
python3 main.py
