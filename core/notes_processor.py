"""
notes_processor.py

Turns raw pasted/uploaded notes into a structured set of
{topic, content} chunks.

Heuristic:
- A line is treated as a HEADING if it is short (<= 8 words),
  doesn't end in punctuation, and is either:
    - Title Case
    - ALL CAPS
    - numbered ("1.", "Unit 2", "Chapter 3")
    - starts with a markdown heading marker (#, ##, etc.)

- Everything between two headings becomes that topic's content.
- If no headings are detected, the notes are split into fixed-size
  chunks and labelled "Topic 1", "Topic 2", etc.

No heavy NLP dependency is required.
"""

import re


# ---------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------

HEADING_NUMBER_RE = re.compile(
    r"^(chapter|unit|topic|section|module)\s+\d+",
    re.IGNORECASE
)

MD_HEADING_RE = re.compile(r"^#{1,6}\s+")


# ---------------------------------------------------------
# Heading detection
# ---------------------------------------------------------

def _looks_like_heading(line: str) -> bool:
    """Return True if a line looks like a section heading."""

    stripped = line.strip()

    if not stripped:
        return False

    # Ignore very long lines
    if len(stripped) > 60:
        return False

    # Headings usually don't end with punctuation
    if stripped.endswith((".", ",", ";")):
        return False

    words = stripped.split()

    # Ignore long sentences
    if len(words) > 8:
        return False

    # Markdown heading
    if MD_HEADING_RE.match(stripped):
        return True

    # Numbered heading such as:
    # Chapter 2
    # Unit 3
    # Topic 1
    if HEADING_NUMBER_RE.match(stripped):
        return True

    # ALL CAPS heading
    if stripped.isupper() and len(words) <= 8:
        return True

    # Title Case check
    #
    # Example:
    # "Photosynthesis Process"
    # "Cellular Respiration"
    #
    # Most words should begin with a capital letter.
    cap_words = sum(
        1 for word in words
        if word[:1].isupper()
    )

    if len(words) >= 2 and cap_words / len(words) >= 0.7:
        return True

    return False


# ---------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------

def extract_topics(raw_text: str, chunk_size: int = 600):
    """
    Extract topics from raw notes.

    Returns:
        [
            {
                "topic": "Topic Name",
                "content": "Topic content..."
            }
        ]
    """

    if not raw_text or not raw_text.strip():
        return [
            {
                "topic": "General Notes",
                "content": ""
            }
        ]

    lines = [line.rstrip() for line in raw_text.splitlines()]

    topics = []
    current_title = None
    current_lines = []

    def flush():
        """Save the current topic if it contains content."""

        content = "\n".join(current_lines).strip()

        if content:
            topics.append(
                {
                    "topic": current_title
                    or f"Topic {len(topics) + 1}",
                    "content": content,
                }
            )

    for line in lines:

        if _looks_like_heading(line):

            # Save previous topic
            flush()

            # Remove markdown heading markers
            current_title = MD_HEADING_RE.sub(
                "",
                line.strip()
            )

            current_lines = []

        else:
            current_lines.append(line)

    # Save final topic
    flush()

    # -----------------------------------------------------
    # Fallback if no useful headings were detected
    # -----------------------------------------------------

    if len(topics) == 0:

        text = raw_text.strip()

        if len(text) <= chunk_size:
            return [
                {
                    "topic": "General Notes",
                    "content": text
                }
            ]

        chunks = [
            text[i:i + chunk_size]
            for i in range(
                0,
                len(text),
                chunk_size
            )
        ]

        return [
            {
                "topic": f"Topic {i + 1}",
                "content": chunk.strip()
            }
            for i, chunk in enumerate(chunks)
            if chunk.strip()
        ]

    return topics


# ---------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------

def split_sentences(text: str):
    """
    Split text into sentences.

    This is intentionally a simple sentence splitter,
    which is sufficient for study notes.
    """

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


# ---------------------------------------------------------
# File upload text extraction
# ---------------------------------------------------------

def extract_text_from_upload(uploaded_file):
    """
    Extract plain text from an uploaded TXT, PDF, or DOCX file.

    Supported formats:
        - .txt
        - .pdf
        - .docx
    """

    filename = uploaded_file.name.lower()

    # TXT
    if filename.endswith(".txt"):

        return uploaded_file.getvalue().decode(
            "utf-8",
            errors="ignore"
        )

    # PDF
    elif filename.endswith(".pdf"):

        from pypdf import PdfReader

        reader = PdfReader(uploaded_file)

        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    # DOCX
    elif filename.endswith(".docx"):

        from docx import Document

        doc = Document(uploaded_file)

        return "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )

    # Unsupported file
    else:

        raise ValueError(
            "Unsupported file type. "
            "Please upload a TXT, PDF, or DOCX file."
        )


# ---------------------------------------------------------
# AI-compatible wrapper
# ---------------------------------------------------------

def extract_topics_with_ai(raw_text: str):
    """
    Extract topics from notes.

    Currently uses the lightweight heuristic parser.
    This function is kept as a wrapper so an AI-based
    implementation can be added later without changing
    the rest of the application.
    """

    return extract_topics(raw_text)
