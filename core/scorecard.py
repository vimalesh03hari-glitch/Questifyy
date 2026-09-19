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
            f"questions until your accuracy climbs above 70%.")
