"""
ai_client.py
Thin, defensive wrapper around the Gemini API using the current unified
`google-genai` SDK (the old `google-generativeai` package is deprecated).

Everything else in the app should go through this module instead of
importing google.genai directly. Responsibilities:

  - Read GEMINI_API_KEY from Streamlit secrets (Streamlit Community Cloud)
    or an environment variable (local dev). NEVER hardcoded, NEVER printed
    or returned to the UI.
  - Build a genai.Client on demand.
  - Run generate_content() calls that ask for structured JSON output, and
    turn ANY failure (missing key, package not installed, network error,
    rate limit, safety block, malformed JSON, empty response, ...) into a
    single AIError whose message is safe to show directly to the student.
    A Gemini outage should degrade the app, never crash it.
"""

import json
import os
import re

import streamlit as st

try:
    from google import genai
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

DEFAULT_MODEL = "gemini-2.5-flash-lite"

# Roughly a large chapter's worth of notes. Keeps requests fast, keeps us
# comfortably inside the model's context window, and keeps free-tier usage
# predictable even if a student pastes a huge document.
MAX_INPUT_CHARS = 45000


class AIError(Exception):
    """Raised for any Gemini-related failure. The message is always safe to
    show to the user as-is — never includes the API key or a raw traceback."""


def get_api_key():
    """Reads the key from Streamlit secrets first (Streamlit Community
    Cloud), then falls back to an environment variable (local dev / other
    hosts). Returns None if not configured anywhere. Never hardcoded."""
    key = None
    try:
        key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        key = None
    if not key:
        key = os.environ.get("GEMINI_API_KEY")
    return key.strip() if key else None


def is_configured() -> bool:
    """Cheap check the UI can use anywhere to decide whether to offer AI
    features or quietly stay in offline/heuristic mode."""
    return _SDK_AVAILABLE and bool(get_api_key())


def get_client():
    if not _SDK_AVAILABLE:
        raise AIError(
            "The `google-genai` package isn't installed. Add `google-genai` "
            "to requirements.txt to enable AI features."
        )
    key = get_api_key()
    if not key:
        raise AIError(
            "Gemini API key not found. Add GEMINI_API_KEY under "
            "Streamlit Cloud → Settings → Secrets, then reload the app."
        )
    try:
        return genai.Client(api_key=key)
    except Exception:
        raise AIError("Couldn't start the Gemini client — double-check the API key is valid.")


def truncate_for_prompt(text: str, max_chars: int = MAX_INPUT_CHARS):
    """Guards against very long notes blowing the context window or the
    free-tier quota. Returns (text_to_send, was_truncated)."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _clean_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def generate_structured(prompt: str, response_schema=None, system_instruction: str = None,
                         model: str = DEFAULT_MODEL, temperature: float = 0.4,
                         max_output_tokens: int = 4096):
    """
    Calls Gemini asking for JSON and returns plain Python data (a dict, or a
    list of dicts) — never a raw SDK/pydantic object — so callers don't need
    to know anything about the SDK. Raises AIError on any failure, including
    an empty prompt, missing key, network/quota/safety errors, or a response
    that isn't valid JSON.
    """
    if not prompt or not prompt.strip():
        raise AIError("Nothing to send to Gemini — the input was empty.")

    client = get_client()

    config = {
        "response_mime_type": "application/json",
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if response_schema is not None:
        config["response_schema"] = response_schema
    if system_instruction:
        config["system_instruction"] = system_instruction

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    except Exception as e:
        msg = str(e).lower()
        print("GEMINI ERROR:", type(e).__name__, str(e)[:300])
        if "api key" in msg or "permission" in msg or "unauthenticated" in msg or "401" in msg:
            raise AIError("Gemini rejected the API key. Check GEMINI_API_KEY in Streamlit secrets.")
        if "quota" in msg or "rate" in msg or "429" in msg or "resource_exhausted" in msg:
            raise AIError("Gemini's rate limit/quota was reached. Please wait a moment and try again.")
        if "safety" in msg or "blocked" in msg:
            raise AIError("Gemini blocked this content. Try different notes or fewer questions.")
        if "timeout" in msg or "deadline" in msg:
            raise AIError("Gemini took too long to respond. Please try again.")
        raise AIError("Couldn't reach Gemini right now. Please try again in a moment.")

    # Prefer the SDK's auto-parsed structured output when a schema was given.
    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        if isinstance(parsed, list):
            return [p.model_dump() if hasattr(p, "model_dump") else p for p in parsed]
        return parsed.model_dump() if hasattr(parsed, "model_dump") else parsed

    text = getattr(response, "text", None)
    if not text or not text.strip():
        raise AIError("Gemini returned an empty response. Please try again.")

    try:
        return json.loads(_clean_json_fences(text))
    except (json.JSONDecodeError, TypeError):
        raise AIError("Gemini's response wasn't valid JSON — please try again.")
