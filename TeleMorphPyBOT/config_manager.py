import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigManager:
    def __init__(self, config_dir="config"):
        load_dotenv()
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self._init_defaults()

    @property
    def telegram_token(self) -> str:
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            raise ValueError("TELEGRAM_TOKEN not set in .env")
        return token

    def get_gemini_api_key(self) -> str:
        settings = self.get_settings()
        key = settings.get('gemini_api_key', '').strip()
        if key:
            return key
        env_key = os.getenv('GEMINI_API_KEY')
        if env_key:
            return env_key
        raise ValueError("GEMINI_API_KEY not set in settings.json")

    def _init_defaults(self):
        defaults = {
            "channels.json": {"channels": ["durov"]},
            "target_channel.json": {"target": ""},
            "stopwords.json": {
                "stopwords": [
                    "", ""
                ]
            },
            "settings.json": {
                "parse_interval": 60,
                "log_level": "INFO",
                "gemini_model": "gemini-3.1-flash-lite",
                "max_tokens": 4000,
                "temperature": 0.7,
                "gemini_api_key": "" 
            },
            "admins.json": {"admins": []},
            "prompt.txt": "Hello.This is default prompt"
        }
        for filename, default_content in defaults.items():
            file_path = self.config_dir / filename
            if not file_path.exists():
                self._write_file(file_path, default_content)
                logger.info(f"Created default config: {filename}")
            else:
                if filename.endswith(".json"):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning(f"Config {filename} corrupted, recreating.")
                        self._write_file(file_path, default_content)
                elif filename == "prompt.txt":
                    if file_path.stat().st_size == 0:
                        self._write_file(file_path, default_content)

    def _write_file(self, path, content):
        if path.suffix == ".json":
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

    def _read_json(self, filename):
        file_path = self.config_dir / filename
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, ValueError):
            logger.warning(f"Error reading {filename}, recreating defaults.")
            self._init_defaults()
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)

    # ---------- METHODS FOR WORKING WITH CONFIGURES ----------
    def get_channels(self):
        data = self._read_json("channels.json")
        if isinstance(data, list):
            return data
        return data.get("channels", [])

    def save_channels(self, channels):
        file_path = self.config_dir / "channels.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"channels": channels}, f, indent=2, ensure_ascii=False)

    def get_target_channel(self):
        data = self._read_json("target_channel.json")
        return data.get("target", "")

    def save_target_channel(self, target):
        file_path = self.config_dir / "target_channel.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"target": target}, f, indent=2, ensure_ascii=False)

    def get_prompt(self):
        file_path = self.config_dir / "prompt.txt"
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            self._init_defaults()
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

    def save_prompt(self, prompt):
        file_path = self.config_dir / "prompt.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt)

    def get_stopwords(self):
        data = self._read_json("stopwords.json")
        return data.get("stopwords", [])

    def save_stopwords(self, stopwords):
        file_path = self.config_dir / "stopwords.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"stopwords": stopwords}, f, indent=2, ensure_ascii=False)

    def get_settings(self):
        data = self._read_json("settings.json")
        return data

    def save_settings(self, settings):
        file_path = self.config_dir / "settings.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

    def get_admins(self):
        data = self._read_json("admins.json")
        return data.get("admins", [])

    def save_admins(self, admins):
        file_path = self.config_dir / "admins.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"admins": admins}, f, indent=2, ensure_ascii=False)

    def reload_all(self):
        logger.info("All configs reloaded")
        return True
