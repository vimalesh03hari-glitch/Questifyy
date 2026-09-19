"""
notes_processor.py
Two jobs:

1. Get plain text OUT of whatever the student uploaded (.txt / .pdf / .docx),
   with clear errors for empty/unreadable files.
2. Turn that text into topics — either the offline heuristic splitter (no
   dependencies, always works) or `extract_topics_with_ai()`, which asks
   Gemini to identify and organize the main topics (used when a
   GEMINI_API_KEY is configured).
"""

import io
import re

from pydantic import BaseModel

from . import ai_client

HEADING_NUMBER_RE = re.compile(r"^(chapter|unit|topic|section|module)\s+\d+", re.IGNORECASE)
MD_HEADING_RE = re.compile(r"^#{1,6}\s+")


# --------------------------------------------------------------------------
# Document text extraction
# --------------------------------------------------------------------------

def extract_text_from_upload(uploaded_file) -> str:
    """Extracts plain text from a Streamlit UploadedFile (.txt, .md, .pdf,
    or .docx). Raises ValueError with a message safe to show the user."""
    if uploaded_file is None:
        raise ValueError("No file was uploaded.")

    name = (uploaded_file.name or "").lower()
    raw = uploaded_file.read()
    if not raw:
        raise ValueError("The uploaded file is empty.")

    if name.endswith(".txt") or name.endswith(".md"):
        text = raw.decode("utf-8", errors="ignore")

    elif name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError("PDF support isn't installed on this server (missing `pypdf`).")
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = [(page.extract_text() or "") for page in reader.pages]
            text = "\n".join(pages)
        except Exception:
            raise ValueError("Couldn't read that PDF — it may be scanned/image-only, encrypted, or corrupted.")

    elif name.endswith(".docx"):
        try:
            import docx
        except ImportError:
            raise ValueError("DOCX support isn't installed on this server (missing `python-docx`).")
        try:
            document = docx.Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in document.paragraphs)
        except Exception:
            raise ValueError("Couldn't read that Word document — it may be corrupted or password-protected.")

    else:
        raise ValueError("Unsupported file type. Please upload a .txt, .pdf, or .docx file.")

    text = (text or "").strip()
    if not text:
        raise ValueError(
            "No readable text was found in that file (a scanned PDF with no "
            "text layer, for example). Try pasting the notes as text instead."
        )
    return text


# --------------------------------------------------------------------------
# Offline heuristic topic extraction (fallback — no API key required)
# --------------------------------------------------------------------------

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
    cap_words = sum(1 for w in words if w[:1].isupper())
    if len(words) >= 2 and cap_words / len(words) >= 0.7:
        return True
    return False


def extract_topics(raw_text: str, chunk_size: int = 600):
    """Offline/heuristic topic splitter. Returns [{"topic": str, "content": str}, ...]."""
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

    if len(topics) <= 1 and len(raw_text) > chunk_size:
        text = raw_text.strip()
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        topics = [{"topic": f"Topic {i+1}", "content": c.strip()} for i, c in enumerate(chunks) if c.strip()]

    return topics or [{"topic": "General Notes", "content": raw_text.strip()}]


def split_sentences(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 25]


# --------------------------------------------------------------------------
# Gemini-powered topic extraction
# --------------------------------------------------------------------------

class _AITopic(BaseModel):
    topic: str
    summary: str


def extract_topics_with_ai(text: str) -> list:
    """
    Uses Gemini to identify and organize the main topics in a student's notes.
    Returns [{"topic": ..., "summary": ...}, ...]. Raises ai_client.AIError
    on any failure (missing key, network error, empty/invalid response) —
    callers should catch this and fall back to extract_topics().
    """
    if not text or not text.strip():
        raise ai_client.AIError("There's no text to analyze.")

    sent_text, _truncated = ai_client.truncate_for_prompt(text)
    prompt = (
        "You are helping a student organize their study notes for revision.\n"
        "Read the notes below and identify the main topics/subtopics covered.\n"
        "For each topic, write a short 1-2 sentence summary of what it covers.\n"
        "Return between 3 and 10 topics, ordered as they appear in the notes. "
        "If the notes only cover one topic, return just that one.\n\n"
        f'NOTES:\n"""\n{sent_text}\n"""'
    )
    topics = ai_client.generate_structured(prompt, response_schema=list[_AITopic])
    topics = [t for t in (topics or []) if t.get("topic")]
    if not topics:
        raise ai_client.AIError("Gemini couldn't find any topics in these notes.")
    return topics
