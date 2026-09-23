# Acme Agent Dashboards

Two curated OpenSearch Dashboards for the Acme Support Agent, built entirely from
**PPL** and **PromQL** `explore` panels (the same saved-object type the stack's own
samples use) plus Markdown overview blocks. Modeled on the eval + observability tools
teams already know — Arize/Phoenix, Braintrust, LangSmith, Langfuse — but expressed in
the PPL/PromQL `explore` framework:

- **Acme Agent — Run Details** — live health, latency, cost, and error triage.
- **Acme Agent — Evals** — automated eval quality: pass rate, per-check scores, trends.

Both open with an **overview block** (what the dashboard is, how to use it, and links to
its sibling + the Agent Traces explorer), a **filter variable** (Model / Check) that
defaults to *All*, and KPI cards that show a **trend sparkline** behind the big number.

![Run Details](../../images/dashboard-run-details.png)
![Evals](../../images/dashboard-evals.png)

## Acme Agent — Run Details

| Panel | Answers | Chart | Query source |
|---|---|---|---|
| Agent health over time | Is the agent up? when did it error? | `state_timeline` | `max(status.code)` by 10-min bucket over `invoke_agent` spans (0→OK green, 2→Error red) |
| Agent runs | How many invocations? | metric + sparkline | `count()` of `invoke_agent` by bucket |
| Success rate | % of runs that didn't error | gauge | `avg(status.code≠2)` |
| Error rate | % of runs that errored | metric + sparkline | `avg(status.code=2)` by bucket |
| P95 latency | Tail latency (threshold-colored) | metric + sparkline | `percentile(durationInNanos,95)` by bucket |
| Est. cost $ | Rough $ from token sums (**Model**-filtered) | metric + sparkline | `sum(in)·$3/M + sum(out)·$15/M` by bucket |
| P50 / P95 / P99 (s) | Latency percentiles | metric + sparkline | `percentile(durationInNanos, N)` by bucket |
| Latency distribution (s) | Shape of the latency spread | `histogram` | per-span duration in seconds |
| Tokens by model | Which model burns tokens (**Model**-filtered) | bar | `sum(total_tokens)` by `request.model` |
| Tokens in vs out over time | Input/output token trend (**Model**-filtered) | stacked area | `sum(in)`, `sum(out)` by bucket |
| Tool analytics | Which tools run, how often, how slow | table | `count()`, `avg(durationInNanos)` by `tool.name` over `execute_tool` spans |
| Throughput (runs / 10m) | Traffic shape | line | `count()` of `invoke_agent` by bucket |
| Recent error traces | The 20 latest failures — **click a trace ID to open the span waterfall** | table + data-link | `status.code=2`, fields `traceId, endTime, name, exception.message` |
| Span ingest vs export rate | Is the collector keeping up? | line (PromQL) | `otelcol_receiver_accepted_spans_total` vs `otelcol_exporter_sent_spans_total` |
| Span export failures | Dropped spans | metric (PromQL) | `otelcol_exporter_send_failed_spans_total` |

## Acme Agent — Evals

| Panel | Answers | Chart | Query source |
|---|---|---|---|
| Eval runs | How many eval cases ran? | metric + sparkline | `count()` of eval `invoke_agent` spans (not Check-filtered) |
| Overall pass rate | Aggregate quality (**Check**-filtered) | gauge | `avg(evaluation.score.value)` |
| Failed checks | How many checks scored < 1 (**Check**-filtered) | metric + sparkline | `count()` where score `< 1` by bucket |
| Score events | Total scored checks (**Check**-filtered) | metric + sparkline | `count()` of `evaluation` spans by bucket |
| Pass rate by check | Which criterion is weakest (**Check**-filtered) | `bar_gauge` | `avg(score)` by `evaluation.name`, threshold-colored |
| Failing checks by metric | Where failures concentrate (**Check**-filtered) | bar | `count()` where score `< 1` by `evaluation.name` |
| Avg score over time | Per-check regression trend (**Check**-filtered) | line | `avg(score)` by bucket, `evaluation.name` |
| Failing checks over time | Failure trend (**Check**-filtered) | stacked area | `count()` where score `< 1` by bucket, `evaluation.name` |
| Failing checks (table) | The failing criteria, ranked (**Check**-filtered) | table | `count()` where score `< 1` by `evaluation.name` |

## How to read it

- **Health strip** — one row of 10-minute buckets colored green (all runs OK) or red (any
  `status.code=2` in the bucket). A red band tells you *when* to zoom the time picker.
- **Gauges vs sparkline cards** — deliberate contrast. Gauges (success rate, pass rate) show
  *current health* against thresholds; the KPI cards show a *trend* (the sparkline behind the
  number is the same metric bucketed over the window).
- **Filter variables** — the **Model** (Run Details) and **Check** (Evals) dropdowns default to
  *All*. Selecting one value scopes the model/cost/token panels (Model) or every eval panel
  (Check). `Eval runs` stays unfiltered on purpose — it counts eval *cases*, which carry no
  `evaluation.name`. Model-independent panels (health, latency, tools, pipeline) are likewise
  left unfiltered, since those spans carry no `request.model`.
- **Trace drill-down** — in *Recent error traces*, the `traceId` column is a data-link to the
  span waterfall in the Agent Traces app (opens in a new tab). Nav links and the drill-down
  carry the `now-24h` window across.

## Install (auto-load on stack start)

`acme-dashboards-init.py` resolves the live `otel-v1-apm-span*` index-pattern id and the
`ObservabilityStack_Prometheus` data connection at runtime, removes the stack's demo dashboards
(Astronomy shop + service telemetry), queries the distinct Model / Check values so the filter
variables default to *All*, and creates the two dashboards (idempotent — fixed object ids,
`overwrite=true`).

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

Env: `OSD_BASE_URL`, `OSD_USER` (default `admin`), `OSD_PASSWORD`, `OPENSEARCH_URL`
(default `https://localhost:9200`, used to seed the filter variables' default-All values),
`WORKSPACE_NAME` (default `Observability Stack`), `SPAN_PATTERN` (default `otel-v1-apm-span*`),
and **`OSD_PUBLIC_URL`** — the browser-facing base used for the nav links and the error-table
**trace-ID drill-down** (data-links require an absolute URL). Defaults to `http://localhost:5601`;
set it to your published URL when serving remotely, e.g.
`OSD_PUBLIC_URL=https://my-host python .../acme-dashboards-init.py`. Nav links carry the
`now-24h` time range across to the Agent Traces app.

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
- **Filter defaults:** OpenSearch query-variables reset to the first option when no `current`
  is stored, so the init script seeds `current` with every value (== *All*). Re-running the
  init refreshes that list as new models / checks appear.
- Token fields are cast (`cast(... as int)`) in PPL sums, matching `verify/queries.md`.
- The dashboards read `endTime` as the time field for the span index pattern.
- **Scoped out** (not expressible in a static PPL/PromQL dashboard): run-vs-run experiment
  diffing, human-annotation queues, drift detection (needs the Anomaly Detection / Alerting
  plugins), and the span waterfall itself — which the linked **Agent Traces app** provides.
