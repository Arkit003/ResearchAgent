## ResearchAgent

A simple Streamlit app for web-assisted research using Groq models and Tavily search.

It takes a research question, runs a compact search workflow, and returns:
- a concise answer
- inline citations
- a short sources list

## What it does

- Uses Tavily for web search
- Uses a Groq-hosted LLM (default: `qwen/qwen3-32b`)
- Keeps responses compact to reduce token usage
- Supports model selection and max iterations from the sidebar
- Lets you download or save a markdown report

## Project structure

- `ui/streamlit_app.py` - Streamlit UI
- `src/main.py` - Agent setup and run helpers
- `src/agents/tools.py` - Search tools
- `src/agents/prompts.py` - Prompt templates

## Requirements

- Python 3.11+
- Groq API key
- Tavily API key

## Setup

Install dependencies with uv:

```bash
uv sync
```

Or install from requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
streamlit run ui/streamlit_app.py
```

Then in the sidebar, add:
- `TAVILY_API_KEY`
- `GROQ_API_KEY`

## Recommended settings

If you see token/rate limit errors:
- Set max iterations to `1` or `2`
- Keep sub-agent mode off
- Use `qwen/qwen3-32b`

## Notes

- Some sites block scraping (403). The app uses compact search snippets instead of full page dumps.
- Output is intentionally short to avoid noisy content (ads/nav text) and token overuse.
