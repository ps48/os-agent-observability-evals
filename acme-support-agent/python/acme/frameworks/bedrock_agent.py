"""Amazon Bedrock adapter — tool-calling loop with the Converse API.

Install: pip install "opensearch-genai-observability-sdk-py[bedrock]"
Uses standard boto3 credentials (env, profile, or instance role).
"""

from __future__ import annotations

import os

from ..observability import enrich
from ..tools import TOOL_FUNCTIONS, TOOL_SCHEMAS, SYSTEM_PROMPT

# Cross-region inference profile; the older 3.5-sonnet v1 id is end-of-life on Bedrock.
MODEL = os.environ.get("ACME_MODEL", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
REGION = os.environ.get("AWS_REGION", "us-west-2")


def _bedrock_tool_config():
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": s["name"],
                    "description": s["description"],
                    "inputSchema": {"json": s["parameters"]},
                }
            }
            for s in TOOL_SCHEMAS
        ]
    }


def run_turn(question: str, history: list[dict]) -> str:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=REGION)
    enrich(model=MODEL, provider="aws.bedrock")

    messages = [*history, {"role": "user", "content": [{"text": question}]}]

    for _ in range(5):
        resp = client.converse(
            modelId=MODEL,
            messages=messages,
            system=[{"text": SYSTEM_PROMPT}],
            toolConfig=_bedrock_tool_config(),
        )
        out = resp["output"]["message"]
        messages.append(out)

        if resp.get("stopReason") != "tool_use":
            return "".join(b["text"] for b in out["content"] if "text" in b)

        tool_results = []
        for block in out["content"]:
            if "toolUse" in block:
                tu = block["toolUse"]
                fn = TOOL_FUNCTIONS[tu["name"]]
                result = fn(**tu["input"])
                tool_results.append({
                    "toolResult": {
                        "toolUseId": tu["toolUseId"],
                        "content": [{"json": result}],
                    }
                })
        messages.append({"role": "user", "content": tool_results})

    return "Sorry, I couldn't complete that request."
