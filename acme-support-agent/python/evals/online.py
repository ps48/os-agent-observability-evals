"""Online (production) evaluation — Blog Part 7.

Offline evals (``run_evals.py``) score a fixed dataset against golden answers
before you ship. **Online** evals score a *sample of live traffic* after you
ship — you have no ground-truth answer for a real customer question, so you can
only run the **reference-free** checks (latency, cost, and loop budgets). They
catch the drift and edge cases the offline dataset never imagined.

``score_online`` must be called from **inside** the agent's ``invoke_agent``
span (see ``acme/agent.py``): ``score()`` with no ``trace_id`` attaches the
evaluation span to the current active span, so the online scores land on the
same live trace they evaluate. It is sampled by ``ACME_ONLINE_EVAL_RATE`` and
is a no-op when that rate is 0 (the default).
"""

from __future__ import annotations

import datetime

from acme.observability import score
from . import criteria


def score_online(question: str, answer: str, elapsed_s: float, total_tokens: int,
                 tool_calls: int | None = None) -> None:
    """Score the reference-free checks on one live turn and attach them to the trace."""
    run_id = "online-" + datetime.date.today().strftime("%Y%m%d")
    common = {
        "eval_question": question,
        "test.suite.run.id": run_id,
        "test.suite.name": "online",
        "dataset": "live",
        "eval_mode": "online",
    }

    checks = {
        "latency_ok": criteria.judge_latency(elapsed_s),
        "cost": criteria.judge_cost(total_tokens),
    }
    if tool_calls is not None:
        checks["no_loops"] = criteria.judge_no_loops(tool_calls)

    passed = all(v >= 1 for v in checks.values())
    common["test.case.result.status"] = "pass" if passed else "fail"
    for name, value in checks.items():
        score(name=name, value=value, attributes=common)
