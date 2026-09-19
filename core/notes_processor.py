"""
notes_processor.py
Turns raw pasted/uploaded notes into a structured set of {topic, content} chunks.

Heuristic (no heavy NLP dependency needed, keeps setup light for a hackathon demo):
- A line is treated as a HEADING if it is short (<= 8 words), doesn't end in a period,
  and is either Title Case, ALL CAPS, numbered ("1.", "Unit 2", "Chapter 3"), or starts
  with a markdown heading marker (#, ##).
- Everything between two headings becomes that topic's content.
- If no headings are detected at all, the notes are split into fixed-size chunks and
  labelled "Topic 1", "Topic 2", ... so the rest of the pipeline still works.
"""

import re

HEADING_NUMBER_RE = re.compile(r"^(chapter|unit|topic|section|module)\s+\d+", re.IGNORECASE)
MD_HEADING_RE = re.compile(r"^#{1,6}\s+")


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
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
    if stripped.isupper() and len(words) <= 8:
        return True
    # Title Case check: most words start with a capital letter
    cap_words = sum(1 for w in words if w[:1].isupper())
    if len(words) >= 2 and cap_words / len(words) >= 0.7:
        return True
    return False


def extract_topics(raw_text: str, chunk_size: int = 600):
    """Returns a list of dicts: [{"topic": str, "content": str}, ...]"""
    lines = [l.rstrip() for l in raw_text.splitlines()]
    topics = []
    current_title = None
    current_lines = []

    def flush():
        content = "\n".join(current_lines).strip()
        if content:
            topics.append({
                "topic": current_title or f"Topic {len(topics) + 1}",
                "content": content,
            })

    for line in lines:
        if _looks_like_heading(line):
            flush()
            current_title = MD_HEADING_RE.sub("", line.strip())
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    # Fallback: no headings found at all -> chunk by size
    if len(topics) <= 1 and len(raw_text) > chunk_size:
        text = raw_text.strip()
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        topics = [{"topic": f"Topic {i+1}", "content": c.strip()} for i, c in enumerate(chunks) if c.strip()]

    return topics or [{"topic": "General Notes", "content": raw_text.strip()}]


def split_sentences(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    # naive sentence splitter, good enough for study notes
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 25]
  
def extract_text_from_upload(uploaded_file):
    """Extract plain text from an uploaded TXT, PDF, or DOCX file."""
    filename = uploaded_file.name.lower()

    if filename.endswith(".txt"):
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")

    elif filename.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(uploaded_file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    elif filename.endswith(".docx"):
        from docx import Document
        doc = Document(uploaded_file)
        return "\n".join(p.text for p in doc.paragraphs)

    else:
        raise ValueError("Unsupported file type. Please upload a TXT, PDF, or DOCX file.")
      def extract_topics_with_ai(raw_text: str):
    """Extract topics from notes."""
    return extract_topics(raw_text)
