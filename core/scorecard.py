"""
scorecard.py
Keeps a running history of quiz results so the student gets a scorecard
showing exactly which topics need more work, plus a trend over time — and,
when GEMINI_API_KEY is configured, personalized revision recommendations
for each weak topic instead of just a generic "practice more" message.
"""

from pydantic import BaseModel

from . import storage
from . import ai_client


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


# --------------------------------------------------------------------------
# Gemini-powered personalized revision recommendations
# --------------------------------------------------------------------------

class _AIRecommendation(BaseModel):
    topic: str
    recommendation: str


def generate_ai_recommendations(weak: list) -> dict:
    """
    weak: [{"topic": ..., "accuracy": ..., "attempts": ...}, ...]
    Returns {topic: recommendation_text}. Raises ai_client.AIError on any
    failure — callers should catch this and fall back to fallback_recommendation().
    """
    if not weak:
        return {}

    topic_lines = "\n".join(
        f"- {t['topic']}: {t['accuracy']}% accuracy over {t['attempts']} question attempts"
        for t in weak
    )
    prompt = (
        "A student is underperforming on these topics based on quiz results:\n"
        f"{topic_lines}\n\n"
        "For EACH topic listed, write one short, specific, encouraging revision tip "
        "(1-2 sentences) telling them exactly what to do next — e.g. what concept to "
        "re-review, or what kind of practice would help. Be concrete, not generic."
    )
    recs = ai_client.generate_structured(prompt, response_schema=list[_AIRecommendation])
    result = {
        r["topic"]: r["recommendation"]
        for r in (recs or [])
        if r.get("topic") and r.get("recommendation")
    }
    if not result:
        raise ai_client.AIError("Gemini didn't return usable recommendations.")
    return result


def fallback_recommendation(topic: str) -> str:
    return (f"Revisit your flashcards for **{topic}** daily and redo the practice "
            f"questions until your accuracy climbs above 70%"
           )
