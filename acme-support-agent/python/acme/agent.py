"""The Acme agent entry point.

`handle_support_question` is the top-level span (invoke_agent). It enriches the
trace with the conversation id and model, then delegates the tool-calling loop to
the selected framework adapter. This single function is what every part of the
tutorial — observe, evaluate, monitor — hangs off of.
"""

from __future__ import annotations

import os
import random
import time

from .observability import observe, enrich, Op
from .frameworks import get_adapter
from .usage import reset_usage, get_usage


# name= on an INVOKE_AGENT span sets gen_ai.agent.name.
@observe(op=Op.INVOKE_AGENT, name="acme-support-agent")
def handle_support_question(
    question: str,
    conversation_id: str = "anonymous",
    history: list[dict] | None = None,
    framework: str | None = None,
) -> str:
    """Answer one customer support question.

    This is the invoke_agent span. The chat + execute_tool child spans are
    emitted by the framework adapter and the @observe-decorated tools.
    """
    enrich(session_id=conversation_id)  # session_id -> gen_ai.conversation.id
    reset_usage()                       # isolate per-turn token usage
    run_turn = get_adapter(framework)

    start = time.time()
    answer = run_turn(question, history or [])

    # Blog Part 7: online evaluation on a sampled fraction of live traffic.
    # score() here runs while this invoke_agent span is still active, so the
    # online scores attach to the live trace. Off unless ACME_ONLINE_EVAL_RATE>0.
    rate = float(os.environ.get("ACME_ONLINE_EVAL_RATE", "0") or 0)
    if rate > 0 and random.random() < rate:
        from evals.online import score_online  # lazy import avoids an acme<->evals cycle
        score_online(question, answer, time.time() - start, get_usage()["total_tokens"])

    return answer
