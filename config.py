"""Configuration constants for YouTube Video Downloader."""

import os

# App info
APP_NAME = "YT Video Downloader Pro"
APP_VERSION = "1.0.0"

# Default download directory
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "YT Downloads")

# Quality options - flexible formats that merge to mp4/mkv via ffmpeg
QUALITY_OPTIONS = {
    "Best Quality": "bestvideo+bestaudio/best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "Audio Only (MP3)": "bestaudio/best",
    "Audio Only (M4A)": "bestaudio[ext=m4a]/bestaudio/best",
}

# Naming schemes
NAMING_SCHEMES = {
    "Video Title": "title",
    "Numbered (1, 2, 3...)": "numbered",
    "Numbered + Title (01 - Title)": "numbered_title",
    "Custom Prefix + Number": "custom_numbered",
    "Custom Prefix + Title": "custom_title",
}

# Video selection modes
SELECTION_MODES = {
    "All Videos": "all",
    "Select Range (e.g., 1-10)": "range",
    "Select Specific (e.g., 1,3,5,7)": "specific",
    "First N Videos": "first_n",
    "Last N Videos": "last_n",
}

# Output formats
VIDEO_FORMATS = ["mp4", "mkv", "webm", "avi"]
AUDIO_FORMATS = ["mp3", "m4a", "wav", "flac", "opus"]
