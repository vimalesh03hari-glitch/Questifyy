# 📚 StudyBuddy — Learn From Your Notes

Built for **Versathon 2.0 — E2: Learn From Your Notes**.

Turns a student's notes into **active recall** instead of passive re-reading:
upload notes → get auto-generated flashcards → review daily with spaced
repetition → take weekly practice tests → see exactly which topics need work.

## Features

| Requirement | How it's implemented |
|---|---|
| Document/text upload | `.txt` upload or paste-in box (`app.py` → Upload page) |
| Topic extraction & organization | Heading + chunk-based extraction, `core/notes_processor.py` |
| Question-answer / flashcard generation | Cloze-deletion active recall cards, `core/flashcard_generator.py` |
| Practice quiz with scoring | Auto-built MCQs from the flashcard bank, `core/quiz_generator.py` |
| Weak-topic & revision tracking | Persistent scorecard, `core/scorecard.py` |
| Daily flashcards | 5-box Leitner spaced repetition, `core/spaced_repetition.py` |
| Pomodoro + next-session reminder | Live countdown + browser notification, `core/pomodoro.py` |

## Project structure

```
study-buddy/
├── app.py                     # Streamlit UI (5 pages, see below)
├── requirements.txt
├── core/
│   ├── notes_processor.py     # splits raw notes into topics
│   ├── flashcard_generator.py # cloze-deletion active recall cards
│   ├── spaced_repetition.py   # Leitner-box scheduling for daily review
│   ├── pomodoro.py            # timer + next-session reminder logic
│   ├── quiz_generator.py      # builds weekly MCQ practice tests
│   ├── scorecard.py           # tracks history, computes weak topics
│   └── storage.py             # zero-setup JSON persistence
└── data/                      # created automatically at runtime
```

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## App pages

1. **📤 Upload Notes** — paste or upload notes, generates flashcards automatically.
2. **🗂️ Daily Flashcards** — spaced-repetition review queue, right/wrong buttons.
3. **⏱️ Pomodoro Timer** — configurable work/break timer with a live countdown and
   a browser notification + on-screen reminder telling you when to start your
   next study session.
4. **📝 Weekly Practice Test** — auto-generated multiple-choice quiz from your
   flashcard bank, scored on submit.
5. **📊 Scorecard** — score trend over time, per-topic accuracy bars, and a
   flagged list of weak topics to revisit.

## Design notes / why this approach

- **No external AI API or model download required** — flashcard/quiz generation
  is rule-based (regex + heuristics), so the demo works fully offline and is
  judge-friendly during a hackathon (no API keys, no latency, no cost). It's
  written so a single call to an LLM (e.g. the Anthropic API) can be dropped
  into `flashcard_generator.py` / `quiz_generator.py` later for smarter card
  generation — the surrounding app doesn't need to change.
- **Zero-setup storage** — plain JSON files in `data/`, so there's nothing to
  configure to run the demo. Swappable for SQLite/Postgres for production.
- **Leitner system** for spaced repetition is simple to explain to judges and
  is what "daily flashcards" should actually mean (not just "show all cards
  every day").

## Possible next steps

- Swap regex-based flashcard/quiz generation for an LLM call for higher-quality
  questions and better distractors.
- PDF/DOCX upload support (parse with `pypdf` / `python-docx`).
- Push notifications via a service worker instead of the in-tab Notification API.
- Multi-user accounts instead of a single local JSON store.
