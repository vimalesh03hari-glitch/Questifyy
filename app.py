"""
StudyBuddy — Learn From Your Notes
Hackathon project: turns raw notes into active recall, with a Pomodoro study
scheduler, daily flashcards (spaced repetition), weekly practice tests, and a
scorecard that shows exactly what to revise next.

Run with:  streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

from core import storage, notes_processor, flashcard_generator, spaced_repetition
from core import pomodoro, quiz_generator, scorecard

st.set_page_config(page_title="StudyBuddy — Learn From Your Notes", page_icon="📚", layout="wide")

PAGES = ["📤 Upload Notes", "🗂️ Daily Flashcards", "⏱️ Pomodoro Timer", "📝 Weekly Practice Test", "📊 Scorecard"]

if "page" not in st.session_state:
    st.session_state.page = PAGES[0]
if "pomodoro_session" not in st.session_state:
    st.session_state.pomodoro_session = None
if "completed_pomodoros" not in st.session_state:
    st.session_state.completed_pomodoros = len(storage.load("sessions"))
if "current_quiz" not in st.session_state:
    st.session_state.current_quiz = None
if "quiz_answers" not in st.session_state:
    st.session_state.quiz_answers = {}

st.sidebar.title("📚 StudyBuddy")
st.sidebar.caption("Learn From Your Notes — Versathon 2.0")
st.session_state.page = st.sidebar.radio("Go to", PAGES, index=PAGES.index(st.session_state.page))

all_cards = storage.load("cards")

# ---------------------------------------------------------------- UPLOAD ----
if st.session_state.page == "📤 Upload Notes":
    st.header("📤 Upload / Paste Your Notes")
    st.write("Paste your notes or upload a .txt file. We'll split them into topics "
             "and auto-generate active-recall flashcards — no more just re-reading.")

    uploaded = st.file_uploader("Upload a .txt file", type=["txt"])
    pasted = st.text_area("...or paste notes here", height=220,
                           placeholder="Paste chapter notes, lecture summary, etc.")

    max_per_topic = st.slider("Max flashcards per topic", 3, 12, 6)

    if st.button("Generate Flashcards", type="primary"):
        raw_text = uploaded.read().decode("utf-8", errors="ignore") if uploaded else pasted
        if not raw_text or not raw_text.strip():
            st.warning("Please paste some notes or upload a file first.")
        else:
            topics = notes_processor.extract_topics(raw_text)
            new_cards = flashcard_generator.generate_all_flashcards(topics, max_per_topic)
            for c in new_cards:
                spaced_repetition.initialize_card(c)

            existing = storage.load("cards")
            existing.extend(new_cards)
            storage.save("cards", existing)

            notes_log = storage.load("notes")
            notes_log.append({"timestamp": storage.now_iso(), "topics": [t["topic"] for t in topics]})
            storage.save("notes", notes_log)

            st.success(f"Generated {len(new_cards)} flashcards across {len(topics)} topic(s)!")
            for t in topics:
                st.markdown(f"**{t['topic']}**")
            st.info("Head to '🗂️ Daily Flashcards' to start reviewing.")

    if all_cards:
        st.divider()
        st.caption(f"Flashcard bank: {len(all_cards)} cards across "
                   f"{len({c['topic'] for c in all_cards})} topics.")

# ------------------------------------------------------------ FLASHCARDS ----
elif st.session_state.page == "🗂️ Daily Flashcards":
    st.header("🗂️ Daily Flashcards (Active Recall)")

    if not all_cards:
        st.info("No flashcards yet — upload notes first.")
    else:
        due_cards = spaced_repetition.get_due_cards(all_cards)
        stats = spaced_repetition.mastery_stats(all_cards)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Due today", len(due_cards))
        c2.metric("New", stats["new"])
        c3.metric("Learning", stats["learning"])
        c4.metric("Mastered", stats["mastered"])

        if "review_queue" not in st.session_state or st.button("🔄 Refresh due cards"):
            st.session_state.review_queue = [c["id"] for c in due_cards]
            st.session_state.show_answer = False

        queue = st.session_state.get("review_queue", [])
        queue = [cid for cid in queue if cid in {c["id"] for c in due_cards}]

        if not queue:
            st.success("🎉 No cards due right now — you're on top of it! Come back tomorrow.")
        else:
            card = next(c for c in all_cards if c["id"] == queue[0])
            st.subheader(f"Topic: {card['topic']}")
            st.markdown(f"### {card['question']}")

            if not st.session_state.get("show_answer"):
                if st.button("Show answer"):
                    st.session_state.show_answer = True
            else:
                st.success(f"**Answer:** {card['answer']}")
                col1, col2 = st.columns(2)
                if col1.button("✅ I got it right"):
                    spaced_repetition.review_card(card, True)
                    storage.save("cards", all_cards)
                    st.session_state.review_queue.pop(0)
                    st.session_state.show_answer = False
                    st.rerun()
                if col2.button("❌ I got it wrong"):
                    spaced_repetition.review_card(card, False)
                    storage.save("cards", all_cards)
                    st.session_state.review_queue.pop(0)
                    st.session_state.show_answer = False
                    st.rerun()
            st.caption(f"{len(queue)} card(s) left in today's session")

# -------------------------------------------------------------- POMODORO ----
elif st.session_state.page == "⏱️ Pomodoro Timer":
    st.header("⏱️ Pomodoro Study Timer")
    st.write("Work in focused blocks. When your timer ends, StudyBuddy tells you "
             "exactly when your next study session should start.")

    colA, colB = st.columns(2)
    work_min = colA.number_input("Work session (minutes)", 5, 90, pomodoro.DEFAULT_WORK_MIN)
    break_min = colB.number_input("Short break (minutes)", 3, 30, pomodoro.DEFAULT_BREAK_MIN)

    if st.session_state.pomodoro_session is None:
        if st.button("▶️ Start Pomodoro Session", type="primary"):
            st.session_state.pomodoro_session = pomodoro.start_session(work_min)
            st.rerun()
    else:
        session = st.session_state.pomodoro_session
        remaining = pomodoro.seconds_remaining(session["end_time"])

        components.html(f"""
        <div style="font-family:sans-serif;text-align:center;padding:20px;">
          <div id="timer" style="font-size:64px;font-weight:bold;color:#e25822;"></div>
          <div id="status" style="font-size:16px;color:#555;">Stay focused 🎯</div>
        </div>
        <script>
        let remaining = {remaining};
        const timerEl = document.getElementById("timer");
        const statusEl = document.getElementById("status");
        if (Notification.permission !== "granted") {{ Notification.requestPermission(); }}
        function tick() {{
            let m = Math.floor(remaining/60), s = remaining%60;
            timerEl.innerText = String(m).padStart(2,'0') + ":" + String(s).padStart(2,'0');
            if (remaining <= 0) {{
                statusEl.innerText = "Session complete! Refresh the page to log it.";
                if (Notification.permission === "granted") {{
                    new Notification("StudyBuddy", {{ body: "Pomodoro session done — time for a break!" }});
                }}
                clearInterval(interval);
                return;
            }}
            remaining -= 1;
        }}
        tick();
        const interval = setInterval(tick, 1000);
        </script>
        """, height=160)

        if remaining <= 0:
            if st.button("✅ Log completed session & get next reminder"):
                sessions = storage.load("sessions")
                sessions.append({"start": session["start_time"], "end": session["end_time"]})
                storage.save("sessions", sessions)
                st.session_state.completed_pomodoros += 1

                next_time, brk = pomodoro.compute_next_session_reminder(
                    datetime.fromisoformat(session["end_time"]),
                    st.session_state.completed_pomodoros, break_min)

                st.session_state.pomodoro_session = None
                st.session_state.next_reminder = next_time.strftime("%I:%M %p")
                st.session_state.next_break_len = brk
                st.rerun()
        else:
            if st.button("⏹️ Cancel session"):
                st.session_state.pomodoro_session = None
                st.rerun()

    if st.session_state.get("next_reminder"):
        st.success(f"⏰ Take a {st.session_state.next_break_len}-minute break. "
                   f"Your next study session should start around **{st.session_state.next_reminder}**.")

    st.caption(f"Completed sessions today: {st.session_state.completed_pomodoros}")

# --------------------------------------------------------------- WEEKLY -----
elif st.session_state.page == "📝 Weekly Practice Test":
    st.header("📝 Weekly Practice Test")

    if not all_cards:
        st.info("No flashcards yet — upload notes first.")
    else:
        num_q = st.slider("Number of questions", 3, min(20, len(all_cards)), min(10, len(all_cards)))

        if st.button("🎯 Generate New Practice Test", type="primary"):
            st.session_state.current_quiz = quiz_generator.generate_quiz(all_cards, num_q)
            st.session_state.quiz_answers = {}
            st.session_state.quiz_submitted = False

        quiz = st.session_state.current_quiz
        if quiz:
            for i, q in enumerate(quiz, 1):
                st.markdown(f"**Q{i}. ({q['topic']}) {q['question']}**")
                choice = st.radio("Choose one:", q["options"], key=f"q_{q['id']}", index=None)
                if choice:
                    st.session_state.quiz_answers[q["id"]] = choice
                st.write("")

            if st.button("✅ Submit Test"):
                result = quiz_generator.score_quiz(quiz, st.session_state.quiz_answers)
                scorecard.save_quiz_result(result)
                st.session_state.quiz_submitted = True
                st.session_state.last_result = result

            if st.session_state.get("quiz_submitted"):
                r = st.session_state.last_result
                st.success(f"Score: {r['total_correct']}/{r['total_questions']} ({r['percent']}%)")
                st.info("Check the 📊 Scorecard tab to see your weak topics.")

# ------------------------------------------------------------- SCORECARD ----
elif st.session_state.page == "📊 Scorecard":
    st.header("📊 Your Scorecard")

    history = scorecard.get_history()
    if not history:
        st.info("No practice tests taken yet. Complete a Weekly Practice Test first.")
    else:
        latest = history[-1]
        avg = round(sum(h["percent"] for h in history) / len(history), 1)
        c1, c2, c3 = st.columns(3)
        c1.metric("Latest score", f"{latest['percent']}%")
        c2.metric("Average score", f"{avg}%")
        c3.metric("Tests taken", len(history))

        st.subheader("Score over time")
        st.line_chart({"score %": [h["percent"] for h in history]})

        st.subheader("Topic breakdown")
        breakdown = scorecard.topic_accuracy_breakdown()
        for b in breakdown:
            color = "🔴" if b["accuracy"] < 50 else ("🟡" if b["accuracy"] < 75 else "🟢")
            st.write(f"{color} **{b['topic']}** — {b['accuracy']}% "
                     f"({b['attempts']} question attempts)")
            st.progress(min(int(b["accuracy"]), 100))

        weak = scorecard.weak_topics()
        if weak:
            st.subheader("📌 Focus on these next")
            for w in weak:
                st.warning(f"**{w['topic']}** — only {w['accuracy']}% accuracy. "
                           f"Revisit the flashcards for this topic today.")
        else:
            st.success("No weak topics below 70% — great work!")
