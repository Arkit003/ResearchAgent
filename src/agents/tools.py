import re
from langchain_core.tools import InjectedToolArg, tool
from tavily import TavilyClient
from typing_extensions import Annotated, Literal


def tavily_client() -> TavilyClient:
    return TavilyClient()


def clean_text(text: str, max_chars: int = 400) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 1,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Args:
        query: Search query to execute
        max_results: Maximum number of results to return (default: 1)
        topic: Topic filter - 'general', 'news', or 'finance' (default: 'general')

    Returns:
        Compact search results with short snippets
    """
    max_results = max(1, min(max_results, 1))

    search_results = tavily_client().search(
        query,
        max_results=max_results,
        topic=topic,
    )

    result_texts = []
    for result in search_results.get("results", []):
        url = result["url"]
        title = result["title"]
        snippet = clean_text(result.get("content", ""))
        if not snippet:
            snippet = "No snippet available."

        result_text = f"""## {title}
**URL:** {url}

{snippet}

---
"""
        result_texts.append(result_text)

    response = f"""🔍 Found {len(result_texts)} result(s) for '{query}':

{chr(10).join(result_texts)}"""

    return response


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on research progress and decision-making.

    Use this tool after each search to analyze results and plan next steps systematically.
    This creates a deliberate pause in the research workflow for quality decision-making.

    When to use:
    - After receiving search results: What key information did I find?
    - Before deciding next steps: Do I have enough to answer comprehensively?
    - When assessing research gaps: What specific information am I still missing?
    - Before concluding research: Can I provide a complete answer now?

    Reflection should address:
    1. Analysis of current findings - What concrete information have I gathered?
    2. Gap assessment - What crucial information is still missing?
    3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
    4. Strategic decision - Should I continue searching or provide my answer?

    Args:
        reflection: Your detailed reflection on research progress, findings, gaps, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """
    return f"Reflection recorded: {reflection}"
