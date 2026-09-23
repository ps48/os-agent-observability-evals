"""Framework adapters.

Each adapter implements the same contract:

    run_turn(question: str, history: list[dict]) -> str

The agent logic (a tool-calling loop) is identical in spirit across all of them;
only the SDK calls to the model differ. Select one with the ACME_FRAMEWORK env var
or the --framework flag. The SDK's auto-instrumentation traces whichever you pick.
"""

from __future__ import annotations

import os


def get_adapter(name: str | None = None):
    """Return the run_turn callable for the requested framework."""
    from ..mock import mock_enabled
    if mock_enabled():
        from .mock_agent import run_turn
        return run_turn

    name = (name or os.environ.get("ACME_FRAMEWORK", "openai")).lower()

    if name == "openai":
        from .openai_agent import run_turn
    elif name == "anthropic":
        from .anthropic_agent import run_turn
    elif name == "bedrock":
        from .bedrock_agent import run_turn
    elif name == "langchain":
        from .langchain_agent import run_turn
    elif name == "llamaindex":
        from .llamaindex_agent import run_turn
    elif name == "mock":
        from .mock_agent import run_turn
    else:
        raise ValueError(
            f"Unknown framework '{name}'. "
            "Choose: openai | anthropic | bedrock | langchain | llamaindex | mock"
        )
    return run_turn
