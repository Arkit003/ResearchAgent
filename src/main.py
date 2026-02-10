from datetime import datetime
from functools import lru_cache
from typing import Any, Iterable, cast

from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

try:
    from src.agents.prompts import (
        RESEARCHER_INSTRUCTIONS,
        RESEARCH_WORKFLOW_INSTRUCTIONS,
        SUBAGENT_DELEGATION_INSTRUCTIONS,
    )
    from src.agents.tools import tavily_search, think_tool
except ModuleNotFoundError:
    from agents.prompts import (
        RESEARCHER_INSTRUCTIONS,
        RESEARCH_WORKFLOW_INSTRUCTIONS,
        SUBAGENT_DELEGATION_INSTRUCTIONS,
    )
    from agents.tools import tavily_search, think_tool

DEFAULT_MAX_UNITS = 3
DEFAULT_MAX_ITERS = 3
DEFAULT_MODEL = "qwen/qwen3-32b"
DEFAULT_USE_SUBAGENT = False

current_date = datetime.now().strftime("%Y-%m-%d")


def build_prompt(
    max_units: int,
    max_iters: int,
) -> str:
    return (
        RESEARCH_WORKFLOW_INSTRUCTIONS
        + "\n\n"
        + "=" * 80
        + "\n\n"
        + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
            max_concurrent_research_units=max_units,
            max_researcher_iterations=max_iters,
        )
    )


def build_small_prompt(max_iters: int) -> str:
    return (
        "You are a focused research assistant. "
        "Use tavily_search to gather evidence and think_tool between searches. "
        "Keep searches concise and stop when you have enough evidence. "
        f"Use at most {max_iters} search iterations. "
        "Return a clear answer with inline citations like [1], [2], and a final Sources section. "
        "Use only 2 to 4 sources unless the query truly needs more. "
        "Do not paste raw snippets, ads, or long copied text from pages."
    )


def build_small_researcher_prompt(max_iters: int) -> str:
    return (
        f"Today's date is {current_date}. "
        "Research the assigned question using tavily_search. "
        f"Perform at most {max_iters} searches. "
        "After each search, call think_tool briefly. "
        "Return concise findings with inline citations and a Sources section. "
        "Keep source count small (about 2 to 4). "
        "Do not include long copied snippets from websites."
    )


def build_research_subagent() -> dict[str, Any]:
    return {
        "name": "research-agent",
        "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
        "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
        "tools": [tavily_search, think_tool],
    }


@lru_cache(maxsize=16)
def get_agent(
    model_name: str = DEFAULT_MODEL,
    max_iters: int = DEFAULT_MAX_ITERS,
    max_units: int = DEFAULT_MAX_UNITS,
    use_subagent: bool = DEFAULT_USE_SUBAGENT,
):
    if use_subagent:
        instructions = build_prompt(
            max_units=max_units,
            max_iters=max_iters,
        )
        research_sub_agent = build_research_subagent()
        research_sub_agent["system_prompt"] = build_small_researcher_prompt(
            max_iters=max_iters
        )
        subagents = cast(Any, [research_sub_agent])
    else:
        instructions = build_small_prompt(max_iters=max_iters)
        subagents = None

    model = init_chat_model(
        model=model_name,
        model_provider="groq",
        temperature=0.0,
        max_tokens=900,
    )

    return create_deep_agent(
        model=model,
        tools=[tavily_search, think_tool],
        system_prompt=instructions,
        subagents=subagents,
    )


def run_research(
    query: str,
    model_name: str = DEFAULT_MODEL,
    max_iters: int = DEFAULT_MAX_ITERS,
    use_subagent: bool = DEFAULT_USE_SUBAGENT,
) -> dict[str, Any]:
    """Run one research request and return raw agent output."""
    agent = get_agent(
        model_name=model_name,
        max_iters=max_iters,
        use_subagent=use_subagent,
    )
    return agent.invoke({"messages": [{"role": "user", "content": query}]})


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(item["text"])
                elif item.get("text"):
                    parts.append(str(item["text"]))
        return "".join(parts)

    return ""


def stream_text(event: Any) -> str:
    message = event[0] if isinstance(event, tuple) and event else event
    message_content = getattr(message, "content", None)
    if message_content is not None:
        return content_to_text(message_content)
    if isinstance(message, dict):
        return content_to_text(message.get("content"))
    return ""


def stream_research(
    query: str,
    model_name: str = DEFAULT_MODEL,
    max_iters: int = DEFAULT_MAX_ITERS,
    use_subagent: bool = DEFAULT_USE_SUBAGENT,
) -> Iterable[str]:
    """Stream model text chunks for one research request."""
    agent = get_agent(
        model_name=model_name,
        max_iters=max_iters,
        use_subagent=use_subagent,
    )
    for event in agent.stream(
        {"messages": [{"role": "user", "content": query}]},
        stream_mode="messages",
    ):
        text = stream_text(event)
        if text:
            yield text
