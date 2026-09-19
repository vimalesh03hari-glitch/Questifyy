"""
scorecard.py
Keeps a running history of quiz results so the student gets a scorecard showing
exactly which topics need more work, plus an overall trend over time.
"""

from . import storage


def save_quiz_result(quiz_score: dict):
    history = storage.load("results")
    history.append({
        "timestamp": storage.now_iso(),
        "percent": quiz_score["percent"],
        "total_correct": quiz_score["total_correct"],
        "total_questions": quiz_score["total_questions"],
        "per_topic": quiz_score["per_topic"],
    })
    storage.save("results", history)
    return history


def get_history():
    return storage.load("results")


def topic_accuracy_breakdown():
    """Aggregate per-topic accuracy across ALL quiz attempts ever taken."""
    history = get_history()
    agg = {}
    for entry in history:
        for topic, stats in entry.get("per_topic", {}).items():
            a = agg.setdefault(topic, {"correct": 0, "total": 0})
            a["correct"] += stats["correct"]
            a["total"] += stats["total"]

    breakdown = []
    for topic, stats in agg.items():
        pct = round(100 * stats["correct"] / stats["total"], 1) if stats["total"] else 0
        breakdown.append({"topic": topic, "accuracy": pct, "attempts": stats["total"]})

    breakdown.sort(key=lambda x: x["accuracy"])  # weakest first
    return breakdown


def weak_topics(threshold: float = 70.0, limit: int = 5):
    return [b for b in topic_accuracy_breakdown() if b["accuracy"] < threshold][:limit]


def overall_trend():
    history = get_history()
    return [{"timestamp": h["timestamp"], "percent": h["percent"]} for h in history]
