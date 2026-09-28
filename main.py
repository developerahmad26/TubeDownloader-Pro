"""YouTube Video Downloader Pro — Entry Point.

A professional YouTube video downloader with support for:
- Single video downloads
- Full playlist downloads
- Channel video downloads
- Full customization of quality, naming, selection, and more.

Usage:
    python main.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_dependencies():
    """Check if all required dependencies are installed."""
    missing = []

    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        missing.append("yt-dlp")

    try:
        import customtkinter  # noqa: F401
    except ImportError:
        missing.append("customtkinter")

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")

    if missing:
        print("\n[ERROR] Missing dependencies detected!")
        print(f"   Missing: {', '.join(missing)}")
        print("\n   Install them with:")
        print(f"   pip install {' '.join(missing)}")
        print("\n   Or install all at once:")
        print("   pip install -r requirements.txt")
        sys.exit(1)


def main():
    """Launch the application."""
    check_dependencies()

    from gui import App

    print("[*] Starting YT Video Downloader Pro...")
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
