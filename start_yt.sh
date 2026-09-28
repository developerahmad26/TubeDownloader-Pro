#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# 1. Automatically sync with latest GitHub code (Conflict-free reset)
git fetch origin main --quiet 2>/dev/null && git reset --hard origin/main --quiet 2>/dev/null || true

# 2. Activate dedicated virtual environment
if [ -d "$DIR/venv" ]; then
    source "$DIR/venv/bin/activate"
fi

# 3. Launch application
python3 main.py
