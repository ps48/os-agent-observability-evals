# Acme Agent Dashboards

Two custom OpenSearch Dashboards for the Acme Support Agent, built entirely from
**PPL** and **PromQL** `explore` panels (the same saved-object type the stack's own
samples use):

Modeled on Arize/Phoenix, Braintrust, LangSmith and Langfuse eval + observability
dashboards, within the PPL/PromQL `explore` viz framework:

- **Acme Agent — Run Details** — a full-width **agent-health `state_timeline`** (OK/Error
  per bucket), a **success-rate gauge**, error-rate/P95/cost KPIs (threshold-colored,
  unit-formatted), **latency P50/P95/P99 + a latency `histogram`**, **tokens by model**,
  tokens-in/out **stacked area**, throughput, **tool analytics** table, and a **recent
  error-traces table whose trace IDs link straight to the trace waterfall** (drill-down).
  PromQL panels cover collector span ingest/export rate + failures.
- **Acme Agent — Evals** — eval-runs / **pass-rate gauge** / failed-checks / score-events
  KPIs, a **`bar_gauge` per-check pass rate** (answer_correctness, right_tool, cost, …),
  failing-checks bar, **score + failure trend** (line + stacked area), and a failing-
  checks table (PPL over `evaluation` spans).

Both dashboards carry a **nav header** linking to each other and to the Agent Traces
explorer. Scoped out (not expressible in a static PPL/PromQL dashboard): run-vs-run
experiment diffing, human-annotation queues, drift detection (needs the Anomaly
Detection/Alerting plugins), and the span waterfall itself — which the linked **Agent
Traces app** already provides.

![Run Details](../../images/dashboard-run-details.png)
![Evals](../../images/dashboard-evals.png)

## Install (auto-load on stack start)

`acme-dashboards-init.py` resolves the live `otel-v1-apm-span*` index-pattern id and
the `ObservabilityStack_Prometheus` data connection at runtime, removes the stack's
demo dashboards (Astronomy shop + service telemetry), and creates the two dashboards
(idempotent — fixed object ids, `overwrite=true`).

Bring the stack up with the override so it runs automatically after the stack's own
Dashboards init:

```bash
cd observability-stack
docker compose -f docker-compose.yml \
  -f ../acme-support-agent/dashboards/docker-compose.dashboards.yml up -d
```

The override also sets `INSTALL_VISUALIZATION_SAMPLES=false` so the bundled Flights /
viz-demo samples are skipped.

### Run it by hand (against an already-running stack)

```bash
OSD_BASE_URL=http://localhost:5601 python acme-support-agent/dashboards/acme-dashboards-init.py
```

Env: `OSD_BASE_URL`, `OSD_USER` (default `admin`), `OSD_PASSWORD`, `WORKSPACE_NAME`
(default `Observability Stack`), `SPAN_PATTERN` (default `otel-v1-apm-span*`).

## Demo data (fault injection)

To populate the dashboards with a realistic **mix of successes and failures**, run the
mock-mode generator (offline, deterministic, no credentials):

```bash
./acme-support-agent/dashboards/demo-data.sh   # stack must be running (OTLP on 4318)
```

It drives baseline success traffic + a clean eval pass, then injects failures via the
`ACME_FAULT` env flag (mock adapter only, see `python/acme/faults.py`):

| `ACME_FAULT` | Effect | Shows up as |
|---|---|---|
| `error` | raises a simulated `ThrottlingException` | error-rate %, error-traces table, status.code=2 |
| `slow`  | sleeps past the 8s budget | P95 latency spike, `latency_ok` failures |
| `loop`  | repeats the tool call | `no_loops` failures |
| `wrong` | wrong tool + non-answer | `answer_correctness` / `right_tool` / `trajectory_match` failures |
| `cost`  | records a token blowup over budget | `cost` failures, big token bars |

Wait ~90s for Data Prepper ingestion, then refresh the dashboards. Default (no
`ACME_FAULT`) behavior is unchanged.

## Notes

- **PromQL scope:** the Python SDK exports traces only, so no per-agent metrics reach
  Prometheus — the PromQL panels use the collector's `otelcol_*` self-metrics
  (span ingest/export rate, export failures). All agent- and eval-specific numbers
  come from PPL over the traces index.
- Token fields are cast (`cast(... as int)`) in PPL sums, matching `verify/queries.md`.
- The dashboards read `endTime` as the time field for the span index pattern.
