"""
flashcard_generator.py
Builds ACTIVE RECALL flashcards from notes.

Two paths, same output shape ({id, topic, question, answer, box, next_due}),
so everything downstream (spaced_repetition, storage, the review UI) works
unchanged either way:

  - generate_flashcards_with_ai()  -> Gemini writes a clear QUESTION and a
    short, bullet-point ANSWER (2-4 short "→" notes, not a full paragraph,
    and never a fill-in-the-blank sentence). This is the primary path and
    is what should run whenever GEMINI_API_KEY is configured.
  - generate_all_flashcards() / generate_flashcards_from_topic() -> offline
    regex cloze-deletion ("fill in the blank"). Zero dependencies, used ONLY
    as a fallback if Gemini is unavailable or a call fails.
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
# Offline heuristic generator (FALLBACK ONLY — used when Gemini is
# unavailable or errors out. This is intentionally simple/regex-based.)
# --------------------------------------------------------------------------

def _pick_blank_word(sentence):
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


def generate_flashcards_from_topic(topic, content, max_cards=6):
    if not content:
        return []

    sentences = split_sentences(content) or [content.strip()]
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
            "answer": f"→ {blank}",
            "box": 1,
            "next_due": None,
        })
    return cards


def generate_all_flashcards(topics, max_cards_per_topic=6):
    all_cards = []
    if not topics:
        return all_cards
    for topic_data in topics:
        topic = topic_data.get("topic", "General Notes")
        content = topic_data.get("content", "")
        all_cards.extend(generate_flashcards_from_topic(topic, content, max_cards_per_topic))
    return all_cards


# --------------------------------------------------------------------------
# Gemini-powered generator (PRIMARY PATH — this is the one that should run
# whenever GEMINI_API_KEY is configured)
# --------------------------------------------------------------------------

class _AIFlashcard(BaseModel):
    topic: str
    question: str
    answer_points: list[str]


def generate_flashcards_with_ai(raw_text, topic_names=None, num_cards=15):
    """
    Asks Gemini to write clear active-recall flashcards directly from the
    notes: a properly worded QUESTION (never a fill-in-the-blank sentence)
    and a short ANSWER made of 2-4 bullet-point notes, rendered as
    "→ point one\n→ point two" for a clean card back.

    Returns the same shape as the offline generator: [{id, topic, question,
    answer, box, next_due}, ...]. Raises ai_client.AIError on any failure —
    the caller (app.py) should catch this and fall back to
    generate_all_flashcards().
    """
    if not raw_text or not raw_text.strip():
        raise ai_client.AIError("There's no text to generate flashcards from.")

    sent_text, _truncated = ai_client.truncate_for_prompt(raw_text)

    topic_hint = ""
    if topic_names:
        topic_hint = ("Tag each flashcard with one of these exact topic names: "
                       + ", ".join(topic_names) + ".\n")

    prompt = (
        "You are building ACTIVE RECALL flashcards for a student from their notes.\n\n"
        "Rules for every flashcard:\n"
        "- `question`: a complete, clearly worded question that tests real understanding "
        "of a concept. NEVER a fill-in-the-blank sentence, NEVER a sentence with a blank "
        "or underscore in it, and never a yes/no question.\n"
        "- `answer_points`: 2 to 4 SHORT bullet points (a few words to one short phrase "
        "each) that together answer the question — like quick revision notes, not a "
        "paragraph. If the answer is genuinely a single short fact, just return one point.\n"
        f"{topic_hint}"
        f"Generate about {num_cards} flashcards, spread across the different topics/concepts "
        "covered in the notes below.\n\n"
        f'NOTES:\n"""\n{sent_text}\n"""'
    )

    raw_cards = ai_client.generate_structured(prompt, response_schema=list[_AIFlashcard])

    cards = []
    for c in (raw_cards or []):
        question = str(c.get("question", "")).strip()
        topic = str(c.get("topic", "")).strip() or "General"
        points = [str(p).strip() for p in (c.get("answer_points") or []) if str(p).strip()]

        if not question or not points:
            continue

        answer_text = "  \n".join(f"→ {p}" for p in points)  # trailing 2 spaces = markdown line break

        cards.append({
            "id": str(uuid.uuid4())[:8],
            "topic": topic,
            "question": question,
            "answer": answer_text,
            "box": 1,
            "next_due": None,
        })

    if not cards:
        raise ai_client.AIError("Gemini's flashcards came back empty or malformed.")
    return cards
