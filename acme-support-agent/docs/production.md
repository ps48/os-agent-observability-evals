# Going to production — Blog Part 7

Production is a **config change, not a code change.** The agent code, spans, and
PPL queries are identical; only the endpoint and authentication change.

## 1. Point telemetry at AWS-managed backends

Local dev sends to the OTel Collector on `localhost:4318`, which fans out to a local
OpenSearch and Prometheus. In production you run the collector in your VPC and target:

- **Amazon OpenSearch Service** for traces/logs
- **Amazon Managed Service for Prometheus (AMP)** for metrics

The agent only needs the collector endpoint changed:

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://otel-collector.internal:4318/v1/traces
```

## 2. Authentication: SigV4 instead of basic auth

Local uses `admin` / password over `-k`. AWS-managed endpoints use SigV4 and real
TLS (no `-k`). Querying traces on Amazon OpenSearch Service:

```bash
curl -s --aws-sigv4 "aws:amz:$REGION:es" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
  -X POST "https://$DOMAIN_ID.$REGION.es.amazonaws.com/_plugins/_ppl" \
  -H 'Content-Type: application/json' \
  -d '{"query": "source=otel-v1-apm-span-* | where `attributes.gen_ai.operation.name` = '\''invoke_agent'\'' | head 20"}'
```

Querying AMP:

```bash
curl -s --aws-sigv4 "aws:amz:$REGION:aps" \
  --user "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
  "https://aps-workspaces.$REGION.amazonaws.com/workspaces/$WORKSPACE_ID/api/v1/query" \
  --data-urlencode 'query=acme:agent_latency:p95_5m'
```

The PPL and PromQL syntax are unchanged from local.

## 3. RED metrics, SLOs, and alerts

The local `infra/` directory (and its `prometheus/rules.yml`) has been
removed; Prometheus configuration for the stack itself now lives in the
`observability-stack` submodule (see
[`observability-stack/docker-compose/prometheus/`](../../observability-stack/docker-compose/prometheus/),
including the health-alerting rule group in
[`rules-stack/stack-alerts.yml`](../../observability-stack/docker-compose/prometheus/rules-stack/stack-alerts.yml)
as a format example). Write your own recording rules and burn-rate alerts on top of
the `gen_ai.*`-derived metrics for:

- **Rate** — agent invocations/sec per agent
- **Errors** — error ratio per agent
- **Duration** — p95 latency per agent
- **Cost** — output tokens/sec per model
- **SLO alerts** — fast burn on the "95% under 4s" latency SLO, and a 5% error-rate alert

Load these into AMP via the rules API or your IaC, and wire the alerts to your pager.

## 4. Online evaluation

Offline evals (Part 6) gate deploys. **Online** evals catch drift in production: keep
calling `score()` on a sample of live traffic so answer-correctness and trajectory
scores keep flowing onto live traces. Query them the same way as offline scores.

## 5. Close the loop

Failing and surprising production traces feed back into the eval dataset — see
[`../python/evals/dataset.py`](../python/evals/dataset.py) `load_from_production_traces()`.
That's Blog Part 8: prod traces → dataset → re-eval → ship → repeat.
