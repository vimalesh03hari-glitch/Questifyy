"""
storage.py
Lightweight JSON-based persistence so the whole app runs with zero database setup.
Everything lives in /data as .json files.
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

FILES = {
    "notes": "notes.json",
    "cards": "flashcards.json",
    "results": "quiz_results.json",
    "sessions": "pomodoro_sessions.json",
}


def _path(key):
    return os.path.join(DATA_DIR, FILES[key])


def load(key):
    path = _path(key)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save(key, data):
    path = _path(key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")
