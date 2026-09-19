"""
quiz_generator.py
Builds the "weekly practice test". Two paths, same output shape
({id, topic, question, options, correct_answer}), so score_quiz() and the UI
work identically either way:

  - generate_quiz_with_ai() -> Gemini writes the MCQs + correct answers
    directly from the notes (used when GEMINI_API_KEY is configured).
  - generate_quiz() -> offline generator built from the flashcard bank
    (distractors pulled from other cards' answers). Always works, used as a
    fallback if Gemini is unavailable, errors out, or no notes text is
    stored yet.
"""

import random
import uuid

from pydantic import BaseModel

from . import ai_client


# --------------------------------------------------------------------------
# Offline heuristic generator (fallback — built from the flashcard bank)
# --------------------------------------------------------------------------

def generate_quiz(cards: list, num_questions: int = 10, choices_per_question: int = 4):
    if not cards:
        return []

    pool = cards.copy()
    random.shuffle(pool)
    quiz_cards = pool[:num_questions]

    all_answers = [c["answer"] for c in cards]
    quiz = []
    for card in quiz_cards:
        same_topic_answers = [a for c, a in zip(cards, all_answers)
                               if c["topic"] == card["topic"] and a != card["answer"]]
        other_answers = [a for a in all_answers if a != card["answer"] and a not in same_topic_answers]

        distractors = list(dict.fromkeys(same_topic_answers))
        random.shuffle(distractors)
        distractors = distractors[:choices_per_question - 1]

        if len(distractors) < choices_per_question - 1:
            extra = [a for a in other_answers if a not in distractors]
            random.shuffle(extra)
            distractors += extra[: (choices_per_question - 1 - len(distractors))]

        options = distractors + [card["answer"]]
        random.shuffle(options)

        quiz.append({
            "id": card["id"],
            "topic": card["topic"],
            "question": card["question"],
            "options": options,
            "correct_answer": card["answer"],
        })
    return quiz


# --------------------------------------------------------------------------
# Gemini-powered generator
# --------------------------------------------------------------------------

class _AIQuizQuestion(BaseModel):
    topic: str
    question: str
    options: list[str]
    correct_answer: str


def generate_quiz_with_ai(text: str, topic_names: list = None, num_questions: int = 10):
    """
    Asks Gemini to write a multiple-choice practice test directly from the
    notes. Returns the same shape as generate_quiz(). Raises ai_client.AIError
    on any failure — callers should catch this and fall back to generate_quiz().
    """
    if not text or not text.strip():
        raise ai_client.AIError("There's no text to build a quiz from.")

    sent_text, _truncated = ai_client.truncate_for_prompt(text)
    topic_hint = ""
    if topic_names:
        topic_hint = "Make sure the questions cover these topics: " + ", ".join(topic_names) + ".\n"

    prompt = (
        "Create a multiple-choice practice quiz from the study notes below.\n"
        f"{topic_hint}"
        f"Generate exactly {num_questions} questions. Each question must have exactly "
        "4 answer options, with only ONE correct option — the `correct_answer` field "
        "must be copied exactly from one of the `options`. Make the wrong options "
        "plausible (not obviously silly). Tag each question with the topic it tests.\n\n"
        f'NOTES:\n"""\n{sent_text}\n"""'
    )
    raw_qs = ai_client.generate_structured(prompt, response_schema=list[_AIQuizQuestion])

    quiz = []
    for q in (raw_qs or []):
        question_text = str(q.get("question", "")).strip()
        topic = str(q.get("topic", "")).strip() or "General"
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        options = list(dict.fromkeys(options))  # de-dupe, keep order
        correct = str(q.get("correct_answer", "")).strip()

        if not question_text or not correct or len(options) < 2:
            continue
        if correct not in options:
            # Repair: guarantee the stated correct answer is actually selectable.
            options = ([correct] + options)[:4]

        quiz.append({
            "id": str(uuid.uuid4())[:8],
            "topic": topic,
            "question": question_text,
            "options": options,
            "correct_answer": correct,
        })

    if not quiz:
        raise ai_client.AIError("Gemini's quiz questions came back empty or malformed.")
    return quiz


def score_quiz(quiz: list, user_answers: dict) -> dict:
    """user_answers: {question_id: chosen_option}. Returns per-topic + overall scoring."""
    per_topic = {}
    total_correct = 0

    for q in quiz:
        chosen = user_answers.get(q["id"])
        correct = chosen == q["correct_answer"]
        total_correct += int(correct)

        topic_stats = per_topic.setdefault(q["topic"], {"correct": 0, "total": 0})
        topic_stats["total"] += 1
        topic_stats["correct"] += int(correct)

    return {
        "total_questions": len(quiz),
        "total_correct": total_correct,
        "percent": round(100 * total_correct / len(quiz), 1) if quiz else 0,
        "per_topic": per_topic,
    }
