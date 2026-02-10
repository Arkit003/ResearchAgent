import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.main import DEFAULT_MODEL, run_research


def get_text(payload: dict[str, Any]) -> str:
    messages = payload.get("messages", [])
    if not messages:
        return "No response returned by agent."

    last = messages[-1]
    content = getattr(last, "content", None)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                if text:
                    parts.append(text)
        if parts:
            return "\n\n".join(parts)

    return str(content) if content else str(last)


def split_answer(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []

    marker = re.search(r"(?im)^#{2,3}\s*sources\s*$", text)
    if marker:
        body = text[: marker.start()].strip()
        src_block = text[marker.end() :].strip()
    else:
        body = text.strip()
        src_block = ""

    sources: list[str] = []
    for line in src_block.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\[\d+\]", line) or line.startswith("-"):
            sources.append(line)

    return body, sources


st.set_page_config(page_title="ResearchAgent", page_icon="🔎", layout="wide")
st.title("ResearchAgent")
st.caption("Ask a question and get a researched answer with citations.")

with st.sidebar:
    st.header("Settings")
    tavily_key = st.text_input("Tavily API key", type="password") or ""
    groq_key = st.text_input("Groq API key", type="password") or ""
    model_options = [
        "openai/gpt-oss-120b",
        "llama-3.3-70b-versatile",
        "qwen/qwen3-32b",
    ]
    default_model_index = (
        model_options.index(DEFAULT_MODEL) if DEFAULT_MODEL in model_options else 0
    )
    model_name = st.selectbox("Model", options=model_options, index=default_model_index)
    max_iters = st.slider(
        "Max researcher iterations", min_value=1, max_value=4, value=1
    )
    use_subagent = st.toggle("Use sub-agent mode", value=False)

    st.caption(
        "Keys are not saved in code. They are used only in this running app process."
    )

if tavily_key.strip():
    os.environ["TAVILY_API_KEY"] = tavily_key.strip()
if groq_key.strip():
    os.environ["GROQ_API_KEY"] = groq_key.strip()

missing_keys = [key for key in ["TAVILY_API_KEY", "GROQ_API_KEY"] if not os.getenv(key)]
if missing_keys:
    st.warning(
        "Missing environment variables: "
        + ", ".join(missing_keys)
        + ". Set them before running research."
    )

if "history" not in st.session_state:
    st.session_state.history = []


def make_report(query: str, answer: str, sources: list[str]) -> str:
    src_text = "\n".join(sources) if sources else "No sources provided."
    return (
        f"# Research Report\n\n## Question\n\n{query}\n\n"
        f"## Answer\n\n{answer}\n\n## Sources\n\n{src_text}\n"
    )


def make_report_path(query: str) -> Path:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in query).strip("-")
    if not safe:
        safe = "research-report"
    safe = "-".join(filter(None, safe.split("-")))[:80]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir / f"{timestamp}-{safe}.md"


with st.form("research_form"):
    query = st.text_area(
        "Research query",
        placeholder="Example: Compare RAG vs long-context prompting for enterprise search.",
        height=140,
    )
    submitted = st.form_submit_button("Run research")

if submitted:
    if not query.strip():
        st.error("Please enter a research query.")
    else:
        with st.spinner("Researching..."):
            result_text = ""
        try:
            result = run_research(
                query.strip(),
                model_name=model_name,
                max_iters=max_iters,
                use_subagent=use_subagent,
            )
            result_text = get_text(result)
            answer, sources = split_answer(result_text)

            st.session_state.history.insert(
                0,
                {
                    "query": query.strip(),
                    "answer": answer.strip(),
                    "sources": sources,
                    "model": model_name,
                    "max_iters": max_iters,
                    "use_subagent": use_subagent,
                },
            )
        except Exception as exc:
            msg = str(exc)
            if "rate_limit_exceeded" in msg or "Request too large" in msg:
                st.error(
                    "Research failed due to Groq token limits. Try lower max iterations, keep sub-agent mode off, or pick a smaller model."
                )
            else:
                st.error(f"Research failed: {exc}")

if st.session_state.history:
    st.subheader("Latest result")
    latest = st.session_state.history[0]
    st.markdown(f"**Question**\n\n{latest['query']}")
    st.caption(
        f"Model: {latest.get('model', DEFAULT_MODEL)} | Max iterations: {latest.get('max_iters', 3)} | Sub-agent: {latest.get('use_subagent', False)}"
    )
    st.markdown("**Answer**")
    st.markdown(latest["answer"])
    st.markdown("**Sources**")
    if latest.get("sources"):
        for src in latest["sources"][:4]:
            st.markdown(f"- {src}")
    else:
        st.markdown("- No sources listed.")

    col1, col2 = st.columns(2)
    with col1:
        report_md = make_report(
            latest["query"], latest["answer"], latest.get("sources", [])
        )
        st.download_button(
            "Download markdown",
            data=report_md,
            file_name="research_report.md",
            mime="text/markdown",
        )
    with col2:
        if st.button("Save report to file"):
            path = make_report_path(latest["query"])
            path.write_text(report_md, encoding="utf-8")
            st.success(f"Saved: {path}")

    with st.expander("Previous runs"):
        for idx, item in enumerate(st.session_state.history[1:], start=2):
            st.markdown(f"**Run {idx}**")
            st.markdown(f"Question: {item['query']}")
            st.caption(
                f"Model: {item.get('model', DEFAULT_MODEL)} | Max iterations: {item.get('max_iters', 3)} | Sub-agent: {item.get('use_subagent', False)}"
            )
            st.markdown(item["answer"])
            if item.get("sources"):
                for src in item["sources"][:4]:
                    st.markdown(f"- {src}")
