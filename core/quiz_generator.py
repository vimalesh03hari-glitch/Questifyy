"""
quiz_generator.py
Builds a multiple-choice "weekly practice test" out of the flashcard bank.
Distractors are pulled from other cards' answers (same topic first, so wrong
options are plausible rather than random).
"""

import random


def generate_quiz(cards: list[dict], num_questions: int = 10, choices_per_question: int = 4):
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

        distractors = list(dict.fromkeys(same_topic_answers))  # de-dupe, keep order
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


def score_quiz(quiz: list[dict], user_answers: dict) -> dict:
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
