#!/usr/bin/env bash
# Generate a deterministic mix of success + failure telemetry (mock mode, offline)
# so the Acme dashboards demo real error / latency / loop / cost scenarios.
#
#   ./acme-support-agent/dashboards/demo-data.sh
#
# Requires: the observability stack running locally (OTLP on 4318) and the venv
# at acme-support-agent/python/.venv. No cloud credentials are used (mock mode).
set -uo pipefail
cd "$(dirname "$0")/../python"
PY=.venv/bin/python

unset AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY
export ACME_MOCK=1
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="http://localhost:4318/v1/traces"
export OTEL_SERVICE_NAME=acme-support-agent

Q=("where is my order #1007?" "has order 1042 shipped yet?" "did order 1099 arrive?"
   "is SK-ROCKET in stock?" "do you have RB-GIANT available?" "can I return an item I don't like?"
   "how long does shipping take?" "my item arrived damaged, what now?")

echo "== baseline success traffic =="
for q in "${Q[@]}"; do "$PY" -m acme.run "$q" >/dev/null 2>&1; done
"$PY" -m evals.run_evals >/dev/null 2>&1 && echo "  clean eval pass done"

echo "== LLM/tool errors (status.code=2) =="
for i in 1 2 3; do ACME_FAULT=error "$PY" -m acme.run "where is my order #1007?" >/dev/null 2>&1; done
echo "  3 error traces emitted"

echo "== eval failures: slow / loop / wrong / cost =="
for f in slow loop wrong cost; do
  echo "  - ACME_FAULT=$f"
  ACME_FAULT=$f "$PY" -m evals.run_evals >/dev/null 2>&1
done

echo "== extra experiment runs (for run-vs-run comparison) =="
for exp in prompt-v1 prompt-v2; do
  ACME_EXPERIMENT=$exp "$PY" -m evals.run_evals >/dev/null 2>&1 && echo "  ran experiment $exp"
done

echo "== online evals on sampled live traffic (eval_mode=online) =="
for q in "${Q[@]}"; do ACME_ONLINE_EVAL_RATE=1 "$PY" -m acme.run "$q" >/dev/null 2>&1; done
echo "  online eval traffic emitted"

# Cosmetic demo aid: the generator emits every trace "now", which piles all points
# into one time bucket and leaves the trend charts + KPI sparklines flat. Spread each
# trace deterministically across the last ~6h (by a hash of its traceId, preserving
# intra-trace timing) so the dashboards render like a continuously-running agent.
# Waits for ingestion first. Skip the whole step with SPREAD=0.
if [ "${SPREAD:-1}" = "1" ]; then
  echo "== waiting ~95s for Data Prepper ingestion, then spreading traces across ~6h =="
  sleep 95
  OS_URL="${OPENSEARCH_URL:-https://localhost:9200}"
  OS_AUTH="${OPENSEARCH_USER:-admin}:${OPENSEARCH_PASSWORD:-My_password_123!@#}"
  curl -sk -u "$OS_AUTH" -X POST "$OS_URL/otel-v1-apm-span*/_update_by_query?refresh=true&conflicts=proceed&wait_for_completion=true" \
    -H 'Content-Type: application/json' \
    -d '{"script":{"lang":"painless","source":"int h = ctx._source.traceId.hashCode(); if (h < 0) { h = -h; } long off = (long)(h % 360) * 60L; def fs = [\"startTime\",\"endTime\",\"time\"]; for (int i=0;i<fs.size();i++){ String f = fs.get(i); if (ctx._source.containsKey(f) && ctx._source[f] != null){ ctx._source[f] = Instant.parse(ctx._source[f]).minusSeconds(off).toString(); } }"}}' \
    >/dev/null 2>&1 && echo "  spread done — refresh the dashboards" \
    || echo "  spread skipped (OpenSearch not reachable at $OS_URL); trends fill in as the agent runs over time"
else
  echo "done — wait ~90s for Data Prepper ingestion, then refresh the dashboards (SPREAD=0: trends fill in over time)"
fi
