"""Modern GUI for YouTube Video Downloader using CustomTkinter."""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_DOWNLOAD_DIR,
    QUALITY_OPTIONS,
    NAMING_SCHEMES,
    SELECTION_MODES,
    VIDEO_FORMATS,
    AUDIO_FORMATS,
)
from downloader import DownloadManager


# Theme setup
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class VideoListWindow(ctk.CTkToplevel):
    """Window to display and select videos from playlist/channel."""

    def __init__(self, parent, videos, title="Video List"):
        super().__init__(parent)
        self.title(title)
        self.geometry("750x550")
        self.videos = videos
        self.selected_indices = []
        self.result = None

        # Make modal
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self.wait_window()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header, text=f"📋 Total Videos: {len(self.videos)}",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left", padx=10)

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=10)

        ctk.CTkButton(
            btn_frame, text="✅ Select All", width=110,
            command=self._select_all
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_frame, text="❎ Deselect All", width=110,
            command=self._deselect_all
        ).pack(side="left", padx=5)

        # Scrollable video list
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.checkboxes = []
        self.check_vars = []

        for video in self.videos:
            var = ctk.BooleanVar(value=True)
            self.check_vars.append(var)

            idx = video['index']
            vtitle = video.get('title', f'Video {idx}')
            duration = video.get('duration', 0)
            dur_str = ""
            if duration:
                mins = duration // 60
                secs = duration % 60
                dur_str = f"  [{mins}:{secs:02d}]"

            cb = ctk.CTkCheckBox(
                self.scroll_frame,
                text=f"{idx}. {vtitle}{dur_str}",
                variable=var,
                font=("Segoe UI", 12),
            )
            cb.pack(anchor="w", padx=10, pady=2)
            self.checkboxes.append(cb)

        # Bottom buttons
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            bottom, text="⬇️ Download Selected", width=200,
            fg_color="#28a745", hover_color="#218838",
            command=self._confirm
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            bottom, text="Cancel", width=100,
            fg_color="#dc3545", hover_color="#c82333",
            command=self._cancel
        ).pack(side="right", padx=10)

        count = sum(v.get() for v in self.check_vars)
        self.selected_label = ctk.CTkLabel(
            bottom, text=f"Selected: {count}",
            font=("Segoe UI", 12, "bold")
        )
        self.selected_label.pack(side="left", padx=20)

        # Bind checkbox changes
        for var in self.check_vars:
            var.trace_add("write", self._update_count)

    def _update_count(self, *args):
        count = sum(v.get() for v in self.check_vars)
        self.selected_label.configure(text=f"Selected: {count}")

    def _select_all(self):
        for var in self.check_vars:
            var.set(True)

    def _deselect_all(self):
        for var in self.check_vars:
            var.set(False)

    def _confirm(self):
        self.result = []
        for i, var in enumerate(self.check_vars):
            if var.get():
                self.result.append(self.videos[i])
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class App(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("920x780")
        self.minsize(880, 720)

        self.dm = DownloadManager()
        self.fetched_videos = []
        self.fetched_playlist_title = ""

        self._build_ui()

    def _build_ui(self):
        # Main scrollable container
        main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=10)

        # ========== Title ==========
        title_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            title_frame, text="🎬 YT Video Downloader Pro",
            font=("Segoe UI", 26, "bold"),
        ).pack()
        ctk.CTkLabel(
            title_frame,
            text="Download Videos • Playlists • Channels — with Full Control",
            font=("Segoe UI", 12), text_color="gray",
        ).pack()

        # ========== Tab View ==========
        self.tabview = ctk.CTkTabview(main_container, height=200)
        self.tabview.pack(fill="x", pady=(0, 10))

        self.tab_single = self.tabview.add("📹 Single Video")
        self.tab_playlist = self.tabview.add("📋 Playlist")
        self.tab_channel = self.tabview.add("📺 Channel")

        self._build_single_tab()
        self._build_playlist_tab()
        self._build_channel_tab()

        # ========== Settings ==========
        settings_frame = ctk.CTkFrame(main_container)
        settings_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            settings_frame, text="⚙️  Download Settings",
            font=("Segoe UI", 15, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))

        # Settings grid
        sg = ctk.CTkFrame(settings_frame, fg_color="transparent")
        sg.pack(fill="x", padx=15, pady=(0, 5))

        # Row 0: Quality + Format
        ctk.CTkLabel(sg, text="Quality:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.quality_var = ctk.StringVar(value="Best Quality")
        ctk.CTkOptionMenu(
            sg, variable=self.quality_var,
            values=list(QUALITY_OPTIONS.keys()), width=200
        ).grid(row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(sg, text="Format:").grid(row=0, column=2, sticky="w", padx=(20, 5), pady=5)
        self.format_var = ctk.StringVar(value="mp4")
        ctk.CTkOptionMenu(
            sg, variable=self.format_var,
            values=VIDEO_FORMATS + AUDIO_FORMATS, width=100
        ).grid(row=0, column=3, padx=5, pady=5)

        # Row 1: Naming + Custom Prefix
        ctk.CTkLabel(sg, text="Naming:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.naming_var = ctk.StringVar(value="Video Title")
        ctk.CTkOptionMenu(
            sg, variable=self.naming_var,
            values=list(NAMING_SCHEMES.keys()), width=200
        ).grid(row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(sg, text="Custom Prefix:").grid(row=1, column=2, sticky="w", padx=(20, 5), pady=5)
        self.prefix_entry = ctk.CTkEntry(sg, placeholder_text="e.g., MyVideo", width=150)
        self.prefix_entry.grid(row=1, column=3, padx=5, pady=5)

        # Row 2: Speed limit + Subtitle language
        ctk.CTkLabel(sg, text="Speed Limit:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        speed_frame = ctk.CTkFrame(sg, fg_color="transparent")
        speed_frame.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.speed_entry = ctk.CTkEntry(speed_frame, placeholder_text="0", width=100)
        self.speed_entry.pack(side="left")
        ctk.CTkLabel(speed_frame, text="KB/s (0=unlimited)", text_color="gray").pack(side="left", padx=5)

        ctk.CTkLabel(sg, text="Sub Language:").grid(row=2, column=2, sticky="w", padx=(20, 5), pady=5)
        self.subtitle_lang_entry = ctk.CTkEntry(sg, placeholder_text="en", width=150)
        self.subtitle_lang_entry.insert(0, "en")
        self.subtitle_lang_entry.grid(row=2, column=3, padx=5, pady=5)

        # Checkboxes row
        cb_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        cb_frame.pack(fill="x", padx=15, pady=(5, 10))

        self.thumbnail_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            cb_frame, text="🖼️ Embed Thumbnail", variable=self.thumbnail_var
        ).pack(side="left", padx=10)

        self.subtitle_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            cb_frame, text="💬 Download Subtitles", variable=self.subtitle_var
        ).pack(side="left", padx=10)

        self.subfolder_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            cb_frame, text="📂 Auto Subfolder (Playlist/Channel name)",
            variable=self.subfolder_var
        ).pack(side="left", padx=10)

        # ========== Download Directory ==========
        dir_frame = ctk.CTkFrame(main_container)
        dir_frame.pack(fill="x", pady=(0, 10))

        dir_inner = ctk.CTkFrame(dir_frame, fg_color="transparent")
        dir_inner.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            dir_inner, text="📁 Save To:",
            font=("Segoe UI", 13, "bold")
        ).pack(side="left", padx=(0, 10))

        self.dir_var = ctk.StringVar(value=DEFAULT_DOWNLOAD_DIR)
        ctk.CTkEntry(
            dir_inner, textvariable=self.dir_var, width=420
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            dir_inner, text="Browse", width=80, command=self._browse_dir
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            dir_inner, text="📂 Open", width=80, command=self._open_download_dir
        ).pack(side="left", padx=5)

        # ========== Progress ==========
        progress_frame = ctk.CTkFrame(main_container)
        progress_frame.pack(fill="x", pady=(0, 10))

        prog_inner = ctk.CTkFrame(progress_frame, fg_color="transparent")
        prog_inner.pack(fill="x", padx=15, pady=10)

        self.status_label = ctk.CTkLabel(
            prog_inner, text="⏳ Ready to download",
            font=("Segoe UI", 12), text_color="#aaaaaa"
        )
        self.status_label.pack(anchor="w", pady=(0, 5))

        bar_frame = ctk.CTkFrame(prog_inner, fg_color="transparent")
        bar_frame.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(bar_frame, height=22)
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_bar.set(0)

        self.progress_percent = ctk.CTkLabel(
            bar_frame, text="0%", font=("Segoe UI", 13, "bold"), width=60
        )
        self.progress_percent.pack(side="right", padx=(10, 0))

        # ========== Action Buttons ==========
        action_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        action_frame.pack(fill="x", pady=(0, 10))

        self.download_btn = ctk.CTkButton(
            action_frame, text="⬇️  Start Download", width=200, height=48,
            font=("Segoe UI", 16, "bold"),
            fg_color="#28a745", hover_color="#218838",
            command=self._start_download
        )
        self.download_btn.pack(side="left", padx=10)

        self.cancel_btn = ctk.CTkButton(
            action_frame, text="❌ Cancel", width=120, height=48,
            font=("Segoe UI", 14),
            fg_color="#dc3545", hover_color="#c82333",
            command=self._cancel_download, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=10)

        self.counter_label = ctk.CTkLabel(
            action_frame, text="", font=("Segoe UI", 12)
        )
        self.counter_label.pack(side="right", padx=15)

        # ========== Log ==========
        log_frame = ctk.CTkFrame(main_container)
        log_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            log_frame, text="📝 Download Log",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=15, pady=(10, 5))

        self.log_text = ctk.CTkTextbox(log_frame, height=120, font=("Consolas", 11))
        self.log_text.pack(fill="x", padx=15, pady=(0, 10))
        self.log_text.configure(state="disabled")

    # ==================== Tab builders ====================

    def _build_single_tab(self):
        """Build Single Video tab."""
        ctk.CTkLabel(
            self.tab_single, text="Enter YouTube Video URL:",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self.single_url_entry = ctk.CTkEntry(
            self.tab_single,
            placeholder_text="https://www.youtube.com/watch?v=...",
            height=38, font=("Segoe UI", 13)
        )
        self.single_url_entry.pack(fill="x", padx=10, pady=5)

        btn_frame = ctk.CTkFrame(self.tab_single, fg_color="transparent")
        btn_frame.pack(anchor="w", padx=10, pady=5)

        ctk.CTkButton(
            btn_frame, text="ℹ️ Fetch Info", width=140,
            command=self._fetch_single_info
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="📋 Paste", width=80,
            command=lambda: self._paste_clipboard(self.single_url_entry)
        ).pack(side="left", padx=10)

        self.single_info_label = ctk.CTkLabel(
            self.tab_single, text="", font=("Segoe UI", 11),
            text_color="#aaaaaa", wraplength=700, justify="left"
        )
        self.single_info_label.pack(anchor="w", padx=10, pady=5)

    def _build_playlist_tab(self):
        """Build Playlist tab."""
        ctk.CTkLabel(
            self.tab_playlist, text="Enter YouTube Playlist URL:",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        url_frame = ctk.CTkFrame(self.tab_playlist, fg_color="transparent")
        url_frame.pack(fill="x", padx=10, pady=5)

        self.playlist_url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://www.youtube.com/playlist?list=...",
            height=38, font=("Segoe UI", 13)
        )
        self.playlist_url_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            url_frame, text="📋", width=40,
            command=lambda: self._paste_clipboard(self.playlist_url_entry)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            url_frame, text="🔍 Fetch Videos", width=140,
            command=lambda: self._fetch_batch_info("playlist")
        ).pack(side="left", padx=5)

        # Selection
        sel_frame = ctk.CTkFrame(self.tab_playlist, fg_color="transparent")
        sel_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(sel_frame, text="Selection:").pack(side="left", padx=5)
        self.playlist_sel_var = ctk.StringVar(value="All Videos")
        ctk.CTkOptionMenu(
            sel_frame, variable=self.playlist_sel_var,
            values=list(SELECTION_MODES.keys()), width=200
        ).pack(side="left", padx=5)

        ctk.CTkLabel(sel_frame, text="Value:").pack(side="left", padx=5)
        self.playlist_sel_value = ctk.CTkEntry(
            sel_frame, placeholder_text="e.g., 1-10 or 1,3,5", width=130
        )
        self.playlist_sel_value.pack(side="left", padx=5)

        ctk.CTkButton(
            sel_frame, text="👁️ Preview & Select", width=150,
            command=lambda: self._show_video_list("playlist")
        ).pack(side="left", padx=5)

        self.playlist_info_label = ctk.CTkLabel(
            self.tab_playlist, text="", font=("Segoe UI", 11),
            text_color="#aaaaaa", wraplength=700, justify="left"
        )
        self.playlist_info_label.pack(anchor="w", padx=10, pady=5)

    def _build_channel_tab(self):
        """Build Channel tab."""
        ctk.CTkLabel(
            self.tab_channel, text="Enter YouTube Channel URL:",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        url_frame = ctk.CTkFrame(self.tab_channel, fg_color="transparent")
        url_frame.pack(fill="x", padx=10, pady=5)

        self.channel_url_entry = ctk.CTkEntry(
            url_frame,
            placeholder_text="https://www.youtube.com/@channelname/videos",
            height=38, font=("Segoe UI", 13)
        )
        self.channel_url_entry.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            url_frame, text="📋", width=40,
            command=lambda: self._paste_clipboard(self.channel_url_entry)
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            url_frame, text="🔍 Fetch Videos", width=140,
            command=lambda: self._fetch_batch_info("channel")
        ).pack(side="left", padx=5)

        # Selection
        sel_frame = ctk.CTkFrame(self.tab_channel, fg_color="transparent")
        sel_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(sel_frame, text="Selection:").pack(side="left", padx=5)
        self.channel_sel_var = ctk.StringVar(value="All Videos")
        ctk.CTkOptionMenu(
            sel_frame, variable=self.channel_sel_var,
            values=list(SELECTION_MODES.keys()), width=200
        ).pack(side="left", padx=5)

        ctk.CTkLabel(sel_frame, text="Value:").pack(side="left", padx=5)
        self.channel_sel_value = ctk.CTkEntry(
            sel_frame, placeholder_text="e.g., 1-10 or 5", width=130
        )
        self.channel_sel_value.pack(side="left", padx=5)

        ctk.CTkButton(
            sel_frame, text="👁️ Preview & Select", width=150,
            command=lambda: self._show_video_list("channel")
        ).pack(side="left", padx=5)

        self.channel_info_label = ctk.CTkLabel(
            self.tab_channel, text="", font=("Segoe UI", 11),
            text_color="#aaaaaa", wraplength=700, justify="left"
        )
        self.channel_info_label.pack(anchor="w", padx=10, pady=5)

    # ==================== Helpers ====================

    def _paste_clipboard(self, entry_widget):
        """Paste clipboard content into an entry widget."""
        try:
            text = self.clipboard_get()
            entry_widget.delete(0, "end")
            entry_widget.insert(0, text)
        except Exception:
            pass

    def _browse_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)

    def _open_download_dir(self):
        path = self.dir_var.get()
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def _log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_status(self, text):
        self.status_label.configure(text=text)
        self._log(text)

    def _update_progress(self, percent):
        self.progress_bar.set(percent / 100)
        self.progress_percent.configure(text=f"{percent:.1f}%")

    def _update_counter(self, total):
        self.counter_label.configure(text=f"📊 Total: {total} videos")

    def _get_current_tab(self):
        current = self.tabview.get()
        if "Single" in current:
            return "single"
        elif "Playlist" in current:
            return "playlist"
        elif "Channel" in current:
            return "channel"
        return "single"

    def _get_common_settings(self):
        """Get settings from UI widgets."""
        speed_text = self.speed_entry.get().strip()
        speed_limit = None
        if speed_text and speed_text.isdigit() and int(speed_text) > 0:
            speed_limit = int(speed_text)

        return {
            'quality': self.quality_var.get(),
            'naming_scheme': NAMING_SCHEMES[self.naming_var.get()],
            'custom_prefix': self.prefix_entry.get().strip(),
            'download_dir': self.dir_var.get(),
            'embed_thumbnail': self.thumbnail_var.get(),
            'download_subtitles': self.subtitle_var.get(),
            'subtitle_lang': self.subtitle_lang_entry.get().strip() or "en",
            'output_format': self.format_var.get(),
            'speed_limit': speed_limit,
            'create_subfolder': self.subfolder_var.get(),
        }

    # ==================== Fetch Info ====================

    def _fetch_single_info(self):
        url = self.single_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a video URL!")
            return

        self._update_status("Fetching video info...")

        def fetch():
            info = self.dm.fetch_info(url)
            if info:
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)
                channel = info.get('channel', info.get('uploader', 'Unknown'))
                views = info.get('view_count', 0)
                dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
                views_str = f"{views:,}" if views else "N/A"

                info_text = (
                    f"📹 {title}\n"
                    f"👤 {channel}  •  ⏱️ {dur_str}  •  👁️ {views_str} views"
                )
                self.after(0, lambda: self.single_info_label.configure(text=info_text))
                self.after(0, lambda: self._update_status("✅ Video info fetched!"))
            else:
                self.after(0, lambda: self._update_status("❌ Failed to fetch video info."))

        threading.Thread(target=fetch, daemon=True).start()

    def _fetch_batch_info(self, mode):
        if mode == "playlist":
            url = self.playlist_url_entry.get().strip()
            info_label = self.playlist_info_label
        else:
            url = self.channel_url_entry.get().strip()
            info_label = self.channel_info_label

        if not url:
            messagebox.showwarning("Warning", "Please enter a URL!")
            return

        self._update_status(f"🔍 Fetching {mode} info... This may take a while.")

        def fetch():
            result = self.dm.get_video_list(url, is_channel=(mode == "channel"))
            if result and len(result) == 3:
                videos, title, count = result
                self.fetched_videos = videos
                self.fetched_playlist_title = title

                icon = "📋" if mode == "playlist" else "📺"
                info_text = f"{icon} {title}  •  🎬 {count} videos found"
                self.after(0, lambda: info_label.configure(text=info_text))
                self.after(
                    0,
                    lambda: self._update_status(f"✅ Found {count} videos: {title}")
                )
            else:
                self.after(
                    0,
                    lambda: self._update_status(f"❌ Failed to fetch {mode} info.")
                )
                self.after(
                    0,
                    lambda: info_label.configure(
                        text="❌ Failed to fetch. Check URL and try again."
                    )
                )

        threading.Thread(target=fetch, daemon=True).start()

    def _show_video_list(self, mode):
        if not self.fetched_videos:
            messagebox.showinfo(
                "Info",
                "Please fetch videos first using the '🔍 Fetch Videos' button!"
            )
            return

        window = VideoListWindow(
            self, self.fetched_videos,
            title=f"Select Videos — {self.fetched_playlist_title}"
        )

        if window.result is not None:
            self.fetched_videos = window.result
            count = len(window.result)

            if mode == "playlist":
                self.playlist_info_label.configure(
                    text=f"📋 {self.fetched_playlist_title}  •  🎬 {count} videos selected"
                )
            else:
                self.channel_info_label.configure(
                    text=f"📺 {self.fetched_playlist_title}  •  🎬 {count} videos selected"
                )
            self._update_status(f"✅ {count} videos selected for download.")

    # ==================== Download ====================

    def _start_download(self):
        if self.dm.is_downloading:
            messagebox.showwarning("Warning", "A download is already in progress!")
            return

        tab = self._get_current_tab()
        settings = self._get_common_settings()

        # Reset
        self.dm.reset()
        self.progress_bar.set(0)
        self.progress_percent.configure(text="0%")
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")

        if tab == "single":
            self._download_single(settings)
        elif tab == "playlist":
            self._download_batch(settings, "playlist")
        elif tab == "channel":
            self._download_batch(settings, "channel")

    def _download_single(self, settings):
        url = self.single_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a video URL!")
            self._reset_buttons()
            return

        def download():
            self.dm.download_single(
                url=url,
                quality=settings['quality'],
                naming_scheme=settings['naming_scheme'],
                custom_prefix=settings['custom_prefix'],
                download_dir=settings['download_dir'],
                embed_thumbnail=settings['embed_thumbnail'],
                download_subtitles=settings['download_subtitles'],
                subtitle_lang=settings['subtitle_lang'],
                output_format=settings['output_format'],
                speed_limit=settings['speed_limit'],
                progress_callback=lambda p: self.after(0, lambda: self._update_progress(p)),
                status_callback=lambda s: self.after(0, lambda: self._update_status(s)),
            )
            self.after(0, self._reset_buttons)

        threading.Thread(target=download, daemon=True).start()

    def _download_batch(self, settings, mode):
        if mode == "playlist":
            url = self.playlist_url_entry.get().strip()
            sel_mode = SELECTION_MODES[self.playlist_sel_var.get()]
            sel_value = self.playlist_sel_value.get().strip()
        else:
            url = self.channel_url_entry.get().strip()
            sel_mode = SELECTION_MODES[self.channel_sel_var.get()]
            sel_value = self.channel_sel_value.get().strip()

        if not url:
            messagebox.showwarning("Warning", f"Please enter a {mode} URL!")
            self._reset_buttons()
            return

        def download():
            if self.fetched_videos:
                videos = self.fetched_videos
                playlist_title = self.fetched_playlist_title
                actual_sel_mode = sel_mode
                actual_sel_value = sel_value
            else:
                self.after(
                    0,
                    lambda: self._update_status(f"🔍 Fetching {mode} info...")
                )
                result = self.dm.get_video_list(
                    url,
                    callback=lambda s: self.after(0, lambda: self._update_status(s)),
                    is_channel=(mode == "channel")
                )
                if not result or len(result) != 3:
                    self.after(
                        0,
                        lambda: self._update_status(f"❌ Failed to fetch {mode}.")
                    )
                    self.after(0, self._reset_buttons)
                    return
                videos, playlist_title, _ = result
                actual_sel_mode = sel_mode
                actual_sel_value = sel_value

            subfolder = playlist_title if settings['create_subfolder'] else ""

            self.dm.download_batch(
                videos=videos,
                quality=settings['quality'],
                naming_scheme=settings['naming_scheme'],
                custom_prefix=settings['custom_prefix'],
                download_dir=settings['download_dir'],
                subfolder=subfolder,
                embed_thumbnail=settings['embed_thumbnail'],
                download_subtitles=settings['download_subtitles'],
                subtitle_lang=settings['subtitle_lang'],
                output_format=settings['output_format'],
                speed_limit=settings['speed_limit'],
                selection_mode=actual_sel_mode,
                selection_value=actual_sel_value,
                progress_callback=lambda p: self.after(0, lambda: self._update_progress(p)),
                status_callback=lambda s: self.after(0, lambda: self._update_status(s)),
                video_count_callback=lambda c: self.after(0, lambda: self._update_counter(c)),
            )
            self.after(0, self._reset_buttons)

        threading.Thread(target=download, daemon=True).start()

    def _cancel_download(self):
        if self.dm.is_downloading:
            self.dm.cancel()
            self._update_status("⚠️ Cancelling download...")

    def _reset_buttons(self):
        self.download_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
