"""
notes_processor.py

Turns raw pasted/uploaded notes into structured
{topic, content} chunks.
"""

import re


HEADING_NUMBER_RE = re.compile(
    r"^(chapter|unit|topic|section|module)\s+\d+",
    re.IGNORECASE
)

MD_HEADING_RE = re.compile(
    r"^#{1,6}\s+"
)


def _looks_like_heading(line):
    stripped = line.strip()

    if not stripped:
        return False

    if len(stripped) > 60:
        return False

    if stripped.endswith((".", ",", ";")):
        return False

    words = stripped.split()

    if len(words) > 8:
        return False

    if MD_HEADING_RE.match(stripped):
        return True

    if HEADING_NUMBER_RE.match(stripped):
        return True

    if stripped.isupper():
        return True

    cap_words = sum(
        1
        for word in words
        if word[:1].isupper()
    )

    if len(words) >= 2:
        if cap_words / len(words) >= 0.7:
            return True

    return False


def extract_topics(raw_text, chunk_size=600):
    """
    Extract topics from raw notes.
    """

    if not raw_text:
        return [
            {
                "topic": "General Notes",
                "content": ""
            }
        ]

    lines = [
        line.rstrip()
        for line in raw_text.splitlines()
    ]

    topics = []
    current_title = None
    current_lines = []

    def flush():
        content = "\n".join(
            current_lines
        ).strip()

        if content:
            topics.append(
                {
                    "topic": (
                        current_title
                        or f"Topic {len(topics) + 1}"
                    ),
                    "content": content
                }
            )

    for line in lines:

        if _looks_like_heading(line):

            flush()

            current_title = MD_HEADING_RE.sub(
                "",
                line.strip()
            )

            current_lines = []

        else:
            current_lines.append(line)

    flush()

    # If no useful headings were detected,
    # split the notes into fixed-size chunks.
    if len(topics) <= 1 and len(raw_text) > chunk_size:

        text = raw_text.strip()

        chunks = [
            text[i:i + chunk_size]
            for i in range(
                0,
                len(text),
                chunk_size
            )
        ]

        topics = [
            {
                "topic": f"Topic {i + 1}",
                "content": chunk.strip()
            }
            for i, chunk in enumerate(chunks)
            if chunk.strip()
        ]

    if topics:
        return topics

    return [
        {
            "topic": "General Notes",
            "content": raw_text.strip()
        }
    ]


def split_sentences(text):
    """
    Split text into simple sentences.
    """

    if not text:
        return []

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    return [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) > 25
    ]


def extract_text_from_upload(uploaded_file):
    """
    Extract plain text from TXT, PDF, or DOCX.
    """

    filename = uploaded_file.name.lower()

    if filename.endswith(".txt"):

        return uploaded_file.getvalue().decode(
            "utf-8",
            errors="ignore"
        )

    elif filename.endswith(".pdf"):

        from pypdf import PdfReader

        reader = PdfReader(uploaded_file)

        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    elif filename.endswith(".docx"):

        from docx import Document

        doc = Document(uploaded_file)

        return "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )

    else:

        raise ValueError(
            "Unsupported file type. "
            "Please upload a TXT, PDF, or DOCX file."
        )


def extract_topics_with_ai(raw_text):
    """
    Compatibility function used by the app.

    Currently uses the local topic extractor.
    """

    return extract_topics(raw_text)
