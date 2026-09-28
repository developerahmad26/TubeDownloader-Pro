"""Configuration constants for YouTube Video Downloader."""

import os

# App info
APP_NAME = "TubeDownloader Pro"
APP_VERSION = "1.0.0"

import sys

def get_base_dir():
    """Return application base directory (works for both dev mode and PyInstaller frozen exe)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

# Default download directory
DEFAULT_DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "YT Downloads")

# Quality options - flexible formats that merge to mp4/mkv via ffmpeg
QUALITY_OPTIONS = {
    "Best Quality": "bestvideo*+bestaudio/best",
    "1080p": "bestvideo*[height<=1080]+bestaudio/best[height<=1080]/best",
    "720p": "bestvideo*[height<=720]+bestaudio/best[height<=720]/best",
    "480p": "bestvideo*[height<=480]+bestaudio/best[height<=480]/best",
    "360p": "bestvideo*[height<=360]+bestaudio/best[height<=360]/best",
    "Audio Only (MP3)": "bestaudio/best",
    "Audio Only (M4A)": "bestaudio[ext=m4a]/bestaudio/best",
}

# Naming schemes
NAMING_SCHEMES = {
    "Video Title": "title",
    "Rewrite Title (Cleaned)": "rewrite_title",
    "Numbered (1, 2, 3...)": "numbered",
    "Numbered + Title (01 - Title)": "numbered_title",
    "Numbered + Rewrite Title (01 - Cleaned)": "numbered_rewrite_title",
    "Custom Prefix + Number": "custom_numbered",
    "Custom Prefix + Title": "custom_title",
    "Custom Prefix + Rewrite Title": "custom_rewrite_title",
}

# Persistent data paths
BATCHES_FILE = os.path.join(BASE_DIR, "batches.json")
SCHEDULES_FILE = os.path.join(BASE_DIR, "schedules.json")

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

# Application Settings file & defaults
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_APP_SETTINGS = {
    "default_quality": "Best Quality",
    "default_format": "mp4",
    "default_naming_scheme": "Numbered + Rewrite Title (01 - Cleaned)",
    "default_custom_prefix": "",
    "default_download_dir": DEFAULT_DOWNLOAD_DIR,
    "default_auto_subfolder": True,
    "default_embed_thumbnail": False,
    "default_download_subtitles": False,
    "default_subtitle_lang": "en",
    "default_speed_limit": "",
}


def load_app_settings():
    """Load user-defined default settings from settings.json."""
    import json
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                res = dict(DEFAULT_APP_SETTINGS)
                if isinstance(data, dict):
                    res.update(data)
                return res
        except Exception:
            pass
    return dict(DEFAULT_APP_SETTINGS)


def save_app_settings(settings):
    """Save user-defined default settings to settings.json."""
    import json
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

