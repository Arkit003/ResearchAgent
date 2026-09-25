## ResearchAgent

> A simple Streamlit app for web-assisted research using Groq models and Tavily search.

Ask it a question, and it runs a small tool-calling loop — web search, reflect, repeat — then
answers with inline citations and a numbered sources list. Everything is built on
[DeepAgents](https://github.com/langchain-ai/deepagents) with a Groq-hosted model, and the
whole thing is ~750 lines across seven files.

The design goal is **restraint**. The agent is told to use 2–4 sources, keep answers short, and
reflect between searches rather than grinding. That keeps token spend and latency down, which
matters because Groq's free tier rate-limits aggressively.

## What it does

- Uses Tavily for web search, returning compact snippets rather than full pages
- Uses a Groq-hosted LLM (default: `qwen/qwen3-32b`) at `temperature=0.0`, `max_tokens=900`
- Ships two prompt strategies: a compact single-agent prompt (default) and a full
  sub-agent workflow that can fan out to parallel researchers
- Supports model selection, max iterations and sub-agent mode from the sidebar
- Parses the answer's `### Sources` section out of the model's reply and shows it separately
- Lets you download the result as markdown, or save it to `reports/<timestamp>-<slug>.md`
- Keeps a session history of previous runs behind an expander

## How a research run works

1. You type a query and hit **Run research**.
2. `run_research()` gets (or builds) an agent via `get_agent()`, which is `@lru_cache`d on
   `(model_name, max_iters, use_subagent)` — so re-running with the same sidebar settings
   reuses the same agent instead of rebuilding it.
3. The agent gets two tools and loops until it decides it has enough evidence.
4. `content_to_text()` normalises whatever content shape the model returns (a plain string, or
   a list of content blocks) into text.
5. `split_answer()` cuts the reply at a `##`/`###` heading matching `sources`, and pulls out
   the numbered lines for the sources panel.

### Single-agent vs sub-agent mode

This is the main switch, and it changes the system prompt entirely:

| | Single-agent (default) | Sub-agent mode |
| --- | --- | --- |
| Prompt | `build_small_prompt()` — a few sentences | `RESEARCH_WORKFLOW_INSTRUCTIONS` + `SUBAGENT_DELEGATION_INSTRUCTIONS` |
| Structure | One agent, one tool loop | Orchestrator writes todos, delegates to `research-agent` sub-agents, consolidates citations |
| Files used | none | `/research_request.md`, `/final_report.md` via `write_file` |
| Cost | Low | High — several LLM calls per sub-agent |

The sub-agent prompt is opinionated on purpose: it tells the orchestrator to **start with one
sub-agent** and only parallelise for explicit comparisons or clearly separated aspects
("Compare A vs B vs C", or geographically split data), because one broad researcher is
cheaper than three narrow ones.

### The two tools

**`tavily_search(query, max_results, topic)`** — runs a Tavily search and formats each result
as a markdown block with title, URL and snippet. `clean_text()` collapses whitespace and
truncates the snippet to **400 characters**, which is what keeps ads and nav boilerplate out
of the context.

**`think_tool(reflection)`** — a deliberate pause. It takes free-text reflection, does nothing
with it, and returns `"Reflection recorded: ..."`. The value is entirely in the prompt
forcing the model to reason about gaps between searches before spending another one.

## Project structure

```
ResearchAgent/
├── ui/
│   └── streamlit_app.py   # Streamlit UI: sidebar, form, results, report export
├── src/
│   ├── main.py            # Agent construction, prompt builders, run/stream helpers
│   ├── agents/
│   │   ├── tools.py       # tavily_search and think_tool
│   │   ├── prompts.py     # The three long-form prompt templates
│   │   └── __init__.py
│   └── utils.py           # Rich console formatters (not currently imported anywhere)
├── pyproject.toml         # uv project definition
├── uv.lock                # Locked dependency versions
├── requirements.txt       # Unpinned fallback for pip
└── .python-version        # 3.11
```

`ui/streamlit_app.py` inserts the project root into `sys.path` before importing, so
`streamlit run ui/streamlit_app.py` works from the repo root. `src/main.py` guards its imports
with a `try: from src.agents... / except ModuleNotFoundError: from agents...` so it also runs
from inside `src/`.

## Requirements

- Python 3.11+ (`.python-version` pins 3.11; `pyproject.toml` requires `>=3.11`)
- A **Groq** API key
- A **Tavily** API key
- Network access to both providers at runtime

Core dependencies: `deepagents`, `langchain`, `langchain-groq`, `streamlit`, `tavily`.

## Setup

With [uv](https://docs.astral.sh/uv/) (recommended — `uv.lock` is committed):

```bash
uv sync
```

Or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run ui/streamlit_app.py
```

Then paste your two keys into the **Tavily API key** and **Groq API key** fields in the
sidebar. They are written into `os.environ` for the running process only — nothing is written
to disk or committed, and they disappear when the app stops.

Keys set in your shell beforehand also work; the app only shows the "Missing environment
variables" warning if neither source provides them.

### Sidebar settings

| Control | Options | Default |
| --- | --- | --- |
| Model | `openai/gpt-oss-120b`, `llama-3.3-70b-versatile`, `qwen/qwen3-32b` | `qwen/qwen3-32b` |
| Max researcher iterations | 1–4 | **1** in the UI (`DEFAULT_MAX_ITERS` is 3) |
| Use sub-agent mode | on / off | off |

## Output and reports

The model's reply is split on the first `##` or `###` "Sources" heading. The body renders as
markdown; lines matching `[1]`-style or `-` bullets below the heading become the sources list,
of which the first four are shown.

**Download markdown** gives you the full report in memory. **Save report to file** writes it to
`reports/<YYYYmmdd-HHMMSS>-<slugified-query>.md`, creating `reports/` if needed; the slug is
lowercased, non-alphanumerics become hyphens, and it's truncated to 80 characters.

## Recommended settings

If you hit token or rate limit errors, the app tells you to:

- Set max iterations to `1` or `2`
- Keep sub-agent mode off
- Use `qwen/qwen3-32b` (the smallest option)

## Notes and limitations

- **`tavily_search` can only ever return one result.** `max_results` is both defaulted to `1`
  and hard-clamped by `max(1, min(max_results, 1))`, which collapses every input to `1`. It is
  also annotated `InjectedToolArg`, so the model can't set it anyway. Raising the cap means
  changing that line.
- **`max_tokens=900`** is a hard output ceiling on the model, so long "full report" answers
  will get truncated. The compact prompt asks for short answers partly to stay under it.
- **Undeclared dependency:** `src/utils.py` imports `rich`, which is not in `pyproject.toml` or
  `requirements.txt`. It only works because Streamlit pulls `rich` in transitively.
- **Unused dependencies:** `markdownify` and `langchain-google-genai` are declared but appear
  nowhere in the code. Only the Groq provider is wired up.
- **`src/utils.py` is dead code** — its Rich formatters aren't imported by `main.py` or the UI.
- **`requirements.txt` lists `langchain-groq` twice** (once as `langchain_groq`, once as
  `langchain-groq`) and pins no versions, unlike `pyproject.toml` + `uv.lock`.
- **`pyproject.toml` has the name `reasearchagent`** (typo) and the stock uv description
  `"Add your description here"`. The lockfile keys off the typo, so renaming it means
  re-locking.
- **No `.env` loading.** `.gitignore` lists `src/.env`, but nothing calls `python-dotenv` —
  keys come from the sidebar or the ambient environment.
- **Results depend on scraping availability.** Some sites block retrieval (403); the compact
  snippet approach is a mitigation, not a fix, so a thin answer usually means the source pages
  weren't readable.
- No tests, no CI, and the project is a single commit (`d7830a7`).
