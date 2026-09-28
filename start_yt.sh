#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

if [ -d "$DIR/venv" ]; then
    source "$DIR/venv/bin/activate"
fi

python3 main.py
