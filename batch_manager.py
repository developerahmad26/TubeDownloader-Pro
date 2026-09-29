"""Batch Manager for saving, managing, and running download batches persistently.
Features:
- Thread-safe operations with RLock
- Atomic write pattern (never leaves empty/corrupt files)
- Automatic recovery from backup if corrupted
"""

import json
import os
import shutil
import threading
import uuid
from datetime import datetime
from config import BATCHES_FILE, DEFAULT_DOWNLOAD_DIR


class BatchManager:
    """Manages persistent download batches with thread-safety and crash resilience."""

    def __init__(self, file_path=BATCHES_FILE):
        self.file_path = file_path
        self._lock = threading.RLock()
        self._ensure_file()

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

            # Maintain a backup of the last known good file
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
        """Get all saved batches safely with auto-recovery."""
        with self._lock:
            if not os.path.exists(self.file_path):
                return []
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception:
                # Attempt recovery from backup file if primary is corrupt
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

    def save_all(self, batches):
        """Save all batches atomically with thread lock."""
        with self._lock:
            return self._atomic_write(batches)

    def get(self, batch_id):
        """Get a single batch by ID."""
        with self._lock:
            for b in self.get_all():
                if b.get("id") == batch_id:
                    return b
            return None

    def add(self, name, batch_type, url, options=None):
        """Add a new download batch safely."""
        with self._lock:
            batches = self.get_all()
            opts = options or {}
            batch = {
                "id": f"batch_{uuid.uuid4().hex[:8]}",
                "name": name or f"Batch {len(batches) + 1}",
                "type": batch_type,  # 'single', 'playlist', 'channel'
                "url": url,
                "quality": opts.get("quality", "Best Quality"),
                "format": opts.get("output_format", "mp4"),
                "naming_scheme": opts.get("naming_scheme", "title"),
                "custom_prefix": opts.get("custom_prefix", ""),
                "selection_mode": opts.get("selection_mode", "all"),
                "selection_value": opts.get("selection_value", ""),
                "download_dir": opts.get("download_dir", DEFAULT_DOWNLOAD_DIR),
                "subfolder": opts.get("subfolder", ""),
                "embed_thumbnail": opts.get("embed_thumbnail", False),
                "download_subtitles": opts.get("download_subtitles", False),
                "subtitle_lang": opts.get("subtitle_lang", "en"),
                "speed_limit": opts.get("speed_limit", None),
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_run": None,
                "status": "Ready",
                "total_items": opts.get("total_items", 0),
            }
            batches.insert(0, batch)  # Newest first
            self.save_all(batches)
            return batch

    def update(self, batch_id, updates):
        """Update fields in an existing batch safely."""
        with self._lock:
            batches = self.get_all()
            for b in batches:
                if b.get("id") == batch_id:
                    b.update(updates)
                    self.save_all(batches)
                    return True
            return False

    def delete(self, batch_id):
        """Delete a batch by ID safely."""
        with self._lock:
            batches = [b for b in self.get_all() if b.get("id") != batch_id]
            return self.save_all(batches)

    def mark_status(self, batch_id, status, last_run=None):
        """Update status of a batch safely."""
        updates = {"status": status}
        if last_run:
            updates["last_run"] = last_run
        return self.update(batch_id, updates)
