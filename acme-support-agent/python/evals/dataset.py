"""The eval dataset + golden paths — Blog Parts 6 and 8.

`GOLDEN_CASES` are hand-written cases that pin the agent's expected behavior:
the expected tool path (the "golden trajectory" for trajectory comparison) and an
expected substring in the final answer.

`load_from_production_traces()` is the Part-8 close-the-loop hook: it shows how you
turn real failing traces in OpenSearch into new dataset rows. By default it returns
an empty list (run it against your own stack to harvest real cases).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def _slug(text: str) -> str:
    """Stable, readable case id from the question (test.case.id)."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:48] or "case"


@dataclass
class EvalCase:
    question: str
    expected_tool: str                 # the one tool that should be called
    expected_answer_substring: str     # what a correct answer must contain
    golden_trajectory: list[str] = field(default_factory=list)  # expected op/tool sequence
    conversation_id: str = "eval"
    case_id: str = ""                  # stable id (test.case.id); derived from the question if unset

    def __post_init__(self):
        if not self.case_id:
            self.case_id = _slug(self.question)


# Hand-written golden cases. The order-status case is the canonical golden path
# used in the blog: invoke_agent -> lookup_order -> answer, no detours.
GOLDEN_CASES: list[EvalCase] = [
    EvalCase(
        question="where is my order #1007?",
        expected_tool="lookup_order",
        expected_answer_substring="shipped",
        golden_trajectory=["invoke_agent", "lookup_order"],
    ),
    EvalCase(
        question="has order 1042 shipped yet?",
        expected_tool="lookup_order",
        expected_answer_substring="processing",
        golden_trajectory=["invoke_agent", "lookup_order"],
    ),
    EvalCase(
        question="is SK-ROCKET in stock?",
        expected_tool="check_inventory",
        expected_answer_substring="14",
        golden_trajectory=["invoke_agent", "check_inventory"],
    ),
    EvalCase(
        question="can I return an item I don't like?",
        expected_tool="search_policy",
        expected_answer_substring="30 days",
        golden_trajectory=["invoke_agent", "search_policy"],
    ),
    EvalCase(
        question="how long does shipping take?",
        expected_tool="search_policy",
        expected_answer_substring="business days",
        golden_trajectory=["invoke_agent", "search_policy"],
    ),
]


def load_from_production_traces(opensearch_url: str | None = None) -> list[EvalCase]:
    """Blog Part 8: harvest failing/surprising traces into new eval cases.

    Sketch of the real implementation:

        1. PPL query for error spans or high-token / looped traces:
           source=otel-v1-apm-span-*
             | where `status.code` = 2 OR <chat-step-count> > MAX_CHAT_STEPS
        2. For each, pull the original question and the tool path taken.
        3. A human (or an LLM) labels the expected_tool / expected_answer.
        4. Append the labeled EvalCase to your dataset.

    Returns [] by default so the suite runs offline. Point it at your stack to
    close the loop with real traffic.
    """
    return []


def full_dataset() -> list[EvalCase]:
    return [*GOLDEN_CASES, *load_from_production_traces()]
