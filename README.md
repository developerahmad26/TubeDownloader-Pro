# 🎬 YT Video Downloader Pro v1.0

A professional, feature-rich YouTube Video Downloader with a modern dark-themed GUI.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![yt-dlp](https://img.shields.io/badge/yt--dlp-powered-red)
![GUI](https://img.shields.io/badge/GUI-CustomTkinter-green)

---

## ✨ Features

### 🎯 Three Download Modes
| Mode | Description |
|------|-------------|
| **📹 Single Video** | Download any YouTube video by URL |
| **📋 Playlist** | Download entire playlists with full customization |
| **📺 Channel** | Download all videos from any YouTube channel |

### 🎛️ Full Customization

- **Quality Selection**: Best, 1080p, 720p, 480p, 360p, Audio Only (MP3/M4A)
- **File Naming Schemes**:
  - `Video Title` — Uses the original video title
  - `Numbered (1, 2, 3...)` — Simple numbering: `001.mp4`, `002.mp4`
  - `Numbered + Title (01 - Title)` — `001 - Video Title.mp4`
  - `Custom Prefix + Number` — `MyPrefix_001.mp4`
  - `Custom Prefix + Title` — `MyPrefix - Video Title.mp4`
- **Video Selection** (for Playlist/Channel):
  - All Videos
  - Range (e.g., `1-10`)
  - Specific indices (e.g., `1,3,5,7`)
  - First N or Last N videos
  - **Visual Preview** — Browse all videos with checkboxes to pick exactly what you want
- **Output Format**: MP4, MKV, WebM, AVI, MP3, M4A, WAV, FLAC, Opus
- **Embed Thumbnails**: Embed video thumbnail into the file
- **Download Subtitles**: Auto-download and embed subtitles (customizable language)
- **Speed Limit**: Control download speed in KB/s
- **Auto Subfolder**: Automatically creates a folder named after the playlist/channel
- **Resume Support**: Interrupted downloads resume where they left off
- **Paste Button**: Quick clipboard paste for URLs
- **Download Log**: Real-time log of all download activity

---

## 🚀 Installation

### 1. Install Python
Make sure you have **Python 3.8+** installed. Download from [python.org](https://www.python.org/downloads/)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg (Recommended)
FFmpeg is needed for merging video+audio streams and format conversion.

- **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
- Or install via: `winget install ffmpeg`

### 4. Run the App
```bash
python main.py
```

---

## 📖 How to Use

### 📹 Single Video
1. Go to the **Single Video** tab
2. Paste the YouTube video URL
3. (Optional) Click **Fetch Info** to preview video details
4. Adjust quality, naming, and format settings
5. Click **Start Download** ✅

### 📋 Playlist Download
1. Go to the **Playlist** tab
2. Paste the playlist URL
3. Click **🔍 Fetch Videos** to load the video list
4. (Optional) Click **👁️ Preview & Select** to pick specific videos
5. Or use the Selection dropdown (Range, First N, etc.)
6. Click **Start Download** ✅

### 📺 Channel Download
1. Go to the **Channel** tab
2. Paste the channel URL (e.g., `https://www.youtube.com/@channelname/videos`)
3. Click **🔍 Fetch Videos** to load all channel videos
4. (Optional) Click **👁️ Preview & Select** to pick specific videos
5. Click **Start Download** ✅

---

## 📁 Project Structure

```
Youtube Video Downloader/
├── main.py              # Entry point with dependency checking
├── gui.py               # CustomTkinter GUI application
├── downloader.py        # Core download engine (yt-dlp)
├── config.py            # Configuration constants
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

---

## ⚙️ Settings Reference

| Setting | Options | Default |
|---------|---------|---------|
| Quality | Best, 1080p, 720p, 480p, 360p, Audio Only | Best Quality |
| Format | mp4, mkv, webm, avi, mp3, m4a, wav, flac, opus | mp4 |
| Naming | Title, Numbered, Numbered+Title, Custom+Number, Custom+Title | Video Title |
| Speed Limit | Any number (KB/s), 0 = unlimited | Unlimited |
| Subtitles | On/Off, Language code (en, hi, ur, etc.) | Off, en |
| Thumbnail | On/Off | Off |
| Subfolder | On/Off | On |

---

## 📋 Requirements

- **Python 3.8+**
- **yt-dlp** — YouTube download engine
- **customtkinter** — Modern themed GUI
- **Pillow** — Image processing
- **FFmpeg** — (Recommended) For video/audio merging and conversion

---

## 📝 Notes

- Downloads are saved to `~/Downloads/YT Downloads` by default
- You can change the download location anytime via the Browse button
- The **Open Folder** button opens the download directory in Explorer
- All downloads support **resume** — if interrupted, they'll continue from where they stopped
- The **Cancel** button safely stops ongoing downloads

---

Made with ❤️ using Python + CustomTkinter + yt-dlp
