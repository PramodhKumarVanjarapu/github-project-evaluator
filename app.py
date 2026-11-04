"""GitHub tech stack report. Run with:  streamlit run app.py"""

import os
import time
from datetime import date

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from analyzer import build_people, parse_pasted, people_to_csv, people_to_rows, run_report

load_dotenv()

st.set_page_config(page_title="GitHub tech stack report", page_icon="🧰", layout="wide")

# ---------- sidebar ----------

with st.sidebar:
    st.header("Settings")
    token = st.text_input(
        "GitHub token",
        value=os.getenv("GITHUB_TOKEN", ""),
        type="password",
        help="Read from GITHUB_TOKEN in your .env file. A token with public-repo read access is enough.",
    )
    if not token.strip():
        st.warning("Without a token, GitHub allows only 60 requests per hour.")
    skip_forks = st.checkbox(
        "Skip forked repositories",
        value=True,
        help="Forks are mostly other people's code.",
    )

# ---------- input ----------

st.title("Resume tech stack report")
st.write(
    "Add each person's phone number and resume link. The resume is read to find their GitHub "
    "profile and the projects they list. You'll get a CSV with one row per person: resume "
    "projects plus the combined tech stack across all their GitHub repositories."
)

st.subheader("People")
pasted = st.text_area(
    "One person per line: phone number and resume link, separated by a tab or comma. "
    "You can paste straight from Excel or Google Sheets.",
    placeholder="+91 98765 43210, https://drive.google.com/file/d/.../view",
    height=250,
)
st.caption(
    "Resume links can be a PDF, Word file, Google Drive or Google Docs link (shared as "
    "'Anyone with the link'), or a web page. Rows with the same phone number are merged."
)
pasted_rows = parse_pasted(pasted)
if pasted_rows:
    st.caption(f"{len(pasted_rows)} rows will be added to the report.")


def collect_rows() -> list[dict]:
    return pasted_rows


def status_frame(people: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Phone": p["phone"] or "—",
                "GitHub": ", ".join(p["profiles"]) or "—",
                "Resume projects": len(p["resume_projects"]),
                "Progress": round(100 * p["done"] / p["total"]) if p["total"] else 0,
                "Repos": f"{p['done']} / {p['total']}" if p["total"] else "",
                "Status": p["status"],
            }
            for p in people
        ]
    )


def format_duration(seconds: float) -> str:
    s = round(seconds)
    return f"{s // 60}m {s % 60}s" if s >= 60 else f"{s}s"


# ---------- run ----------

if st.button("Create report", type="primary"):
    people = build_people(collect_rows())

    if not any(p["profiles"] or p["resumes"] for p in people):
        st.error("Add at least one resume link first.")
    else:
        st.session_state.pop("report", None)
        bar = st.progress(0.0, text="Reading resumes…")
        table = st.empty()

        def on_progress(people: list[dict], done: int, total: int) -> None:
            if total:
                bar.progress(done / total, text=f"{done} of {total} repositories analysed")
            table.dataframe(
                status_frame(people),
                hide_index=True,
                width="stretch",
                column_config={
                    "Progress": st.column_config.ProgressColumn(
                        "Progress", min_value=0, max_value=100, format="%d%%"
                    ),
                },
            )

        started = time.time()
        run_report(people, token.strip() or None, skip_forks, on_progress)
        bar.empty()
        table.empty()

        st.session_state.report = people
        st.session_state.report_time = time.time() - started

# ---------- results ----------

if "report" in st.session_state:
    people = st.session_state.report
    failed = sum(1 for p in people if p["status"] != "Done")

    st.subheader("Report")
    summary = (
        f"Finished {len(people)} {'person' if len(people) == 1 else 'people'} "
        f"in {format_duration(st.session_state.report_time)}."
    )
    if failed:
        summary += f" {failed} could not be analysed; see the Notes column."
    st.caption(summary)

    st.dataframe(
        pd.DataFrame(people_to_rows(people)),
        hide_index=True,
        width="stretch",
        column_config={
            "Technologies": st.column_config.TextColumn(width="large"),
            "Projects in resume": st.column_config.TextColumn(width="large"),
            "Project categories": st.column_config.TextColumn(width="medium"),
        },
    )

    st.download_button(
        "Download CSV",
        data=people_to_csv(people),
        file_name=f"tech-stack-{date.today()}.csv",
        mime="text/csv",
        type="primary",
    )