"""Runtime-mutable config — UI থেকে পরিবর্তনযোগ্য মান।"""
import json
from pathlib import Path

from config import BET_STAKE

_STATE_FILE = Path(__file__).resolve().parent / ".runtime_state.json"


class RuntimeConfig:
    def __init__(self, default_stake):
        loaded = self._load()
        if loaded:
            self._stake = loaded
        else:
            try:
                self._stake = int(default_stake) if default_stake else 15
            except (TypeError, ValueError):
                self._stake = 15
            if self._stake < 1:
                self._stake = 15

    def _load(self):
        try:
            with _STATE_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                s = int(data.get("stake", 0))
                return s if s >= 1 else 0
        except Exception:
            return 0

    def _save(self):
        try:
            with _STATE_FILE.open("w", encoding="utf-8") as f:
                json.dump({"stake": self._stake}, f)
        except Exception:
            pass

    @property
    def stake(self) -> int:
        return self._stake

    def set_stake(self, s) -> int:
        s = int(s)
        if s < 1:
            raise ValueError("stake must be >= 1")
        if s > 1_000_000:
            raise ValueError("stake too large (max 1,000,000)")
        self._stake = s
        self._save()
        return s


runtime = RuntimeConfig(BET_STAKE)