 """
flashcard_generator.py

Generates active-recall flashcards from study notes.

The generator:
1. Splits notes into topics.
2. Finds useful sentences.
3. Creates fill-in-the-blank questions.
4. Keeps the original answer.
5. Adds Leitner/spaced-repetition fields.
"""

import re
import uuid

from .notes_processor import split_sentences, extract_topics


# Words/phrases that often indicate a definition.
DEFINITION_TRIGGERS = [
    r"\bis\b",
    r"\bare\b",
    r"\bmeans\b",
    r"\brefers to\b",
    r"\bdefined as\b",
    r"\bis called\b",
    r"\bconsists of\b",
]


TRIGGER_RE = re.compile(
    "|".join(DEFINITION_TRIGGERS),
    re.IGNORECASE,
)


def _clean_answer(answer: str) -> str:
    """Clean up an extracted answer."""

    answer = answer.strip()

    # Remove common punctuation.
    answer = answer.strip(".,;:!?")

    # Fix common article problems.
    answer = re.sub(
        r"^an\s+(?=[bcdfghjklmnpqrstvwxyz])",
        "a ",
        answer,
        flags=re.IGNORECASE,
    )

    return answer.strip()


def _pick_blank_word(sentence: str):
    """
    Select the most useful phrase to hide in a sentence.
    """

    # First try definition-style sentences.
    match = TRIGGER_RE.search(sentence)

    if match:
        after = sentence[match.end():].strip(" .,:;")

        # Stop at common sentence connectors.
        candidate = re.split(
            r",|\band\b|\bwhich\b|\bthat\b",
            after,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

        words = candidate.split()

        if words:
            # Don't create enormous blanks.
            answer = " ".join(words[:4])
            return _clean_answer(answer)

    # Try capitalized terms.
    capitalized = []

    for word in sentence.split():
        cleaned = word.strip(".,;:!?()[]{}")

        if (
            len(cleaned) > 2
            and cleaned[:1].isupper()
            and cleaned.lower() not in {"the", "a", "an", "this", "that"}
        ):
            capitalized.append(cleaned)

    if capitalized:
        return max(capitalized, key=len)

    # Otherwise choose a reasonably long word.
    words = []

    for word in sentence.split():
        cleaned = word.strip(".,;:!?()[]{}")

        if len(cleaned) >= 6:
            words.append(cleaned)

    if words:
        return max(words, key=len)

    return None


def _make_question(sentence: str, answer: str):
    """Replace the answer with a blank."""

    pattern = re.compile(
        re.escape(answer),
        re.IGNORECASE,
    )

    question = pattern.sub(
        "______",
        sentence,
        count=1,
    )

    if question == sentence:
        return None

    return question


def generate_flashcards_from_topic(
    topic: str,
    content: str,
    max_cards: int = 6,
):
    """
    Generate flashcards for one topic.
    """

    if not content or not content.strip():
        return []

    sentences = split_sentences(content)

    # If the sentence splitter produces nothing,
    # try splitting by lines.
    if not sentences:
        sentences = [
            line.strip()
            for line in content.splitlines()
            if len(line.strip()) > 20
        ]

    # Put definition-style sentences first.
    sentences.sort(
        key=lambda sentence: (
            0 if TRIGGER_RE.search(sentence) else 1
        )
    )

    cards = []
    used_questions = set()

    for sentence in sentences:

        if len(cards) >= max_cards:
            break

        answer = _pick_blank_word(sentence)

        if not answer:
            continue

        question = _make_question(
            sentence,
            answer,
        )

        if not question:
            continue

        # Avoid duplicate cards.
        question_key = question.lower().strip()

        if question_key in used_questions:
            continue

        used_questions.add(question_key)

        cards.append(
            {
                "id": str(uuid.uuid4())[:8],
                "topic": topic,
                "question": question,
                "answer": answer,

                # Leitner box.
                # 1 = new/hardest
                # 5 = mastered
                "box": 1,

                # Spaced repetition will update this later.
                "next_due": None,
            }
        )

    return cards


def generate_all_flashcards(
    topics: list[dict],
    max_cards_per_topic: int = 6,
):
    """
    Generate flashcards from all topics.
    """

    all_cards = []

    for topic_data in topics:

        topic = topic_data.get(
            "topic",
            "General Notes",
        )

        content = topic_data.get(
            "content",
            "",
        )

        cards = generate_flashcards_from_topic(
            topic,
            content,
            max_cards_per_topic,
        )

        all_cards.extend(cards)

    return all_cards


def generate_flashcards_with_ai(
    raw_text,
    topic_names=None,
    num_cards=6,
):
    """
    Compatibility function used by app.py.

    app.py can call:

        generate_flashcards_with_ai(
            raw_text,
            topic_names,
            num_cards
        )

    This version does not require an external AI API.
    """

    # Make sure raw_text is a string.
    if raw_text is None:
        raw_text = ""

    raw_text = str(raw_text)

    if not raw_text.strip():
        return []

    # Extract topics from the notes.
    topics = extract_topics(raw_text)

    # If the user selected specific topics,
    # keep those topics when possible.
    if topic_names:

        selected_names = {
            str(name).strip().lower()
            for name in topic_names
        }

        filtered_topics = []

        for topic_data in topics:

            topic_name = str(
                topic_data.get(
                    "topic",
                    "",
                )
            ).strip().lower()

            if topic_name in selected_names:
                filtered_topics.append(topic_data)

        # Only replace the topics if we actually
        # found matching topics.
        if filtered_topics:
            topics = filtered_topics

    # Safely convert the requested card count.
    try:
        num_cards = int(num_cards)
    except (TypeError, ValueError):
        num_cards = 6

    if num_cards < 1:
        num_cards = 6

    # Generate cards.
    cards = generate_all_flashcards(
        topics,
        max_cards_per_topic=num_cards,)

    # Limit total cards returned.
    return cards[:num_cards]
