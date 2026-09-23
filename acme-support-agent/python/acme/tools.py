"""The three Acme tools, plus their JSON-schema definitions.

The tools return deterministic, fixed data so that evaluation can be objective:
given a question, there is exactly one correct tool call and one correct answer.

Each tool is wrapped with @observe(op=Op.EXECUTE_TOOL) so it shows up as an
`execute_tool` span with the gen_ai.tool.* attributes attached. The framework
adapters call these same functions, so tool behavior is identical everywhere.
"""

from __future__ import annotations

import os
import json

from .observability import observe, enrich, Op
from .mock import mock_enabled

# ---------------------------------------------------------------------------
# Fake backing data (a real agent would hit a DB / service here).
# ---------------------------------------------------------------------------

_ORDERS = {
    "1007": {"status": "shipped", "items": ["Acme Rocket Skates"], "ship_date": "2026-06-09"},
    "1042": {"status": "processing", "items": ["Acme Giant Rubber Band"], "ship_date": None},
    "1099": {"status": "delivered", "items": ["Acme Anvil"], "ship_date": "2026-06-01"},
}

_INVENTORY = {
    "SK-ROCKET": 14,
    "RB-GIANT": 0,
    "ANVIL-XL": 230,
}

_POLICY_DOC = {
    "returns": "Items may be returned within 30 days of delivery for a full refund.",
    "shipping": "Standard shipping is 3-5 business days. Express is next-day.",
    "damaged": "Damaged items are replaced free of charge; contact support within 7 days.",
}


# ---------------------------------------------------------------------------
# Tools — each emits an execute_tool span.
# ---------------------------------------------------------------------------

# @observe(op=Op.EXECUTE_TOOL, name=...) automatically captures the function's
# arguments into gen_ai.tool.call.arguments, the return value into
# gen_ai.tool.call.result, and the name into gen_ai.tool.name — all serialized
# correctly. So the tools just do their work; no manual enrich() is needed.

@observe(op=Op.EXECUTE_TOOL, name="lookup_order")
def lookup_order(order_id: str) -> dict:
    """Look up an order by its ID."""
    order = _ORDERS.get(str(order_id).strip().lstrip("#"))
    return order or {"error": "order_not_found", "order_id": order_id}


@observe(op=Op.EXECUTE_TOOL, name="check_inventory")
def check_inventory(sku: str) -> dict:
    """Check stock level for a SKU."""
    count = _INVENTORY.get(str(sku).strip().upper())
    return {"sku": sku, "in_stock": count} if count is not None else {"error": "sku_not_found", "sku": sku}


@observe(op=Op.EMBEDDINGS, name="embed_query")
def _embed_query(query: str) -> list[float]:
    """Embed the query with Bedrock Titan (real embeddings span).

    Falls back to a deterministic stub vector if the call fails or creds are
    missing, so the suite still runs offline — the embeddings span still appears.
    """
    if mock_enabled():
        enrich(embedding_mock=True)
        return [float((abs(hash(query)) >> i) & 1) for i in range(8)]
    try:
        import boto3
        region = os.environ.get("AWS_REGION", "us-west-2")
        model = os.environ.get("ACME_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
        client = boto3.client("bedrock-runtime", region_name=region)
        resp = client.invoke_model(modelId=model, body=json.dumps({"inputText": query}))
        vec = json.loads(resp["body"].read())["embedding"]
        enrich(embedding_model=model, embedding_dim=len(vec))
        return vec
    except Exception as e:  # stub fallback
        enrich(embedding_fallback=str(e)[:120])
        return [float((abs(hash(query)) >> i) & 1) for i in range(8)]


@observe(op=Op.RETRIEVAL, name="retrieve_policy")
def _retrieve_policy(query: str) -> dict:
    """Retrieve the matching policy section (the RAG retrieval step)."""
    q = query.lower()
    for key, text in _POLICY_DOC.items():
        if key in q:
            return {"topic": key, "answer": text}
    return {"topic": "returns", "answer": _POLICY_DOC["returns"]}


@observe(op=Op.EXECUTE_TOOL, name="search_policy")
def search_policy(query: str) -> dict:
    """Search the returns/shipping policy doc — a small RAG stand-in.

    Embeds the query (embeddings span) then retrieves the matching section
    (retrieval span), so the trace exercises the full retrieval path.
    """
    _embed_query(query)
    return _retrieve_policy(query)


# ---------------------------------------------------------------------------
# Tool registry + schemas shared by every framework adapter.
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = {
    "lookup_order": lookup_order,
    "check_inventory": check_inventory,
    "search_policy": search_policy,
}

TOOL_SCHEMAS = [
    {
        "name": "lookup_order",
        "description": "Look up the status, items, and ship date of an order by its order ID.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "The order ID, e.g. 1007"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "check_inventory",
        "description": "Check how many units of a SKU are in stock.",
        "parameters": {
            "type": "object",
            "properties": {"sku": {"type": "string", "description": "The product SKU, e.g. SK-ROCKET"}},
            "required": ["sku"],
        },
    },
    {
        "name": "search_policy",
        "description": "Search Acme's returns and shipping policy for an answer.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What the customer is asking about"}},
            "required": ["query"],
        },
    },
]

SYSTEM_PROMPT = (
    "You are the Acme customer support agent. Use the provided tools to answer "
    "customer questions about orders, inventory, and policies. Always call a tool "
    "to get real data before answering — never guess an order status or stock count. "
    "Keep answers short and friendly."
)
