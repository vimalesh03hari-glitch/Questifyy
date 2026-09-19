"""
pomodoro.py
Core Pomodoro logic, kept UI-agnostic so it can be driven by Streamlit (see app.py)
or a plain CLI. Tracks sessions and tells the student exactly when their next
study session should start.
"""

from datetime import datetime, timedelta

DEFAULT_WORK_MIN = 25
DEFAULT_BREAK_MIN = 5
DEFAULT_LONG_BREAK_MIN = 15
SESSIONS_BEFORE_LONG_BREAK = 4


def start_session(work_minutes: int = DEFAULT_WORK_MIN):
    start = datetime.now()
    return {
        "start_time": start.isoformat(timespec="seconds"),
        "work_minutes": work_minutes,
        "end_time": (start + timedelta(minutes=work_minutes)).isoformat(timespec="seconds"),
    }


def next_break_length(completed_sessions: int, break_minutes: int = DEFAULT_BREAK_MIN,
                       long_break_minutes: int = DEFAULT_LONG_BREAK_MIN) -> int:
    if completed_sessions > 0 and completed_sessions % SESSIONS_BEFORE_LONG_BREAK == 0:
        return long_break_minutes
    return break_minutes


def compute_next_session_reminder(session_end: datetime, completed_sessions: int,
                                   break_minutes: int = DEFAULT_BREAK_MIN,
                                   long_break_minutes: int = DEFAULT_LONG_BREAK_MIN):
    """Given when the current work block ends, return the datetime the NEXT
    study session should start (i.e. after the appropriate break)."""
    brk = next_break_length(completed_sessions, break_minutes, long_break_minutes)
    return session_end + timedelta(minutes=brk), brk


def seconds_remaining(end_time_iso: str) -> int:
    end_time = datetime.fromisoformat(end_time_iso)
    remaining = (end_time - datetime.now()).total_seconds()
    return max(0, int(remaining))


def format_mmss(total_seconds: int) -> str:
    m, s = divmod(total_seconds, 60)
    return f"{m:02d}:{s:02d}"
