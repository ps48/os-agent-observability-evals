"""Eval runner — Blog Part 6.

Runs the agent over the dataset, scores each case against the criteria, attaches
the scores to the trace via score(), and prints a summary table. This is the
"run evals in a loop" step: run it, read the failures, fix the prompt/tools, re-run.

Usage:
  python -m evals.run_evals
  python -m evals.run_evals --framework anthropic
"""

from __future__ import annotations

import argparse
import time

from acme.observability import setup_observability, observe, enrich, score, Op
from acme.agent import handle_support_question
from acme.tools import TOOL_FUNCTIONS
from acme.usage import reset_usage, get_usage

from .dataset import full_dataset, EvalCase
from . import criteria


# We track which tools got called per case by wrapping the tool registry.
_called_tools: list[str] = []


def _instrument_tool_tracking():
    """Wrap each tool so we can observe which were called during a case."""
    import acme.tools as tools_mod

    for name, fn in list(TOOL_FUNCTIONS.items()):
        def make_tracker(orig, tool_name):
            def tracker(*args, **kwargs):
                _called_tools.append(tool_name)
                return orig(*args, **kwargs)
            return tracker
        TOOL_FUNCTIONS[name] = make_tracker(fn, name)
        # also patch the module-level reference used by adapters
        setattr(tools_mod, name, TOOL_FUNCTIONS[name])


@observe(op=Op.INVOKE_AGENT, name="eval_case")
def run_case(case: EvalCase, framework: str | None) -> dict:
    """Run one eval case and score it. Scores are attached to this span."""
    _called_tools.clear()
    reset_usage()
    enrich(eval_question=case.question, expected_tool=case.expected_tool)

    start = time.time()
    answer = handle_support_question(
        case.question,
        conversation_id=case.conversation_id,
        framework=framework,
    )
    elapsed = time.time() - start

    # --- score against criteria (Blog Part 1 goals) ---
    correctness = criteria.judge_answer_correctness(
        case.question, answer, case.expected_answer_substring)
    right_tool = 1.0 if case.expected_tool in _called_tools else 0.0
    no_loops = criteria.judge_no_loops(_called_tools.count(case.expected_tool) or len(_called_tools))
    latency_ok = criteria.judge_latency(elapsed)
    total_tokens = get_usage()["total_tokens"]
    cost_ok = criteria.judge_cost(total_tokens)
    # trajectory check: did the tool path match the golden path?
    actual_traj = ["invoke_agent", *_called_tools]
    trajectory_match = 1.0 if actual_traj[: len(case.golden_trajectory)] == case.golden_trajectory else 0.0

    # attach every score to the trace
    score(name="answer_correctness", value=correctness)
    score(name="right_tool", value=right_tool)
    score(name="trajectory_match", value=trajectory_match)
    score(name="latency_ok", value=latency_ok)
    score(name="no_loops", value=no_loops)
    score(name="cost", value=cost_ok)

    return {
        "question": case.question,
        "answer": answer,
        "tools_called": list(_called_tools),
        "correctness": correctness,
        "right_tool": right_tool,
        "trajectory_match": trajectory_match,
        "latency_s": round(elapsed, 2),
        "tokens": total_tokens,
        "no_loops": no_loops,
        "cost": cost_ok,
        "passed": all([correctness, right_tool, trajectory_match, latency_ok, no_loops, cost_ok]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Acme eval suite.")
    parser.add_argument("--framework", default=None)
    args = parser.parse_args()

    setup_observability()
    _instrument_tool_tracking()

    dataset = full_dataset()
    results = [run_case(c, args.framework) for c in dataset]

    # --- summary ---
    passed = sum(r["passed"] for r in results)
    print("\n" + "=" * 72)
    print(f"  ACME EVAL RESULTS — {passed}/{len(results)} passed")
    print("=" * 72)
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        print(f"{mark}  {r['question']}")
        print(f"      tools={r['tools_called']}  correct={r['correctness']:.0f}  "
              f"traj={r['trajectory_match']:.0f}  loops_ok={r['no_loops']:.0f}  "
              f"cost_ok={r['cost']:.0f}  tok={r['tokens']}  {r['latency_s']}s")
        if not r["passed"]:
            print(f"      answer: {r['answer'][:90]}")
    print("=" * 72)
    print("Scores are attached to traces — query them in OpenSearch by score name.\n")


if __name__ == "__main__":
    main()
