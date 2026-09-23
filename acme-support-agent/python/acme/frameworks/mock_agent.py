"""Offline mock adapter — no AWS/OpenAI/Anthropic calls.

Selected automatically when ACME_MOCK is set (see acme/mock.py). Routes the
question to the same deterministic tools every other adapter uses
(acme/tools.py), via the TOOL_FUNCTIONS registry so run_evals' tool-tracking
monkeypatch still works, and builds the answer straight from the tool's
deterministic result. The chat span is still emitted (op=Op.CHAT) so the same
telemetry shape (invoke_agent -> chat -> execute_tool -> retrieval/embeddings)
comes out of the trace, just without any real model or embedding call.

Records a deterministic nominal token usage per turn so cost/token dashboards
are meaningful offline. Honors ACME_FAULT (see acme/faults.py) to emit failure
telemetry for demos.
"""

from __future__ import annotations

import os
import random
import re
import time

from ..observability import observe, enrich, Op
from ..tools import TOOL_FUNCTIONS
from ..usage import record_usage
from ..faults import active_faults

_ORDER_HINT_RE = re.compile(r"order")
_NUMBER_RE = re.compile(r"\d{3,}")
_SKU_RE = re.compile(r"[A-Z]{2,}-[A-Z0-9]+")

# Offline mode picks one of these per turn so the dashboards' Model filter has
# variety (real Bedrock model IDs, so the demo looks like a multi-model fleet).
_MOCK_MODELS = [
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    "amazon.titan-text-express-v1",
]


def _pick_mock_model() -> str:
    """One mock model per turn. ACME_MODEL pins a single model when set."""
    return os.environ.get("ACME_MODEL") or random.choice(_MOCK_MODELS)


def _route_and_call(question: str) -> tuple[str, dict]:
    """Pick a tool for the question and call it via TOOL_FUNCTIONS[name]."""
    q_lower = question.lower()
    number_match = _NUMBER_RE.search(question)

    if _ORDER_HINT_RE.search(q_lower) or number_match:
        order_id = number_match.group(0) if number_match else ""
        return "lookup_order", TOOL_FUNCTIONS["lookup_order"](order_id)

    sku_match = _SKU_RE.search(question)
    if sku_match or "stock" in q_lower or "inventory" in q_lower:
        sku = sku_match.group(0) if sku_match else ""
        return "check_inventory", TOOL_FUNCTIONS["check_inventory"](sku)

    return "search_policy", TOOL_FUNCTIONS["search_policy"](question)


def _answer_from(tool_name: str, result: dict, question: str) -> str:
    """Synthesize the mock answer from a tool result."""
    if isinstance(result, dict) and result.get("error"):
        if tool_name == "lookup_order":
            return f"Sorry, I couldn't find an order matching {question!r}."
        if tool_name == "check_inventory":
            return "Sorry, I couldn't find that SKU."
        return "Sorry, I couldn't find an answer to that in our policy docs."

    if tool_name == "lookup_order":
        answer = f"Your order is {result['status']}."
        items = result.get("items")
        if items:
            answer += f" Items: {', '.join(items)}."
        ship_date = result.get("ship_date")
        if ship_date:
            answer += f" Ship date: {ship_date}."
        return answer

    if tool_name == "check_inventory":
        return f"In stock: {result['in_stock']} units."

    return result["answer"]


def _record_nominal(question: str, answer: str, model: str) -> None:
    """Deterministic token accounting so cost/token panels have data offline.

    Feeds the in-process counter (for the eval cost check) *and* enriches the
    active chat span with gen_ai.request.model + usage, so the Run Details
    cost/token panels populate in mock mode (real adapters get this from the
    provider response; the mock has to supply it explicitly).
    """
    inp = len(question) * 3 + 400
    out = len(answer) * 3 + 40
    record_usage(inp, out)
    enrich(model=model, input_tokens=inp, output_tokens=out)


@observe(op=Op.CHAT, name="mock-chat")
def _mock_chat(question: str, faults: frozenset = frozenset(), model: str = "mock") -> str:
    """The mock "model turn" — deterministic routing + answer synthesis."""
    # wrong: call the wrong tool and return a non-answer (fails correctness/right_tool/trajectory).
    if "wrong" in faults:
        TOOL_FUNCTIONS["search_policy"](question)
        answer = "I'm not sure about that — please contact Acme support."
        _record_nominal(question, answer, model)
        return answer

    tool_name, result = _route_and_call(question)

    # loop: repeat the tool call so the trace shows a runaway loop (fails no_loops).
    if "loop" in faults:
        for _ in range(4):  # 1 call already made above -> 5 execute_tool spans total
            _route_and_call(question)

    answer = _answer_from(tool_name, result, question)
    _record_nominal(question, answer, model)
    return answer


def run_turn(question: str, history: list[dict]) -> str:
    """Offline drop-in for the real framework adapters' run_turn."""
    model = _pick_mock_model()
    enrich(model=model, provider="aws.bedrock")
    faults = frozenset(active_faults())

    if "error" in faults:
        raise RuntimeError("Simulated Bedrock ThrottlingException: request rate exceeded")
    if "slow" in faults:
        time.sleep(9)  # breach LATENCY_BUDGET_S (8s)
    if "cost" in faults:
        record_usage(5200, 900)  # exceed TOKEN_BUDGET (4000)
        enrich(model=model, input_tokens=5200, output_tokens=900)  # show the blowup in token panels

    return _mock_chat(question, faults, model)
