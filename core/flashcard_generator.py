import re
import uuid

from .notes_processor import split_sentences


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
    re.IGNORECASE
)


def _pick_blank_word(sentence):
    match = TRIGGER_RE.search(sentence)

    if match:
        after = sentence[match.end():].strip(" .")

        candidate = (
            after
            .split(",")[0]
            .split(" and ")[0]
        )

        words = candidate.split()

        if words:
            return " ".join(words[:4]).strip(" .")

    capitalized = []

    for word in sentence.split():
        cleaned = word.strip(".,;:")

        if (
            cleaned
            and cleaned[0].isupper()
            and cleaned.lower() not in ("the", "a", "an")
        ):
            capitalized.append(cleaned)

    if capitalized:
        return max(capitalized, key=len)

    words = []

    for word in sentence.split():
        cleaned = word.strip(".,;:")

        if len(cleaned) > 5:
            words.append(cleaned)

    if words:
        return max(words, key=len)

    return None


def generate_flashcards_from_topic(
    topic,
    content,
    max_cards=6
):
    if not content:
        return []

    sentences = split_sentences(content)

    if not sentences:
        sentences = [content.strip()]

    sentences.sort(
        key=lambda s: 0 if TRIGGER_RE.search(s) else 1
    )

    cards = []

    for sentence in sentences:

        if len(cards) >= max_cards:
            break

        blank = _pick_blank_word(sentence)

        if not blank:
            continue

        if blank.lower() not in sentence.lower():
            continue

        pattern = re.compile(
            re.escape(blank),
            re.IGNORECASE
        )

        question = pattern.sub(
            "______",
            sentence,
            count=1
        )

        if question == sentence:
            continue

        cards.append(
            {
                "id": str(uuid.uuid4())[:8],
                "topic": topic,
                "question": question,
                "answer": blank,
                "box": 1,
                "next_due": None,
            }
        )

    return cards


def generate_all_flashcards(
    topics,
    max_cards_per_topic=6
):
    all_cards = []

    if not topics:
        return all_cards

    for topic_data in topics:

        topic = topic_data.get("topic", "General Notes") 
        content = topic_data.get(
            "content",
            ""
        )

        cards = generate_flashcards_from_topic(
            topic,
            content,
            max_cards_per_topic
        )

        all_cards.extend(cards)

    return all_cards


def generate_flashcards_with_ai(raw_text, topic_names=None, max_cards_per_topic=6):
    topics = [{"topic": t, "content": raw_text} for t in (topic_names or ["General Notes"])]
    return generate_all_flashcards(topics, max_cards_per_topic)
