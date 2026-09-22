"""In-process token accumulator (mirrors run_evals._called_tools).

Framework adapters call record_usage() per model call; the eval runner resets
before a case and reads get_usage() after, so cost can be scored without querying
the trace store. Thread-local because eval cases run sequentially per thread.
"""
from __future__ import annotations
import threading

_local = threading.local()

def reset_usage() -> None:
    _local.input_tokens = 0
    _local.output_tokens = 0

def record_usage(input_tokens: int = 0, output_tokens: int = 0) -> None:
    _local.input_tokens = getattr(_local, "input_tokens", 0) + int(input_tokens or 0)
    _local.output_tokens = getattr(_local, "output_tokens", 0) + int(output_tokens or 0)

def get_usage() -> dict:
    i = getattr(_local, "input_tokens", 0)
    o = getattr(_local, "output_tokens", 0)
    return {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}
