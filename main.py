# app/main.py
"""
Dataset Copilot · Streamlit UI
Upload ➜ Profile ➜ Ideas (LLM + custom) ➜ Code ➜ Run ➜ Chat
Each heavy step runs once per dataset and persists via st.session_state.
"""

from pathlib import Path
import sys, os
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
from agents import (
    LoaderAgent, ProfilerAgent,
    IdeatorAgent, CoderAgent,
    ChatQAAgent, RunnerAgent
)
from config import CONFIG

# ──────────────────────────── page config ─────────────────────────────
st.set_page_config(page_title="Dataset Copilot", page_icon="📊", layout="wide")
st.title("📊 Dataset Copilot")

# ─────────────────────── env / key sanity check ───────────────────────
if "gemini" not in CONFIG or not CONFIG["gemini"].get("light_api_key"):
    st.error("Gemini API key missing.  Add it to config/settings.toml.")
    st.stop()

# ───────────────────────── session defaults ───────────────────────────
for k in (
    "file_name", "df", "file_path",
    "profile", "ideas",
    "selected_idea", "code_text",
    "run_output", "run_success"
):
    st.session_state.setdefault(k, None)

# ────────────────────────────── upload  ───────────────────────────────
uploaded = st.file_uploader(
    "Upload CSV • Excel • ZIP", type=["csv", "xlsx", "xls", "zip"]
)

# Reset downstream state on new upload
if uploaded and uploaded.name != st.session_state.file_name:
    st.session_state.update({
        "file_name": uploaded.name,
        "df": None, "file_path": None,
        "profile": None, "ideas": None,
        "selected_idea": None, "code_text": None,
        "run_output": None, "run_success": None,
    })

# ---------- LOAD ----------
if uploaded and st.session_state.df is None:
    loader = LoaderAgent()
    try:
        res = loader.run(uploaded)
    except Exception as e:
        st.error(f"Loader error: {e}")
        st.stop()
    st.session_state.df        = res["df"]
    st.session_state.file_path = res["file_path"]
    others = res.get("other_files", [])
    st.success(f"Loaded **{os.path.basename(st.session_state.file_path)}** "
               f"({st.session_state.df.shape[0]}×{st.session_state.df.shape[1]})")
    if others:
        st.info("Ignoring extra files in archive: " + ", ".join(map(os.path.basename, others)))

# ---------- PREVIEW ----------
if st.session_state.df is not None:
    st.subheader("Preview")
    st.dataframe(st.session_state.df.head(), use_container_width=True)

# ---------- PROFILE ----------
if st.session_state.df is not None and st.session_state.profile is None:
    if st.button("▶️ Run Profiler"):
        profiler = ProfilerAgent()
        with st.spinner("Profiling…"):
            try:
                st.session_state.profile = profiler.run(st.session_state.df)
            except Exception as e:
                st.error(f"Profiling failed: {e}")

# display profile
if st.session_state.profile:
    prof = st.session_state.profile
    st.subheader("Dataset Profile")
    rows  = prof.get("num_rows")  or prof.get("rows")
    cols  = prof.get("num_columns") or prof.get("columns")
    if rows and cols:
        st.write(f"**Rows:** {rows}   **Columns:** {cols}")
    if prof.get("summary"):
        st.write(prof["summary"])
    with st.expander("Full profile JSON"):
        st.json(prof)

# ---------- IDEAS ----------
if st.session_state.profile and st.session_state.ideas is None:
    if st.button("💡 Generate Ideas"):
        ideator = IdeatorAgent()
        with st.spinner("Thinking…"):
            try:
                res = ideator.run(st.session_state.profile)
                st.session_state.ideas = res.get("ideas") if isinstance(res, dict) else res
            except Exception as e:
                st.error(f"Ideation failed: {e}")

# show ideas + custom box
user_custom_idea = st.text_input("Or type your own idea:", key="custom_idea") if st.session_state.profile else None
if st.session_state.ideas:
    st.subheader("Ideas from Copilot")
    for i, idea in enumerate(st.session_state.ideas, 1):
        st.markdown(f"{i}. {idea}")

# choose idea (drop-down or custom)
if st.session_state.ideas or user_custom_idea:
    default_options = st.session_state.ideas or []
    st.session_state.selected_idea = st.selectbox(
        "Select an idea to implement:",
        options=default_options + (["<Your custom idea>"] if user_custom_idea else []),
        key="idea_select"
    )
    # if user chose placeholder, override with custom text
    if st.session_state.selected_idea == "<Your custom idea>":
        st.session_state.selected_idea = user_custom_idea
    if not user_custom_idea and st.session_state.selected_idea not in default_options:
        st.session_state.selected_idea = None  # nothing picked yet

# ---------- CODE ----------
if st.session_state.selected_idea and st.session_state.code_text is None:
    if st.button("🛠️ Generate Code"):
        coder = CoderAgent()
        with st.spinner("Writing code…"):
            try:
                res = coder.run(
                        st.session_state.selected_idea,
                        st.session_state.file_path,
                        df_columns=list(st.session_state.df.columns)   # ← add this
                )

                lines = res.get("code") if isinstance(res, dict) else []
                st.session_state.code_text = "\n".join(lines)
            except Exception as e:
                st.error(f"Code generation failed: {e}")

# show / edit code area
if st.session_state.code_text is not None:
    st.subheader("Generated Code (editable)")
    st.text_area(
        "Python code:", value=st.session_state.code_text,
        height=300, key="code_editor"
    )

    st.download_button(
        "💾 Download code as generated_app.py",
        data=st.session_state.code_text,
        file_name="generated_app.py",
        mime="text/x-python"
    )


# ---------- RUN ----------
if st.session_state.code_text is not None:
    if st.button("▶️ Run Code"):
        runner = RunnerAgent()
        with st.spinner("Executing…"):
            user_code = st.session_state.get("code_editor", st.session_state.code_text)
            out = runner.run(user_code)

            plots = out.get("plots", [])
            for p in plots:
                p_path = os.path.join("app/assets/data", p)
                if os.path.isfile(p_path):
                    st.image(p_path, caption=p)

        st.session_state.run_output  = out.get("output", "")
        st.session_state.run_success = out.get("success", False)

# show run output
if st.session_state.run_output is not None:
    st.subheader("Execution Output")
    if st.session_state.run_success:
        st.success("Execution succeeded.")
    else:
        st.error("Execution errored.")
    st.code(st.session_state.run_output or "(no stdout/stderr)")


# ---------- CHAT ----------
if st.session_state.profile:
    st.subheader("Ask the Copilot")
    q = st.text_input("Question:", key="chat_q")
    if q:
        chat = ChatQAAgent()
        with st.spinner("Answering…"):
            ans = chat.run(
                q,
                dataset_summary=st.session_state.profile.get("summary"),
                last_result=st.session_state.run_output,
                df=st.session_state.df                          # ← pass DataFrame
            )
        st.write(ans.get("answer") if isinstance(ans, dict) else ans)  # ← show answer
