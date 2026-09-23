"""Eval criteria — Blog Part 1, "define goals first."

Each goal from the blog becomes a concrete, checkable criterion here. Some are
deterministic (right tool, no loops); the answer-correctness one is where an
LLM-as-judge would plug in. We keep a simple substring judge as the default so the
suite runs with no extra dependencies, and show where to swap in a real judge.
"""

from __future__ import annotations

import os

from acme.mock import mock_enabled


# Goal -> criterion mapping (mirrors the table in blog Part 1).
GOALS = {
    "answer_correctness": "Final answer contains the expected fact.",
    "right_tool": "Agent called the expected tool for the question.",
    "cost": "Total tokens stayed under budget.",
    "latency": "Answer returned under the latency budget.",
    "no_loops": "Agent did not exceed the max reasoning steps.",
}

TOKEN_BUDGET = 4000          # per request
LATENCY_BUDGET_S = 8.0       # per request
MAX_CHAT_STEPS = 3           # more than this is a loop


def judge_answer_correctness(question: str, answer: str, expected_substring: str) -> float:
    """Substring match by default; opt-in LLM-as-judge via ACME_LLM_JUDGE=1.

    Set ACME_LLM_JUDGE=1 to score with Bedrock (falls back to substring on any
    error). DeepEval/Ragas variants show alternative judges.
    """
    if not answer:
        return 0.0
    if os.environ.get("ACME_LLM_JUDGE") == "1":
        verdict = _llm_judge(question, answer, expected_substring)
        if verdict is not None:
            return verdict
    return 1.0 if expected_substring.lower() in answer.lower() else 0.0


def _llm_judge(question: str, answer: str, expected: str):
    """Return 1.0/0.0 from a Bedrock judge, or None if the call is unavailable."""
    if mock_enabled():
        return 1.0 if expected.lower() in answer.lower() else 0.0
    try:
        import boto3
        region = os.environ.get("AWS_REGION", "us-west-2")
        model = os.environ.get("ACME_JUDGE_MODEL",
                               os.environ.get("ACME_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"))
        client = boto3.client("bedrock-runtime", region_name=region)
        prompt = (
            f"Question: {question}\n"
            f"The answer is correct if it contains this fact: {expected!r}\n"
            f"Answer: {answer}\n"
            "Reply with exactly '1' if correct, otherwise '0'."
        )
        resp = client.converse(modelId=model, messages=[{"role": "user", "content": [{"text": prompt}]}])
        txt = "".join(b.get("text", "") for b in resp["output"]["message"]["content"]).strip()
        return 1.0 if txt.startswith("1") else 0.0
    except Exception:
        return None


def judge_no_loops(chat_step_count: int) -> float:
    return 1.0 if chat_step_count <= MAX_CHAT_STEPS else 0.0


def judge_cost(total_tokens: int) -> float:
    return 1.0 if total_tokens <= TOKEN_BUDGET else 0.0


def judge_latency(seconds: float) -> float:
    return 1.0 if seconds <= LATENCY_BUDGET_S else 0.0
