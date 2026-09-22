# Observe & debug — PPL query cookbook (Blog Part 5)

Copy-paste PPL queries for exploring the Acme agent's traces. All use the local
stack defaults (`admin` / `My_password_123!@#`, `-k` to skip TLS verification).
Run them via the PPL API or paste the query body into OpenSearch Dashboards →
Observability → PPL.

Data Prepper stores OTel span attributes as a nested `attributes` object with
dot-path keys, so `gen_ai.operation.name` is queried as
`` `attributes.gen_ai.operation.name` ``; resource attributes use
`resource.attributes.…` and event attributes use `events.attributes.…`. The
queries below use those nested names.

Set these once:

```bash
OS=https://localhost:9200
AUTH='admin:My_password_123!@#'
ppl() { curl -sk -u "$AUTH" -X POST "$OS/_plugins/_ppl" -H 'Content-Type: application/json' -d "{\"query\": \"$1\"}"; }
```

## Reconstruct one trace (the full reasoning tree)

```bash
ppl "source=otel-v1-apm-span-* | where traceId = '<TRACE_ID>' | fields spanId, parentSpanId, name, \`attributes.gen_ai.operation.name\`, durationInNanos, startTime | sort startTime"
```

## Recent agent invocations

```bash
ppl "source=otel-v1-apm-span-* | where \`attributes.gen_ai.operation.name\` = 'invoke_agent' | fields traceId, \`attributes.gen_ai.agent.name\`, durationInNanos, startTime | sort - startTime | head 20"
```

## Slow agent invocations (> 5s)

```bash
ppl "source=otel-v1-apm-span-* | where \`attributes.gen_ai.operation.name\` = 'invoke_agent' AND durationInNanos > 5000000000 | fields traceId, \`attributes.gen_ai.agent.name\`, durationInNanos | sort - durationInNanos"
```

## Error spans (status.code = 2 is ERROR in OTel)

```bash
ppl "source=otel-v1-apm-span-* | where \`status.code\` = 2 | fields traceId, serviceName, name, \`events.attributes.exception.message\`, startTime | sort - startTime | head 20"
```

## Token usage by model (cost signal)

```bash
ppl "source=otel-v1-apm-span-* | where cast(\`attributes.gen_ai.usage.input_tokens\` as int) > 0 | stats sum(cast(\`attributes.gen_ai.usage.input_tokens\` as int)) as in_tokens, sum(cast(\`attributes.gen_ai.usage.output_tokens\` as int)) as out_tokens by \`attributes.gen_ai.request.model\`"
```

## Tool call inspection (arguments + results)

```bash
ppl "source=otel-v1-apm-span-* | where \`attributes.gen_ai.operation.name\` = 'execute_tool' | fields \`attributes.gen_ai.tool.name\`, \`attributes.gen_ai.tool.call.arguments\`, \`attributes.gen_ai.tool.call.result\`, durationInNanos, startTime | sort - startTime | head 20"
```

## Multi-turn conversation tracking

```bash
ppl "source=otel-v1-apm-span-* | where \`attributes.gen_ai.conversation.id\` != '' | stats count() as turns, sum(cast(\`attributes.gen_ai.usage.input_tokens\` as int)) as in_tokens by \`attributes.gen_ai.conversation.id\`"
```

## Eval scores (Blog Part 6) — find low-scoring runs

```bash
# score() emits one `evaluation` span per metric, carrying gen_ai.evaluation.name
# and gen_ai.evaluation.score.value. Group by metric to see the score distribution:
ppl "source=otel-v1-apm-span-* | where \`attributes.gen_ai.operation.name\` = 'evaluation' | stats count() as n by \`attributes.gen_ai.evaluation.name\`, \`attributes.gen_ai.evaluation.score.value\`"
```

## Detect the "looped & hallucinated" failure mode

A trace with multiple `chat` spans and no `execute_tool` is the classic bad case:

```bash
ppl "source=otel-v1-apm-span-* | eval is_chat=if(\`attributes.gen_ai.operation.name\`='chat',1,0), is_tool=if(\`attributes.gen_ai.operation.name\`='execute_tool',1,0) | stats sum(is_chat) as chats, sum(is_tool) as tools by traceId | where chats > 2 AND tools = 0"
```
