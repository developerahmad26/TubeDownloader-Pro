"""Scheduling System for automated downloads of Single Videos, Playlists, Channels, and Saved Batches.
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime
from config import SCHEDULES_FILE


class DownloadScheduler:
    """Manages scheduled download jobs with persistent storage and background execution."""

    def __init__(self, file_path=SCHEDULES_FILE, runner_callback=None):
        self.file_path = file_path
        self.runner_callback = runner_callback  # function(job) -> None
        self._is_busy = False
        self._running = True
        self._ensure_file()
        self._worker_thread = threading.Thread(target=self._loop, daemon=True)
        self._worker_thread.start()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=4)
            except Exception:
                pass

    def get_all(self):
        """Get all scheduled jobs."""
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def get(self, job_id):
        """Get a single scheduled job by ID."""
        for j in self.get_all():
            if j.get("id") == job_id:
                return j
        return None

    def save_all(self, jobs):
        """Save jobs to schedules.json."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

    def add(self, name, job_type, target_data, run_at_str, repeat_daily=False):
        """Add a new scheduled job.

        Args:
            name: Human-friendly name (e.g., 'Shiv Bhai Vlogs Night Download')
            job_type: 'batch' (saved batch id) or 'direct' (raw options)
            target_data: Dict with url/batch_id and download options
            run_at_str: Scheduled time formatted as 'YYYY-MM-DD HH:MM:SS'
            repeat_daily: Whether to repeat this job automatically every 24 hours
        """
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
        """Delete a job."""
        jobs = [j for j in self.get_all() if j.get("id") != job_id]
        return self.save_all(jobs)

    def cancel(self, job_id):
        """Cancel a pending job."""
        jobs = self.get_all()
        for j in jobs:
            if j.get("id") == job_id and j.get("status") == "Pending":
                j["status"] = "Cancelled"
                self.save_all(jobs)
                return True
        return False

    def mark_status(self, job_id, status, log_msg=""):
        """Update job status and log message, rescheduling if repeat_daily is True."""
        from datetime import timedelta
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
                return "Due now"
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

    def _loop(self):
        """Background thread monitoring schedules."""
        while self._running:
            time.sleep(3)
            try:
                if self._is_busy:
                    continue  # Wait until current download engine is free

                now = datetime.now()
                jobs = self.get_all()
                pending = [
                    j for j in jobs if j.get("status") == "Pending"
                ]

                # Find any job whose time has arrived
                for job in pending:
                    run_at_str = job.get("run_at", "")
                    try:
                        target = datetime.strptime(run_at_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        continue

                    if now >= target:
                        # Trigger this job
                        self.mark_status(job["id"], "Running", "Started by scheduler")
                        if self.runner_callback:
                            try:
                                self.runner_callback(job)
                            except Exception as e:
                                self.mark_status(job["id"], "Failed", f"Error: {e}")
                        break  # Run one at a time
            except Exception:
                pass
