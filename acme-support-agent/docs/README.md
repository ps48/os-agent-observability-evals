# The journey — docs index

The tutorial walks eight parts, from first instrumentation to a self-improving
production agent. The narrative lives in [`../../blog.md`](../../blog.md); this index
maps each part to **where it lives in the repo** and **how to run it**.

> Only Part 7 has its own deep-dive page ([`production.md`](production.md)) because the
> AWS-managed path needs extra setup. Every other part is implemented directly in code —
> the table below is your map to it.

| Part | Step | Read | Code | Run |
|---|---|---|---|---|
| **1** | Define goals → eval criteria | [blog §Part 1](../../blog.md#part-1--define-goals-first) | [`python/evals/criteria.py`](../python/evals/criteria.py) | — |
| **2** | Stand up the stack | [blog §Part 2](../../blog.md#part-2--stand-up-the-stack) | [`observability-stack/docker-compose.yml`](../../observability-stack/docker-compose.yml) (pinned submodule) | `docker compose up -d` |
| **3** | Instrument your framework | [blog §Part 3](../../blog.md#part-3--instrument) | [`python/acme/observability.py`](../python/acme/observability.py), [`python/acme/frameworks/`](../python/acme/frameworks/), [`typescript/src/observability.ts`](../typescript/src/observability.ts) | `pip install -e ".[openai]"` |
| **4** | Verify telemetry lands | [blog §Part 4](../../blog.md#part-4--verify-instrumentation) | [`verify/check-stack.sh`](../verify/check-stack.sh), [`verify/check-instrumentation.sh`](../verify/check-instrumentation.sh) | `./verify/check-instrumentation.sh` |
| **5** | Observe & debug | [blog §Part 5](../../blog.md#part-5--observe-and-debug) | [`verify/queries.md`](../verify/queries.md) | paste PPL in Dashboards |
| **6** | Evaluate against a dataset | [blog §Part 6](../../blog.md#part-6--evaluate) | [`python/evals/dataset.py`](../python/evals/dataset.py), [`python/evals/run_evals.py`](../python/evals/run_evals.py) | `python -m evals.run_evals` |
| **7** | Monitor production | [blog §Part 7](../../blog.md#part-7--ship-and-monitor-production) | [**`production.md`**](production.md) (Prometheus config now lives in the `observability-stack` submodule) | see [production.md](production.md) |
| **8** | Close the loop | [blog §Part 8](../../blog.md#part-8--close-the-loop) | [`python/evals/dataset.py`](../python/evals/dataset.py) → `load_from_production_traces()` | — |

## Suggested reading order

1. Skim [`../../blog.md`](../../blog.md) end to end for the narrative.
2. Follow the [repo README quick start](../README.md#quick-start) to run the agent once.
3. Use this table to jump to whichever part you want to go deeper on.

## Pages in this folder

- [`production.md`](production.md) — Part 7 deep dive: the AWS-managed path
  (Amazon OpenSearch Service + Amazon Managed Prometheus, SigV4 auth), RED metrics,
  SLO burn-rate alerts, and online evaluation.
