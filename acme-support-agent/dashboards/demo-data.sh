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

echo "done — wait ~90s for Data Prepper ingestion, then refresh the dashboards"
