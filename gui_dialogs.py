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

    MODE_LABELS = {
        "✨ Smart Rephrase & Restructure (Real Rewriting)": "smart_rephrase",
        "💥 Add Dramatic Hook (MUST WATCH, SHOCKING)": "hook",
        "🔄 Reverse / Reorder Clauses": "reorder",
        "🤖 AI Rephrase (Google Gemini API)": "ai_gemini",
        "🧹 Clean Only (No Wording Changes)": "clean_only",
    }
    MODE_KEYS = {v: k for k, v in MODE_LABELS.items()}

    def __init__(self, parent):
        super().__init__(parent)
        self.title("⚙️ Title Rewriting Engine & Live Preview")
        self.geometry("680x640")
        self.resizable(False, False)
        self.rules = load_rules()
        self.parent = parent

        self.after(100, self.lift)
        self.after(150, self.focus_force)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        self.configure(fg_color="#0b0e14")
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Header Hero Card
        header_card = ctk.CTkFrame(container, fg_color="#181329", corner_radius=10, border_width=1, border_color="#3d2d5e")
        header_card.pack(fill="x", pady=(0, 10))

        h_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        h_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            h_inner,
            text="⚙️ Title Rewriting Engine",
            font=("Segoe UI", 18, "bold"), text_color="#FFFFFF"
        ).pack(anchor="w")

        ctk.CTkLabel(
            h_inner,
            text="Choose how video titles are rephrased, transformed, and organized automatically.",
            font=("Segoe UI", 11),
            text_color="#94a3b8",
        ).pack(anchor="w", pady=(2, 0))

        # 1. Rewrite Mode Selection Box
        mode_box = ctk.CTkFrame(container, fg_color="#121624", corner_radius=8, border_width=1, border_color="#1f293d")
        mode_box.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(mode_box, text="Rewrite Style / Engine:", font=("Segoe UI", 12, "bold"), text_color="#38bdf8").pack(anchor="w", padx=15, pady=(10, 4))
        current_mode_key = self.rules.get("rewrite_mode", "smart_rephrase")
        default_label = self.MODE_KEYS.get(current_mode_key, "✨ Smart Rephrase & Restructure (Real Rewriting)")

        self.mode_var = ctk.StringVar(value=default_label)
        self.mode_menu = ctk.CTkOptionMenu(
            mode_box,
            variable=self.mode_var,
            values=list(self.MODE_LABELS.keys()),
            width=450, corner_radius=6,
            command=self._on_mode_change,
        )
        self.mode_menu.pack(anchor="w", padx=15, pady=(0, 10))

        # Gemini API Key Entry (Collapsible)
        self.ai_key_frame = ctk.CTkFrame(mode_box, fg_color="transparent")
        ctk.CTkLabel(self.ai_key_frame, text="Gemini API Key (Free from aistudio.google.com):", font=("Segoe UI", 11, "bold"), text_color="#c084fc").pack(anchor="w", padx=15)
        self.ai_key_entry = ctk.CTkEntry(self.ai_key_frame, width=450, placeholder_text="AIzaSy...", show="*", fg_color="#090d16", border_color="#1e2638")
        self.ai_key_entry.insert(0, self.rules.get("gemini_api_key", ""))
        self.ai_key_entry.pack(anchor="w", padx=15, pady=(2, 8))
        self.ai_key_entry.bind("<KeyRelease>", lambda e: self._update_preview())

        if current_mode_key == "ai_gemini":
            self.ai_key_frame.pack(fill="x")

        # 2. Cleaning Flags Frame
        opts_frame = ctk.CTkFrame(container, fg_color="#121624", corner_radius=8, border_width=1, border_color="#1f293d")
        opts_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(opts_frame, text="Pre-Cleaning Options:", font=("Segoe UI", 12, "bold"), text_color="#34d399").pack(anchor="w", padx=15, pady=(8, 2))

        chk_grid = ctk.CTkFrame(opts_frame, fg_color="transparent")
        chk_grid.pack(fill="x", padx=10, pady=(0, 8))

        self.emoji_var = ctk.BooleanVar(value=self.rules.get("remove_emojis", True))
        self.hashtag_var = ctk.BooleanVar(value=self.rules.get("remove_hashtags", True))
        self.mention_var = ctk.BooleanVar(value=self.rules.get("remove_mentions", True))
        self.tags_var = ctk.BooleanVar(value=self.rules.get("remove_resolution_tags", True))
        self.sep_var = ctk.BooleanVar(value=self.rules.get("clean_separators", True))

        ctk.CTkCheckBox(chk_grid, text="Remove Emojis (😱, 🔥, etc.)", variable=self.emoji_var, text_color="#cbd5e1", command=self._update_preview).grid(row=0, column=0, sticky="w", padx=10, pady=4)
        ctk.CTkCheckBox(chk_grid, text="Remove Hashtags (#shorts, #vlog)", variable=self.hashtag_var, text_color="#cbd5e1", command=self._update_preview).grid(row=0, column=1, sticky="w", padx=10, pady=4)
        ctk.CTkCheckBox(chk_grid, text="Remove Mentions (@channel)", variable=self.mention_var, text_color="#cbd5e1", command=self._update_preview).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        ctk.CTkCheckBox(chk_grid, text="Remove Tags ([1080p], Official)", variable=self.tags_var, text_color="#cbd5e1", command=self._update_preview).grid(row=1, column=1, sticky="w", padx=10, pady=4)

        # 3. Live Test & Preview Frame (Illuminated Cyber Dashboard)
        prev_frame = ctk.CTkFrame(container, fg_color="#090e18", corner_radius=8, border_width=1, border_color="#0284c7")
        prev_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(prev_frame, text="🧪 Live Title Rewriting Preview:", font=("Segoe UI", 12, "bold"), text_color="#38bdf8").pack(anchor="w", padx=15, pady=(10, 4))
        ctk.CTkLabel(prev_frame, text="Test Title:", font=("Segoe UI", 11), text_color="#94a3b8").pack(anchor="w", padx=15)
        self.test_entry = ctk.CTkEntry(prev_frame, height=32, font=("Segoe UI", 12), fg_color="#06090e", border_color="#1e2638")
        self.test_entry.insert(0, "Aaj सुबह सुबह Ye Kya Ho Gaya | Vlog #12 #shorts @shiv [1080p] 😱")
        self.test_entry.pack(fill="x", padx=15, pady=(2, 6))
        self.test_entry.bind("<KeyRelease>", lambda e: self._update_preview())

        ctk.CTkLabel(prev_frame, text="Rewritten Output:", font=("Segoe UI", 11, "bold"), text_color="#34d399").pack(anchor="w", padx=15)
        self.result_label = ctk.CTkLabel(
            prev_frame,
            text="",
            font=("Segoe UI", 13, "bold"),
            text_color="#00f0ff",
            anchor="w",
            wraplength=620,
            justify="left",
        )
        self.result_label.pack(fill="x", padx=15, pady=(2, 10))

        # Bottom buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame,
            text="💾 Save & Apply Rules",
            font=("Segoe UI", 12, "bold"),
            fg_color="#059669",
            hover_color="#10b981",
            width=180,
            height=36,
            corner_radius=6,
            command=self._save,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text="🔄 Reset Defaults",
            font=("Segoe UI", 11, "bold"),
            fg_color="#334155",
            hover_color="#475569",
            width=140,
            height=36,
            corner_radius=6,
            command=self._reset_defaults,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Close",
            font=("Segoe UI", 11),
            fg_color="#1e293b",
            hover_color="#334155",
            width=90,
            height=36,
            corner_radius=6,
            command=self.destroy,
        ).pack(side="right")

        self._update_preview()

    def _on_mode_change(self, val):
        mode_code = self.MODE_LABELS.get(val, "smart_rephrase")
        if mode_code == "ai_gemini":
            self.ai_key_frame.pack(fill="x")
        else:
            self.ai_key_frame.pack_forget()
        self._update_preview()

    def _get_current_rules(self):
        mode_code = self.MODE_LABELS.get(self.mode_var.get(), "smart_rephrase")
        return {
            "rewrite_mode": mode_code,
            "hook_style": "Dramatic Hook",
            "gemini_api_key": self.ai_key_entry.get().strip(),
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
        self.mode_var.set("✨ Smart Rephrase & Restructure (Real Rewriting)")
        self.emoji_var.set(True)
        self.hashtag_var.set(True)
        self.mention_var.set(True)
        self.tags_var.set(True)
        self.sep_var.set(True)
        self._on_mode_change(self.mode_var.get())

    def _save(self):
        new_rules = self._get_current_rules()
        save_rules(new_rules)
        if hasattr(self.parent, "_update_status"):
            self.parent._update_status("✅ Title Rewrite Rules saved successfully!")
        self.destroy()


class ScheduleDialog(ctk.CTkToplevel):
    """Easy and robust scheduling dialog with direct time spinners, quick presets, and live countdown."""

    def __init__(self, parent, scheduler, target_name="", target_type="direct", target_data=None, on_scheduled=None):
        super().__init__(parent)
        self.title("⏰ Schedule Download")
        self.geometry("600x560")
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
        self.configure(fg_color="#0b0e14")
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=22, pady=16)

        # Header Hero Card
        header_card = ctk.CTkFrame(container, fg_color="#181329", corner_radius=10, border_width=1, border_color="#3d2d5e")
        header_card.pack(fill="x", pady=(0, 10))

        h_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        h_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(h_inner, text="⏰ Schedule Download", font=("Segoe UI", 18, "bold"), text_color="#FFFFFF").pack(anchor="w")
        ctk.CTkLabel(h_inner, text=f"Target: {self.target_name or 'Current Download'}", font=("Segoe UI", 11), text_color="#c084fc").pack(anchor="w", pady=(2, 0))

        # Task Name
        ctk.CTkLabel(container, text="Task Label / Name:", font=("Segoe UI", 11, "bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.name_entry = ctk.CTkEntry(container, height=32, font=("Segoe UI", 12), fg_color="#090d16", border_color="#1e2638")
        default_label = f"Schedule - {self.target_name}" if self.target_name else "Scheduled Download"
        self.name_entry.insert(0, default_label[:50])
        self.name_entry.pack(fill="x", pady=(0, 10))

        # Quick 1-Click Presets Box
        presets_frame = ctk.CTkFrame(container, fg_color="#121624", corner_radius=8, border_width=1, border_color="#1f293d")
        presets_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(presets_frame, text="⚡ Quick 1-Click Presets:", font=("Segoe UI", 11, "bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(8, 4))
        p_row1 = ctk.CTkFrame(presets_frame, fg_color="transparent")
        p_row1.pack(fill="x", padx=8, pady=(0, 4))

        ctk.CTkButton(p_row1, text="+15 Mins", width=75, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._add_offset(minutes=15)).pack(side="left", padx=3)
        ctk.CTkButton(p_row1, text="+30 Mins", width=75, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._add_offset(minutes=30)).pack(side="left", padx=3)
        ctk.CTkButton(p_row1, text="+1 Hour", width=75, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._add_offset(hours=1)).pack(side="left", padx=3)
        ctk.CTkButton(p_row1, text="+2 Hours", width=75, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._add_offset(hours=2)).pack(side="left", padx=3)
        ctk.CTkButton(p_row1, text="+6 Hours", width=75, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._add_offset(hours=6)).pack(side="left", padx=3)

        p_row2 = ctk.CTkFrame(presets_frame, fg_color="transparent")
        p_row2.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkButton(p_row2, text="Tonight 23:00 (11 PM)", width=135, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._set_clock(23, 0, days=0)).pack(side="left", padx=3)
        ctk.CTkButton(p_row2, text="Midnight 00:00", width=110, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._set_clock(0, 0, days=1)).pack(side="left", padx=3)
        ctk.CTkButton(p_row2, text="Tomorrow 02:00 AM", width=135, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._set_clock(2, 0, days=1)).pack(side="left", padx=3)
        ctk.CTkButton(p_row2, text="Tomorrow 06:00 AM", width=135, height=26, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._set_clock(6, 0, days=1)).pack(side="left", padx=3)

        # Time & Date Spinner Box
        picker_box = ctk.CTkFrame(container, fg_color="#121624", corner_radius=8, border_width=1, border_color="#1f293d")
        picker_box.pack(fill="x", pady=(0, 10))

        # Row: Date buttons & entry
        d_row = ctk.CTkFrame(picker_box, fg_color="transparent")
        d_row.pack(fill="x", padx=12, pady=(10, 6))

        ctk.CTkLabel(d_row, text="Date:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1", width=50).pack(side="left")
        ctk.CTkButton(d_row, text="Today", width=65, height=28, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 11, "bold"), corner_radius=4, command=self._set_today).pack(side="left", padx=3)
        ctk.CTkButton(d_row, text="Tomorrow", width=75, height=28, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 11, "bold"), corner_radius=4, command=self._set_tomorrow).pack(side="left", padx=3)

        self.date_entry = ctk.CTkEntry(d_row, width=120, height=28, fg_color="#090d16", border_color="#1e2638")
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(side="left", padx=(10, 0))
        self.date_entry.bind("<KeyRelease>", lambda e: self._update_summary())

        # Row: Easy Time Adjusters (Hour : Minute)
        t_row = ctk.CTkFrame(picker_box, fg_color="transparent")
        t_row.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(t_row, text="Time:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1", width=50).pack(side="left")

        # Hour Box with +/-
        init_time = datetime.now() + timedelta(minutes=15)
        self.hour_entry = ctk.CTkEntry(t_row, width=45, height=32, font=("Segoe UI", 14, "bold"), justify="center", fg_color="#090d16", border_color="#1e2638")
        self.hour_entry.insert(0, f"{init_time.hour:02d}")
        self.hour_entry.pack(side="left", padx=(0, 2))
        self.hour_entry.bind("<KeyRelease>", lambda e: self._update_summary())

        h_btn_box = ctk.CTkFrame(t_row, fg_color="transparent")
        h_btn_box.pack(side="left", padx=(0, 6))
        ctk.CTkButton(h_btn_box, text="▲", width=22, height=15, font=("Segoe UI", 9), fg_color="#334155", hover_color="#475569", command=lambda: self._step_hour(1)).pack()
        ctk.CTkButton(h_btn_box, text="▼", width=22, height=15, font=("Segoe UI", 9), fg_color="#334155", hover_color="#475569", command=lambda: self._step_hour(-1)).pack()

        ctk.CTkLabel(t_row, text=":", font=("Segoe UI", 18, "bold"), text_color="#cbd5e1").pack(side="left", padx=2)

        # Minute Box with +/-
        self.min_entry = ctk.CTkEntry(t_row, width=45, height=32, font=("Segoe UI", 14, "bold"), justify="center", fg_color="#090d16", border_color="#1e2638")
        self.min_entry.insert(0, f"{init_time.minute:02d}")
        self.min_entry.pack(side="left", padx=(2, 2))
        self.min_entry.bind("<KeyRelease>", lambda e: self._update_summary())

        m_btn_box = ctk.CTkFrame(t_row, fg_color="transparent")
        m_btn_box.pack(side="left", padx=(0, 15))
        ctk.CTkButton(m_btn_box, text="▲", width=22, height=15, font=("Segoe UI", 9), fg_color="#334155", hover_color="#475569", command=lambda: self._step_min(5)).pack()
        ctk.CTkButton(m_btn_box, text="▼", width=22, height=15, font=("Segoe UI", 9), fg_color="#334155", hover_color="#475569", command=lambda: self._step_min(-5)).pack()

        # Quick min step buttons
        ctk.CTkButton(t_row, text="+5m", width=42, height=28, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._step_min(5)).pack(side="left", padx=2)
        ctk.CTkButton(t_row, text="+15m", width=48, height=28, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._step_min(15)).pack(side="left", padx=2)
        ctk.CTkButton(t_row, text="+1h", width=42, height=28, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=lambda: self._step_hour(1)).pack(side="left", padx=2)

        # Recurring check
        self.repeat_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(picker_box, text="🔁 Repeat Daily at this exact time", variable=self.repeat_var, text_color="#cbd5e1").pack(anchor="w", padx=12, pady=(0, 8))

        # Live Countdown Confirmation Card
        self.summary_box = ctk.CTkFrame(container, fg_color="#090e18", corner_radius=8, border_width=1.5, border_color="#7c3aed")
        self.summary_box.pack(fill="x", pady=(0, 12))

        self.summary_label = ctk.CTkLabel(
            self.summary_box, text="", font=("Segoe UI", 13, "bold"), text_color="#00f0ff", padx=14, pady=8
        )
        self.summary_label.pack(anchor="w")
        self._update_summary()

        # Bottom Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x")

        ctk.CTkButton(
            btn_box,
            text="⏰ Confirm & Schedule",
            font=("Segoe UI", 12, "bold"),
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            width=200,
            height=38,
            corner_radius=6,
            command=self._confirm,
        ).pack(side="left")

        ctk.CTkButton(
            btn_box,
            text="Cancel",
            font=("Segoe UI", 11),
            fg_color="#1e293b",
            hover_color="#334155",
            width=90,
            height=38,
            corner_radius=6,
            command=self.destroy,
        ).pack(side="right")

    def _set_today(self):
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._update_summary()

    def _set_tomorrow(self):
        target = datetime.now() + timedelta(days=1)
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, target.strftime("%Y-%m-%d"))
        self._update_summary()

    def _add_offset(self, minutes=0, hours=0):
        target = datetime.now() + timedelta(minutes=minutes, hours=hours)
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, target.strftime("%Y-%m-%d"))
        self.hour_entry.delete(0, "end")
        self.hour_entry.insert(0, f"{target.hour:02d}")
        self.min_entry.delete(0, "end")
        self.min_entry.insert(0, f"{target.minute:02d}")
        self._update_summary()

    def _set_clock(self, hour, minute, days=0):
        target = datetime.now() + timedelta(days=days)
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, target.strftime("%Y-%m-%d"))
        self.hour_entry.delete(0, "end")
        self.hour_entry.insert(0, f"{hour:02d}")
        self.min_entry.delete(0, "end")
        self.min_entry.insert(0, f"{minute:02d}")
        self._update_summary()

    def _step_hour(self, delta):
        try:
            val = int(self.hour_entry.get() or 0)
            new_val = (val + delta) % 24
            self.hour_entry.delete(0, "end")
            self.hour_entry.insert(0, f"{new_val:02d}")
            self._update_summary()
        except Exception:
            pass

    def _step_min(self, delta):
        try:
            val = int(self.min_entry.get() or 0)
            new_val = (val + delta) % 60
            self.min_entry.delete(0, "end")
            self.min_entry.insert(0, f"{new_val:02d}")
            self._update_summary()
        except Exception:
            pass

    def _get_target_datetime_str(self):
        d_str = self.date_entry.get().strip()
        try:
            h = int(self.hour_entry.get().strip() or 0)
            m = int(self.min_entry.get().strip() or 0)
            return f"{d_str} {h:02d}:{m:02d}:00"
        except Exception:
            return f"{d_str} 00:00:00"

    def _update_summary(self):
        dt_str = self._get_target_datetime_str()
        try:
            target = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            diff = target - now
            if diff.total_seconds() <= 0:
                self.summary_label.configure(
                    text="⚠️ Selected time is in the past! Please choose a future time.",
                    text_color="#e74c3c"
                )
            else:
                total_sec = int(diff.total_seconds())
                hours, remainder = divmod(total_sec, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                self.summary_label.configure(
                    text=f"⏳ Will start on {dt_str} (in ~{time_str})",
                    text_color="#2ECC71"
                )
        except Exception:
            self.summary_label.configure(
                text="⚠️ Invalid date format. Use YYYY-MM-DD",
                text_color="#e74c3c"
            )

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
        is_repeat = self.repeat_var.get()
        if is_repeat:
            self.target_data["repeat_daily"] = True

        self.scheduler.add(
            name=name,
            job_type=self.target_type,
            target_data=self.target_data,
            run_at_str=dt_str,
            repeat_daily=is_repeat,
        )

        if hasattr(self.parent, "_update_status"):
            self.parent._update_status(f"⏰ Scheduled: '{name}' for {dt_str}")

        if self.on_scheduled:
            self.on_scheduled()

        self.destroy()


class SaveBatchDialog(ctk.CTkToplevel):
    """Dialog for creating and saving a download batch."""

    def __init__(self, parent, batch_manager, default_data=None, on_saved=None):
        super().__init__(parent)
        self.title("💾 Save as Download Batch")
        self.geometry("620x620")
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
        self.configure(fg_color="#0b0e14")
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Header Hero Card
        header_card = ctk.CTkFrame(container, fg_color="#092019", corner_radius=10, border_width=1, border_color="#059669")
        header_card.pack(fill="x", pady=(0, 10))

        h_inner = ctk.CTkFrame(header_card, fg_color="transparent")
        h_inner.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            h_inner,
            text="💾 Save Download Batch",
            font=("Segoe UI", 18, "bold"), text_color="#FFFFFF"
        ).pack(anchor="w")

        ctk.CTkLabel(
            h_inner,
            text="Save this channel, playlist, or video configuration as a reusable automated batch.",
            font=("Segoe UI", 11),
            text_color="#94a3b8",
        ).pack(anchor="w", pady=(2, 0))

        form = ctk.CTkFrame(container, fg_color="#121624", corner_radius=8, border_width=1, border_color="#1f293d")
        form.pack(fill="both", expand=True, pady=(0, 12), padx=2)

        # 1. Batch Name
        ctk.CTkLabel(form, text="Batch Name:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        self.name_entry = ctk.CTkEntry(form, width=390, height=30, fg_color="#090d16", border_color="#1e2638")
        default_name = self.data.get("name") or self.data.get("subfolder") or "My Download Batch"
        self.name_entry.insert(0, default_name[:60])
        self.name_entry.grid(row=0, column=1, sticky="w", padx=10, pady=6)

        # 2. Type
        ctk.CTkLabel(form, text="Type:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.type_var = ctk.StringVar(value=self.data.get("type", "channel"))
        ctk.CTkOptionMenu(form, variable=self.type_var, values=["single", "playlist", "channel"], width=180, height=28, corner_radius=6).grid(row=1, column=1, sticky="w", padx=10, pady=6)

        # 3. URL
        ctk.CTkLabel(form, text="YouTube URL:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=2, column=0, sticky="w", padx=12, pady=6)
        self.url_entry = ctk.CTkEntry(form, width=390, height=30, fg_color="#090d16", border_color="#1e2638")
        self.url_entry.insert(0, self.data.get("url", ""))
        self.url_entry.grid(row=2, column=1, sticky="w", padx=10, pady=6)

        # 4. Quality & Format
        ctk.CTkLabel(form, text="Quality / Format:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=3, column=0, sticky="w", padx=12, pady=6)
        qf_row = ctk.CTkFrame(form, fg_color="transparent")
        qf_row.grid(row=3, column=1, sticky="w", padx=10, pady=6)

        self.quality_var = ctk.StringVar(value=self.data.get("quality", "Best Quality"))
        ctk.CTkOptionMenu(qf_row, variable=self.quality_var, values=list(QUALITY_OPTIONS.keys()), width=200, height=28, corner_radius=6).pack(side="left")

        self.format_var = ctk.StringVar(value=self.data.get("format", "mp4"))
        ctk.CTkOptionMenu(qf_row, variable=self.format_var, values=VIDEO_FORMATS + AUDIO_FORMATS, width=90, height=28, corner_radius=6).pack(side="left", padx=8)

        # 5. Naming Scheme (Reverse mapped to human label)
        raw_naming = self.data.get("naming_scheme", "title")
        display_naming = "Video Title"
        for k, v in NAMING_SCHEMES.items():
            if v == raw_naming or k == raw_naming:
                display_naming = k
                break

        ctk.CTkLabel(form, text="Naming Scheme:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=4, column=0, sticky="w", padx=12, pady=6)
        self.naming_var = ctk.StringVar(value=display_naming)
        ctk.CTkOptionMenu(form, variable=self.naming_var, values=list(NAMING_SCHEMES.keys()), width=330, height=28, corner_radius=6).grid(row=4, column=1, sticky="w", padx=10, pady=6)

        # 6. Custom Prefix
        ctk.CTkLabel(form, text="Custom Prefix:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=5, column=0, sticky="w", padx=12, pady=6)
        self.prefix_entry = ctk.CTkEntry(form, width=220, height=30, fg_color="#090d16", border_color="#1e2638")
        self.prefix_entry.insert(0, self.data.get("custom_prefix", ""))
        self.prefix_entry.grid(row=5, column=1, sticky="w", padx=10, pady=6)

        # 7. Selection Range (Reverse mapped to human label)
        raw_sel = self.data.get("selection_mode", "all")
        display_sel = "All Videos"
        for k, v in SELECTION_MODES.items():
            if v == raw_sel or k == raw_sel:
                display_sel = k
                break

        ctk.CTkLabel(form, text="Range / Selection:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=6, column=0, sticky="w", padx=12, pady=6)
        sel_row = ctk.CTkFrame(form, fg_color="transparent")
        sel_row.grid(row=6, column=1, sticky="w", padx=10, pady=6)

        self.sel_var = ctk.StringVar(value=display_sel)
        ctk.CTkOptionMenu(sel_row, variable=self.sel_var, values=list(SELECTION_MODES.keys()), width=160, height=28, corner_radius=6).pack(side="left")

        self.sel_val_entry = ctk.CTkEntry(sel_row, width=120, height=28, placeholder_text="e.g. 1-50", fg_color="#090d16", border_color="#1e2638")
        self.sel_val_entry.insert(0, self.data.get("selection_value", ""))
        self.sel_val_entry.pack(side="left", padx=8)

        # 8. Download Directory
        ctk.CTkLabel(form, text="Download Folder:", font=("Segoe UI", 12, "bold"), text_color="#cbd5e1").grid(row=7, column=0, sticky="w", padx=12, pady=6)
        dir_row = ctk.CTkFrame(form, fg_color="transparent")
        dir_row.grid(row=7, column=1, sticky="w", padx=10, pady=6)

        self.dir_entry = ctk.CTkEntry(dir_row, width=285, height=28, fg_color="#090d16", border_color="#1e2638")
        self.dir_entry.insert(0, self.data.get("download_dir", DEFAULT_DOWNLOAD_DIR))
        self.dir_entry.pack(side="left")

        def _browse_dir():
            chosen = filedialog.askdirectory(initialdir=self.dir_entry.get())
            if chosen:
                self.dir_entry.delete(0, "end")
                self.dir_entry.insert(0, chosen)

        ctk.CTkButton(dir_row, text="📁 Browse", width=75, height=28, fg_color="#1e293b", hover_color="#334155", font=("Segoe UI", 10, "bold"), corner_radius=4, command=_browse_dir).pack(side="left", padx=6)

        # 9. Extra checkboxes
        cb_row = ctk.CTkFrame(form, fg_color="transparent")
        cb_row.grid(row=8, column=1, sticky="w", padx=10, pady=6)
        self.thumb_var = ctk.BooleanVar(value=bool(self.data.get("embed_thumbnail", False)))
        ctk.CTkCheckBox(cb_row, text="Embed Thumbnail", variable=self.thumb_var, text_color="#cbd5e1").pack(side="left", padx=(0, 15))
        self.sub_var = ctk.BooleanVar(value=bool(self.data.get("download_subtitles", False)))
        ctk.CTkCheckBox(cb_row, text="Download Subtitles", variable=self.sub_var, text_color="#cbd5e1").pack(side="left")

        # Buttons
        btn_box = ctk.CTkFrame(container, fg_color="transparent")
        btn_box.pack(fill="x")

        ctk.CTkButton(
            btn_box,
            text="💾 Save Batch",
            font=("Segoe UI", 12, "bold"),
            fg_color="#059669",
            hover_color="#10b981",
            width=180,
            height=38,
            corner_radius=6,
            command=self._confirm,
        ).pack(side="left")

        ctk.CTkButton(
            btn_box,
            text="Cancel",
            font=("Segoe UI", 11),
            fg_color="#1e293b",
            hover_color="#334155",
            width=90,
            height=38,
            corner_radius=6,
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

        chosen_dir = self.dir_entry.get().strip() or DEFAULT_DOWNLOAD_DIR

        opts = {
            "quality": self.quality_var.get(),
            "output_format": self.format_var.get(),
            "naming_scheme": naming_scheme,
            "custom_prefix": self.prefix_entry.get().strip(),
            "selection_mode": sel_mode,
            "selection_value": self.sel_val_entry.get().strip(),
            "download_dir": chosen_dir,
            "subfolder": self.data.get("subfolder", ""),
            "embed_thumbnail": self.thumb_var.get(),
            "download_subtitles": self.sub_var.get(),
            "subtitle_lang": self.data.get("subtitle_lang", "en"),
            "speed_limit": self.data.get("speed_limit", None),
        }

        batch_id = self.data.get("id")
        if batch_id:
            updates = {
                "name": name,
                "type": self.type_var.get(),
                "url": url,
                **opts,
            }
            self.batch_manager.update(batch_id, updates)
            if hasattr(self.parent, "_update_status"):
                self.parent._update_status(f"✏️ Updated batch: '{name}'")
        else:
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
