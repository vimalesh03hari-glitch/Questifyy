"""
spaced_repetition.py
A simple 5-box Leitner system so "daily flashcards" actually means something:
- Box 1: review every day
- Box 2: every 2 days
- Box 3: every 4 days
- Box 4: every 7 days
- Box 5: every 14 days (mastered, rarely shown)

Correct answer -> move up a box (harder to see again soon).
Wrong answer   -> reset to box 1 (see it again tomorrow).
"""

from datetime import datetime, timedelta

BOX_INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}


def _today():
    return datetime.now().date()


def initialize_card(card: dict) -> dict:
    if not card.get("next_due"):
        card["box"] = card.get("box", 1)
        card["next_due"] = _today().isoformat()
    return card


def get_due_cards(cards: list[dict]) -> list[dict]:
    today = _today()
    due = []
    for c in cards:
        initialize_card(c)
        due_date = datetime.fromisoformat(c["next_due"]).date()
        if due_date <= today:
            due.append(c)
    return due


def review_card(card: dict, correct: bool) -> dict:
    if correct:
        card["box"] = min(card.get("box", 1) + 1, 5)
    else:
        card["box"] = 1
    interval = BOX_INTERVAL_DAYS[card["box"]]
    card["next_due"] = (_today() + timedelta(days=interval)).isoformat()
    card["last_reviewed"] = _today().isoformat()
    return card


def mastery_stats(cards: list[dict]) -> dict:
    if not cards:
        return {"total": 0, "mastered": 0, "learning": 0, "new": 0}
    mastered = sum(1 for c in cards if c.get("box", 1) >= 4)
    new = sum(1 for c in cards if c.get("box", 1) == 1)
    learning = len(cards) - mastered - new
    return {"total": len(cards), "mastered": mastered, "learning": learning, "new": new}
