"""Core download engine using yt-dlp."""

import os
import re
import shutil
import threading
from datetime import datetime

import yt_dlp

from config import (
    DEFAULT_DOWNLOAD_DIR,
    QUALITY_OPTIONS,
)


def get_ffmpeg_dir():
    """Find directory containing ffmpeg and ffprobe binaries."""
    # 1. Check Python site-packages static_ffmpeg
    try:
        import site
        for sp in site.getsitepackages():
            p = os.path.join(sp, 'static_ffmpeg', 'bin', 'win32')
            if os.path.exists(os.path.join(p, 'ffmpeg.exe')):
                return p
    except Exception:
        pass

    # 2. Check Scripts folder
    scripts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Scripts")
    if os.path.exists(os.path.join(scripts_dir, 'ffmpeg.exe')):
        return scripts_dir

    # 3. Check system PATH
    ff = shutil.which('ffmpeg')
    if ff:
        return os.path.dirname(ff)

    return None


def get_js_runtime_config():
    """Find or auto-install Node.js (>=22) or Deno (>=2.3) JS runtime for yt-dlp challenge solving."""
    import sys, subprocess, re

    def is_valid_node(path):
        try:
            out = subprocess.check_output([path, '--version'], stderr=subprocess.STDOUT, timeout=5).decode()
            m = re.search(r'v(\d+)\.', out)
            return m is not None and int(m.group(1)) >= 22
        except Exception:
            return False

    def is_valid_deno(path):
        try:
            out = subprocess.check_output([path, '--version'], stderr=subprocess.STDOUT, timeout=5).decode()
            m = re.search(r'deno (\d+)\.(\d+)', out)
            if m:
                major, minor = int(m.group(1)), int(m.group(2))
                return (major > 2) or (major == 2 and minor >= 3)
            return True
        except Exception:
            return False

    home = os.path.expanduser("~")
    app_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Check Deno in app dir, PATH, or home
    deno_candidates = [
        os.path.join(app_dir, 'deno'),
        os.path.join(app_dir, 'deno.exe'),
        os.path.join(home, '.deno', 'bin', 'deno'),
        os.path.join(home, '.deno', 'bin', 'deno.exe'),
        shutil.which('deno'),
        '/usr/local/bin/deno',
        '/usr/bin/deno',
        '/root/.deno/bin/deno',
    ]
    for d in deno_candidates:
        if d and os.path.isfile(d) and is_valid_deno(d):
            return {'deno': {'path': d}}

    # 2. Check Node in PATH or system paths (must be version >= 22)
    node_candidates = [
        shutil.which('node'),
        shutil.which('nodejs'),
        '/usr/bin/node',
        '/usr/local/bin/node',
        '/bin/node',
    ]
    for n in node_candidates:
        if n and os.path.isfile(n) and is_valid_node(n):
            return {'node': {'path': n}}

    # 3. If on Linux and no valid JS runtime found, auto-download standalone Deno 2.4.2 binary
    if sys.platform.startswith('linux'):
        local_deno = os.path.join(app_dir, 'deno')
        if not os.path.isfile(local_deno) or not is_valid_deno(local_deno):
            try:
                import urllib.request, zipfile, io
                url = "https://github.com/denoland/deno/releases/download/v2.4.2/deno-x86_64-unknown-linux-gnu.zip"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                resp = urllib.request.urlopen(req, timeout=30)
                with zipfile.ZipFile(io.BytesIO(resp.read())) as zf:
                    zf.extract("deno", path=app_dir)
                os.chmod(local_deno, 0o755)
            except Exception:
                pass

        if os.path.isfile(local_deno) and os.access(local_deno, os.X_OK):
            return {'deno': {'path': local_deno}}

    return None


class ErrorCaptureLogger:
    """Custom logger to capture yt-dlp warnings and errors for reporting."""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.warnings.append(str(msg))

    def error(self, msg):
        self.errors.append(str(msg))

    def get_last_error(self):
        # 1. Check for cookie rotation warning (Google session invalidation)
        for w in reversed(self.warnings):
            w_lower = w.lower()
            if any(t in w_lower for t in ['rotated in the browser', 'no longer valid', 'cookies are no longer valid']):
                return "YouTube Cookies Expired/Rotated! (Export fresh cookies via Incognito window)"

        if not self.errors:
            for w in reversed(self.warnings):
                if 'bot' in w.lower() or 'sign in' in w.lower():
                    return "Bot Check Triggered! (Fresh YouTube Cookies required)"
            return ""

        err = self.errors[-1]
        # Strip ANSI escape codes (e.g. [0;31m)
        err = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', err)
        err = re.sub(r'\[[0-9;]+m', '', err)
        # Clean up common prefixes
        err = re.sub(r'^(ERROR:\s*|\[youtube\]\s*)', '', err).strip()
        # Take first line only
        err = err.split('\n')[0].strip()
        if len(err) > 80:
            err = err[:80] + "..."
        return err


class DownloadManager:
    """Manages video downloads with full customization."""

    def __init__(self):
        self.is_downloading = False
        self.cancel_flag = False
        self.current_progress = 0
        self.current_status = ""
        self.total_videos = 0
        self.completed_videos = 0
        self.failed_videos = []
        self.skipped_videos = []
        self.download_log = []
        self._lock = threading.Lock()
        self.ffmpeg_dir = get_ffmpeg_dir()

    def reset(self):
        """Reset download state."""
        self.is_downloading = False
        self.cancel_flag = False
        self.current_progress = 0
        self.current_status = ""
        self.total_videos = 0
        self.completed_videos = 0
        self.failed_videos = []
        self.skipped_videos = []
        self.download_log = []

    @staticmethod
    def is_valid_youtube_cookie_file(path):
        """Check if file exists and contains valid YouTube domain cookies."""
        if not path or not os.path.isfile(path):
            return False
        try:
            if os.path.getsize(path) < 10:
                return False
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(16384)
                return 'youtube.com' in content or '.youtube.com' in content
        except Exception:
            return False

    @classmethod
    def find_cookie_file(cls):
        """Search all possible locations for a valid YouTube cookies file (ignores Rumble/other sites)."""
        app_dir = os.path.dirname(os.path.abspath(__file__))
        home_dir = os.path.expanduser("~")
        candidates = [
            os.path.join(app_dir, "cookies.txt"),
            os.path.join(app_dir, "youtube_cookies.txt"),
            os.path.abspath("cookies.txt"),
            os.path.join(home_dir, "youtube_cookies.txt"),
            os.path.join(home_dir, "cookies.txt"),
            "/root/youtube_cookies.txt",
            "/root/cookies.txt",
            os.path.join(home_dir, "Desktop", "youtube_cookies.txt"),
            os.path.join(home_dir, "Desktop", "cookies.txt"),
            os.path.join(home_dir, "Downloads", "youtube_cookies.txt"),
            os.path.join(home_dir, "Downloads", "cookies.txt"),
        ]
        for p in candidates:
            if cls.is_valid_youtube_cookie_file(p):
                return p
        return None

    def cancel(self):
        """Cancel the current download."""
        self.cancel_flag = True
        self.current_status = "Cancelling..."

    def _normalize_channel_url(self, url):
        """Ensure channel URL points to /videos tab for complete listing."""
        url = url.strip().rstrip('/')
        channel_patterns = ['/@', '/channel/', '/c/', '/user/']
        is_channel = any(p in url for p in channel_patterns)

        if is_channel:
            for tab in ['/videos', '/shorts', '/streams', '/playlists',
                        '/community', '/channels', '/about', '/featured']:
                if url.endswith(tab):
                    url = url[:-len(tab)]
                    break
            url = url + '/videos'
        return url

    def _clean_title(self, text):
        """Clean multiline or noisy YouTube titles."""
        if not text:
            return "Unknown"
        clean = str(text).split('\n')[0].split('\r')[0]
        if ' • ' in clean:
            clean = clean.split(' • ')[0]
        elif ' - Videos' in clean:
            clean = clean.replace(' - Videos', '')
        clean = re.sub(r'[\r\n\t]+', ' ', clean)
        clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip(' .')
        return clean if clean else "Unknown"

    def _sanitize_filename(self, name):
        """Remove invalid characters, newlines, and limit length for Windows filesystem."""
        if not name:
            return "video"
        name = str(name).replace('\r', ' ').replace('\n', ' ').replace('\t', ' ')
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
        name = re.sub(r'\s+', ' ', name).strip(' .')
        if len(name) > 60:
            name = name[:60].strip(' .')
        return name if name else "video"

    def fetch_info(self, url, callback=None, flat=True):
        """Fetch video/playlist/channel information without downloading."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist' if flat else False,
            'ignoreerrors': True,
            'lazy_playlist': False,
            'remote_components': ['ejs:github'],
            'extractor_args': {
                'youtube': {
                    'player_client': ['default', '-tv', '-tv_embedded'],
                }
            },
        }
        js_rt = get_js_runtime_config()
        if js_rt:
            ydl_opts['js_runtimes'] = js_rt

        cookie_path = self.find_cookie_file()
        if cookie_path:
            ydl_opts['cookiefile'] = cookie_path

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return None
                return info
        except Exception as e:
            if callback:
                callback(f"Error fetching info: {str(e)}")
            return None

    def _flatten_entries(self, entries):
        """Recursively flatten nested entries (channel tabs > playlists > videos)."""
        flat = []
        if entries is None:
            return flat
        for entry in entries:
            if entry is None:
                continue
            nested = entry.get('entries', None)
            if nested is not None:
                flat.extend(self._flatten_entries(nested))
            else:
                flat.append(entry)
        return flat

    def get_video_list(self, url, callback=None, is_channel=False):
        """Get list of videos from a playlist or channel URL."""
        if callback:
            callback("Fetching video list... This may take a moment.")

        orig_url = url
        if is_channel:
            url = self._normalize_channel_url(url)
        else:
            channel_patterns = ['/@', '/channel/', '/c/', '/user/']
            if any(p in url for p in channel_patterns):
                url = self._normalize_channel_url(url)

        if callback:
            callback(f"Fetching from: {url}")

        info = self.fetch_info(url, callback, flat=True)
        if not info and url != orig_url:
            if callback:
                callback(f"Retrying with original URL: {orig_url}")
            info = self.fetch_info(orig_url, callback, flat=True)

        if not info:
            return [], "Unknown", 0

        videos = []
        entries = info.get('entries', [])

        if entries:
            flat_entries = self._flatten_entries(entries)
        else:
            flat_entries = []

        if not flat_entries:
            if info.get('id'):
                videos.append({
                    'index': 1,
                    'title': self._clean_title(info.get('title', 'Unknown')),
                    'url': info.get('webpage_url', url),
                    'duration': info.get('duration', 0),
                    'id': info.get('id', ''),
                })
        else:
            for i, entry in enumerate(flat_entries, 1):
                if entry is None:
                    continue

                video_id = entry.get('id', '')
                video_url = entry.get('url', entry.get('webpage_url', ''))

                if video_id and (not video_url or not video_url.startswith('http')):
                    video_url = f"https://www.youtube.com/watch?v={video_id}"

                entry_type = entry.get('_type', '')
                if entry_type == 'playlist':
                    continue

                clean_vid_title = self._clean_title(entry.get('title', f'Video {i}'))
                videos.append({
                    'index': i,
                    'title': clean_vid_title,
                    'url': video_url,
                    'duration': entry.get('duration', 0),
                    'id': video_id,
                })

        for i, v in enumerate(videos, 1):
            v['index'] = i

        raw_title = info.get('channel') or info.get('uploader') or info.get('title') or 'YouTube_Videos'
        playlist_title = self._clean_title(raw_title)
        total_count = len(videos)

        if callback:
            callback(f"Found {total_count} videos in: {playlist_title}")

        return videos, playlist_title, total_count

    def _get_output_template(self, naming_scheme, custom_prefix="", index=1,
                              download_dir=DEFAULT_DOWNLOAD_DIR, subfolder="",
                              video_title=None, video_id=""):
        """Generate output template based on naming scheme."""
        base_dir = download_dir
        if subfolder:
            clean_sub = self._sanitize_filename(subfolder)
            base_dir = os.path.join(download_dir, clean_sub)

        os.makedirs(base_dir, exist_ok=True)

        # Unique suffix with video ID guarantees no file collision/overwrite
        unique_suffix = f" [{video_id}]" if video_id else " [%(id)s]"

        from title_rewriter import rewrite_title

        if naming_scheme == "title":
            return base_dir, os.path.join(base_dir, f"%(title).80s{unique_suffix}.%(ext)s")
        elif naming_scheme == "rewrite_title":
            if video_title:
                clean_t = self._sanitize_filename(rewrite_title(video_title))[:80]
                return base_dir, os.path.join(base_dir, f"{clean_t}{unique_suffix}.%(ext)s")
            return base_dir, os.path.join(base_dir, f"%(title).80s{unique_suffix}.%(ext)s")
        elif naming_scheme == "numbered":
            return base_dir, os.path.join(base_dir, f"{index:03d}.%(ext)s")
        elif naming_scheme == "numbered_title":
            return base_dir, os.path.join(base_dir, f"{index:03d} - %(title).80s{unique_suffix}.%(ext)s")
        elif naming_scheme == "numbered_rewrite_title":
            if video_title:
                clean_t = self._sanitize_filename(rewrite_title(video_title))[:80]
                return base_dir, os.path.join(base_dir, f"{index:03d} - {clean_t}{unique_suffix}.%(ext)s")
            return base_dir, os.path.join(base_dir, f"{index:03d} - %(title).80s{unique_suffix}.%(ext)s")
        elif naming_scheme == "custom_numbered":
            prefix = self._sanitize_filename(custom_prefix) if custom_prefix else "video"
            return base_dir, os.path.join(base_dir, f"{prefix}_{index:03d}.%(ext)s")
        elif naming_scheme == "custom_title":
            prefix = self._sanitize_filename(custom_prefix) if custom_prefix else "video"
            return base_dir, os.path.join(base_dir, f"{prefix} - %(title).80s{unique_suffix}.%(ext)s")
        elif naming_scheme == "custom_rewrite_title":
            prefix = self._sanitize_filename(custom_prefix) if custom_prefix else "video"
            if video_title:
                clean_t = self._sanitize_filename(rewrite_title(video_title))[:80]
                return base_dir, os.path.join(base_dir, f"{prefix} - {clean_t}{unique_suffix}.%(ext)s")
            return base_dir, os.path.join(base_dir, f"{prefix} - %(title).80s{unique_suffix}.%(ext)s")
        else:
            return base_dir, os.path.join(base_dir, f"%(title).80s{unique_suffix}.%(ext)s")

    def _get_files_in_dir(self, directory):
        """Get set of all non-temp files in a directory."""
        if not os.path.exists(directory):
            return set()
        return {
            f for f in os.listdir(directory)
            if not f.endswith(('.part', '.ytdl', '.temp', '.tmp'))
        }

    def _build_ydl_opts(self, quality, output_template, embed_thumbnail=False,
                        download_subtitles=False, subtitle_lang="en",
                        output_format="mp4", progress_hook=None,
                        speed_limit=None, proxy=None, logger=None):
        """Build yt-dlp options dictionary."""
        is_audio_only = "Audio Only" in quality
        format_string = QUALITY_OPTIONS.get(quality, QUALITY_OPTIONS["Best Quality"])

        opts = {
            'format': format_string,
            'outtmpl': output_template,
            'ignoreerrors': 'only_download',
            'no_warnings': True,
            'quiet': True,
            'noprogress': True,
            'retries': 5,
            'fragment_retries': 5,
            'continuedl': True,
            'overwrites': False,
            'remote_components': ['ejs:github'],
            'extractor_args': {
                'youtube': {
                    'player_client': ['default', '-tv', '-tv_embedded'],
                }
            },
        }

        if not is_audio_only:
            opts['format_sort'] = ['hasvid']
            opts['format_sort_force'] = True

        if logger:
            opts['logger'] = logger

        # Set ffmpeg / ffprobe location
        if self.ffmpeg_dir:
            opts['ffmpeg_location'] = self.ffmpeg_dir

        # Configure JS runtime (Node.js or Deno)
        js_rt = get_js_runtime_config()
        if js_rt:
            opts['js_runtimes'] = js_rt

        # Auto-detect cookies.txt if present
        cookie_path = self.find_cookie_file()
        if cookie_path:
            opts['cookiefile'] = cookie_path

        postprocessors = []

        if is_audio_only:
            audio_fmt = "mp3" if "MP3" in quality else "m4a"
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_fmt,
                'preferredquality': '192',
            })
        else:
            if output_format and output_format != "mp4":
                postprocessors.append({
                    'key': 'FFmpegVideoRemuxer',
                    'preferedformat': output_format,
                })
            opts['merge_output_format'] = output_format if output_format else 'mp4'

        if embed_thumbnail:
            opts['writethumbnail'] = True
            postprocessors.append({
                'key': 'EmbedThumbnail',
                'already_have_thumbnail': False,
            })

        if download_subtitles:
            opts['writesubtitles'] = True
            opts['subtitleslangs'] = [subtitle_lang]
            postprocessors.append({
                'key': 'FFmpegSubtitlesConvertor',
                'format': 'srt',
            })
            postprocessors.append({'key': 'FFmpegEmbedSubtitle'})

        if postprocessors:
            opts['postprocessors'] = postprocessors

        if progress_hook:
            opts['progress_hooks'] = [progress_hook]

        if speed_limit:
            opts['ratelimit'] = speed_limit * 1024

        if proxy:
            opts['proxy'] = proxy

        return opts

    def download_single(self, url, quality="Best Quality", naming_scheme="title",
                        custom_prefix="", download_dir=DEFAULT_DOWNLOAD_DIR,
                        embed_thumbnail=False, download_subtitles=False,
                        subtitle_lang="en", output_format="mp4",
                        speed_limit=None, proxy=None,
                        progress_callback=None, status_callback=None):
        """Download a single video."""
        self.is_downloading = True
        self.cancel_flag = False
        self.total_videos = 1
        self.completed_videos = 0

        try:
            video_title = None
            video_id = ""
            if "rewrite" in naming_scheme:
                if status_callback:
                    status_callback("Fetching video metadata for title rewrite...")
                info = self.fetch_info(url, flat=True)
                if info:
                    video_title = info.get('title')
                    video_id = info.get('id', '')

            base_dir, output_template = self._get_output_template(
                naming_scheme, custom_prefix, 1, download_dir,
                video_title=video_title, video_id=video_id
            )

            files_before = self._get_files_in_dir(base_dir)

            def progress_hook(d):
                if self.cancel_flag:
                    raise Exception("Download cancelled by user")
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    speed = d.get('speed', 0)
                    eta = d.get('eta', 0)

                    percent = 0
                    if total > 0:
                        percent = (downloaded / total) * 100
                        self.current_progress = percent
                        if progress_callback:
                            progress_callback(percent)

                    speed_str = f"{speed / 1024 / 1024:.1f} MB/s" if speed else "-- MB/s"
                    eta_str = f"{eta}s" if eta else "--"
                    status = f"Downloading: {percent:.1f}% | Speed: {speed_str} | ETA: {eta_str}"
                    self.current_status = status
                    if status_callback:
                        status_callback(status)

                elif d['status'] == 'finished':
                    self.current_status = "Processing / Converting..."
                    if status_callback:
                        status_callback("Processing / Converting...")

            logger = ErrorCaptureLogger()
            opts = self._build_ydl_opts(
                quality, output_template, embed_thumbnail,
                download_subtitles, subtitle_lang, output_format,
                progress_hook, speed_limit, proxy, logger=logger
            )

            if status_callback:
                status_callback("Starting download...")

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    result = ydl.download([url])
                files_after = self._get_files_in_dir(base_dir)
                new_files = files_after - files_before
            except Exception as e:
                result = 1
                files_after = self._get_files_in_dir(base_dir)
                new_files = files_after - files_before
                if not logger.get_last_error():
                    logger.error(str(e))

            # Multi-tiered fallback if primary download failed
            if result != 0:
                is_audio = "Audio Only" in quality
                tier1_fmt = 'bestaudio/best' if is_audio else 'bestvideo*+bestaudio/best'
                tier2_fmt = '140/bestaudio/best' if is_audio else '18/best'

                if status_callback:
                    status_callback("🔄 Retrying with mobile stream engine...")
                tier1_opts = dict(opts)
                tier1_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'web']}}
                tier1_opts['format'] = tier1_fmt
                try:
                    with yt_dlp.YoutubeDL(tier1_opts) as ydl:
                        result = ydl.download([url])
                    files_after = self._get_files_in_dir(base_dir)
                    new_files = files_after - files_before
                except Exception:
                    pass

            if result != 0:
                if status_callback:
                    status_callback("🔄 Retrying with direct progressive stream...")
                tier2_opts = dict(opts)
                tier2_opts['extractor_args'] = {'youtube': {'player_client': ['android']}}
                tier2_opts['format'] = tier2_fmt
                try:
                    with yt_dlp.YoutubeDL(tier2_opts) as ydl:
                        result = ydl.download([url])
                    files_after = self._get_files_in_dir(base_dir)
                    new_files = files_after - files_before
                except Exception:
                    pass

            if result == 0:
                self.completed_videos = 1
                self.current_progress = 100
                if status_callback:
                    status_callback("✅ Download completed successfully!")
                if progress_callback:
                    progress_callback(100)
                self.download_log.append({
                    'url': url,
                    'status': 'success',
                    'time': datetime.now().strftime('%H:%M:%S'),
                })
                return True
            else:
                last_err = logger.get_last_error() or f"Code {result}"
                if status_callback:
                    status_callback(f"❌ Download failed: {last_err}")
                self.failed_videos.append({'url': url, 'error': last_err})
                return False

        except Exception as e:
            error_msg = str(e)
            if "cancelled" in error_msg.lower():
                if status_callback:
                    status_callback("❌ Download cancelled.")
            else:
                if status_callback:
                    status_callback(f"❌ Error: {error_msg}")
                self.failed_videos.append({'url': url, 'error': error_msg})
            self.download_log.append({
                'url': url,
                'status': 'failed',
                'error': error_msg,
                'time': datetime.now().strftime('%H:%M:%S'),
            })
            return False

        finally:
            self.is_downloading = False

    def download_batch(self, videos, quality="Best Quality", naming_scheme="title",
                       custom_prefix="", download_dir=DEFAULT_DOWNLOAD_DIR,
                       subfolder="", embed_thumbnail=False,
                       download_subtitles=False, subtitle_lang="en",
                       output_format="mp4", speed_limit=None, proxy=None,
                       selection_mode="all", selection_value="",
                       progress_callback=None, status_callback=None,
                       video_count_callback=None):
        """Download multiple videos (playlist/channel)."""
        self.is_downloading = True
        self.cancel_flag = False
        self.completed_videos = 0
        self.failed_videos = []
        self.skipped_videos = []
        actual_downloaded = 0

        try:
            selected_videos = self._apply_selection(videos, selection_mode, selection_value)
            self.total_videos = len(selected_videos)

            if video_count_callback:
                video_count_callback(self.total_videos)

            if status_callback:
                status_callback(f"Starting batch download of {self.total_videos} videos...")
                cookie_path = self.find_cookie_file()
                if cookie_path:
                    status_callback(f"🍪 Using YouTube Cookies: {os.path.basename(cookie_path)}")
                else:
                    status_callback("⚠️ No YouTube cookies active. (Click '🍪 Manage YouTube Cookies' if YouTube blocks with bot error)")

            clean_subfolder = self._sanitize_filename(subfolder) if subfolder else ""

            for idx, video in enumerate(selected_videos, 1):
                if self.cancel_flag:
                    if status_callback:
                        status_callback(
                            f"❌ Cancelled after {self.completed_videos}/{self.total_videos} videos."
                        )
                    break

                video_url = video.get('url', '')
                video_title = self._clean_title(video.get('title', f'Video {idx}'))
                video_id = video.get('id', '')

                if not video_url:
                    self.failed_videos.append({'title': video_title, 'error': 'No URL'})
                    if status_callback:
                        status_callback(f"[{idx}/{self.total_videos}] ⚠️ Skipped: No URL for {video_title}")
                    continue

                if not video_url.startswith('http'):
                    video_url = f"https://www.youtube.com/watch?v={video_url}"

                base_dir, output_template = self._get_output_template(
                    naming_scheme, custom_prefix, idx, download_dir, clean_subfolder,
                    video_title=video_title, video_id=video_id
                )

                # Snapshot existing files before download
                files_before = self._get_files_in_dir(base_dir)

                if status_callback:
                    status_callback(f"[{idx}/{self.total_videos}] Downloading: {video_title}")

                current_idx = idx

                def make_progress_hook(vid_idx):
                    def progress_hook(d):
                        if self.cancel_flag:
                            raise Exception("Download cancelled by user")
                        if d['status'] == 'downloading':
                            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                            downloaded = d.get('downloaded_bytes', 0)
                            speed = d.get('speed', 0)
                            eta = d.get('eta', 0)

                            video_percent = 0
                            if total > 0:
                                video_percent = (downloaded / total) * 100

                            overall = (
                                (self.completed_videos + video_percent / 100)
                                / self.total_videos
                            ) * 100
                            self.current_progress = overall
                            if progress_callback:
                                progress_callback(overall)

                            speed_str = (
                                f"{speed / 1024 / 1024:.1f} MB/s" if speed else "-- MB/s"
                            )
                            eta_str = f"{eta}s" if eta else "--"
                            status = (
                                f"[{vid_idx}/{self.total_videos}] "
                                f"{video_percent:.1f}% | {speed_str} | ETA: {eta_str}"
                            )
                            if status_callback:
                                status_callback(status)

                        elif d['status'] == 'finished':
                            if status_callback:
                                status_callback(f"[{vid_idx}/{self.total_videos}] Processing...")
                    return progress_hook

                logger = ErrorCaptureLogger()
                opts = self._build_ydl_opts(
                    quality, output_template, embed_thumbnail,
                    download_subtitles, subtitle_lang, output_format,
                    make_progress_hook(current_idx), speed_limit, proxy,
                    logger=logger
                )

                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        result = ydl.download([video_url])

                    files_after = self._get_files_in_dir(base_dir)
                    new_files = files_after - files_before

                    # Multi-tiered fallback if primary batch item download failed
                    if result != 0:
                        is_audio = "Audio Only" in quality
                        tier1_fmt = 'bestaudio/best' if is_audio else 'bestvideo*+bestaudio/best'
                        tier2_fmt = '140/bestaudio/best' if is_audio else '18/best'

                        if status_callback:
                            status_callback(f"[{idx}/{self.total_videos}] 🔄 Retrying with mobile stream engine...")
                        tier1_opts = dict(opts)
                        tier1_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'web']}}
                        tier1_opts['format'] = tier1_fmt
                        try:
                            with yt_dlp.YoutubeDL(tier1_opts) as ydl:
                                result = ydl.download([video_url])
                            files_after = self._get_files_in_dir(base_dir)
                            new_files = files_after - files_before
                        except Exception:
                            pass

                    if result != 0:
                        if status_callback:
                            status_callback(f"[{idx}/{self.total_videos}] 🔄 Retrying with direct progressive stream...")
                        tier2_opts = dict(opts)
                        tier2_opts['extractor_args'] = {'youtube': {'player_client': ['android']}}
                        tier2_opts['format'] = tier2_fmt
                        try:
                            with yt_dlp.YoutubeDL(tier2_opts) as ydl:
                                result = ydl.download([video_url])
                            files_after = self._get_files_in_dir(base_dir)
                            new_files = files_after - files_before
                        except Exception:
                            pass

                    if result == 0:
                        self.completed_videos += 1
                        if new_files:
                            actual_downloaded += 1
                            filename = list(new_files)[0]
                            self.download_log.append({
                                'title': video_title,
                                'url': video_url,
                                'status': 'success',
                                'file': filename,
                                'time': datetime.now().strftime('%H:%M:%S'),
                            })
                            if status_callback:
                                status_callback(f"[{idx}/{self.total_videos}] ✅ Saved: {filename}")
                        else:
                            self.skipped_videos.append({'title': video_title, 'reason': 'Already exists'})
                            self.download_log.append({
                                'title': video_title,
                                'url': video_url,
                                'status': 'skipped',
                                'reason': 'Already exists',
                                'time': datetime.now().strftime('%H:%M:%S'),
                            })
                            if status_callback:
                                status_callback(f"[{idx}/{self.total_videos}] ⚡ Already exists: {video_title}")
                    else:
                        last_err = logger.get_last_error() or f"Code {result}"
                        has_cookie = self.find_cookie_file() is not None
                        if "rotated" in last_err.lower() or "no longer valid" in last_err.lower():
                            display_err = "Cookies Expired/Rotated by Google! (Export fresh cookies from Incognito tab)"
                        elif "bot" in last_err.lower() or "sign in" in last_err.lower():
                            if has_cookie:
                                display_err = "Cookies Expired/Rejected by YouTube! (Export fresh cookies from Incognito tab)"
                            else:
                                display_err = "Bot Check Triggered! (Add YouTube Cookies via button above)"
                        else:
                            display_err = last_err
                        self.failed_videos.append({
                            'title': video_title,
                            'error': display_err,
                        })
                        self.download_log.append({
                            'title': video_title,
                            'url': video_url,
                            'status': 'failed',
                            'error': display_err,
                            'time': datetime.now().strftime('%H:%M:%S'),
                        })
                        if status_callback:
                            status_callback(f"[{idx}/{self.total_videos}] ❌ FAILED: {video_title} ({display_err})")

                except Exception as e:
                    error_msg = str(e)
                    if "cancelled" in error_msg.lower():
                        break
                    clean_err = error_msg.split('\n')[0]
                    if len(clean_err) > 80:
                        clean_err = clean_err[:80] + "..."

                    self.failed_videos.append({'title': video_title, 'error': clean_err})
                    self.download_log.append({
                        'title': video_title,
                        'url': video_url,
                        'status': 'failed',
                        'error': clean_err,
                        'time': datetime.now().strftime('%H:%M:%S'),
                    })
                    if status_callback:
                        status_callback(f"[{idx}/{self.total_videos}] ❌ ERROR: {video_title} — {clean_err}")

            # Final summary
            if not self.cancel_flag:
                self.current_progress = 100
                if progress_callback:
                    progress_callback(100)

                final_dir = os.path.join(download_dir, clean_subfolder) if clean_subfolder else download_dir
                actual_files = len(self._get_files_in_dir(final_dir))
                failed_count = len(self.failed_videos)
                skipped_count = len(self.skipped_videos)

                summary = (
                    f"🎉 All Done! In folder: {actual_files} | "
                    f"New: {actual_downloaded} | "
                    f"Already had: {skipped_count} | "
                    f"Failed: {failed_count}"
                )
                if status_callback:
                    status_callback(summary)

            return self.completed_videos, self.failed_videos

        except Exception as e:
            if status_callback:
                status_callback(f"❌ Batch error: {str(e)}")
            return self.completed_videos, self.failed_videos

        finally:
            self.is_downloading = False

    def _apply_selection(self, videos, mode, value):
        """Apply video selection filter."""
        if mode == "all" or not value:
            return videos

        try:
            if mode == "range":
                parts = value.strip().split("-")
                start = max(0, int(parts[0]) - 1)
                end = int(parts[1]) if len(parts) > 1 else start + 1
                return videos[start:end]

            elif mode == "specific":
                indices = [int(x.strip()) - 1 for x in value.split(",")]
                return [videos[i] for i in indices if 0 <= i < len(videos)]

            elif mode == "first_n":
                n = int(value.strip())
                return videos[:n]

            elif mode == "last_n":
                n = int(value.strip())
                return videos[-n:] if n > 0 else []

        except (ValueError, IndexError):
            return videos

        return videos
