#!/bin/bash
cd "$(dirname "$0")"
source /root/rumble-uploader/venv/bin/activate
python3 gui.py
