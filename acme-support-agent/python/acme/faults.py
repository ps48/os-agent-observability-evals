"""Env-gated fault injection for demos (mock mode only).

Set ACME_FAULT to a comma-separated list to make the mock adapter emit failure
telemetry so the dashboards show real error/latency/loop/cost scenarios:

    error  -> raise a simulated provider error (invoke_agent span = error)
    slow   -> sleep past the latency budget (latency_ok fails, P95 spike)
    loop   -> call the tool repeatedly (no_loops fails)
    wrong  -> call the wrong tool + return a non-answer (correctness/right_tool/trajectory fail)
    cost   -> record a token blowup over budget (cost fails)

Default (unset) leaves behavior unchanged.
"""
from __future__ import annotations
import os


def active_faults() -> set[str]:
    return {f.strip().lower() for f in os.environ.get("ACME_FAULT", "").split(",") if f.strip()}
