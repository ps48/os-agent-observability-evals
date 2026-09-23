# Acme Agent Dashboards

Two custom OpenSearch Dashboards for the Acme Support Agent, built entirely from
**PPL** and **PromQL** `explore` panels (the same saved-object type the stack's own
samples use):

- **Acme Agent — Run Details** — LLM calls, models used, tokens in/out, success vs
  failure, sessions, tokens over time (PPL over `otel-v1-apm-span*`), plus span
  ingest/export throughput and export failures (PromQL over the collector's
  `otelcol_*` self-metrics).
- **Acme Agent — Evals** — eval runs, overall pass %, score events, average score
  and event counts per metric, average score over time, and failing evals by metric
  (PPL over the `evaluation` spans).

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

## Notes

- **PromQL scope:** the Python SDK exports traces only, so no per-agent metrics reach
  Prometheus — the PromQL panels use the collector's `otelcol_*` self-metrics
  (span ingest/export rate, export failures). All agent- and eval-specific numbers
  come from PPL over the traces index.
- Token fields are cast (`cast(... as int)`) in PPL sums, matching `verify/queries.md`.
- The dashboards read `endTime` as the time field for the span index pattern.
