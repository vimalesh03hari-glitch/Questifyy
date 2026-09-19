"""
flashcard_generator.py
Builds ACTIVE RECALL flashcards from notes, instead of letting students just
re-read them.

Two paths, same output shape ({id, topic, question, answer, box, next_due}),
so everything downstream (spaced_repetition, storage) works unchanged either
way:

  - generate_flashcards_with_ai()  -> Gemini writes the questions/answers
    (used when GEMINI_API_KEY is configured). Better quality.
  - generate_all_flashcards() / generate_flashcards_from_topic() -> offline
    regex cloze-deletion. Always works, zero dependencies, used as a
    fallback if Gemini is unavailable or errors out.
"""

import re
import uuid

from pydantic import BaseModel

from .notes_processor import split_sentences
from . import ai_client

DEFINITION_TRIGGERS = [
    r"\bis\b", r"\bare\b", r"\bmeans\b", r"\brefers to\b",
    r"\bdefined as\b", r"\bis called\b", r"\bconsists of\b",
]
TRIGGER_RE = re.compile("|".join(DEFINITION_TRIGGERS), re.IGNORECASE)


# --------------------------------------------------------------------------
# Offline heuristic generator (fallback — no API key required)
# --------------------------------------------------------------------------

def _pick_blank_word(sentence: str):
    match = TRIGGER_RE.search(sentence)
    if match:
        after = sentence[match.end():].strip(" .")
        candidate = after.split(",")[0].split(" and ")[0]
        words = candidate.split()
        if words:
            return " ".join(words[:4]).strip(" .")

    capitalized = [w.strip(".,;:") for w in sentence.split()
                   if w[:1].isupper() and w.lower() not in ("the", "a", "an")]
    if capitalized:
        return max(capitalized, key=len)

    words = [w.strip(".,;:") for w in sentence.split() if len(w) > 5]
    return max(words, key=len) if words else None


def generate_flashcards_from_topic(topic: str, content: str, max_cards: int = 6):
    sentences = split_sentences(content)
    sentences.sort(key=lambda s: 0 if TRIGGER_RE.search(s) else 1)

    cards = []
    for sentence in sentences:
        if len(cards) >= max_cards:
            break
        blank = _pick_blank_word(sentence)
        if not blank or blank.lower() not in sentence.lower():
            continue
        pattern = re.compile(re.escape(blank), re.IGNORECASE)
        question = pattern.sub("______", sentence, count=1)
        if question == sentence:
            continue
        cards.append({
            "id": str(uuid.uuid4())[:8],
            "topic": topic,
            "question": question,
            "answer": blank,
            "box": 1,
            "next_due": None,
        })
    return cards


def generate_all_flashcards(topics: list, max_cards_per_topic: int = 6):
    all_cards = []
    for t in topics:
        all_cards.extend(generate_flashcards_from_topic(t["topic"], t["content"], max_cards_per_topic))
    return all_cards


# --------------------------------------------------------------------------
# Gemini-powered generator
# --------------------------------------------------------------------------

class _AIFlashcard(BaseModel):
    topic: str
    question: str
    answer: str


def generate_flashcards_with_ai(text: str, topic_names: list = None,num_cards: int=15):
    """
    Asks Gemini to write active-recall flashcards directly from the notes.
    Returns the same shape as the offline generator. Raises ai_client.AIError
    on any failure — callers should catch this and fall back to the offline
    generator.
    """
    if not text or not text.strip():
        raise ai_client.AIError("There's no text to generate flashcards from.")

    sent_text, _truncated = ai_client.truncate_for_prompt(text)
    topic_hint = ""
    if topic_names:
        topic_hint = "Tag each flashcard with one of these exact topic names: " + ", ".join(topic_names) + ".\n"

    prompt = (
        "You are building ACTIVE RECALL flashcards for a student from their notes.\n"
        "Each flashcard needs a clear, specific QUESTION that tests real understanding "
        "(not trivial 'what is X' recall) and a concise ANSWER — a short phrase or one "
        "sentence, never a full paragraph. Avoid yes/no questions.\n"
        f"{topic_hint}"
        f"Generate about {num_cards} flashcards, spread across the different topics "
        "covered in the notes below.\n\n"
        f'NOTES:\n"""\n{sent_text}\n"""'
    )
    raw_cards = ai_client.generate_structured(prompt, response_schema=list[_AIFlashcard])

    cards = []
    for c in (raw_cards or []):
        question = str(c.get("question", "")).strip()
        answer = str(c.get("answer", "")).strip()
        topic = str(c.get("topic", "")).strip() or "General"
        if not question or not answer:
            continue
        cards.append({
            "id": str(uuid.uuid4())[:8],
            "topic": topic,
            "question": question,
            "answer": answer,
            "box": 1,
            "next_due": None,
        })

    if not cards:
        raise ai_client.AIError("Gemini's flashcards came back empty or malformed.")
    return cards
