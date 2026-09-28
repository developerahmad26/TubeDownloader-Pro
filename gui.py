"""Modern GUI for YouTube Video Downloader using CustomTkinter."""

import os
import sys
import shutil
import subprocess
import threading
from datetime import datetime
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
    DEFAULT_APP_SETTINGS,
    load_app_settings,
    save_app_settings,
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
        self.geometry("1020x840")
        self.minsize(940, 720)

        # Load persistent application default settings
        self.app_settings = load_app_settings()

        self.dm = DownloadManager()
        self.batch_manager = BatchManager()
        self.scheduler = DownloadScheduler(runner_callback=self._run_scheduled_job)
        self.fetched_videos = []
        self.fetched_playlist_title = ""
        self.current_nav_view = "downloads"
        self.current_running_batch_id = None
        self.batch_filter_var = ctk.StringVar(value="All Batches")
        self.batch_search_var = ctk.StringVar(value="")
        self.schedule_filter_var = ctk.StringVar(value="All Schedules")
        self.schedule_search_var = ctk.StringVar(value="")
        self._schedule_countdown_labels = {}
        self._batch_countdown_labels = {}

        self._build_ui()
        self._check_system_deps()
        self.after(1000, self._start_scheduler_ticker)

    def _build_ui(self):
        # 1. Top Fixed Navigation Bar
        self._build_top_nav_bar()

        # 2. Main Container holding the isolated views
        self.content_container = ctk.CTkFrame(self, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True)

        # 3. Create four distinct view frames
        self.downloads_view = ctk.CTkScrollableFrame(self.content_container, fg_color="transparent")
        self.batches_view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.scheduler_view = ctk.CTkFrame(self.content_container, fg_color="transparent")
        self.settings_view = ctk.CTkScrollableFrame(self.content_container, fg_color="transparent")

        # 4. Build components for each view
        self._build_downloads_view()
        self._build_batches_view()
        self._build_scheduler_view()
        self._build_settings_view()

        # 5. Show default view: Downloads Studio
        self._switch_nav_view("downloads")

    def _build_top_nav_bar(self):
        """Build top navigation header with 4 distinct studio views."""
        top_bar = ctk.CTkFrame(self, fg_color="#10131c", corner_radius=0, height=62)
        top_bar.pack(fill="x", side="top", pady=(0, 2))
        top_bar.pack_propagate(False)

        # Left: App Brand & Version
        brand_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        brand_frame.pack(side="left", padx=16, pady=8)

        ctk.CTkLabel(
            brand_frame, text="🎬 YT Downloader Studio",
            font=("Segoe UI", 18, "bold"), text_color="#FFFFFF"
        ).pack(side="left")
        ctk.CTkLabel(
            brand_frame, text=f"v{APP_VERSION} PRO",
            font=("Segoe UI", 10, "bold"), text_color="#38bdf8", fg_color="#0c2538", corner_radius=4, padx=6, pady=2
        ).pack(side="left", padx=(8, 0), pady=(2, 0))

        # Center: 4 Clean Segregated Studio Nav Buttons
        nav_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        nav_box.pack(side="left", expand=True, pady=8)

        self.nav_btn_downloads = ctk.CTkButton(
            nav_box, text="📹 Downloads Studio", width=160, height=36,
            font=("Segoe UI", 12, "bold"), corner_radius=6,
            command=lambda: self._switch_nav_view("downloads")
        )
        self.nav_btn_downloads.pack(side="left", padx=4)

        self.nav_btn_batches = ctk.CTkButton(
            nav_box, text="📁 Batches Studio", width=150, height=36,
            font=("Segoe UI", 12, "bold"), corner_radius=6,
            command=lambda: self._switch_nav_view("batches")
        )
        self.nav_btn_batches.pack(side="left", padx=4)

        self.nav_btn_scheduler = ctk.CTkButton(
            nav_box, text="⏰ Scheduler Studio", width=160, height=36,
            font=("Segoe UI", 12, "bold"), corner_radius=6,
            command=lambda: self._switch_nav_view("scheduler")
        )
        self.nav_btn_scheduler.pack(side="left", padx=4)

        self.nav_btn_settings = ctk.CTkButton(
            nav_box, text="⚙️ Settings Studio", width=145, height=36,
            font=("Segoe UI", 12, "bold"), corner_radius=6,
            command=lambda: self._switch_nav_view("settings")
        )
        self.nav_btn_settings.pack(side="left", padx=4)

        # Right: Update & Restart
        right_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_box.pack(side="right", padx=16, pady=8)

        ctk.CTkButton(
            right_box, text="🔄 Update & Restart", width=145, height=34,
            fg_color="#1e293b", hover_color="#334155", text_color="#cbd5e1",
            font=("Segoe UI", 11, "bold"), corner_radius=6,
            command=self._update_and_restart
        ).pack(side="right")

    def _switch_nav_view(self, view_name):
        """Strictly isolate each section view to avoid any UI clutter across tabs."""
        self.current_nav_view = view_name

        inactive_col = "#181c26"
        inactive_hover = "#252b3b"
        inactive_txt = "#94a3b8"

        configs = {
            "downloads": {"btn": self.nav_btn_downloads, "active": "#0284c7", "hover": "#0369a1"},
            "batches": {"btn": self.nav_btn_batches, "active": "#0284c7", "hover": "#0369a1"},
            "scheduler": {"btn": self.nav_btn_scheduler, "active": "#7c3aed", "hover": "#6d28d9"},
            "settings": {"btn": self.nav_btn_settings, "active": "#475569", "hover": "#334155"},
        }

        for k, v in configs.items():
            btn = v["btn"]
            if k == view_name:
                btn.configure(fg_color=v["active"], hover_color=v["hover"], text_color="#ffffff")
            else:
                btn.configure(fg_color=inactive_col, hover_color=inactive_hover, text_color=inactive_txt)

        # Hide all view containers
        self.downloads_view.pack_forget()
        self.batches_view.pack_forget()
        self.scheduler_view.pack_forget()
        self.settings_view.pack_forget()

        # Display exclusively the selected view
        if view_name == "downloads":
            self.downloads_view.pack(fill="both", expand=True, padx=15, pady=8)
        elif view_name == "batches":
            self.batches_view.pack(fill="both", expand=True, padx=15, pady=8)
            self._render_batches_list()
        elif view_name == "scheduler":
            self.scheduler_view.pack(fill="both", expand=True, padx=15, pady=8)
            self._render_schedules_list()
        elif view_name == "settings":
            self.settings_view.pack(fill="both", expand=True, padx=15, pady=8)
            self._refresh_settings_view()

    def _build_downloads_view(self):
        """Build the dedicated Downloads Studio view with a clear, professional card-based structure."""
        # ================= Card 1: Media Source & Input =================
        source_card = ctk.CTkFrame(self.downloads_view, corner_radius=8)
        source_card.pack(fill="x", pady=(0, 10))

        s_head = ctk.CTkFrame(source_card, fg_color="transparent")
        s_head.pack(fill="x", padx=15, pady=(10, 4))
        ctk.CTkLabel(
            s_head, text="🔗 Media Source & Video Input",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left")
        ctk.CTkLabel(
            s_head, text="— Select single video, playlist, or full channel",
            font=("Segoe UI", 11), text_color="gray"
        ).pack(side="left", padx=8)

        # Tab View for Single, Playlist, Channel inside Card 1
        self.tabview = ctk.CTkTabview(source_card, height=185)
        self.tabview.pack(fill="x", padx=10, pady=(0, 10))

        self.tab_single = self.tabview.add("📹 Single Video")
        self.tab_playlist = self.tabview.add("📋 Playlist")
        self.tab_channel = self.tabview.add("📺 Channel")

        self._build_single_tab()
        self._build_playlist_tab()
        self._build_channel_tab()

        # ================= Card 2: Download Configuration & Storage =================
        config_card = ctk.CTkFrame(self.downloads_view, corner_radius=8)
        config_card.pack(fill="x", pady=(0, 10))

        c_head = ctk.CTkFrame(config_card, fg_color="transparent")
        c_head.pack(fill="x", padx=15, pady=(10, 4))
        ctk.CTkLabel(
            c_head, text="⚙️ Download Configuration & Preferences",
            font=("Segoe UI", 14, "bold")
        ).pack(side="left")

        # Two-column layout inside config card
        columns_frame = ctk.CTkFrame(config_card, fg_color="transparent")
        columns_frame.pack(fill="x", padx=15, pady=(0, 6))

        # Col 1: Format & Stream settings
        col1 = ctk.CTkFrame(columns_frame, fg_color="#1c1f26", corner_radius=6)
        col1.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=4)

        ctk.CTkLabel(col1, text="Stream & Format", font=("Segoe UI", 12, "bold"), text_color="#17a2b8").pack(anchor="w", padx=12, pady=(8, 4))

        row_qf = ctk.CTkFrame(col1, fg_color="transparent")
        row_qf.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_qf, text="Quality:", width=60, anchor="w").pack(side="left")
        self.quality_var = ctk.StringVar(value=self.app_settings.get("default_quality", "Best Quality"))
        ctk.CTkOptionMenu(row_qf, variable=self.quality_var, values=list(QUALITY_OPTIONS.keys()), width=180).pack(side="left", padx=4)

        ctk.CTkLabel(row_qf, text="Format:", width=50, anchor="w").pack(side="left", padx=(10, 0))
        self.format_var = ctk.StringVar(value=self.app_settings.get("default_format", "mp4"))
        ctk.CTkOptionMenu(row_qf, variable=self.format_var, values=VIDEO_FORMATS + AUDIO_FORMATS, width=90).pack(side="left", padx=4)

        row_cb1 = ctk.CTkFrame(col1, fg_color="transparent")
        row_cb1.pack(fill="x", padx=12, pady=(6, 8))
        self.thumbnail_var = ctk.BooleanVar(value=self.app_settings.get("default_embed_thumbnail", False))
        ctk.CTkCheckBox(row_cb1, text="🖼️ Embed Thumbnail", variable=self.thumbnail_var).pack(side="left", padx=(0, 10))

        self.subtitle_var = ctk.BooleanVar(value=self.app_settings.get("default_download_subtitles", False))
        ctk.CTkCheckBox(row_cb1, text="💬 Subtitles", variable=self.subtitle_var).pack(side="left", padx=4)
        self.subtitle_lang_entry = ctk.CTkEntry(row_cb1, placeholder_text="en", width=50)
        self.subtitle_lang_entry.insert(0, self.app_settings.get("default_subtitle_lang", "en"))
        self.subtitle_lang_entry.pack(side="left", padx=4)
        self._attach_entry_context_menu(self.subtitle_lang_entry)

        # Col 2: Naming & File Organization
        col2 = ctk.CTkFrame(columns_frame, fg_color="#1c1f26", corner_radius=6)
        col2.pack(side="right", fill="both", expand=True, padx=(6, 0), pady=4)

        ctk.CTkLabel(col2, text="Naming & Organization", font=("Segoe UI", 12, "bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(8, 4))

        row_name = ctk.CTkFrame(col2, fg_color="transparent")
        row_name.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(row_name, text="Naming:", width=60, anchor="w").pack(side="left")
        self.naming_var = ctk.StringVar(value=self.app_settings.get("default_naming_scheme", "Numbered + Rewrite Title (01 - Cleaned)"))
        ctk.CTkOptionMenu(row_name, variable=self.naming_var, values=list(NAMING_SCHEMES.keys()), width=215).pack(side="left", padx=4)
        ctk.CTkButton(
            row_name, text="⚙️ Rules", width=65, height=28,
            fg_color="#495057", hover_color="#343a40", font=("Segoe UI", 11, "bold"),
            command=self._open_title_rules_dialog
        ).pack(side="left", padx=4)

        row_pref = ctk.CTkFrame(col2, fg_color="transparent")
        row_pref.pack(fill="x", padx=12, pady=(4, 8))
        ctk.CTkLabel(row_pref, text="Prefix:", width=50, anchor="w").pack(side="left")
        self.prefix_entry = ctk.CTkEntry(row_pref, placeholder_text="e.g. MyVideo", width=120)
        self.prefix_entry.insert(0, self.app_settings.get("default_custom_prefix", ""))
        self.prefix_entry.pack(side="left", padx=4)
        self._attach_entry_context_menu(self.prefix_entry)

        self.subfolder_var = ctk.BooleanVar(value=self.app_settings.get("default_auto_subfolder", True))
        ctk.CTkCheckBox(row_pref, text="📂 Auto Subfolder", variable=self.subfolder_var).pack(side="left", padx=(10, 0))

        # Bottom Strip inside config card: Save Directory & Cookies row
        storage_strip = ctk.CTkFrame(config_card, fg_color="transparent")
        storage_strip.pack(fill="x", padx=15, pady=(2, 10))

        # Save Directory row
        dir_row = ctk.CTkFrame(storage_strip, fg_color="transparent")
        dir_row.pack(fill="x", pady=2)
        ctk.CTkLabel(dir_row, text="📁 Save Directory:", font=("Segoe UI", 12, "bold"), width=120, anchor="w").pack(side="left")
        self.dir_var = ctk.StringVar(value=self.app_settings.get("default_download_dir", DEFAULT_DOWNLOAD_DIR))
        self.dir_entry = ctk.CTkEntry(dir_row, textvariable=self.dir_var, width=520)
        self.dir_entry.pack(side="left", padx=5, fill="x", expand=True)
        self._attach_entry_context_menu(self.dir_entry)
        ctk.CTkButton(dir_row, text="Browse", width=80, command=self._browse_dir).pack(side="left", padx=3)
        ctk.CTkButton(dir_row, text="📂 Open", width=80, command=self._open_download_dir).pack(side="left", padx=3)

        # Cookies & Speed limit row
        extra_row = ctk.CTkFrame(storage_strip, fg_color="transparent")
        extra_row.pack(fill="x", pady=(6, 0))

        ctk.CTkButton(
            extra_row, text="🍪 YouTube Cookies", width=160, height=28,
            command=self._open_cookie_manager, fg_color="#1F6AA5", hover_color="#144870"
        ).pack(side="left", padx=(0, 8))

        self.cookie_status_label = ctk.CTkLabel(
            extra_row, text=self._get_cookie_status_text(),
            font=("Segoe UI", 11), text_color="#2ECC71" if self._has_cookies() else "#F39C12"
        )
        self.cookie_status_label.pack(side="left")

        speed_box = ctk.CTkFrame(extra_row, fg_color="transparent")
        speed_box.pack(side="right")
        ctk.CTkLabel(speed_box, text="Speed Limit:").pack(side="left", padx=4)
        self.speed_entry = ctk.CTkEntry(speed_box, placeholder_text="0", width=80)
        self.speed_entry.insert(0, self.app_settings.get("default_speed_limit", ""))
        self.speed_entry.pack(side="left")
        self._attach_entry_context_menu(self.speed_entry)
        ctk.CTkLabel(speed_box, text="KB/s (0=unlimited)", text_color="gray").pack(side="left", padx=4)

        # ================= Card 3: Action & Live Progress Center =================
        action_card = ctk.CTkFrame(self.downloads_view, corner_radius=8)
        action_card.pack(fill="x", pady=(0, 10))

        act_inner = ctk.CTkFrame(action_card, fg_color="transparent")
        act_inner.pack(fill="x", padx=15, pady=12)

        # Primary Buttons Row
        btns_row = ctk.CTkFrame(act_inner, fg_color="transparent")
        btns_row.pack(fill="x", pady=(0, 8))

        self.download_btn = ctk.CTkButton(
            btns_row, text="⬇️  Start Download", width=190, height=46,
            font=("Segoe UI", 15, "bold"),
            fg_color="#28a745", hover_color="#218838",
            command=self._start_download
        )
        self.download_btn.pack(side="left", padx=(0, 6))

        self.cancel_btn = ctk.CTkButton(
            btns_row, text="❌ Cancel", width=110, height=46,
            font=("Segoe UI", 13, "bold"),
            fg_color="#dc3545", hover_color="#c82333",
            command=self._cancel_download, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=4)

        self.save_batch_btn = ctk.CTkButton(
            btns_row, text="💾 Save as Batch", width=150, height=46,
            font=("Segoe UI", 13, "bold"),
            fg_color="#17a2b8", hover_color="#138496",
            command=self._save_current_as_batch
        )
        self.save_batch_btn.pack(side="left", padx=4)

        self.schedule_btn = ctk.CTkButton(
            btns_row, text="⏰ Schedule Setup", width=150, height=46,
            font=("Segoe UI", 13, "bold"),
            fg_color="#6f42c1", hover_color="#59359a",
            command=self._schedule_current_download
        )
        self.schedule_btn.pack(side="left", padx=4)

        self.counter_label = ctk.CTkLabel(
            btns_row, text="", font=("Segoe UI", 12, "bold"), text_color="#17a2b8"
        )
        self.counter_label.pack(side="right", padx=6)

        # Dedicated Live Progress Dashboard
        monitor_frame = ctk.CTkFrame(act_inner, fg_color="#12151e", corner_radius=8, border_width=1, border_color="#242b3d")
        monitor_frame.pack(fill="x", pady=(6, 2))

        mon_inner = ctk.CTkFrame(monitor_frame, fg_color="transparent")
        mon_inner.pack(fill="x", padx=14, pady=10)

        # Top row: Status info (Left) + Real-time Speed & ETA (Right)
        mon_top = ctk.CTkFrame(mon_inner, fg_color="transparent")
        mon_top.pack(fill="x", pady=(0, 6))

        self.status_label = ctk.CTkLabel(
            mon_top, text="⏳ Ready to download",
            font=("Segoe UI", 12, "bold"), text_color="#f1f5f9"
        )
        self.status_label.pack(side="left")

        self.speed_eta_label = ctk.CTkLabel(
            mon_top, text="",
            font=("Segoe UI", 11, "bold"), text_color="#38bdf8"
        )
        self.speed_eta_label.pack(side="right")

        # Middle row: Progress bar + Live Percentage Label
        bar_frame = ctk.CTkFrame(mon_inner, fg_color="transparent")
        bar_frame.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(
            bar_frame, height=22, corner_radius=6,
            progress_color="#0284c7", fg_color="#1e2433"
        )
        self.progress_bar.pack(side="left", fill="x", expand=True)
        self.progress_bar.set(0)

        self.progress_percent = ctk.CTkLabel(
            bar_frame, text="0.0%", font=("Segoe UI", 13, "bold"),
            text_color="#00f0ff", width=65
        )
        self.progress_percent.pack(side="right", padx=(10, 0))

        # ================= Card 4: Activity Console =================
        log_card = ctk.CTkFrame(self.downloads_view, corner_radius=8, fg_color="#141822", border_width=1, border_color="#242b3d")
        log_card.pack(fill="x", pady=(0, 8))

        log_head = ctk.CTkFrame(log_card, fg_color="transparent")
        log_head.pack(fill="x", padx=15, pady=(10, 6))

        ctk.CTkLabel(
            log_head, text="📝 Download Console Activity Log",
            font=("Segoe UI", 13, "bold"), text_color="#FFFFFF"
        ).pack(side="left")

        ctk.CTkButton(
            log_head, text="📋 Copy Log", width=80, height=24,
            fg_color="#334155", hover_color="#475569", font=("Segoe UI", 10, "bold"),
            corner_radius=4, command=self._copy_download_log
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            log_head, text="🧹 Clear Log", width=80, height=24,
            fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10),
            corner_radius=4, command=self._clear_download_log
        ).pack(side="right")

        self.log_text = ctk.CTkTextbox(log_card, height=260, font=("Consolas", 11), fg_color="#0b0e14", corner_radius=6, border_width=1, border_color="#1e2330")
        self.log_text.pack(fill="x", padx=15, pady=(0, 12))
        self.log_text.configure(state="disabled")
        self._attach_textbox_context_menu(self.log_text)

    def _clear_download_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _copy_download_log(self):
        try:
            content = self.log_text.get("1.0", "end-1c")
            if content.strip():
                self.clipboard_clear()
                self.clipboard_append(content)
                self._update_status("📋 Console log copied to clipboard!", force_log=True)
        except Exception:
            pass

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

    # ==================== Batches Studio View ====================

    def _get_active_schedule_for_batch(self, batch_id):
        """Check if this batch is scheduled to run and return the active schedule job."""
        try:
            for job in self.scheduler.get_all():
                if job.get("status") == "Pending" and job.get("job_type") == "batch":
                    tdata = job.get("target_data", {})
                    if tdata.get("id") == batch_id:
                        return job
        except Exception:
            pass
        return None

    def _build_batches_view(self):
        """Build the ultra-premium full-screen Batches Studio view."""
        # 1. Top Header Bar
        header = ctk.CTkFrame(self.batches_view, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        h_left = ctk.CTkFrame(header, fg_color="transparent")
        h_left.pack(side="left")

        ctk.CTkLabel(
            h_left, text="📁 Batches Studio",
            font=("Segoe UI", 20, "bold"), text_color="#FFFFFF"
        ).pack(anchor="w")
        ctk.CTkLabel(
            h_left, text="Organize, automate, and trigger reusable multi-video download workflows with 1-click",
            font=("Segoe UI", 11), text_color="#94a3b8"
        ).pack(anchor="w", pady=(1, 0))

        h_right = ctk.CTkFrame(header, fg_color="transparent")
        h_right.pack(side="right")

        ctk.CTkButton(
            h_right, text="➕ Save Current Setup", width=165, height=34,
            fg_color="#0284c7", hover_color="#0369a1", font=("Segoe UI", 12, "bold"),
            corner_radius=6, command=self._save_current_as_batch
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            h_right, text="🔄 Refresh", width=85, height=34,
            fg_color="#334155", hover_color="#475569", font=("Segoe UI", 11, "bold"),
            corner_radius=6, command=self._render_batches_list
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            h_right, text="🧹 Clear Completed", width=125, height=34,
            fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 11),
            corner_radius=6, command=self._clear_completed_batches
        ).pack(side="left", padx=4)

        # 2. Modern 5-KPI Stat Dashboard Cards Row
        kpi_row = ctk.CTkFrame(self.batches_view, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 8))

        def _make_kpi_card(parent, title, val_color, bg_color, border_color):
            card = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=8, border_width=1, border_color=border_color, height=52)
            card.pack(side="left", fill="x", expand=True, padx=3)
            card.pack_propagate(False)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=10, pady=4)
            val_lbl = ctk.CTkLabel(inner, text="0", font=("Segoe UI", 16, "bold"), text_color=val_color)
            val_lbl.pack(anchor="w")
            ctk.CTkLabel(inner, text=title, font=("Segoe UI", 9, "bold"), text_color="#94a3b8").pack(anchor="w")
            return val_lbl

        self.batch_stat_total = _make_kpi_card(kpi_row, "TOTAL BATCHES", "#F8FAFC", "#141824", "#262d3d")
        self.batch_stat_ready = _make_kpi_card(kpi_row, "READY TO RUN", "#38BDF8", "#0c1d2e", "#1b3c5a")
        self.batch_stat_scheduled = _make_kpi_card(kpi_row, "SCHEDULED JOBS", "#C084FC", "#1e1133", "#45226e")
        self.batch_stat_running = _make_kpi_card(kpi_row, "RUNNING NOW", "#FBBF24", "#2a1b08", "#633c0c")
        self.batch_stat_completed = _make_kpi_card(kpi_row, "COMPLETED", "#34D399", "#092418", "#124a30")

        # 3. Search Bar & Filter Control Bar
        control_bar = ctk.CTkFrame(self.batches_view, corner_radius=8, fg_color="#141822", border_width=1, border_color="#242b3d")
        control_bar.pack(fill="x", pady=(0, 8))

        ctrl_inner = ctk.CTkFrame(control_bar, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=12, pady=6)

        # Real-time search entry
        self.batch_search_entry = ctk.CTkEntry(
            ctrl_inner, textvariable=self.batch_search_var,
            placeholder_text="🔍 Search batch by name, link, format, #01...", width=360, height=32,
            fg_color="#0b0e14", border_color="#2d3748", corner_radius=6
        )
        self.batch_search_entry.pack(side="left", padx=(0, 10))
        self._attach_entry_context_menu(self.batch_search_entry)
        self.batch_search_var.trace_add("write", lambda *_: self._render_batches_list())

        # Filter dropdown
        filter_box = ctk.CTkFrame(ctrl_inner, fg_color="transparent")
        filter_box.pack(side="right")
        ctk.CTkLabel(filter_box, text="Filter:", font=("Segoe UI", 11, "bold"), text_color="#94a3b8").pack(side="left", padx=4)
        ctk.CTkOptionMenu(
            filter_box, variable=self.batch_filter_var,
            values=["All Batches", "Ready", "Scheduled", "Running", "Completed", "Failed"],
            width=140, height=30, corner_radius=6,
            command=lambda _: self._render_batches_list()
        ).pack(side="left")

        # 4. Scrollable Batch Cards Area
        self.batches_scroll = ctk.CTkScrollableFrame(self.batches_view, fg_color="transparent")
        self.batches_scroll.pack(fill="both", expand=True, pady=(0, 8))

    def _batch_log(self, message):
        pass

    def _clear_batch_log(self):
        pass

    def _render_batches_list(self):
        """Render all saved batch cards with modern dashboard card styling, chips, and live countdowns."""
        for widget in self.batches_scroll.winfo_children():
            widget.destroy()

        self._batch_countdown_labels.clear()

        all_batches = self.batch_manager.get_all()
        total_count = len(all_batches)

        # Count states including active schedules
        sched_count = sum(1 for b in all_batches if self._get_active_schedule_for_batch(b.get("id")) is not None)
        running_count = sum(1 for b in all_batches if self.current_running_batch_id == b.get("id") or b.get("status") == "Running")
        comp_count = sum(1 for b in all_batches if b.get("status") == "Completed" and not self._get_active_schedule_for_batch(b.get("id")))
        ready_count = total_count - sched_count - running_count - comp_count
        if ready_count < 0:
            ready_count = 0

        if hasattr(self, "batch_stat_total"):
            self.batch_stat_total.configure(text=str(total_count))
            self.batch_stat_ready.configure(text=str(ready_count))
            self.batch_stat_scheduled.configure(text=str(sched_count))
            self.batch_stat_running.configure(text=str(running_count))
            self.batch_stat_completed.configure(text=str(comp_count))

        # Filter by status
        selected_filter = self.batch_filter_var.get()
        filtered = []
        for b in all_batches:
            active_sched = self._get_active_schedule_for_batch(b.get("id"))
            is_running = (self.current_running_batch_id == b.get("id") or b.get("status") == "Running")
            is_comp = (b.get("status") == "Completed" and not active_sched)

            if selected_filter == "All Batches":
                filtered.append(b)
            elif selected_filter == "Scheduled" and active_sched is not None:
                filtered.append(b)
            elif selected_filter == "Running" and is_running:
                filtered.append(b)
            elif selected_filter == "Completed" and is_comp:
                filtered.append(b)
            elif selected_filter == "Ready" and not active_sched and not is_running and not is_comp:
                filtered.append(b)
            elif selected_filter == "Failed" and b.get("status") == "Failed":
                filtered.append(b)

        # Filter by search text
        search_query = self.batch_search_var.get().strip().lower()
        if search_query:
            matched = []
            for i, b in enumerate(filtered):
                num_tag = f"#{i+1:02d}".lower()
                num_raw = str(i+1)
                name = b.get("name", "").lower()
                url = b.get("url", "").lower()
                btype = b.get("type", "").lower()
                quality = b.get("quality", "").lower()
                if (search_query in num_tag or search_query in num_raw or
                    search_query in name or search_query in url or
                    search_query in btype or search_query in quality):
                    matched.append(b)
            filtered = matched

        if not filtered:
            empty_frame = ctk.CTkFrame(self.batches_scroll, fg_color="#141822", corner_radius=10, border_width=1, border_color="#242b3d")
            empty_frame.pack(fill="x", padx=10, pady=30)
            ctk.CTkLabel(
                empty_frame,
                text="📁 No Batches Found\n\nNo saved batches match your current search or filter criteria.\nConfigure any download in 'Downloads Studio' and click '💾 Save as Batch'!",
                font=("Segoe UI", 13), text_color="#94a3b8", justify="center"
            ).pack(padx=20, pady=(24, 16))
            ctk.CTkButton(
                empty_frame, text="➕ Save Current Setup as Batch", width=220, height=36,
                fg_color="#0284c7", hover_color="#0369a1", font=("Segoe UI", 12, "bold"),
                corner_radius=6, command=self._save_current_as_batch
            ).pack(pady=(0, 24))
            return

        for idx, b in enumerate(filtered, start=1):
            bid = b.get("id")
            name = b.get("name", "Untitled Batch")
            btype = b.get("type", "channel")
            url = b.get("url", "")
            quality = b.get("quality", "Best Quality")
            fmt = b.get("format", "mp4")
            naming = b.get("naming_scheme", "title")
            sel_val = b.get("selection_value", "")
            prefix = b.get("custom_prefix", "")
            subfolder = b.get("subfolder", "")
            last_run = b.get("last_run", "")

            # Check if this batch is currently scheduled
            active_sched = self._get_active_schedule_for_batch(bid)
            is_running = (self.current_running_batch_id == bid or b.get("status") == "Running")
            is_comp = (b.get("status") == "Completed" and not active_sched)

            # Determine Card Border & Background Theme based on State
            if is_running:
                card_bg = "#21160c"
                card_border = "#f59e0b"
                border_w = 2
                status_text = "⚡ RUNNING"
                st_color = "#fcd34d"
                st_bg = "#451a03"
            elif active_sched is not None:
                card_bg = "#191226"
                card_border = "#8b5cf6"
                border_w = 2
                status_text = "⏰ SCHEDULED"
                st_color = "#d8b4fe"
                st_bg = "#3b1d5c"
            elif is_comp:
                card_bg = "#0f1916"
                card_border = "#059669"
                border_w = 1
                status_text = "✅ COMPLETED"
                st_color = "#6ee7b7"
                st_bg = "#064e3b"
            else:
                card_bg = "#141822"
                card_border = "#262d3d"
                border_w = 1
                status_text = "● READY"
                st_color = "#38bdf8"
                st_bg = "#0c2738"

            # Outer Card
            card = ctk.CTkFrame(
                self.batches_scroll, corner_radius=10,
                fg_color=card_bg, border_width=border_w, border_color=card_border
            )
            card.pack(fill="x", padx=4, pady=5)

            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="both", expand=True, padx=14, pady=12)

            # Row 1: Header (Number Badge + Batch Name + Type Badge + State Badge)
            row1 = ctk.CTkFrame(card_inner, fg_color="transparent")
            row1.pack(fill="x")

            # Numbering badge (#01, #02...)
            num_lbl = ctk.CTkLabel(
                row1, text=f"#{idx:02d}", font=("Segoe UI", 11, "bold"),
                text_color="#38bdf8", fg_color="#0f172a", corner_radius=6, padx=8, pady=3
            )
            num_lbl.pack(side="left")

            # Batch Title
            ctk.CTkLabel(
                row1, text=name, font=("Segoe UI", 15, "bold"), text_color="#FFFFFF"
            ).pack(side="left", padx=(10, 8))

            # Type Badge
            type_icons = {"single": "📹 Single Video", "playlist": "📋 Playlist", "channel": "📺 Channel"}
            type_str = type_icons.get(btype, "🎬 Video")
            ctk.CTkLabel(
                row1, text=type_str, font=("Segoe UI", 10, "bold"),
                text_color="#94a3b8", fg_color="#1e293b", corner_radius=6, padx=8, pady=3
            ).pack(side="left")

            # Right Status Badge
            st_pill = ctk.CTkLabel(
                row1, text=status_text, font=("Segoe UI", 11, "bold"),
                text_color=st_color, fg_color=st_bg, corner_radius=6, padx=10, pady=4
            )
            st_pill.pack(side="right")

            # Row 2: URL Container with 1-click Copy button
            row2 = ctk.CTkFrame(card_inner, fg_color="#0b0e14", corner_radius=6, border_width=1, border_color="#1e2536")
            row2.pack(fill="x", pady=(8, 6))

            r2_inner = ctk.CTkFrame(row2, fg_color="transparent")
            r2_inner.pack(fill="x", padx=10, pady=5)

            ctk.CTkLabel(r2_inner, text="🔗", font=("Segoe UI", 11)).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(r2_inner, text=url, font=("Segoe UI", 11), text_color="#60a5fa", anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                r2_inner, text="📋 Copy", width=65, height=22,
                fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"),
                corner_radius=4, command=lambda u=url: self._copy_text_to_clipboard(u)
            ).pack(side="right")

            # Row 3: Metadata Badges (Styled individual chips)
            row3 = ctk.CTkFrame(card_inner, fg_color="transparent")
            row3.pack(fill="x", pady=(2, 6))

            chips_box = ctk.CTkFrame(row3, fg_color="transparent")
            chips_box.pack(side="left", fill="x", expand=True)

            def _add_chip(parent, icon, text_val):
                chip = ctk.CTkFrame(parent, fg_color="#1a202c", corner_radius=6, border_width=1, border_color="#2d3748")
                chip.pack(side="left", padx=(0, 6), pady=2)
                ctk.CTkLabel(chip, text=f"{icon} {text_val}", font=("Segoe UI", 10, "bold"), text_color="#cbd5e1").pack(padx=8, pady=3)

            _add_chip(chips_box, "🎯", quality)
            _add_chip(chips_box, "📦", fmt.upper())
            _add_chip(chips_box, "🏷️", naming)
            if prefix:
                _add_chip(chips_box, "🔤", f"Prefix: '{prefix}'")
            if sel_val:
                _add_chip(chips_box, "🔢", f"Range: {sel_val}")
            if subfolder:
                _add_chip(chips_box, "📂", subfolder)

            if last_run and not active_sched and not is_running:
                ctk.CTkLabel(
                    row3, text=f"🕒 Last run: {last_run}", font=("Segoe UI", 10), text_color="#64748b"
                ).pack(side="right", padx=4)

            # SCHEDULED ALERT BANNER (Prominently illuminated when batch is scheduled)
            if active_sched:
                sched_run_at = active_sched.get("run_at", "")
                sched_cd = self.scheduler.get_countdown(sched_run_at)
                is_daily = active_sched.get("repeat_daily", False)

                sched_banner = ctk.CTkFrame(card_inner, fg_color="#22123d", corner_radius=8, border_width=1, border_color="#9333ea")
                sched_banner.pack(fill="x", pady=(4, 6))

                sb_inner = ctk.CTkFrame(sched_banner, fg_color="transparent")
                sb_inner.pack(fill="x", padx=12, pady=7)

                ctk.CTkLabel(
                    sb_inner, text="⏰ SCHEDULED RUN:",
                    font=("Segoe UI", 11, "bold"), text_color="#e9d5ff"
                ).pack(side="left")

                ctk.CTkLabel(
                    sb_inner, text=f"{sched_run_at}",
                    font=("Segoe UI", 11, "bold"), text_color="#FFFFFF"
                ).pack(side="left", padx=8)

                cd_disp = ctk.CTkLabel(
                    sb_inner, text=f"⏳ Starts In: {sched_cd}",
                    font=("Segoe UI", 12, "bold"), text_color="#00f0ff"
                )
                cd_disp.pack(side="left", padx=10)
                self._batch_countdown_labels[bid] = (cd_disp, sched_run_at)

                if is_daily:
                    ctk.CTkLabel(
                        sb_inner, text="🔁 DAILY RECURRING",
                        font=("Segoe UI", 9, "bold"), text_color="#34d399", fg_color="#064e3b", corner_radius=4, padx=8, pady=3
                    ).pack(side="right")

            # RUNNING INLINE PROGRESS (If currently downloading)
            if is_running:
                prog_box = ctk.CTkFrame(card_inner, fg_color="#291804", corner_radius=8, border_width=1, border_color="#d97706")
                prog_box.pack(fill="x", pady=(4, 6))
                pb_inner = ctk.CTkFrame(prog_box, fg_color="transparent")
                pb_inner.pack(fill="x", padx=12, pady=7)

                ctk.CTkLabel(pb_inner, text="🚀 Downloading...", font=("Segoe UI", 11, "bold"), text_color="#f59e0b").pack(side="left")
                run_bar = ctk.CTkProgressBar(pb_inner, height=12)
                run_bar.pack(side="left", fill="x", expand=True, padx=12)
                run_bar.set(self.progress_bar.get())

                pct_txt = self.progress_percent.cget("text")
                ctk.CTkLabel(pb_inner, text=pct_txt, font=("Segoe UI", 11, "bold"), text_color="#f59e0b").pack(side="right")

            # Row 4: Action Buttons Bar
            row4 = ctk.CTkFrame(card_inner, fg_color="transparent")
            row4.pack(fill="x", pady=(6, 0))

            btn_box_left = ctk.CTkFrame(row4, fg_color="transparent")
            btn_box_left.pack(side="left")

            ctk.CTkButton(
                btn_box_left, text="▶️ Run Now", width=105, height=32,
                fg_color="#059669", hover_color="#10b981", font=("Segoe UI", 11, "bold"),
                corner_radius=6, command=lambda b_item=b: self._run_batch(b_item)
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btn_box_left, text="⏰ Schedule", width=105, height=32,
                fg_color="#6366f1", hover_color="#4f46e5", font=("Segoe UI", 11, "bold"),
                corner_radius=6, command=lambda b_item=b: self._open_schedule_dialog(
                    target_name=b_item.get("name"),
                    target_type="batch",
                    target_data=b_item
                )
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                btn_box_left, text="✏️ Edit Batch", width=95, height=32,
                fg_color="#334155", hover_color="#475569", font=("Segoe UI", 11, "bold"),
                corner_radius=6, command=lambda b_item=b: self._edit_batch(b_item)
            ).pack(side="left")

            ctk.CTkButton(
                row4, text="🗑️ Delete", width=80, height=32,
                fg_color="#450a0a", hover_color="#991b1b", text_color="#fca5a5", font=("Segoe UI", 11, "bold"),
                corner_radius=6, command=lambda bid_val=bid: self._delete_batch(bid_val)
            ).pack(side="right")

    def _copy_text_to_clipboard(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self._update_status("📄 URL copied to clipboard!")
        except Exception:
            pass

    def _edit_batch(self, batch_item):
        """Open batch editor dialog."""
        SaveBatchDialog(
            parent=self,
            batch_manager=self.batch_manager,
            default_data=batch_item,
            on_saved=self._render_batches_list
        )

    def _delete_batch(self, batch_id):
        if messagebox.askyesno("Delete Batch", "Are you sure you want to delete this batch?"):
            self.batch_manager.delete(batch_id)
            self._render_batches_list()
            self._update_status("Batch deleted.")
            self._batch_log(f"Deleted batch {batch_id}")

    def _clear_completed_batches(self):
        batches = self.batch_manager.get_all()
        to_del = [b["id"] for b in batches if b.get("status") in ("Completed", "Failed")]
        if not to_del:
            messagebox.showinfo("Batches", "No completed or failed batches to clear.")
            return
        if messagebox.askyesno("Clear Completed", f"Clear {len(to_del)} completed / failed batches?"):
            for bid in to_del:
                self.batch_manager.delete(bid)
            self._render_batches_list()
            self._batch_log(f"Cleared {len(to_del)} finished batches.")

    def _save_current_as_batch(self):
        pkg = self._get_current_download_package()
        if not pkg["url"]:
            messagebox.showwarning("Warning", "Please enter a valid YouTube URL in Downloads Studio first!")
            return
        SaveBatchDialog(
            parent=self,
            batch_manager=self.batch_manager,
            default_data=pkg,
            on_saved=self._render_batches_list
        )

    # ==================== Scheduler Studio View ====================

    def _build_scheduler_view(self):
        """Build the ultra-premium full-screen Scheduler Studio view."""
        # 1. Top Live Countdown Banner & Hero Card
        hero_frame = ctk.CTkFrame(self.scheduler_view, fg_color="#181329", corner_radius=10, border_width=1, border_color="#3d2d5e")
        hero_frame.pack(fill="x", pady=(0, 8))

        hero_inner = ctk.CTkFrame(hero_frame, fg_color="transparent")
        hero_inner.pack(fill="x", padx=16, pady=12)

        hero_left = ctk.CTkFrame(hero_inner, fg_color="transparent")
        hero_left.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            hero_left, text="⏰ Scheduler Studio",
            font=("Segoe UI", 20, "bold"), text_color="#FFFFFF"
        ).pack(anchor="w")
        ctk.CTkLabel(
            hero_left, text="Automate recurring or delayed YouTube downloads with microsecond precision",
            font=("Segoe UI", 11), text_color="#94a3b8"
        ).pack(anchor="w", pady=(2, 0))

        # Hero Right: Illuminated Next Trigger Live Display Card
        hero_right = ctk.CTkFrame(hero_inner, fg_color="#0e0a17", corner_radius=8, border_width=1, border_color="#6b21a8")
        hero_right.pack(side="right", padx=(10, 0))

        hr_inner = ctk.CTkFrame(hero_right, fg_color="transparent")
        hr_inner.pack(padx=14, pady=8)

        ctk.CTkLabel(
            hr_inner, text="⚡ NEXT SCHEDULED TRIGGER",
            font=("Segoe UI", 9, "bold"), text_color="#c084fc"
        ).pack(anchor="w")

        self.scheduler_ticker_label = ctk.CTkLabel(
            hr_inner, text="⏳ No upcoming scheduled downloads.",
            font=("Segoe UI", 12, "bold"), text_color="#00f0ff"
        )
        self.scheduler_ticker_label.pack(anchor="w", pady=(2, 0))

        # 2. Modern 4-KPI Metric Cards Row
        kpi_row = ctk.CTkFrame(self.scheduler_view, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 8))

        def _make_sched_kpi(parent, title, val_color, bg_color, border_color):
            card = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=8, border_width=1, border_color=border_color, height=52)
            card.pack(side="left", fill="x", expand=True, padx=3)
            card.pack_propagate(False)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=10, pady=4)
            val_lbl = ctk.CTkLabel(inner, text="0", font=("Segoe UI", 16, "bold"), text_color=val_color)
            val_lbl.pack(anchor="w")
            ctk.CTkLabel(inner, text=title, font=("Segoe UI", 9, "bold"), text_color="#94a3b8").pack(anchor="w")
            return val_lbl

        self.sched_stat_active = _make_sched_kpi(kpi_row, "ACTIVE TASKS", "#FBBF24", "#2a1b08", "#633c0c")
        self.sched_stat_daily = _make_sched_kpi(kpi_row, "DAILY RECURRING", "#34D399", "#092418", "#124a30")
        self.sched_stat_completed = _make_sched_kpi(kpi_row, "COMPLETED", "#38BDF8", "#0c1d2e", "#1b3c5a")
        self.sched_stat_total = _make_sched_kpi(kpi_row, "TOTAL SCHEDULES", "#C084FC", "#1e1133", "#45226e")

        # 3. Control, Search, and Filter Toolbar
        ctrl_bar = ctk.CTkFrame(self.scheduler_view, corner_radius=8, fg_color="#141822", border_width=1, border_color="#242b3d")
        ctrl_bar.pack(fill="x", pady=(0, 8))

        ctrl_inner = ctk.CTkFrame(ctrl_bar, fg_color="transparent")
        ctrl_inner.pack(fill="x", padx=12, pady=6)

        # Real-time search entry for scheduler
        self.schedule_search_entry = ctk.CTkEntry(
            ctrl_inner, textvariable=self.schedule_search_var,
            placeholder_text="🔍 Search schedule by task, URL, or #01...", width=340, height=32,
            fg_color="#0b0e14", border_color="#2d3748", corner_radius=6
        )
        self.schedule_search_entry.pack(side="left", padx=(0, 10))
        self._attach_entry_context_menu(self.schedule_search_entry)
        self.schedule_search_var.trace_add("write", lambda *_: self._render_schedules_list())

        ctk.CTkLabel(ctrl_inner, text="Filter:", font=("Segoe UI", 11, "bold"), text_color="#94a3b8").pack(side="left", padx=4)
        ctk.CTkOptionMenu(
            ctrl_inner, variable=self.schedule_filter_var,
            values=["All Schedules", "Pending Only", "Recurring Daily", "Completed", "Cancelled"],
            width=140, height=30, corner_radius=6,
            command=lambda _: self._render_schedules_list()
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            ctrl_inner, text="➕ Schedule Current Setup", width=180, height=32,
            fg_color="#6366f1", hover_color="#4f46e5", font=("Segoe UI", 11, "bold"),
            corner_radius=6, command=self._schedule_current_download
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            ctrl_inner, text="🔄 Refresh", width=80, height=32,
            fg_color="#334155", hover_color="#475569", font=("Segoe UI", 11, "bold"),
            corner_radius=6, command=self._render_schedules_list
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            ctrl_inner, text="🧹 Clear Inactive", width=115, height=32,
            fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 11),
            corner_radius=6, command=self._clear_inactive_schedules
        ).pack(side="right", padx=4)

        # 4. Scrollable Schedule Cards Area
        self.schedules_scroll = ctk.CTkScrollableFrame(self.scheduler_view, fg_color="transparent")
        self.schedules_scroll.pack(fill="both", expand=True, pady=(0, 8))

    def _scheduler_log(self, message):
        pass

    def _clear_scheduler_log(self):
        pass

    def _render_schedules_list(self):
        """Render all scheduled jobs with sleek modern cards, glowing countdown banners, and status badges."""
        for widget in self.schedules_scroll.winfo_children():
            widget.destroy()

        self._schedule_countdown_labels.clear()

        jobs = self.scheduler.get_all()
        total_count = len(jobs)
        active_count = sum(1 for j in jobs if j.get("status") == "Pending")
        daily_count = sum(1 for j in jobs if j.get("repeat_daily"))
        comp_count = sum(1 for j in jobs if j.get("status") == "Completed")

        if hasattr(self, "sched_stat_active"):
            self.sched_stat_active.configure(text=str(active_count))
            self.sched_stat_daily.configure(text=str(daily_count))
            self.sched_stat_completed.configure(text=str(comp_count))
            if hasattr(self, "sched_stat_total"):
                self.sched_stat_total.configure(text=str(total_count))

        # Filter by status
        selected_filter = self.schedule_filter_var.get()
        if selected_filter == "Pending Only":
            jobs = [j for j in jobs if j.get("status") == "Pending"]
        elif selected_filter == "Recurring Daily":
            jobs = [j for j in jobs if j.get("repeat_daily")]
        elif selected_filter == "Completed":
            jobs = [j for j in jobs if j.get("status") == "Completed"]
        elif selected_filter == "Cancelled":
            jobs = [j for j in jobs if j.get("status") in ("Cancelled", "Failed")]

        # Filter by search text
        search_query = self.schedule_search_var.get().strip().lower()
        if search_query:
            matched = []
            for i, job in enumerate(jobs):
                num_tag = f"#{i+1:02d}".lower()
                num_raw = str(i+1)
                name = job.get("name", "").lower()
                run_at = job.get("run_at", "").lower()
                url = job.get("target_data", {}).get("url", "").lower()
                if (search_query in num_tag or search_query in num_raw or
                    search_query in name or search_query in run_at or search_query in url):
                    matched.append(job)
            jobs = matched

        if not jobs:
            empty_frame = ctk.CTkFrame(self.schedules_scroll, fg_color="#141822", corner_radius=10, border_width=1, border_color="#242b3d")
            empty_frame.pack(fill="x", padx=10, pady=30)
            ctk.CTkLabel(
                empty_frame,
                text="⏰ No Scheduled Tasks Found\n\nNo tasks match your search or filter.\nSet up any download or batch and click 'Schedule' to automate execution!",
                font=("Segoe UI", 13), text_color="#94a3b8", justify="center"
            ).pack(padx=20, pady=(24, 16))
            ctk.CTkButton(
                empty_frame, text="➕ Schedule Current Setup", width=220, height=36,
                fg_color="#6366f1", hover_color="#4f46e5", font=("Segoe UI", 12, "bold"),
                corner_radius=6, command=self._schedule_current_download
            ).pack(pady=(0, 24))
            return

        for idx, job in enumerate(jobs, start=1):
            jid = job.get("id")
            name = job.get("name", "Scheduled Download")
            run_at = job.get("run_at", "")
            status = job.get("status", "Pending")
            jtype = job.get("job_type", "direct")
            tdata = job.get("target_data", {})
            repeat_daily = job.get("repeat_daily", False)
            countdown = self.scheduler.get_countdown(run_at) if status == "Pending" else status

            # Status styling
            if status == "Pending":
                card_bg = "#191226"
                card_border = "#8b5cf6"
                border_w = 2
                status_text = "● PENDING"
                st_color = "#fcd34d"
                st_bg = "#451a03"
            elif status == "Running":
                card_bg = "#0f1c29"
                card_border = "#0284c7"
                border_w = 2
                status_text = "⚡ RUNNING"
                st_color = "#38bdf8"
                st_bg = "#0c2738"
            elif status == "Completed":
                card_bg = "#0f1916"
                card_border = "#059669"
                border_w = 1
                status_text = "✅ COMPLETED"
                st_color = "#6ee7b7"
                st_bg = "#064e3b"
            else:
                card_bg = "#1f1214"
                card_border = "#dc2626"
                border_w = 1
                status_text = "❌ CANCELLED"
                st_color = "#fca5a5"
                st_bg = "#450a0a"

            # Outer Card
            card = ctk.CTkFrame(
                self.schedules_scroll, corner_radius=10,
                fg_color=card_bg, border_width=border_w, border_color=card_border
            )
            card.pack(fill="x", padx=4, pady=5)

            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="both", expand=True, padx=14, pady=12)

            # Row 1: Header (Number Badge + Task Name + Job Type + Recurring + Status Badge)
            row1 = ctk.CTkFrame(card_inner, fg_color="transparent")
            row1.pack(fill="x")

            # Numbering badge (#01, #02...)
            num_lbl = ctk.CTkLabel(
                row1, text=f"#{idx:02d}", font=("Segoe UI", 11, "bold"),
                text_color="#c084fc", fg_color="#26173a", corner_radius=6, padx=8, pady=3
            )
            num_lbl.pack(side="left")

            # Job Name
            ctk.CTkLabel(
                row1, text=name, font=("Segoe UI", 15, "bold"), text_color="#FFFFFF"
            ).pack(side="left", padx=(10, 8))

            # Job Type Pill
            type_label = "📦 BATCH JOB" if jtype == "batch" else "📹 DIRECT JOB"
            ctk.CTkLabel(
                row1, text=type_label, font=("Segoe UI", 10, "bold"),
                text_color="#38bdf8", fg_color="#0e2a3b", corner_radius=6, padx=8, pady=3
            ).pack(side="left", padx=(0, 6))

            if repeat_daily:
                ctk.CTkLabel(
                    row1, text="🔁 DAILY RECURRING", font=("Segoe UI", 9, "bold"),
                    text_color="#34d399", fg_color="#064e3b", corner_radius=6, padx=8, pady=3
                ).pack(side="left")

            # Right Status Badge
            st_pill = ctk.CTkLabel(
                row1, text=status_text, font=("Segoe UI", 11, "bold"),
                text_color=st_color, fg_color=st_bg, corner_radius=6, padx=10, pady=4
            )
            st_pill.pack(side="right")

            # Row 2: Target URL Container (if URL exists)
            target_url = tdata.get("url", "")
            if target_url:
                row2 = ctk.CTkFrame(card_inner, fg_color="#0b0e14", corner_radius=6, border_width=1, border_color="#1e2536")
                row2.pack(fill="x", pady=(8, 6))

                r2_inner = ctk.CTkFrame(row2, fg_color="transparent")
                r2_inner.pack(fill="x", padx=10, pady=5)

                ctk.CTkLabel(r2_inner, text="🔗", font=("Segoe UI", 11)).pack(side="left", padx=(0, 6))
                ctk.CTkLabel(r2_inner, text=target_url, font=("Segoe UI", 11), text_color="#60a5fa", anchor="w").pack(side="left", fill="x", expand=True)
                ctk.CTkButton(
                    r2_inner, text="📋 Copy", width=65, height=22,
                    fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"),
                    corner_radius=4, command=lambda u=target_url: self._copy_text_to_clipboard(u)
                ).pack(side="right")

            # Row 3: Metadata Chips Row
            row3 = ctk.CTkFrame(card_inner, fg_color="transparent")
            row3.pack(fill="x", pady=(2, 6))

            chips_box = ctk.CTkFrame(row3, fg_color="transparent")
            chips_box.pack(side="left", fill="x", expand=True)

            def _add_sched_chip(parent, icon, text_val):
                chip = ctk.CTkFrame(parent, fg_color="#1a202c", corner_radius=6, border_width=1, border_color="#2d3748")
                chip.pack(side="left", padx=(0, 6), pady=2)
                ctk.CTkLabel(chip, text=f"{icon} {text_val}", font=("Segoe UI", 10, "bold"), text_color="#cbd5e1").pack(padx=8, pady=3)

            _add_sched_chip(chips_box, "📅 Trigger Time", run_at)
            if jtype == "batch":
                _add_sched_chip(chips_box, "🏷️ Batch ID", tdata.get("id", "N/A")[:8])
            if tdata.get("quality"):
                _add_sched_chip(chips_box, "🎯", tdata.get("quality"))
            if tdata.get("format"):
                _add_sched_chip(chips_box, "📦", str(tdata.get("format")).upper())

            # Row 4: Countdown Box (for Pending jobs)
            if status == "Pending":
                cd_banner = ctk.CTkFrame(card_inner, fg_color="#22123d", corner_radius=8, border_width=1, border_color="#9333ea")
                cd_banner.pack(fill="x", pady=(4, 6))

                cd_inner = ctk.CTkFrame(cd_banner, fg_color="transparent")
                cd_inner.pack(fill="x", padx=12, pady=7)

                ctk.CTkLabel(
                    cd_inner, text="⏰ UPCOMING TRIGGER:",
                    font=("Segoe UI", 11, "bold"), text_color="#e9d5ff"
                ).pack(side="left")

                cd_label = ctk.CTkLabel(
                    cd_inner, text=f"⏳ Starts In: {countdown}",
                    font=("Segoe UI", 12, "bold"), text_color="#00f0ff"
                )
                cd_label.pack(side="left", padx=12)
                self._schedule_countdown_labels[jid] = (cd_label, run_at)

            # Row 5: Action Buttons Bar
            row5 = ctk.CTkFrame(card_inner, fg_color="transparent")
            row5.pack(fill="x", pady=(6, 0))

            btn_box_left = ctk.CTkFrame(row5, fg_color="transparent")
            btn_box_left.pack(side="left")

            if status == "Pending":
                ctk.CTkButton(
                    btn_box_left, text="▶️ Run Now", width=105, height=32,
                    fg_color="#059669", hover_color="#10b981", font=("Segoe UI", 11, "bold"),
                    corner_radius=6, command=lambda j_item=job: self._run_scheduled_job(j_item)
                ).pack(side="left", padx=(0, 6))

                ctk.CTkButton(
                    btn_box_left, text="⏸️ Cancel", width=95, height=32,
                    fg_color="#d97706", hover_color="#b45309", font=("Segoe UI", 11, "bold"),
                    corner_radius=6, command=lambda jid_val=jid: self._cancel_schedule(jid_val)
                ).pack(side="left")

            ctk.CTkButton(
                row5, text="🗑️ Delete", width=80, height=32,
                fg_color="#450a0a", hover_color="#991b1b", text_color="#fca5a5", font=("Segoe UI", 11, "bold"),
                corner_radius=6, command=lambda jid_val=jid: self._delete_schedule(jid_val)
            ).pack(side="right")

    def _delete_schedule(self, job_id):
        if messagebox.askyesno("Delete Schedule", "Delete this scheduled download task?"):
            self.scheduler.delete(job_id)
            self._render_schedules_list()
            self._update_status("Schedule deleted.")
            self._scheduler_log(f"Deleted task {job_id}")

    def _cancel_schedule(self, job_id):
        self.scheduler.cancel(job_id)
        self._render_schedules_list()
        self._update_status("Schedule cancelled.")
        self._scheduler_log(f"Cancelled task {job_id}")

    def _clear_inactive_schedules(self):
        jobs = self.scheduler.get_all()
        to_del = [j["id"] for j in jobs if j.get("status") in ("Completed", "Cancelled", "Failed")]
        if not to_del:
            messagebox.showinfo("Scheduler", "No inactive or completed tasks to clear.")
            return
        if messagebox.askyesno("Clear Inactive", f"Clear {len(to_del)} finished / cancelled schedules?"):
            for jid in to_del:
                self.scheduler.delete(jid)
            self._render_schedules_list()
            self._scheduler_log(f"Cleared {len(to_del)} inactive schedules.")

    def _schedule_current_download(self):
        pkg = self._get_current_download_package()
        if not pkg["url"]:
            messagebox.showwarning("Warning", "Please enter a valid YouTube URL in Downloads Studio first!")
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

    # ==================== Settings Studio View ====================

    def _build_settings_view(self):
        """Build the dedicated Global Application Settings Studio."""
        # Top Header Card
        header_card = ctk.CTkFrame(self.settings_view, corner_radius=10, fg_color="#181329", border_width=1, border_color="#3d2d5e")
        header_card.pack(fill="x", pady=(0, 8))

        h_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        h_inner.pack(fill="x", padx=16, pady=12)

        h_left = ctk.CTkFrame(h_inner, fg_color="transparent")
        h_left.pack(side="left")

        ctk.CTkLabel(
            h_left, text="⚙️ Settings Studio",
            font=("Segoe UI", 20, "bold"), text_color="#FFFFFF"
        ).pack(anchor="w")
        ctk.CTkLabel(
            h_left, text="Configure global defaults for downloads, directory automation, and anti-bot security",
            font=("Segoe UI", 11), text_color="#94a3b8"
        ).pack(anchor="w", pady=(1, 0))

        h_right = ctk.CTkFrame(h_inner, fg_color="transparent")
        h_right.pack(side="right")

        ctk.CTkButton(
            h_right, text="💾 Save Default Settings", width=190, height=34,
            fg_color="#059669", hover_color="#10b981", font=("Segoe UI", 12, "bold"),
            corner_radius=6, command=self._save_default_settings
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            h_right, text="🔄 Reset Defaults", width=130, height=34,
            fg_color="#334155", hover_color="#475569", font=("Segoe UI", 11, "bold"),
            corner_radius=6, command=self._reset_default_settings
        ).pack(side="left", padx=4)

        # Card 1: Download & Storage Defaults
        card_dir = ctk.CTkFrame(self.settings_view, corner_radius=10, fg_color="#141822", border_width=1, border_color="#242b3d")
        card_dir.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            card_dir, text="📁 Default Storage & File Management",
            font=("Segoe UI", 14, "bold"), text_color="#38bdf8"
        ).pack(anchor="w", padx=16, pady=(12, 6))

        d_inner = ctk.CTkFrame(card_dir, fg_color="#0e1118", corner_radius=8, border_width=1, border_color="#1e2433")
        d_inner.pack(fill="x", padx=16, pady=(0, 12))

        d_row1 = ctk.CTkFrame(d_inner, fg_color="transparent")
        d_row1.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(d_row1, text="Default Save Directory:", width=180, anchor="w", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").pack(side="left")
        self.set_dir_var = ctk.StringVar(value=self.app_settings.get("default_download_dir", DEFAULT_DOWNLOAD_DIR))
        self.set_dir_entry = ctk.CTkEntry(d_row1, textvariable=self.set_dir_var, width=450, fg_color="#0b0e14", border_color="#2d3748")
        self.set_dir_entry.pack(side="left", fill="x", expand=True, padx=6)
        self._attach_entry_context_menu(self.set_dir_entry)
        ctk.CTkButton(d_row1, text="Browse", width=80, fg_color="#334155", hover_color="#475569", corner_radius=6, command=self._browse_settings_dir).pack(side="left", padx=4)
        ctk.CTkButton(d_row1, text="📂 Open", width=80, fg_color="#1e293b", hover_color="#334155", corner_radius=6, command=self._open_download_dir).pack(side="left", padx=4)

        d_row2 = ctk.CTkFrame(d_inner, fg_color="transparent")
        d_row2.pack(fill="x", padx=12, pady=(4, 10))
        self.set_subfolder_var = ctk.BooleanVar(value=self.app_settings.get("default_auto_subfolder", True))
        ctk.CTkCheckBox(d_row2, text="📂 Automatically create subfolders for Playlist and Channel names by default", variable=self.set_subfolder_var).pack(side="left")

        # Card 2: Video & Audio Quality Defaults
        card_stream = ctk.CTkFrame(self.settings_view, corner_radius=10, fg_color="#141822", border_width=1, border_color="#242b3d")
        card_stream.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            card_stream, text="🎬 Default Video & Audio Stream Preferences",
            font=("Segoe UI", 14, "bold"), text_color="#38bdf8"
        ).pack(anchor="w", padx=16, pady=(12, 6))

        s_inner = ctk.CTkFrame(card_stream, fg_color="#0e1118", corner_radius=8, border_width=1, border_color="#1e2433")
        s_inner.pack(fill="x", padx=16, pady=(0, 12))

        s_grid = ctk.CTkFrame(s_inner, fg_color="transparent")
        s_grid.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(s_grid, text="Default Quality:", width=120, anchor="w", font=("Segoe UI", 11, "bold"), text_color="#cbd5e1").grid(row=0, column=0, sticky="w", pady=6)
        self.set_quality_var = ctk.StringVar(value=self.app_settings.get("default_quality", "Best Quality"))
        ctk.CTkOptionMenu(s_grid, variable=self.set_quality_var, values=list(QUALITY_OPTIONS.keys()), width=220, corner_radius=6).grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ctk.CTkLabel(s_grid, text="Default Format:", width=110, anchor="w", font=("Segoe UI", 11, "bold"), text_color="#cbd5e1").grid(row=0, column=2, sticky="w", padx=(20, 0), pady=6)
        self.set_format_var = ctk.StringVar(value=self.app_settings.get("default_format", "mp4"))
        ctk.CTkOptionMenu(s_grid, variable=self.set_format_var, values=VIDEO_FORMATS + AUDIO_FORMATS, width=120, corner_radius=6).grid(row=0, column=3, sticky="w", padx=6, pady=6)

        s_row2 = ctk.CTkFrame(s_inner, fg_color="transparent")
        s_row2.pack(fill="x", padx=12, pady=(4, 10))

        self.set_thumb_var = ctk.BooleanVar(value=self.app_settings.get("default_embed_thumbnail", False))
        ctk.CTkCheckBox(s_row2, text="🖼️ Embed Thumbnail by default", variable=self.set_thumb_var).pack(side="left", padx=(0, 15))

        self.set_sub_var = ctk.BooleanVar(value=self.app_settings.get("default_download_subtitles", False))
        ctk.CTkCheckBox(s_row2, text="💬 Download Subtitles by default", variable=self.set_sub_var).pack(side="left", padx=4)

        ctk.CTkLabel(s_row2, text="Language:", font=("Segoe UI", 11, "bold"), text_color="#cbd5e1").pack(side="left", padx=(10, 4))
        self.set_sub_lang_entry = ctk.CTkEntry(s_row2, width=60, fg_color="#0b0e14", border_color="#2d3748")
        self.set_sub_lang_entry.insert(0, self.app_settings.get("default_subtitle_lang", "en"))
        self.set_sub_lang_entry.pack(side="left", padx=4)
        self._attach_entry_context_menu(self.set_sub_lang_entry)

        ctk.CTkLabel(s_row2, text="Speed Limit:", font=("Segoe UI", 11, "bold"), text_color="#cbd5e1").pack(side="left", padx=(20, 4))
        self.set_speed_entry = ctk.CTkEntry(s_row2, width=80, placeholder_text="0", fg_color="#0b0e14", border_color="#2d3748")
        self.set_speed_entry.insert(0, self.app_settings.get("default_speed_limit", ""))
        self.set_speed_entry.pack(side="left", padx=4)
        self._attach_entry_context_menu(self.set_speed_entry)
        ctk.CTkLabel(s_row2, text="KB/s (0=unlimited)", font=("Segoe UI", 10), text_color="gray").pack(side="left", padx=4)

        # Card 3: Title Rewriting & Naming Defaults
        card_naming = ctk.CTkFrame(self.settings_view, corner_radius=10, fg_color="#141822", border_width=1, border_color="#242b3d")
        card_naming.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            card_naming, text="🏷️ Default Title Rewriting & File Naming",
            font=("Segoe UI", 14, "bold"), text_color="#c084fc"
        ).pack(anchor="w", padx=16, pady=(12, 6))

        n_inner = ctk.CTkFrame(card_naming, fg_color="#0e1118", corner_radius=8, border_width=1, border_color="#1e2433")
        n_inner.pack(fill="x", padx=16, pady=(0, 12))

        n_row1 = ctk.CTkFrame(n_inner, fg_color="transparent")
        n_row1.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(n_row1, text="Default Scheme:", width=120, anchor="w", font=("Segoe UI", 11, "bold"), text_color="#cbd5e1").pack(side="left")
        self.set_naming_var = ctk.StringVar(value=self.app_settings.get("default_naming_scheme", "Numbered + Rewrite Title (01 - Cleaned)"))
        ctk.CTkOptionMenu(n_row1, variable=self.set_naming_var, values=list(NAMING_SCHEMES.keys()), width=260, corner_radius=6).pack(side="left", padx=4)

        ctk.CTkLabel(n_row1, text="Default Prefix:", width=100, anchor="w", font=("Segoe UI", 11, "bold"), text_color="#cbd5e1").pack(side="left", padx=(15, 0))
        self.set_prefix_entry = ctk.CTkEntry(n_row1, width=150, placeholder_text="e.g. MyVideo", fg_color="#0b0e14", border_color="#2d3748")
        self.set_prefix_entry.insert(0, self.app_settings.get("default_custom_prefix", ""))
        self.set_prefix_entry.pack(side="left", padx=4)
        self._attach_entry_context_menu(self.set_prefix_entry)

        n_row2 = ctk.CTkFrame(n_inner, fg_color="transparent")
        n_row2.pack(fill="x", padx=12, pady=(6, 10))

        ctk.CTkButton(
            n_row2, text="⚙️ Configure Semantic & AI Title Rewrite Rules", width=330, height=32,
            fg_color="#6366f1", hover_color="#4f46e5", font=("Segoe UI", 11, "bold"),
            corner_radius=6, command=self._open_title_rules_dialog
        ).pack(side="left")

        # Card 4: Anti-Bot & Cookies Protection (VPS Safe)
        card_cookies = ctk.CTkFrame(self.settings_view, corner_radius=10, fg_color="#141822", border_width=1, border_color="#242b3d")
        card_cookies.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            card_cookies, text="🍪 YouTube Anti-Bot & Cookies Protection (VPS / Datacenter)",
            font=("Segoe UI", 14, "bold"), text_color="#34d399"
        ).pack(anchor="w", padx=16, pady=(12, 6))

        c_inner = ctk.CTkFrame(card_cookies, fg_color="#0e1118", corner_radius=8, border_width=1, border_color="#1e2433")
        c_inner.pack(fill="x", padx=16, pady=(0, 12))

        c_row = ctk.CTkFrame(c_inner, fg_color="transparent")
        c_row.pack(fill="x", padx=12, pady=10)

        ctk.CTkButton(
            c_row, text="🍪 Open YouTube Cookies Manager", width=240, height=32,
            fg_color="#0284c7", hover_color="#0369a1", font=("Segoe UI", 11, "bold"),
            corner_radius=6, command=self._open_cookie_manager
        ).pack(side="left", padx=(0, 12))

        self.set_cookie_status_label = ctk.CTkLabel(
            c_row, text=self._get_cookie_status_text(), font=("Segoe UI", 11, "bold"),
            text_color="#34d399" if self._has_cookies() else "#fbbf24"
        )
        self.set_cookie_status_label.pack(side="left")

    def _browse_settings_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.set_dir_var.set(d)

    def _save_default_settings(self):
        """Save settings to settings.json and synchronize with live Downloads Studio."""
        new_settings = {
            "default_quality": self.set_quality_var.get(),
            "default_format": self.set_format_var.get(),
            "default_naming_scheme": self.set_naming_var.get(),
            "default_custom_prefix": self.set_prefix_entry.get().strip(),
            "default_download_dir": self.set_dir_var.get().strip() or DEFAULT_DOWNLOAD_DIR,
            "default_auto_subfolder": self.set_subfolder_var.get(),
            "default_embed_thumbnail": self.set_thumb_var.get(),
            "default_download_subtitles": self.set_sub_var.get(),
            "default_subtitle_lang": self.set_sub_lang_entry.get().strip() or "en",
            "default_speed_limit": self.set_speed_entry.get().strip(),
        }

        save_app_settings(new_settings)
        self.app_settings = new_settings

        # Synchronize live Downloads Studio controls
        self.quality_var.set(new_settings["default_quality"])
        self.format_var.set(new_settings["default_format"])
        self.naming_var.set(new_settings["default_naming_scheme"])
        self.prefix_entry.delete(0, "end")
        self.prefix_entry.insert(0, new_settings["default_custom_prefix"])
        self.dir_var.set(new_settings["default_download_dir"])
        self.subfolder_var.set(new_settings["default_auto_subfolder"])
        self.thumbnail_var.set(new_settings["default_embed_thumbnail"])
        self.subtitle_var.set(new_settings["default_download_subtitles"])
        self.subtitle_lang_entry.delete(0, "end")
        self.subtitle_lang_entry.insert(0, new_settings["default_subtitle_lang"])
        self.speed_entry.delete(0, "end")
        self.speed_entry.insert(0, new_settings["default_speed_limit"])

        messagebox.showinfo("Settings Saved", "✅ Default settings saved successfully!\nDownloads Studio has been updated with your new defaults.")
        self._update_status("⚙️ Global default settings saved.")

    def _reset_default_settings(self):
        """Reset default settings to factory defaults."""
        if messagebox.askyesno("Reset Defaults", "Reset all default settings to original factory values?"):
            save_app_settings(dict(DEFAULT_APP_SETTINGS))
            self.app_settings = dict(DEFAULT_APP_SETTINGS)
            self._refresh_settings_view()
            messagebox.showinfo("Reset Complete", "Default settings restored to factory defaults.")

    def _refresh_settings_view(self):
        """Populate settings widgets with latest app_settings."""
        if hasattr(self, "set_quality_var"):
            self.set_quality_var.set(self.app_settings.get("default_quality", "Best Quality"))
            self.set_format_var.set(self.app_settings.get("default_format", "mp4"))
            self.set_naming_var.set(self.app_settings.get("default_naming_scheme", "Numbered + Rewrite Title (01 - Cleaned)"))
            self.set_prefix_entry.delete(0, "end")
            self.set_prefix_entry.insert(0, self.app_settings.get("default_custom_prefix", ""))
            self.set_dir_var.set(self.app_settings.get("default_download_dir", DEFAULT_DOWNLOAD_DIR))
            self.set_subfolder_var.set(self.app_settings.get("default_auto_subfolder", True))
            self.set_thumb_var.set(self.app_settings.get("default_embed_thumbnail", False))
            self.set_sub_var.set(self.app_settings.get("default_download_subtitles", False))
            self.set_sub_lang_entry.delete(0, "end")
            self.set_sub_lang_entry.insert(0, self.app_settings.get("default_subtitle_lang", "en"))
            self.set_speed_entry.delete(0, "end")
            self.set_speed_entry.insert(0, self.app_settings.get("default_speed_limit", ""))
            if hasattr(self, "set_cookie_status_label"):
                self.set_cookie_status_label.configure(
                    text=self._get_cookie_status_text(),
                    text_color="#2ECC71" if self._has_cookies() else "#F39C12"
                )

    def _start_scheduler_ticker(self):
        """Update live countdown across Scheduler Studio and Batches Studio dynamically every 1 second."""
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
                        text=f"⏳ Next: '{name}' starts in {cd}  (Scheduled for {run_at})"
                    )
            else:
                if hasattr(self, "scheduler_ticker_label"):
                    self.scheduler_ticker_label.configure(text="⏳ No upcoming scheduled downloads.")

            # Live update per-card countdowns in Scheduler Studio
            if self.current_nav_view == "scheduler" and hasattr(self, "_schedule_countdown_labels"):
                for jid, (lbl, r_at) in list(self._schedule_countdown_labels.items()):
                    try:
                        c_text = self.scheduler.get_countdown(r_at)
                        lbl.configure(text=f"⏳ Countdown: {c_text}")
                    except Exception:
                        pass

            # Live update per-card countdowns in Batches Studio
            if self.current_nav_view == "batches" and hasattr(self, "_batch_countdown_labels"):
                for bid, (b_lbl, r_at) in list(self._batch_countdown_labels.items()):
                    try:
                        b_cd = self.scheduler.get_countdown(r_at)
                        b_lbl.configure(text=f"⏳ Starts In: {b_cd}")
                    except Exception:
                        pass
        except Exception:
            pass
        self.after(1000, self._start_scheduler_ticker)

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

        self.current_running_batch_id = batch["id"]
        self.batch_manager.mark_status(batch["id"], "Running", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._render_batches_list()
        self._batch_log(f"▶️ Starting batch: '{batch.get('name')}'")

        def done_callback(success):
            self.current_running_batch_id = None
            status = "Completed" if success else "Failed"
            self.batch_manager.mark_status(batch["id"], status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self._batch_log(f"Batch '{batch.get('name')}' finished with status: {status}")
            self.after(0, self._render_batches_list)

        self._execute_package_download(batch, on_complete=done_callback)

    def _run_scheduled_job(self, job):
        """Called automatically by DownloadScheduler when scheduled time arrives."""
        self.scheduler.set_busy(True)
        job_name = job.get("name", "Scheduled Task")
        msg = f"⏰ Scheduler triggered: '{job_name}'!"
        self.after(0, lambda: self._update_status(msg))
        self.after(0, lambda: self._scheduler_log(msg))

        jtype = job.get("job_type", "direct")
        tdata = job.get("target_data", {})

        def done_callback(success):
            st = "Completed" if success else "Failed"
            finish_msg = f"Finished at {datetime.now().strftime('%H:%M:%S')}"
            self.scheduler.mark_status(job["id"], st, finish_msg)
            self.scheduler.set_busy(False)
            self._scheduler_log(f"✅ Job '{job_name}' finished as {st} ({finish_msg})")
            if job.get("repeat_daily"):
                self._scheduler_log(f"🔁 Job '{job_name}' auto-rescheduled for tomorrow!")
            self.after(0, self._render_schedules_list)

        if jtype == "batch":
            bid = tdata.get("id")
            saved_batch = self.batch_manager.get(bid) if bid else tdata
            if saved_batch:
                self.current_running_batch_id = bid
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
        self.progress_percent.configure(text="0.0%")
        if hasattr(self, "speed_eta_label"):
            self.speed_eta_label.configure(text="")
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
            try:
                if js_cfg:
                    rt_name = list(js_cfg.keys())[0]
                    rt_label = 'Deno' if rt_name == 'deno' else 'Node.js'
                    self.after(0, lambda: self._log(f"⚡ JS Runtime: {rt_label} active (YouTube challenge solver enabled)"))
                else:
                    self.after(0, lambda: self._log("⚠️ JS Engine missing! YouTube challenge solver may be restricted."))
            except Exception:
                pass

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

    def _update_status(self, text, force_log=False):
        if not text:
            return

        # Check if text is a high-frequency download progress tick
        is_progress_tick = (" | " in text and ("MB/s" in text or "KB/s" in text or "ETA:" in text))

        if hasattr(self, "status_label"):
            if is_progress_tick:
                parts = text.split(" | ")
                main_part = parts[0].strip()
                meta_part = "  •  ".join(p.strip() for p in parts[1:])
                self.status_label.configure(text=f"⚡ {main_part}")
                if hasattr(self, "speed_eta_label"):
                    self.speed_eta_label.configure(text=f"🚀 {meta_part}")
            else:
                self.status_label.configure(text=text)
                if hasattr(self, "speed_eta_label"):
                    self.speed_eta_label.configure(text="")

        # Only write to log textboxes if it's a real milestone or forced log, NOT high-frequency speed ticks
        if force_log or not is_progress_tick:
            self._log(text)
            if getattr(self, "current_running_batch_id", None):
                self._batch_log(text)

    def _update_progress(self, percent):
        try:
            val = max(0.0, min(100.0, float(percent)))
            self.progress_bar.set(val / 100.0)
            self.progress_percent.configure(text=f"{val:.1f}%")
        except Exception:
            pass

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
        if hasattr(self, "speed_eta_label"):
            self.speed_eta_label.configure(text="")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
