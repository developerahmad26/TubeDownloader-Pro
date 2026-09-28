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

# 4. Ensure Deno or Node.js (>=22) & xclip are available for YouTube JS challenge & RDP clipboard
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
which xclip >/dev/null 2>&1 || (apt install -y xclip --quiet 2>/dev/null || true)

# 5. Launch application
python3 main.py
