# Acme Support Agent — OpenSearch AI Observability Tutorial

A runnable example agent for the OpenSearch AI observability stack. Clone it,
`docker compose up`, run the agent on **your** framework, and watch the traces,
metrics, and eval scores land in OpenSearch.

This is the companion repo to the blog post *"From day one to healthy production:
instrumenting and evaluating AI agents with OpenSearch."* It threads one example
agent — a customer-support bot for a fictional store — through the whole journey:
**instrument → verify → observe → evaluate → monitor → close the loop.**

## What the agent does

The Acme Support Agent answers customer questions using three deterministic tools:

| Tool | Returns |
|---|---|
| `lookup_order(order_id)` | order status, items, ship date |
| `check_inventory(sku)` | stock count |
| `search_policy(query)` | RAG over a returns/shipping policy doc |

Because the tools return fixed data, evaluation is objective — *did the agent call
`lookup_order` with `1007` when asked "where's my order #1007?"* — and there's a clear
**golden path** for trajectory comparison.

It exercises every span type the stack cares about: `invoke_agent` → `chat` →
`execute_tool` → `retrieval` / `embeddings`.

## Pick your framework

The agent logic and observability code are written **once**. Only the model/tool-calling
layer changes per framework, and the SDK instruments all of them identically.

| Runtime | Frameworks | Path |
|---|---|---|
| **Python** | OpenAI · Anthropic · Bedrock · LangChain · LlamaIndex | [`python/`](python/) — native SDK |
| **TypeScript** | raw OpenTelemetry (native SDK [in development](https://github.com/opensearch-project/genai-observability-sdk-js)) | [`typescript/`](typescript/) |

## Quick start

The stack is the official [observability-stack](https://github.com/opensearch-project/observability-stack),
included in this repo as a pinned git submodule at `observability-stack/` (repo root).

```bash
# 1. clone with the observability-stack submodule
git clone --recurse-submodules https://github.com/anirudha/os-agent-observability-evals.git
cd os-agent-observability-evals

# 2. bring up the stack (OpenSearch, OTel Collector, Data Prepper, Prometheus, Dashboards)
cd observability-stack && docker compose up -d
cd ../acme-support-agent

# 3. wait for green, then run the verify script
./verify/check-stack.sh

# 4. run the agent (Python example)
cd python
pip install -e ".[openai]"          # or [anthropic], [bedrock], [langchain], [llamaindex], [all]
export OPENAI_API_KEY=sk-...
python -m acme.run "where is my order #1007?"

# 5. confirm telemetry landed
cd ..
./verify/check-instrumentation.sh

# 6. run the eval suite
cd python
python -m evals.run_evals
```

Then open OpenSearch Dashboards at http://localhost:5601 (admin / `My_password_123!@#`)
to explore the traces.

## Repo layout

```
acme-support-agent/
├── docker-compose.yml          # the full local stack
├── infra/                      # collector, data-prepper, prometheus config
├── python/                     # native SDK agent (all frameworks)
│   ├── acme/                   # agent + tools + framework adapters
│   └── evals/                  # dataset + golden paths + eval runner
├── typescript/                 # raw-OTel agent (interim path)
└── verify/                     # stack + instrumentation health checks
```

## The journey, mapped to this repo

Full index with read / code / run links for every part: [`docs/README.md`](docs/README.md).

| Blog part | Where in the repo |
|---|---|
| 1 — Define goals | [`python/evals/criteria.py`](python/evals/criteria.py) |
| 2 — Stand up the stack | [`docker-compose.yml`](docker-compose.yml) |
| 3 — Instrument | [`python/acme/observability.py`](python/acme/observability.py), [`typescript/src/observability.ts`](typescript/src/observability.ts) |
| 4 — Verify | [`verify/`](verify/) |
| 5 — Observe | [`verify/queries.md`](verify/queries.md) |
| 6 — Evaluate | [`python/evals/`](python/evals/) |
| 7 — Monitor production | [`infra/prometheus/`](infra/prometheus/), [`docs/production.md`](docs/production.md) |
| 8 — Close the loop | [`python/evals/dataset.py`](python/evals/dataset.py) |

## Credentials

This is a **local development** setup. The default OpenSearch credentials
(`admin` / `My_password_123!@#`) and the `-k` TLS skip are for local use only —
never use these in production. See [`docs/production.md`](docs/production.md) for the
AWS-managed path (Amazon OpenSearch Service + Amazon Managed Prometheus with SigV4).
