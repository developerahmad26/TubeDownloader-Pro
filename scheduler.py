"""Scheduling System for automated downloads of Single Videos, Playlists, Channels, and Saved Batches.
Features:
- Thread-safe operations with RLock
- Atomic write pattern (never leaves empty/corrupt schedules.json)
- Automatic recovery from backup if corrupted
- Zero race-condition background scheduler loop
"""

import json
import os
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta
from config import SCHEDULES_FILE


class DownloadScheduler:
    """Manages scheduled download jobs with persistent storage and robust background execution."""

    def __init__(self, file_path=SCHEDULES_FILE, runner_callback=None, is_busy_check=None):
        self.file_path = file_path
        self.runner_callback = runner_callback  # function(job) -> None
        self.is_busy_check = is_busy_check  # function() -> bool
        self._is_busy = False
        self._running = True
        self._lock = threading.RLock()
        self._ensure_file()
        self._worker_thread = threading.Thread(target=self._loop, daemon=True)
        self._worker_thread.start()

    def _ensure_file(self):
        with self._lock:
            if not os.path.exists(self.file_path):
                try:
                    self._atomic_write([])
                except Exception:
                    pass

    def _atomic_write(self, data):
        """Write JSON data atomically to prevent corruption on crash or abrupt power off."""
        tmp_path = f"{self.file_path}.tmp"
        bak_path = f"{self.file_path}.bak"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # Maintain backup of last known good file
            if os.path.exists(self.file_path):
                try:
                    shutil.copy2(self.file_path, bak_path)
                except Exception:
                    pass

            os.replace(tmp_path, self.file_path)
            return True
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    def get_all(self):
        """Get all scheduled jobs safely with auto-recovery."""
        with self._lock:
            if not os.path.exists(self.file_path):
                return []
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception:
                bak_path = f"{self.file_path}.bak"
                if os.path.exists(bak_path):
                    try:
                        with open(bak_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                self._atomic_write(data)
                                return data
                    except Exception:
                        pass
                return []

    def get(self, job_id):
        """Get a single scheduled job by ID."""
        with self._lock:
            for j in self.get_all():
                if j.get("id") == job_id:
                    return j
            return None

    def save_all(self, jobs):
        """Save jobs to schedules.json atomically."""
        with self._lock:
            return self._atomic_write(jobs)

    def add(self, name, job_type, target_data, run_at_str, repeat_daily=False):
        """Add a new scheduled job safely."""
        with self._lock:
            jobs = self.get_all()
            is_repeat = repeat_daily or (isinstance(target_data, dict) and target_data.get("repeat_daily", False))
            job = {
                "id": f"sched_{uuid.uuid4().hex[:8]}",
                "name": name or f"Schedule {len(jobs) + 1}",
                "job_type": job_type,
                "target_data": target_data,
                "run_at": run_at_str,
                "repeat_daily": bool(is_repeat),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Pending",  # Pending, Running, Completed, Failed, Cancelled
                "log": "",
            }
            jobs.insert(0, job)
            self.save_all(jobs)
            return job

    def delete(self, job_id):
        """Delete a job safely."""
        with self._lock:
            jobs = [j for j in self.get_all() if j.get("id") != job_id]
            return self.save_all(jobs)

    def cancel(self, job_id):
        """Cancel a pending job safely."""
        with self._lock:
            jobs = self.get_all()
            for j in jobs:
                if j.get("id") == job_id and j.get("status") == "Pending":
                    j["status"] = "Cancelled"
                    self.save_all(jobs)
                    return True
            return False

    def mark_status(self, job_id, status, log_msg=""):
        """Update job status and log message, rescheduling if repeat_daily is True."""
        with self._lock:
            jobs = self.get_all()
            for j in jobs:
                if j.get("id") == job_id:
                    tdata = j.get("target_data", {})
                    is_repeat = j.get("repeat_daily") or (isinstance(tdata, dict) and tdata.get("repeat_daily"))
                    if status == "Completed" and is_repeat:
                        try:
                            cur_target = datetime.strptime(j["run_at"], "%Y-%m-%d %H:%M:%S")
                            next_target = cur_target + timedelta(days=1)
                            j["run_at"] = next_target.strftime("%Y-%m-%d %H:%M:%S")
                            j["status"] = "Pending"
                            j["log"] = f"Finished at {datetime.now().strftime('%H:%M:%S')}. Next run scheduled for {j['run_at']}."
                            self.save_all(jobs)
                            return True
                        except Exception:
                            pass

                    j["status"] = status
                    if log_msg:
                        j["log"] = log_msg
                    self.save_all(jobs)
                    return True
            return False

    def get_countdown(self, run_at_str):
        """Calculate human-readable time remaining until run_at."""
        try:
            target = datetime.strptime(run_at_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            diff = target - now
            if diff.total_seconds() <= 0:
                return "Starting now..."
            total_sec = int(diff.total_seconds())
            hours, remainder = divmod(total_sec, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 24:
                days = hours // 24
                rem_hours = hours % 24
                return f"{days}d {rem_hours}h {minutes}m"
            if hours > 0:
                return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
            return f"{minutes:02d}m {seconds:02d}s"
        except Exception:
            return "--"

    def set_busy(self, busy: bool):
        """Set whether download engine is currently occupied."""
        self._is_busy = busy

    def is_engine_busy(self):
        """Check if download engine is currently active."""
        if callable(self.is_busy_check):
            try:
                return bool(self.is_busy_check())
            except Exception:
                pass
        return bool(self._is_busy)

    def _loop(self):
        """Background thread monitoring schedules (checking every second)."""
        while self._running:
            time.sleep(1)
            try:
                if self.is_engine_busy():
                    continue  # Wait until current download engine is free

                now = datetime.now()
                with self._lock:
                    jobs = self.get_all()
                    pending = [
                        j for j in jobs if j.get("status") == "Pending"
                    ]

                    # Find any job whose time has arrived
                    job_to_run = None
                    for job in pending:
                        run_at_str = job.get("run_at", "")
                        try:
                            target = datetime.strptime(run_at_str, "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            continue

                        if now >= target:
                            job_to_run = job
                            break

                if job_to_run:
                    # Double check engine availability right before trigger
                    if self.is_engine_busy():
                        continue

                    # Trigger this job safely
                    self.mark_status(job_to_run["id"], "Running", f"Started at {now.strftime('%H:%M:%S')}")
                    if self.runner_callback:
                        try:
                            self.runner_callback(job_to_run)
                        except Exception as e:
                            self.mark_status(job_to_run["id"], "Failed", f"Error: {e}")
            except Exception:
                pass
