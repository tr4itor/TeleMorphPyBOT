import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class HistoryManager:
    def __init__(self, history_file="history.json", max_records=100):
        self.history_file = Path(history_file)
        self.max_records = max_records
        self._ensure_file()

    def _ensure_file(self):
        if not self.history_file.exists():
            self._save_data({"history": []})

    def _load_data(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"history": []}

    def _save_data(self, data):
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_record(self, channel: str, original_post_id: str, original_url: str,
                   published_text: str, tokens_used: int, time_taken: float):
        """Adds a post entry"""
        data = self._load_data()
        record = {
            "timestamp": datetime.now().isoformat(),
            "channel": channel,
            "original_post_id": original_post_id,
            "original_url": original_url,
            "published_text": published_text[:500] + "..." if len(published_text) > 500 else published_text,
            "tokens_used": tokens_used,
            "time_taken": round(time_taken, 2)
        }
        data["history"].insert(0, record)
        # Limit the number of entries
        if len(data["history"]) > self.max_records:
            data["history"] = data["history"][:self.max_records]
        self._save_data(data)

    def get_recent(self, limit=20):
        """Returns the last N records"""
        data = self._load_data()
        return data["history"][:limit]

    def clear(self):
        """Clears history"""
        self._save_data({"history": []})
