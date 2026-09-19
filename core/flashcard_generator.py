"""
flashcard_generator.py
Builds ACTIVE RECALL flashcards (cloze deletion, i.e. fill-in-the-blank) from notes,
instead of just letting students re-read them.

Approach:
1. Split each topic's content into candidate sentences.
2. Prefer "definition-style" sentences (contains is/are/means/refers to/defined as),
   since blanking the key term there tests real understanding.
3. Blank out the most "information-dense" word/phrase in the sentence (longest
   capitalized token, or the noun phrase right after the definition verb).
4. Store as {topic, question (with ____), answer, id}.

This is intentionally dependency-free (regex only) so it runs anywhere in a hackathon
environment without model downloads. It's easy to swap in an LLM call later.
"""

import re
import uuid
from .notes_processor import split_sentences

DEFINITION_TRIGGERS = [
    r"\bis\b", r"\bare\b", r"\bmeans\b", r"\brefers to\b",
    r"\bdefined as\b", r"\bis called\b", r"\bconsists of\b",
]
TRIGGER_RE = re.compile("|".join(DEFINITION_TRIGGERS), re.IGNORECASE)


def _pick_blank_word(sentence: str) -> str | None:
    """Pick the term to hide: prefer the phrase right after a definition trigger,
    otherwise the longest capitalized word, otherwise the longest word overall."""
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
    # Rank: definition-style sentences first
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
            "box": 1,          # Leitner box: 1 = new/hardest, 5 = mastered
            "next_due": None,  # set by spaced_repetition on first save
        })
    return cards


def generate_all_flashcards(topics: list[dict], max_cards_per_topic: int = 6):
    all_cards = []
    for t in topics:
        all_cards.extend(generate_flashcards_from_topic(t["topic"], t["content"], max_cards_per_topic))
    return all_cards
