"""Dialog modals for Title Rewriter Rules, Batch Creation, and Download Scheduling.
"""

from datetime import datetime, timedelta
from tkinter import messagebox
import customtkinter as ctk

from config import (
    AUDIO_FORMATS,
    DEFAULT_DOWNLOAD_DIR,
    NAMING_SCHEMES,
    QUALITY_OPTIONS,
    SELECTION_MODES,
    VIDEO_FORMATS,
)
from title_rewriter import load_rules, rewrite_title, save_rules


class TitleRulesDialog(ctk.CTkToplevel):
    """Dialog for customizing Title Rewriting rules with live preview."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("⚙️ Title Rewrite Rules & Live Preview")
        self.geometry("640x580")
        self.resizable(False, False)
        self.rules = load_rules()
        self.parent = parent

        self.after(100, self.lift)
        self.after(150, self.focus_force)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Header
        ctk.CTkLabel(
            container,
            text="⚙️ Title Rewrite Rules",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            container,
            text="Configure how video titles are cleaned and formatted automatically.",
            font=("Segoe UI", 12),
            text_color="gray",
        ).pack(anchor="w", pady=(0, 15))

        # Checkboxes Frame
        opts_frame = ctk.CTkFrame(container)
        opts_frame.pack(fill="x", pady=(0, 15))

        self.emoji_var = ctk.BooleanVar(value=self.rules.get("remove_emojis", True))
        self.hashtag_var = ctk.BooleanVar(value=self.rules.get("remove_hashtags", True))
        self.mention_var = ctk.BooleanVar(value=self.rules.get("remove_mentions", True))
        self.tags_var = ctk.BooleanVar(value=self.rules.get("remove_resolution_tags", True))
        self.sep_var = ctk.BooleanVar(value=self.rules.get("clean_separators", True))

        ctk.CTkCheckBox(
            opts_frame,
            text="🔥 Remove Emojis & Graphic Icons (😱, 🔥, 🚀, etc.)",
            variable=self.emoji_var,
            command=self._update_preview,
        ).pack(anchor="w", padx=15, pady=8)

        ctk.CTkCheckBox(
            opts_frame,
            text="🏷️ Remove Hashtags (#shorts, #vlog, #viral, etc.)",
            variable=self.hashtag_var,
            command=self._update_preview,
        ).pack(anchor="w", padx=15, pady=8)

        ctk.CTkCheckBox(
            opts_frame,
            text="👤 Remove Channel Mentions (@channel, @user)",
            variable=self.mention_var,
            command=self._update_preview,
        ).pack(anchor="w", padx=15, pady=8)

        ctk.CTkCheckBox(
            opts_frame,
            text="🎬 Remove Video/Media Tags ([1080p], (Official Video), (4K), etc.)",
            variable=self.tags_var,
            command=self._update_preview,
        ).pack(anchor="w", padx=15, pady=8)

        ctk.CTkCheckBox(
            opts_frame,
            text="➖ Normalize Separators (convert |, //, __ to clean hyphen -)",
            variable=self.sep_var,
            command=self._update_preview,
        ).pack(anchor="w", padx=15, pady=8)

        # Live Test & Preview Frame
        prev_frame = ctk.CTkFrame(container)
        prev_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            prev_frame,
            text="🧪 Live Title Preview:",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w", padx=15, pady=(10, 5))

        ctk.CTkLabel(prev_frame, text="Input dirty title:", font=("Segoe UI", 11), text_color="gray").pack(anchor="w", padx=15)
        self.test_entry = ctk.CTkEntry(prev_frame, height=32, font=("Segoe UI", 12))
        self.test_entry.insert(0, "Aaj सुबह सुबह Ye Kya Ho Gaya | Vlog #12 #shorts #viral @shiv [1080p] 😱")
        self.test_entry.pack(fill="x", padx=15, pady=(2, 8))
        self.test_entry.bind("<KeyRelease>", lambda e: self._update_preview())

        ctk.CTkLabel(prev_frame, text="Rewritten result:", font=("Segoe UI", 11), text_color="#2ECC71").pack(anchor="w", padx=15)
        self.result_label = ctk.CTkLabel(
            prev_frame,
            text="",
            font=("Segoe UI", 13, "bold"),
            text_color="#3498DB",
            anchor="w",
            wraplength=580,
            justify="left",
        )
        self.result_label.pack(fill="x", padx=15, pady=(2, 12))

        # Bottom buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(5, 0))

        ctk.CTkButton(
            btn_frame,
            text="💾 Save & Apply Rules",
            font=("Segoe UI", 13, "bold"),
            fg_color="#28a745",
            hover_color="#218838",
            width=180,
            height=36,
            command=self._save,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text="Reset to Defaults",
            font=("Segoe UI", 12),
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=140,
            height=36,
            command=self._reset_defaults,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Close",
            font=("Segoe UI", 12),
            fg_color="#343a40",
            hover_color="#23272b",
            width=100,
            height=36,
            command=self.destroy,
        ).pack(side="right")

        self._update_preview()

    def _get_current_rules(self):
        return {
            "remove_emojis": self.emoji_var.get(),
            "remove_hashtags": self.hashtag_var.get(),
            "remove_mentions": self.mention_var.get(),
            "remove_resolution_tags": self.tags_var.get(),
            "clean_separators": self.sep_var.get(),
            "custom_replacements": self.rules.get("custom_replacements", {}),
        }

    def _update_preview(self):
        dirty = self.test_entry.get()
        rules = self._get_current_rules()
        clean = rewrite_title(dirty, rules)
        self.result_label.configure(text=f"👉  {clean}")

    def _reset_defaults(self):
        self.emoji_var.set(True)
        self.hashtag_var.set(True)
        self.mention_var.set(True)
        self.tags_var.set(True)
        self.sep_var.set(True)
        self._update_preview()

    def _save(self):
        new_rules = self._get_current_rules()
        save_rules(new_rules)
        if hasattr(self.parent, "_update_status"):
            self.parent._update_status("✅ Title Rewrite Rules saved successfully!")
        self.destroy()


class ScheduleDialog(ctk.CTkToplevel):
    """Dialog for scheduling single, batch, playlist, or channel downloads."""

    def __init__(self, parent, scheduler, target_name="", target_type="direct", target_data=None, on_scheduled=None):
        super().__init__(parent)
        self.title("⏰ Schedule Download")
        self.geometry("560x520")
        self.resizable(False, False)

        self.parent = parent
        self.scheduler = scheduler
        self.target_name = target_name
        self.target_type = target_type
        self.target_data = target_data or {}
        self.on_scheduled = on_scheduled

        self.after(100, self.lift)
        self.after(150, self.focus_force)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Header
        ctk.CTkLabel(
            container,
            text="⏰ Schedule Download",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            container,
            text=f"Target: {self.target_name or 'Current Download'}",
            font=("Segoe UI", 12),
            text_color="#3498DB",
        ).pack(anchor="w", pady=(0, 15))

        # Schedule Name
        ctk.CTkLabel(container, text="Task Name / Label:", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 4))
        self.name_entry = ctk.CTkEntry(container, height=34, font=("Segoe UI", 12))
        default_label = f"Schedule - {self.target_name}" if self.target_name else "Scheduled Download"
        self.name_entry.insert(0, default_label[:50])
        self.name_entry.pack(fill="x", pady=(0, 15))

        # Quick Presets Frame
        presets_box = ctk.CTkFrame(container)
        presets_box.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(presets_box, text="⚡ Quick Presets:", font=("Segoe UI", 11, "bold"), text_color="gray").pack(anchor="w", padx=12, pady=(8, 4))
        btn_row = ctk.CTkFrame(presets_box, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(
            btn_row, text="+15 Mins", width=80, height=28,
            command=lambda: self._set_preset(minutes=15)
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row, text="+1 Hour", width=80, height=28,
            command=lambda: self._set_preset(hours=1)
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row, text="Tonight 23:00", width=105, height=28,
            command=lambda: self._set_specific_time(23, 0)
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row, text="Tomorrow 02:00 AM", width=135, height=28,
            command=lambda: self._set_specific_time(2, 0, days=1)
        ).pack(side="left", padx=4)

        # Date & Time Pickers
        dt_frame = ctk.CTkFrame(container)
        dt_frame.pack(fill="x", pady=(0, 15))

        # Row 1: Date
        ctk.CTkLabel(dt_frame, text="Date (YYYY-MM-DD):", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.date_entry = ctk.CTkEntry(dt_frame, width=160, height=32)
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.date_entry.insert(0, today_str)
        self.date_entry.grid(row=0, column=1, sticky="w", padx=10, pady=(12, 6))
        self.date_entry.bind("<KeyRelease>", lambda e: self._update_summary())

        # Row 2: Time
        ctk.CTkLabel(dt_frame, text="Time (Hour : Minute):", font=("Segoe UI", 12, "bold")).grid(row=1, column=0, sticky="w", padx=12, pady=(6, 12))
        time_inner = ctk.CTkFrame(dt_frame, fg_color="transparent")
        time_inner.grid(row=1, column=1, sticky="w", padx=10, pady=(6, 12))

        now_plus_10 = datetime.now() + timedelta(minutes=10)
        self.hour_var = ctk.StringVar(value=f"{now_plus_10.hour:02d}")
        hours = [f"{h:02d}" for h in range(24)]
        self.hour_menu = ctk.CTkOptionMenu(time_inner, variable=self.hour_var, values=hours, width=70, command=lambda v: self._update_summary())
        self.hour_menu.pack(side="left")

        ctk.CTkLabel(time_inner, text=":", font=("Segoe UI", 16, "bold")).pack(side="left", padx=6)

        self.min_var = ctk.StringVar(value=f"{now_plus_10.minute:02d}")
        mins = [f"{m:02d}" for m in range(0, 60, 5)]
        if self.min_var.get() not in mins:
            mins.insert(0, self.min_var.get())
        self.min_menu = ctk.CTkOptionMenu(time_inner, variable=self.min_var, values=mins, width=70, command=lambda v: self._update_summary())
        self.min_menu.pack(side="left")

        # Summary box
        self.summary_label = ctk.CTkLabel(
            container,
            text="",
            font=("Segoe UI", 13, "bold"),
            text_color="#F39C12",
        )
        self.summary_label.pack(anchor="w", pady=(0, 15))
        self._update_summary()

        # Bottom Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x")

        ctk.CTkButton(
            btn_box,
            text="⏰ Confirm & Schedule",
            font=("Segoe UI", 13, "bold"),
            fg_color="#1F6AA5",
            hover_color="#144870",
            width=200,
            height=38,
            command=self._confirm,
        ).pack(side="left")

        ctk.CTkButton(
            btn_box,
            text="Cancel",
            font=("Segoe UI", 12),
            fg_color="#343a40",
            hover_color="#23272b",
            width=100,
            height=38,
            command=self.destroy,
        ).pack(side="right")

    def _set_preset(self, minutes=0, hours=0):
        target = datetime.now() + timedelta(minutes=minutes, hours=hours)
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, target.strftime("%Y-%m-%d"))
        self.hour_var.set(f"{target.hour:02d}")
        self.min_var.set(f"{target.minute:02d}")
        self._update_summary()

    def _set_specific_time(self, hour, minute, days=0):
        target = datetime.now() + timedelta(days=days)
        target = target.replace(hour=hour, minute=minute, second=0)
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, target.strftime("%Y-%m-%d"))
        self.hour_var.set(f"{target.hour:02d}")
        self.min_var.set(f"{target.minute:02d}")
        self._update_summary()

    def _get_target_datetime_str(self):
        d_str = self.date_entry.get().strip()
        h_str = self.hour_var.get()
        m_str = self.min_var.get()
        return f"{d_str} {h_str}:{m_str}:00"

    def _update_summary(self):
        dt_str = self._get_target_datetime_str()
        try:
            target = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            diff = target - now
            if diff.total_seconds() <= 0:
                self.summary_label.configure(text="⚠️ Selected time is in the past! Please pick a future time.", text_color="#dc3545")
            else:
                total_sec = int(diff.total_seconds())
                hours, remainder = divmod(total_sec, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                self.summary_label.configure(text=f"⏳ Will start on {dt_str} (in ~{time_str})", text_color="#2ECC71")
        except Exception:
            self.summary_label.configure(text="⚠️ Invalid date format. Use YYYY-MM-DD", text_color="#dc3545")

    def _confirm(self):
        dt_str = self._get_target_datetime_str()
        try:
            target = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            if target <= datetime.now():
                messagebox.showerror("Error", "Please select a date and time in the future.")
                return
        except Exception:
            messagebox.showerror("Error", "Invalid Date or Time format.")
            return

        name = self.name_entry.get().strip() or "Scheduled Download"
        self.scheduler.add(
            name=name,
            job_type=self.target_type,
            target_data=self.target_data,
            run_at_str=dt_str,
        )

        if hasattr(self.parent, "_update_status"):
            self.parent._update_status(f"⏰ Scheduled: '{name}' at {dt_str}")

        if self.on_scheduled:
            self.on_scheduled()

        self.destroy()


class SaveBatchDialog(ctk.CTkToplevel):
    """Dialog for creating and saving a download batch."""

    def __init__(self, parent, batch_manager, default_data=None, on_saved=None):
        super().__init__(parent)
        self.title("💾 Save as Download Batch")
        self.geometry("600x560")
        self.resizable(False, False)

        self.parent = parent
        self.batch_manager = batch_manager
        self.data = default_data or {}
        self.on_saved = on_saved

        self.after(100, self.lift)
        self.after(150, self.focus_force)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Header
        ctk.CTkLabel(
            container,
            text="💾 Save Download Batch",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            container,
            text="Save this channel, playlist, or video configuration as a reusable batch.",
            font=("Segoe UI", 12),
            text_color="gray",
        ).pack(anchor="w", pady=(0, 15))

        form = ctk.CTkFrame(container)
        form.pack(fill="both", expand=True, pady=(0, 15), padx=5)

        # 1. Batch Name
        ctk.CTkLabel(form, text="Batch Name:", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=8)
        self.name_entry = ctk.CTkEntry(form, width=380, height=32)
        default_name = self.data.get("name") or self.data.get("subfolder") or "My Download Batch"
        self.name_entry.insert(0, default_name[:60])
        self.name_entry.grid(row=0, column=1, sticky="w", padx=10, pady=8)

        # 2. Type
        ctk.CTkLabel(form, text="Type:", font=("Segoe UI", 12, "bold")).grid(row=1, column=0, sticky="w", padx=12, pady=8)
        self.type_var = ctk.StringVar(value=self.data.get("type", "channel"))
        ctk.CTkOptionMenu(form, variable=self.type_var, values=["single", "playlist", "channel"], width=180).grid(row=1, column=1, sticky="w", padx=10, pady=8)

        # 3. URL
        ctk.CTkLabel(form, text="YouTube URL:", font=("Segoe UI", 12, "bold")).grid(row=2, column=0, sticky="w", padx=12, pady=8)
        self.url_entry = ctk.CTkEntry(form, width=380, height=32)
        self.url_entry.insert(0, self.data.get("url", ""))
        self.url_entry.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        # 4. Quality & Format
        ctk.CTkLabel(form, text="Quality / Format:", font=("Segoe UI", 12, "bold")).grid(row=3, column=0, sticky="w", padx=12, pady=8)
        qf_row = ctk.CTkFrame(form, fg_color="transparent")
        qf_row.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        self.quality_var = ctk.StringVar(value=self.data.get("quality", "Best Quality"))
        ctk.CTkOptionMenu(qf_row, variable=self.quality_var, values=list(QUALITY_OPTIONS.keys()), width=200).pack(side="left")

        self.format_var = ctk.StringVar(value=self.data.get("format", "mp4"))
        ctk.CTkOptionMenu(qf_row, variable=self.format_var, values=VIDEO_FORMATS + AUDIO_FORMATS, width=90).pack(side="left", padx=8)

        # 5. Naming Scheme
        ctk.CTkLabel(form, text="Naming Scheme:", font=("Segoe UI", 12, "bold")).grid(row=4, column=0, sticky="w", padx=12, pady=8)
        self.naming_var = ctk.StringVar(value=self.data.get("naming_scheme", "Numbered + Rewrite Title (01 - Cleaned)"))
        ctk.CTkOptionMenu(form, variable=self.naming_var, values=list(NAMING_SCHEMES.keys()), width=320).grid(row=4, column=1, sticky="w", padx=10, pady=8)

        # 6. Custom Prefix
        ctk.CTkLabel(form, text="Custom Prefix:", font=("Segoe UI", 12, "bold")).grid(row=5, column=0, sticky="w", padx=12, pady=8)
        self.prefix_entry = ctk.CTkEntry(form, width=220, height=32)
        self.prefix_entry.insert(0, self.data.get("custom_prefix", ""))
        self.prefix_entry.grid(row=5, column=1, sticky="w", padx=10, pady=8)

        # 7. Selection Range
        ctk.CTkLabel(form, text="Range / Selection:", font=("Segoe UI", 12, "bold")).grid(row=6, column=0, sticky="w", padx=12, pady=8)
        sel_row = ctk.CTkFrame(form, fg_color="transparent")
        sel_row.grid(row=6, column=1, sticky="w", padx=10, pady=8)

        self.sel_var = ctk.StringVar(value=self.data.get("selection_mode", "All Videos"))
        ctk.CTkOptionMenu(sel_row, variable=self.sel_var, values=list(SELECTION_MODES.keys()), width=160).pack(side="left")

        self.sel_val_entry = ctk.CTkEntry(sel_row, width=120, height=32, placeholder_text="e.g. 1-50")
        self.sel_val_entry.insert(0, self.data.get("selection_value", ""))
        self.sel_val_entry.pack(side="left", padx=8)

        # Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x")

        ctk.CTkButton(
            btn_box,
            text="💾 Save Batch",
            font=("Segoe UI", 13, "bold"),
            fg_color="#28a745",
            hover_color="#218838",
            width=180,
            height=38,
            command=self._confirm,
        ).pack(side="left")

        ctk.CTkButton(
            btn_box,
            text="Cancel",
            font=("Segoe UI", 12),
            fg_color="#343a40",
            hover_color="#23272b",
            width=100,
            height=38,
            command=self.destroy,
        ).pack(side="right")

    def _confirm(self):
        name = self.name_entry.get().strip() or "Download Batch"
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a valid YouTube URL.")
            return

        naming_key = self.naming_var.get()
        naming_scheme = NAMING_SCHEMES.get(naming_key, "title")

        sel_key = self.sel_var.get()
        sel_mode = SELECTION_MODES.get(sel_key, "all")

        opts = {
            "quality": self.quality_var.get(),
            "output_format": self.format_var.get(),
            "naming_scheme": naming_scheme,
            "custom_prefix": self.prefix_entry.get().strip(),
            "selection_mode": sel_mode,
            "selection_value": self.sel_val_entry.get().strip(),
            "download_dir": self.data.get("download_dir", DEFAULT_DOWNLOAD_DIR),
            "subfolder": self.data.get("subfolder", ""),
            "embed_thumbnail": self.data.get("embed_thumbnail", False),
            "download_subtitles": self.data.get("download_subtitles", False),
            "subtitle_lang": self.data.get("subtitle_lang", "en"),
        }

        self.batch_manager.add(
            name=name,
            batch_type=self.type_var.get(),
            url=url,
            options=opts,
        )

        if hasattr(self.parent, "_update_status"):
            self.parent._update_status(f"💾 Saved batch: '{name}'")

        if self.on_saved:
            self.on_saved()

        self.destroy()
