"""Modern GUI for YouTube Video Downloader using CustomTkinter."""

import os
import sys
import subprocess
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
from batch_manager import BatchManager
from scheduler import DownloadScheduler
from gui_dialogs import TitleRulesDialog, ScheduleDialog, SaveBatchDialog


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
        self.batch_manager = BatchManager()
        self.scheduler = DownloadScheduler(runner_callback=self._run_scheduled_job)
        self.fetched_videos = []
        self.fetched_playlist_title = ""

        self._build_ui()
        self._check_system_deps()
        self.after(2000, self._start_scheduler_ticker)

    def _build_ui(self):
        # Main scrollable container
        main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=15, pady=10)

        # ========== Title ==========
        title_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))

        title_left = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_left, text="🎬 YT Video Downloader Pro",
            font=("Segoe UI", 26, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_left,
            text="Download Videos • Playlists • Channels — with Full Control",
            font=("Segoe UI", 12), text_color="gray",
        ).pack(anchor="w")

        ctk.CTkButton(
            title_frame, text="🔄 Update & Restart", width=150, height=34,
            fg_color="#1F6AA5", hover_color="#144870",
            font=("Segoe UI", 12, "bold"),
            command=self._update_and_restart
        ).pack(side="right", padx=5)

        # ========== Tab View ==========
        self.tabview = ctk.CTkTabview(main_container, height=200)
        self.tabview.pack(fill="x", pady=(0, 10))

        self.tab_single = self.tabview.add("📹 Single Video")
        self.tab_playlist = self.tabview.add("📋 Playlist")
        self.tab_channel = self.tabview.add("📺 Channel")
        self.tab_batches = self.tabview.add("📁 Batches")
        self.tab_scheduler = self.tabview.add("⏰ Scheduler")

        self._build_single_tab()
        self._build_playlist_tab()
        self._build_channel_tab()
        self._build_batches_tab()
        self._build_scheduler_tab()

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

        # Row 1: Naming + Rules Button + Custom Prefix
        ctk.CTkLabel(sg, text="Naming:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.naming_var = ctk.StringVar(value="Numbered + Rewrite Title (01 - Cleaned)")
        naming_box = ctk.CTkFrame(sg, fg_color="transparent")
        naming_box.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ctk.CTkOptionMenu(
            naming_box, variable=self.naming_var,
            values=list(NAMING_SCHEMES.keys()), width=230
        ).pack(side="left")

        ctk.CTkButton(
            naming_box, text="⚙️ Rules", width=65, height=28,
            fg_color="#495057", hover_color="#343a40",
            font=("Segoe UI", 11, "bold"),
            command=self._open_title_rules_dialog
        ).pack(side="left", padx=(5, 0))

        ctk.CTkLabel(sg, text="Custom Prefix:").grid(row=1, column=2, sticky="w", padx=(20, 5), pady=5)
        self.prefix_entry = ctk.CTkEntry(sg, placeholder_text="e.g., MyVideo", width=150)
        self.prefix_entry.grid(row=1, column=3, padx=5, pady=5)
        self._attach_entry_context_menu(self.prefix_entry)

        # Row 2: Speed limit + Subtitle language
        ctk.CTkLabel(sg, text="Speed Limit:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        speed_frame = ctk.CTkFrame(sg, fg_color="transparent")
        speed_frame.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.speed_entry = ctk.CTkEntry(speed_frame, placeholder_text="0", width=100)
        self.speed_entry.pack(side="left")
        self._attach_entry_context_menu(self.speed_entry)
        ctk.CTkLabel(speed_frame, text="KB/s (0=unlimited)", text_color="gray").pack(side="left", padx=5)

        ctk.CTkLabel(sg, text="Sub Language:").grid(row=2, column=2, sticky="w", padx=(20, 5), pady=5)
        self.subtitle_lang_entry = ctk.CTkEntry(sg, placeholder_text="en", width=150)
        self.subtitle_lang_entry.insert(0, "en")
        self.subtitle_lang_entry.grid(row=2, column=3, padx=5, pady=5)
        self._attach_entry_context_menu(self.subtitle_lang_entry)

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

        # Cookies row (for VPS / Anti-Bot)
        cookie_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        cookie_frame.pack(fill="x", padx=15, pady=(0, 10))

        ctk.CTkButton(
            cookie_frame,
            text="🍪 Manage YouTube Cookies",
            width=210,
            command=self._open_cookie_manager,
            fg_color="#1F6AA5",
            hover_color="#144870"
        ).pack(side="left", padx=(0, 10))

        self.cookie_status_label = ctk.CTkLabel(
            cookie_frame,
            text=self._get_cookie_status_text(),
            font=("Segoe UI", 11),
            text_color="#2ECC71" if self._has_cookies() else "#F39C12"
        )
        self.cookie_status_label.pack(side="left")

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
        self.dir_entry = ctk.CTkEntry(
            dir_inner, textvariable=self.dir_var, width=420
        )
        self.dir_entry.pack(side="left", padx=5)
        self._attach_entry_context_menu(self.dir_entry)

        ctk.CTkButton(
            dir_inner, text="Browse", width=80, command=self._browse_dir
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            dir_inner, text="📂 Open", width=80, command=self._open_download_dir
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
            action_frame, text="⬇️  Start Download", width=180, height=48,
            font=("Segoe UI", 15, "bold"),
            fg_color="#28a745", hover_color="#218838",
            command=self._start_download
        )
        self.download_btn.pack(side="left", padx=(10, 5))

        self.cancel_btn = ctk.CTkButton(
            action_frame, text="❌ Cancel", width=110, height=48,
            font=("Segoe UI", 14),
            fg_color="#dc3545", hover_color="#c82333",
            command=self._cancel_download, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=5)

        self.save_batch_btn = ctk.CTkButton(
            action_frame, text="💾 Save as Batch", width=145, height=48,
            font=("Segoe UI", 13, "bold"),
            fg_color="#17a2b8", hover_color="#138496",
            command=self._save_current_as_batch
        )
        self.save_batch_btn.pack(side="left", padx=5)

        self.schedule_btn = ctk.CTkButton(
            action_frame, text="⏰ Schedule", width=125, height=48,
            font=("Segoe UI", 13, "bold"),
            fg_color="#6f42c1", hover_color="#59359a",
            command=self._schedule_current_download
        )
        self.schedule_btn.pack(side="left", padx=5)

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
        self._attach_textbox_context_menu(self.log_text)

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
        self._attach_entry_context_menu(self.single_url_entry)

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
        self._attach_entry_context_menu(self.playlist_url_entry)

        ctk.CTkButton(
            url_frame, text="📋 Paste", width=80,
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
        self._attach_entry_context_menu(self.playlist_sel_value)

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
        self._attach_entry_context_menu(self.channel_url_entry)

        ctk.CTkButton(
            url_frame, text="📋 Paste", width=80,
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
        self._attach_entry_context_menu(self.channel_sel_value)

        ctk.CTkButton(
            sel_frame, text="👁️ Preview & Select", width=150,
            command=lambda: self._show_video_list("channel")
        ).pack(side="left", padx=5)

        self.channel_info_label = ctk.CTkLabel(
            self.tab_channel, text="", font=("Segoe UI", 11),
            text_color="#aaaaaa", wraplength=700, justify="left"
        )
        self.channel_info_label.pack(anchor="w", padx=10, pady=5)

    def _open_title_rules_dialog(self):
        """Open modal dialog to view and customize Title Rewrite Rules."""
        TitleRulesDialog(self)

    # ==================== Batches Tab ====================

    def _build_batches_tab(self):
        """Build Saved Batches tab."""
        header_frame = ctk.CTkFrame(self.tab_batches, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            header_frame, text="📁 Saved Download Batches",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left")

        ctk.CTkButton(
            header_frame, text="➕ Save Current as Batch", width=170, height=30,
            fg_color="#17a2b8", hover_color="#138496",
            command=self._save_current_as_batch
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            header_frame, text="🔄 Refresh", width=80, height=30,
            command=self._render_batches_list
        ).pack(side="right", padx=4)

        self.batches_scroll = ctk.CTkScrollableFrame(self.tab_batches, height=130)
        self.batches_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self._render_batches_list()

    def _render_batches_list(self):
        """Render all saved batch cards in the batches tab."""
        for widget in self.batches_scroll.winfo_children():
            widget.destroy()

        batches = self.batch_manager.get_all()
        if not batches:
            empty_frame = ctk.CTkFrame(self.batches_scroll, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=25)
            ctk.CTkLabel(
                empty_frame,
                text="📁 No saved download batches yet.\nSet up a Single, Playlist, or Channel download and click '💾 Save as Batch'!",
                font=("Segoe UI", 12), text_color="gray", justify="center"
            ).pack()
            return

        for b in batches:
            bid = b.get("id")
            name = b.get("name", "Untitled Batch")
            btype = b.get("type", "channel")
            url = b.get("url", "")
            quality = b.get("quality", "Best Quality")
            fmt = b.get("format", "mp4")
            naming = b.get("naming_scheme", "title")
            sel_val = b.get("selection_value", "")
            status = b.get("status", "Ready")

            type_icons = {"single": "📹 Single", "playlist": "📋 Playlist", "channel": "📺 Channel"}
            type_str = type_icons.get(btype, "🎬 Video")

            card = ctk.CTkFrame(self.batches_scroll)
            card.pack(fill="x", padx=5, pady=4)

            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            title_row = ctk.CTkFrame(left, fg_color="transparent")
            title_row.pack(fill="x")
            ctk.CTkLabel(
                title_row, text=name, font=("Segoe UI", 13, "bold")
            ).pack(side="left")
            ctk.CTkLabel(
                title_row, text=f" [{type_str}]", font=("Segoe UI", 11, "bold"), text_color="#17a2b8"
            ).pack(side="left", padx=5)

            sub_text = f"🔗 {url[:50]}...  •  ⚙️ {quality} ({fmt})  •  🏷️ {naming}"
            if sel_val:
                sub_text += f"  •  Range: {sel_val}"
            ctk.CTkLabel(
                left, text=sub_text, font=("Segoe UI", 10), text_color="gray", anchor="w"
            ).pack(fill="x", pady=(2, 0))

            right = ctk.CTkFrame(card, fg_color="transparent")
            right.pack(side="right", padx=10, pady=8)

            status_colors = {"Ready": "#17a2b8", "Running": "#ffc107", "Completed": "#28a745", "Failed": "#dc3545"}
            col = status_colors.get(status, "gray")
            ctk.CTkLabel(
                right, text=f"● {status}", font=("Segoe UI", 11, "bold"), text_color=col, width=80
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                right, text="▶️ Run Now", width=85, height=28,
                fg_color="#28a745", hover_color="#218838",
                command=lambda b_item=b: self._run_batch(b_item)
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                right, text="⏰ Schedule", width=85, height=28,
                fg_color="#6f42c1", hover_color="#59359a",
                command=lambda b_item=b: self._open_schedule_dialog(
                    target_name=b_item.get("name"),
                    target_type="batch",
                    target_data=b_item
                )
            ).pack(side="left", padx=3)

            ctk.CTkButton(
                right, text="🗑️", width=35, height=28,
                fg_color="#dc3545", hover_color="#c82333",
                command=lambda bid_val=bid: self._delete_batch(bid_val)
            ).pack(side="left", padx=3)

    def _delete_batch(self, batch_id):
        if messagebox.askyesno("Delete Batch", "Are you sure you want to delete this batch?"):
            self.batch_manager.delete(batch_id)
            self._render_batches_list()
            self._update_status("Batch deleted.")

    def _save_current_as_batch(self):
        pkg = self._get_current_download_package()
        if not pkg["url"]:
            messagebox.showwarning("Warning", "Please enter a valid YouTube URL first!")
            return
        SaveBatchDialog(
            parent=self,
            batch_manager=self.batch_manager,
            default_data=pkg,
            on_saved=self._render_batches_list
        )

    # ==================== Scheduler Tab ====================

    def _build_scheduler_tab(self):
        """Build Scheduler tab."""
        header_frame = ctk.CTkFrame(self.tab_scheduler, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            header_frame, text="⏰ Automated Download Scheduler",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left")

        ctk.CTkButton(
            header_frame, text="➕ Schedule Current", width=150, height=30,
            fg_color="#6f42c1", hover_color="#59359a",
            command=self._schedule_current_download
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            header_frame, text="🔄 Refresh", width=80, height=30,
            command=self._render_schedules_list
        ).pack(side="right", padx=4)

        self.scheduler_ticker_label = ctk.CTkLabel(
            self.tab_scheduler, text="⏳ No upcoming scheduled downloads.",
            font=("Segoe UI", 11, "bold"), text_color="#17a2b8"
        )
        self.scheduler_ticker_label.pack(anchor="w", padx=10, pady=(0, 4))

        self.schedules_scroll = ctk.CTkScrollableFrame(self.tab_scheduler, height=120)
        self.schedules_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self._render_schedules_list()

    def _render_schedules_list(self):
        """Render all scheduled jobs in the scheduler tab."""
        for widget in self.schedules_scroll.winfo_children():
            widget.destroy()

        jobs = self.scheduler.get_all()
        if not jobs:
            empty_frame = ctk.CTkFrame(self.schedules_scroll, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=25)
            ctk.CTkLabel(
                empty_frame,
                text="⏰ No scheduled downloads yet.\nSchedule any batch or current download to start automatically at your chosen time!",
                font=("Segoe UI", 12), text_color="gray", justify="center"
            ).pack()
            return

        for job in jobs:
            jid = job.get("id")
            name = job.get("name", "Scheduled Download")
            run_at = job.get("run_at", "")
            status = job.get("status", "Pending")
            jtype = job.get("job_type", "direct")
            tdata = job.get("target_data", {})
            countdown = self.scheduler.get_countdown(run_at) if status == "Pending" else status

            card = ctk.CTkFrame(self.schedules_scroll)
            card.pack(fill="x", padx=5, pady=4)

            left = ctk.CTkFrame(card, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            title_row = ctk.CTkFrame(left, fg_color="transparent")
            title_row.pack(fill="x")
            ctk.CTkLabel(title_row, text=name, font=("Segoe UI", 13, "bold")).pack(side="left")
            ctk.CTkLabel(
                title_row, text=f" [{jtype.upper()}]", font=("Segoe UI", 11), text_color="#3498DB"
            ).pack(side="left", padx=5)

            target_url = tdata.get("url", "")
            sub = f"⏰ Run at: {run_at} (⏳ {countdown})"
            if target_url:
                sub += f"  •  🔗 {target_url[:40]}..."
            ctk.CTkLabel(left, text=sub, font=("Segoe UI", 10), text_color="gray", anchor="w").pack(fill="x", pady=(2, 0))

            right = ctk.CTkFrame(card, fg_color="transparent")
            right.pack(side="right", padx=10, pady=8)

            status_colors = {"Pending": "#f39c12", "Running": "#3498db", "Completed": "#2ecc71", "Cancelled": "#e74c3c", "Failed": "#e74c3c"}
            col = status_colors.get(status, "gray")
            ctk.CTkLabel(right, text=status, font=("Segoe UI", 11, "bold"), text_color=col, width=75).pack(side="left", padx=5)

            if status == "Pending":
                ctk.CTkButton(
                    right, text="▶️ Run Now", width=80, height=28,
                    fg_color="#28a745", hover_color="#218838",
                    command=lambda j_item=job: self._run_scheduled_job(j_item)
                ).pack(side="left", padx=3)

                ctk.CTkButton(
                    right, text="⏸️ Cancel", width=75, height=28,
                    fg_color="#ffc107", hover_color="#e0a800", text_color="black",
                    command=lambda jid_val=jid: self._cancel_schedule(jid_val)
                ).pack(side="left", padx=3)

            ctk.CTkButton(
                right, text="🗑️", width=35, height=28,
                fg_color="#dc3545", hover_color="#c82333",
                command=lambda jid_val=jid: self._delete_schedule(jid_val)
            ).pack(side="left", padx=3)

    def _delete_schedule(self, job_id):
        if messagebox.askyesno("Delete Schedule", "Delete this scheduled download task?"):
            self.scheduler.delete(job_id)
            self._render_schedules_list()
            self._update_status("Schedule deleted.")

    def _cancel_schedule(self, job_id):
        self.scheduler.cancel(job_id)
        self._render_schedules_list()
        self._update_status("Schedule cancelled.")

    def _schedule_current_download(self):
        pkg = self._get_current_download_package()
        if not pkg["url"]:
            messagebox.showwarning("Warning", "Please enter a valid YouTube URL first!")
            return
        ScheduleDialog(
            parent=self,
            scheduler=self.scheduler,
            target_name=pkg["name"],
            target_type="direct",
            target_data=pkg,
            on_scheduled=self._render_schedules_list
        )

    def _open_schedule_dialog(self, target_name="", target_type="direct", target_data=None):
        ScheduleDialog(
            parent=self,
            scheduler=self.scheduler,
            target_name=target_name,
            target_type=target_type,
            target_data=target_data,
            on_scheduled=self._render_schedules_list
        )

    def _start_scheduler_ticker(self):
        """Update live countdown on scheduler tab periodically."""
        try:
            jobs = self.scheduler.get_all()
            pending = [j for j in jobs if j.get("status") == "Pending"]
            if pending:
                next_job = pending[0]
                run_at = next_job.get("run_at", "")
                name = next_job.get("name", "Task")
                cd = self.scheduler.get_countdown(run_at)
                if hasattr(self, "scheduler_ticker_label"):
                    self.scheduler_ticker_label.configure(
                        text=f"⏳ Next: '{name}' starts in {cd} ({run_at})"
                    )
            else:
                if hasattr(self, "scheduler_ticker_label"):
                    self.scheduler_ticker_label.configure(text="⏳ No upcoming scheduled downloads.")
        except Exception:
            pass
        self.after(2000, self._start_scheduler_ticker)

    def _get_current_download_package(self):
        """Extract all current configuration details from the active tab and settings."""
        tab = self._get_current_tab()
        settings = self._get_common_settings()
        url = ""
        name = "Download"
        sel_mode = "all"
        sel_val = ""

        if tab == "single":
            url = self.single_url_entry.get().strip()
            name = "Single Video"
        elif tab == "playlist":
            url = self.playlist_url_entry.get().strip()
            name = self.fetched_playlist_title or "Playlist Download"
            sel_mode = SELECTION_MODES.get(self.playlist_sel_var.get(), "all")
            sel_val = self.playlist_sel_value.get().strip()
        elif tab == "channel":
            url = self.channel_url_entry.get().strip()
            name = self.fetched_playlist_title or "Channel Download"
            sel_mode = SELECTION_MODES.get(self.channel_sel_var.get(), "all")
            sel_val = self.channel_sel_value.get().strip()

        return {
            "name": name,
            "type": tab,
            "url": url,
            "quality": settings.get("quality", "Best Quality"),
            "format": settings.get("output_format", "mp4"),
            "naming_scheme": settings.get("naming_scheme", "title"),
            "custom_prefix": settings.get("custom_prefix", ""),
            "selection_mode": sel_mode,
            "selection_value": sel_val,
            "download_dir": settings.get("download_dir", DEFAULT_DOWNLOAD_DIR),
            "subfolder": settings.get("subfolder", ""),
            "embed_thumbnail": settings.get("embed_thumbnail", False),
            "download_subtitles": settings.get("download_subtitles", False),
            "subtitle_lang": settings.get("subtitle_lang", "en"),
            "speed_limit": settings.get("speed_limit", None),
        }

    def _run_batch(self, batch):
        """Run a saved batch immediately."""
        if self.dm.is_downloading:
            messagebox.showwarning("Warning", "A download is already running! Please wait for it to complete.")
            return

        url = batch.get("url")
        if not url:
            messagebox.showerror("Error", "Batch has no URL!")
            return

        self.batch_manager.mark_status(batch["id"], "Running", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._render_batches_list()

        def done_callback(success):
            status = "Completed" if success else "Failed"
            self.batch_manager.mark_status(batch["id"], status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.after(0, self._render_batches_list)

        self._execute_package_download(batch, on_complete=done_callback)

    def _run_scheduled_job(self, job):
        """Called automatically by DownloadScheduler when scheduled time arrives."""
        self.scheduler.set_busy(True)
        self.after(0, lambda: self._update_status(f"⏰ Scheduler triggered: '{job.get('name')}'!"))

        jtype = job.get("job_type", "direct")
        tdata = job.get("target_data", {})

        def done_callback(success):
            st = "Completed" if success else "Failed"
            self.scheduler.mark_status(job["id"], st, f"Finished at {datetime.now().strftime('%H:%M:%S')}")
            self.scheduler.set_busy(False)
            self.after(0, self._render_schedules_list)

        if jtype == "batch":
            bid = tdata.get("id")
            saved_batch = self.batch_manager.get(bid) if bid else tdata
            if saved_batch:
                self.after(0, lambda: self._execute_package_download(saved_batch, on_complete=done_callback))
            else:
                done_callback(False)
        else:
            self.after(0, lambda: self._execute_package_download(tdata, on_complete=done_callback))

    def _execute_package_download(self, pkg, on_complete=None):
        """Execute a download package (single or batch) on a background thread."""
        btype = pkg.get("type", "single")
        url = pkg.get("url", "")
        naming = pkg.get("naming_scheme", "title")
        quality = pkg.get("quality", "Best Quality")
        custom_prefix = pkg.get("custom_prefix", "")
        download_dir = pkg.get("download_dir", DEFAULT_DOWNLOAD_DIR)
        embed_thumb = pkg.get("embed_thumbnail", False)
        subtitles = pkg.get("download_subtitles", False)
        sub_lang = pkg.get("subtitle_lang", "en")
        fmt = pkg.get("format", "mp4")
        speed = pkg.get("speed_limit", None)
        sel_mode = pkg.get("selection_mode", "all")
        sel_val = pkg.get("selection_value", "")
        subfolder = pkg.get("subfolder", "")

        self.dm.reset()
        self.progress_bar.set(0)
        self.progress_percent.configure(text="0%")
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")

        def worker():
            success = False
            try:
                if btype == "single":
                    success = self.dm.download_single(
                        url=url,
                        quality=quality,
                        naming_scheme=naming,
                        custom_prefix=custom_prefix,
                        download_dir=download_dir,
                        embed_thumbnail=embed_thumb,
                        download_subtitles=subtitles,
                        subtitle_lang=sub_lang,
                        output_format=fmt,
                        speed_limit=speed,
                        progress_callback=lambda p: self.after(0, lambda: self._update_progress(p)),
                        status_callback=lambda s: self.after(0, lambda: self._update_status(s)),
                    )
                else:
                    self.after(0, lambda: self._update_status(f"🔍 Fetching {btype} info for batch download..."))
                    videos, pl_title, _ = self.dm.fetch_playlist_or_channel(url, flat=True)
                    actual_subfolder = subfolder or pl_title
                    success = self.dm.download_batch(
                        videos=videos,
                        quality=quality,
                        naming_scheme=naming,
                        custom_prefix=custom_prefix,
                        download_dir=download_dir,
                        subfolder=actual_subfolder,
                        embed_thumbnail=embed_thumb,
                        download_subtitles=subtitles,
                        subtitle_lang=sub_lang,
                        output_format=fmt,
                        speed_limit=speed,
                        selection_mode=sel_mode,
                        selection_value=sel_val,
                        progress_callback=lambda p: self.after(0, lambda: self._update_progress(p)),
                        status_callback=lambda s: self.after(0, lambda: self._update_status(s)),
                        video_count_callback=lambda c: self.after(0, lambda: self._update_counter(c)),
                    )
            except Exception as e:
                self.after(0, lambda: self._update_status(f"❌ Error: {e}"))
                success = False
            finally:
                self.after(0, self._reset_buttons)
                if on_complete:
                    on_complete(success)

        threading.Thread(target=worker, daemon=True).start()

    # ==================== Helpers ====================

    def _get_clipboard_text(self):
        """Robustly retrieve clipboard text across Windows, macOS, and Linux/XRDP."""
        # 1. Standard Tkinter clipboard (UTF8)
        try:
            val = self.clipboard_get(type='UTF8_STRING')
            if val and val.strip():
                return val.strip()
        except Exception:
            pass

        # 2. Standard Tkinter clipboard (Default)
        try:
            val = self.clipboard_get()
            if val and val.strip():
                return val.strip()
        except Exception:
            pass

        # 3. Linux PRIMARY selection (X11 mouse highlight)
        try:
            val = self.clipboard_get(selection='PRIMARY')
            if val and val.strip():
                return val.strip()
        except Exception:
            pass

        # 4. Linux xclip / xsel (essential for XRDP clipboard sync)
        if sys.platform.startswith('linux'):
            for cmd in [
                ['xclip', '-selection', 'clipboard', '-o'],
                ['xclip', '-selection', 'primary', '-o'],
                ['xsel', '-b', '-o'],
                ['xsel', '-p', '-o'],
            ]:
                try:
                    out = subprocess.check_output(cmd, timeout=1, stderr=subprocess.DEVNULL)
                    text = out.decode('utf-8', errors='ignore').strip()
                    if text:
                        return text
                except Exception:
                    pass

        return ""

    def _paste_clipboard(self, entry_widget):
        """Paste clipboard content into an entry widget."""
        text = self._get_clipboard_text()
        if text:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, text)
            inner = getattr(entry_widget, '_entry', entry_widget)
            try:
                inner.focus_set()
                inner.icursor("end")
            except Exception:
                pass
            self._update_status("📋 URL pasted successfully!")
        else:
            self._update_status("⚠️ Clipboard is empty or could not be read.")

    def _attach_entry_context_menu(self, ctk_entry):
        """Attach right-click context menu (Paste, Copy, Clear) and key bindings to an entry widget."""
        inner = getattr(ctk_entry, '_entry', ctk_entry)

        def paste_action(event=None):
            text = self._get_clipboard_text()
            if text:
                try:
                    inner.focus_set()
                    if inner.select_present():
                        inner.delete("sel.first", "sel.last")
                except Exception:
                    pass
                ctk_entry.insert(inner.index("insert"), text)
                self._update_status("📋 Pasted successfully!")
            return "break"

        def copy_action(event=None):
            try:
                selected = inner.selection_get()
            except Exception:
                selected = inner.get()
            if selected:
                self.clipboard_clear()
                self.clipboard_append(selected)
                self._update_status("📄 Copied to clipboard!")
            return "break"

        def cut_action(event=None):
            copy_action()
            try:
                if inner.select_present():
                    inner.delete("sel.first", "sel.last")
                else:
                    ctk_entry.delete(0, "end")
            except Exception:
                ctk_entry.delete(0, "end")
            return "break"

        def select_all_action(event=None):
            inner.focus_set()
            inner.select_range(0, "end")
            inner.icursor("end")
            return "break"

        def clear_action(event=None):
            ctk_entry.delete(0, "end")
            return "break"

        # Right-click context menu
        menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        menu.add_command(label="📋 Paste (Ctrl+V)", command=paste_action)
        menu.add_command(label="📄 Copy (Ctrl+C)", command=copy_action)
        menu.add_command(label="✂️ Cut (Ctrl+X)", command=cut_action)
        menu.add_separator()
        menu.add_command(label="Select All (Ctrl+A)", command=select_all_action)
        menu.add_command(label="🗑️ Clear", command=clear_action)

        def show_menu(event):
            try:
                inner.focus_set()
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widgets_to_bind = [inner]
        if ctk_entry != inner:
            widgets_to_bind.append(ctk_entry)

        for w in widgets_to_bind:
            w.bind("<Control-v>", paste_action)
            w.bind("<Control-V>", paste_action)
            w.bind("<Shift-Insert>", paste_action)
            w.bind("<Button-2>", paste_action)
            w.bind("<Button-3>", show_menu)
            w.bind("<Control-Button-1>", show_menu)

    def _attach_textbox_context_menu(self, ctk_textbox):
        """Attach right-click context menu and key bindings to a CTkTextbox widget."""
        inner = getattr(ctk_textbox, '_textbox', ctk_textbox)

        def is_editable():
            try:
                return str(inner.cget("state")) != "disabled"
            except Exception:
                return True

        def paste_action(event=None):
            if not is_editable():
                return "break"
            text = self._get_clipboard_text()
            if text:
                try:
                    inner.focus_set()
                    inner.delete("sel.first", "sel.last")
                except Exception:
                    pass
                inner.insert("insert", text)
                self._update_status("📋 Pasted successfully!")
            return "break"

        def copy_action(event=None):
            try:
                selected = inner.get("sel.first", "sel.last")
            except Exception:
                selected = inner.get("1.0", "end-1c")
            if selected:
                self.clipboard_clear()
                self.clipboard_append(selected)
                self._update_status("📄 Copied to clipboard!")
            return "break"

        def cut_action(event=None):
            if not is_editable():
                return copy_action(event)
            copy_action()
            try:
                inner.delete("sel.first", "sel.last")
            except Exception:
                inner.delete("1.0", "end")
            return "break"

        def select_all_action(event=None):
            inner.focus_set()
            inner.tag_add("sel", "1.0", "end")
            return "break"

        def clear_action(event=None):
            if not is_editable():
                return "break"
            inner.delete("1.0", "end")
            return "break"

        def show_menu(event):
            try:
                inner.focus_set()
                menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
                if is_editable():
                    menu.add_command(label="📋 Paste (Ctrl+V)", command=paste_action)
                menu.add_command(label="📄 Copy (Ctrl+C)", command=copy_action)
                if is_editable():
                    menu.add_command(label="✂️ Cut (Ctrl+X)", command=cut_action)
                menu.add_separator()
                menu.add_command(label="Select All (Ctrl+A)", command=select_all_action)
                if is_editable():
                    menu.add_command(label="🗑️ Clear", command=clear_action)
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass

        widgets_to_bind = [inner]
        if ctk_textbox != inner:
            widgets_to_bind.append(ctk_textbox)

        for w in widgets_to_bind:
            w.bind("<Control-v>", paste_action)
            w.bind("<Control-V>", paste_action)
            w.bind("<Shift-Insert>", paste_action)
            w.bind("<Button-2>", paste_action)
            w.bind("<Button-3>", show_menu)
            w.bind("<Control-Button-1>", show_menu)

    def _update_and_restart(self):
        """Pull latest code from GitHub, install dependencies and restart the application cleanly."""
        self._update_status("🔄 Checking for updates from GitHub...")
        try:
            subprocess.run(["git", "fetch", "origin", "main"], timeout=15)
            subprocess.run(["git", "reset", "--hard", "origin/main"], timeout=15)
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"], timeout=45)
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "--quiet"], timeout=45)
            if sys.platform.startswith('linux'):
                if not shutil.which('node') and not shutil.which('deno') and not shutil.which('nodejs'):
                    subprocess.run(["apt", "update", "-y"], timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["apt", "install", "-y", "nodejs", "xclip"], timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists('/usr/bin/nodejs') and not os.path.exists('/usr/bin/node'):
                    try:
                        os.symlink('/usr/bin/nodejs', '/usr/bin/node')
                    except Exception:
                        pass
        except Exception:
            pass
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def _check_system_deps(self):
        """Ensure JavaScript runtime (Node.js/Deno) and clipboard tools (xclip) are available."""
        def worker():
            from downloader import get_js_runtime_config
            js_cfg = get_js_runtime_config()
            if js_cfg:
                rt_name = list(js_cfg.keys())[0]
                rt_label = 'Deno' if rt_name == 'deno' else 'Node.js'
                self.after(0, lambda: self._log(f"⚡ JS Runtime: {rt_label} active (YouTube challenge solver enabled)"))
            else:
                self.after(0, lambda: self._log("⚠️ JS Engine missing! YouTube challenge solver may be restricted."))

            if sys.platform.startswith('linux'):
                missing = []
                if not shutil.which('xclip'):
                    missing.append('xclip')
                if not shutil.which('unzip'):
                    missing.append('unzip')
                if missing:
                    try:
                        subprocess.run(['apt', 'update', '-y'], timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        subprocess.run(['apt', 'install', '-y'] + missing, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
        threading.Thread(target=worker, daemon=True).start()

    def _browse_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.dir_var.set(directory)

    def _open_download_dir(self):
        path = self.dir_var.get()
        os.makedirs(path, exist_ok=True)
        try:
            if hasattr(os, 'startfile'):
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', path])
            else:
                subprocess.run(['xdg-open', path])
        except Exception:
            pass

    def _get_cookie_file_path(self):
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

    def _has_cookies(self):
        return DownloadManager.find_cookie_file() is not None

    def _get_cookie_status_text(self):
        cookie_path = DownloadManager.find_cookie_file()
        if cookie_path:
            return f"✅ YouTube Cookies Active: {os.path.basename(cookie_path)}"
        app_cookie = self._get_cookie_file_path()
        if os.path.exists(app_cookie):
            return "⚠️ cookies.txt found but NOT for YouTube (Click to update)"
        return "⚠️ No YouTube Cookies (Click to Add / Bypass Bot Check)"

    def _update_cookie_status_label(self):
        if hasattr(self, 'cookie_status_label'):
            cookie_path = DownloadManager.find_cookie_file()
            if cookie_path:
                self.cookie_status_label.configure(
                    text=f"✅ YouTube Cookies Active: {os.path.basename(cookie_path)}",
                    text_color="#2ECC71"
                )
            else:
                self.cookie_status_label.configure(
                    text=self._get_cookie_status_text(),
                    text_color="#F39C12"
                )

    def _open_cookie_manager(self):
        top = ctk.CTkToplevel(self)
        top.title("🍪 YouTube Cookies Manager (Fix Bot & 403 Errors)")
        top.geometry("720x620")
        top.transient(self)
        top.grab_set()

        ctk.CTkLabel(
            top, text="🍪 YouTube Cookies Manager (VPS / Anti-Bot Fix)",
            font=("Segoe UI", 16, "bold")
        ).pack(padx=20, pady=(15, 5))

        info_msg = (
            "YouTube datacenter / VPS IP addresses par automated bot check lagata hai.\n"
            "Apne computer ke browser se YouTube cookies yahan paste karne se bot error 100% bypass ho jata hai!\n\n"
            "⭐ ZAROORI (Cookies Expire / Rotate Hone Se Kaise Bachayein):\n"
            "Google normal browser tab ke cookies ko kuch hi der me ROTATE (expire) kar deta hai.\n"
            "Isliye:\n"
            "1. Browser me 'Incognito / Private Window' open karein aur youtube.com login karein.\n"
            "2. 'Get cookies.txt LOCALLY' extension se cookies Copy karein.\n"
            "3. Yahan '📋 Paste Clipboard' dabayein aur '💾 Save Cookies' karein.\n"
            "4. Export ke baad us Incognito window ko close kar dein (taaki session tokens rotate na hon)."
        )
        ctk.CTkLabel(
            top, text=info_msg, font=("Segoe UI", 11),
            text_color="#cccccc", justify="left", wraplength=680
        ).pack(padx=20, pady=(0, 10))

        text_box = ctk.CTkTextbox(top, width=680, height=210, font=("Consolas", 11))
        text_box.pack(padx=20, pady=5)
        self._attach_textbox_context_menu(text_box)

        cookie_path = DownloadManager.find_cookie_file() or self._get_cookie_file_path()
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    text_box.insert("1.0", content)
            except Exception:
                pass

        btn_frame = ctk.CTkFrame(top, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)

        def paste_from_clipboard():
            text = self._get_clipboard_text()
            if text:
                text_box.delete("1.0", "end")
                text_box.insert("1.0", text)
                self._update_status("📋 Cookies pasted from clipboard!")
            else:
                messagebox.showwarning(
                    "Clipboard Empty",
                    "Clipboard is empty or could not be read.\n"
                    "Please copy your YouTube cookies to clipboard first."
                )

        def extract_from_browser():
            dlg = ctk.CTkToplevel(top)
            dlg.title("Select Browser")
            dlg.geometry("380x210")
            dlg.transient(top)
            dlg.grab_set()

            ctk.CTkLabel(
                dlg, text="Choose browser with active YouTube login:",
                font=("Segoe UI", 12, "bold")
            ).pack(padx=15, pady=(15, 10))

            b_var = ctk.StringVar(value="chrome")
            ctk.CTkOptionMenu(
                dlg, variable=b_var,
                values=["chrome", "firefox", "edge", "brave", "chromium"],
                width=200
            ).pack(pady=5)

            def do_extract():
                selected_browser = b_var.get()
                dlg.destroy()
                try:
                    self._update_status(f"🌐 Extracting cookies from {selected_browser}...")
                    import yt_dlp.cookies
                    import tempfile
                    jar = yt_dlp.cookies.extract_cookies_from_browser(selected_browser)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w') as tf:
                        temp_p = tf.name
                    jar.save(temp_p, ignore_discard=True, ignore_expires=True)
                    with open(temp_p, 'r', encoding='utf-8', errors='ignore') as f:
                        data = f.read()
                    try:
                        os.remove(temp_p)
                    except Exception:
                        pass
                    if 'youtube.com' in data or '.youtube.com' in data:
                        text_box.delete("1.0", "end")
                        text_box.insert("1.0", data)
                        save_cookies()
                    else:
                        messagebox.showwarning(
                            "No YouTube Cookies",
                            f"{selected_browser.title()} me YouTube cookies nahi mile.\n"
                            f"Kripya us browser me pehle youtube.com par login karein."
                        )
                except Exception as ex:
                    messagebox.showerror(
                        "Browser Cookie Error",
                        f"{selected_browser.title()} se cookies read nahi ho paayi.\n\n"
                        f"Agar browser open hai toh use band karke try karein, ya '📋 Paste Clipboard' use karein.\n\nDetails: {ex}"
                    )

            ctk.CTkButton(
                dlg, text="Extract & Save", command=do_extract,
                fg_color="#2ECC71", hover_color="#27AE60"
            ).pack(pady=15)

        def browse_file():
            fn = filedialog.askopenfilename(
                title="Select YouTube cookies.txt file",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if fn:
                try:
                    with open(fn, "r", encoding="utf-8", errors="ignore") as f:
                        data = f.read()
                    text_box.delete("1.0", "end")
                    text_box.insert("1.0", data)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to read file: {e}")

        def save_cookies():
            content = text_box.get("1.0", "end").strip()
            content = content.lstrip('\ufeff')
            if not content:
                messagebox.showwarning("Warning", "Please paste cookies or browse a file first.")
                return

            if "youtube.com" not in content and ".youtube.com" not in content:
                confirm = messagebox.askyesno(
                    "Warning: Not YouTube Cookies?",
                    "Is text me 'youtube.com' domain ke cookies nahi mile!\n\n"
                    "Dhyan dein: Rumble ya kisi doosri site ke cookies YouTube par kaam nahi karenge aur 'Sign in bot' error aayega.\n\n"
                    "Kya aap phir bhi ise save karna chahte hain?"
                )
                if not confirm:
                    return

            try:
                target_path = self._get_cookie_file_path()
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content + "\n")
                self._update_cookie_status_label()
                messagebox.showinfo("Success", "✅ YouTube cookies successfully saved! Bot protection bypassed.")
                top.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save cookies: {e}")

        def clear_cookies():
            target_path = self._get_cookie_file_path()
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            text_box.delete("1.0", "end")
            self._update_cookie_status_label()
            messagebox.showinfo("Cleared", "Cookies have been cleared.")

        ctk.CTkButton(
            btn_frame, text="📋 Paste Clipboard", width=140, fg_color="#17a2b8",
            hover_color="#138496", font=("Segoe UI", 12, "bold"),
            command=paste_from_clipboard
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="🌐 From Browser", width=120, command=extract_from_browser
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="📁 Browse File", width=110, command=browse_file
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="💾 Save Cookies", width=140, fg_color="#2ECC71",
            hover_color="#27AE60", command=save_cookies
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="🗑️ Clear", width=100, fg_color="#E74C3C",
            hover_color="#C0392B", command=clear_cookies
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame, text="Close", width=90, command=top.destroy
        ).pack(side="right", padx=5)

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
