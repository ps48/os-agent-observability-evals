#!/usr/bin/env python3
"""Curated dashboard init for the Acme Support Agent.

Creates two agent dashboards ("Acme Agent - Run Details" and "Acme Agent - Evals")
from PPL + PromQL `explore` panels (plus Markdown section headers), and removes the
stack's demo dashboards so Dashboards shows only what this tutorial needs.

Runs after the stack's own `opensearch-dashboards-init` (which creates the index
patterns and the `ObservabilityStack_Prometheus` data connection this relies on).
Idempotent: fixed object ids + `overwrite=true`.

Env:
  OSD_BASE_URL   default http://localhost:5601   (container: http://opensearch-dashboards:5601)
  OSD_USER       default admin
  OSD_PASSWORD   default My_password_123!@#
  WORKSPACE_NAME default "Observability Stack"
  SPAN_PATTERN   default otel-v1-apm-span*
"""
from __future__ import annotations
import json, os, sys, time
import urllib3, requests
urllib3.disable_warnings()

BASE = os.environ.get("OSD_BASE_URL", "http://localhost:5601").rstrip("/")
USER = os.environ.get("OSD_USER", "admin")
PW = os.environ.get("OSD_PASSWORD", "My_password_123!@#")
WORKSPACE_NAME = os.environ.get("WORKSPACE_NAME", "Observability Stack")
SPAN_PATTERN = os.environ.get("SPAN_PATTERN", "otel-v1-apm-span*")
PROM = "ObservabilityStack_Prometheus"
H = {"osd-xsrf": "true", "Content-Type": "application/json"}
S = requests.Session(); S.auth = (USER, PW); S.verify = False

DEMO_TITLES = {"Astronomy Shop", "Astronomy shop - service telemetry"}

# colors
GREEN = "#017D73"; RED = "#BD271E"; BLUE = "#0a65c6"; AMBER = "#F5A700"; SLATE = "#343741"


def _req(method, path, **kw):
    return S.request(method, f"{BASE}{path}", headers=H, timeout=30, **kw)


def wait_for_osd():
    for _ in range(60):
        try:
            if S.get(f"{BASE}/api/status", headers=H, timeout=5).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(5)
    print("OSD not reachable", file=sys.stderr); sys.exit(1)


def find_workspace_id():
    r = _req("POST", "/api/workspaces/_list", data="{}")
    for w in r.json().get("result", {}).get("workspaces", []):
        if w.get("name") == WORKSPACE_NAME:
            return w.get("id")
    return None


def wp(ws):
    return f"/w/{ws}" if ws else ""


def find_index_pattern_id(ws, title):
    r = _req("GET", f"{wp(ws)}/api/saved_objects/_find?type=index-pattern&per_page=100&fields=title")
    for o in r.json().get("saved_objects", []):
        if o["attributes"].get("title") == title:
            return o["id"]
    raise SystemExit(f"index-pattern {title!r} not found - is the stack init done?")


# --- panel builders ---------------------------------------------------------

def _ppl_dataset(span_id):
    return {"id": span_id, "title": SPAN_PATTERN, "type": "INDEX_PATTERN", "timeFieldName": "endTime"}


def _prom_dataset():
    return {"id": PROM, "title": PROM, "type": "PROMETHEUS", "language": "PROMQL",
            "timeFieldName": "Time", "dataSource": {}, "signalType": "metrics"}


def ppl_panel(pid, title, ppl, chart_type, viz_params, axes, span_id):
    ssj = {"query": {"query": ppl, "language": "PPL", "dataset": _ppl_dataset(span_id)},
           "filter": [], "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"}
    viz = {"title": "", "chartType": chart_type, "params": viz_params, "axesMapping": axes}
    return {"id": pid, "type": "explore", "attributes": {
        "title": title, "description": "", "hits": 0, "columns": [], "sort": [],
        "uiState": "", "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(ssj)},
        "visualization": json.dumps(viz)},
        "references": [{"id": span_id, "name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern"}]}


def promql_panel(pid, title, promql, chart_type, viz_params, axes):
    ssj = {"query": {"query": promql, "language": "PROMQL", "dataset": _prom_dataset()},
           "filter": [], "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"}
    viz = {"title": "", "chartType": chart_type, "params": viz_params, "axesMapping": axes}
    return {"id": pid, "type": "explore", "attributes": {
        "title": title, "description": "", "hits": 0, "columns": ["_source"], "sort": [],
        "uiState": "{\"activeTab\":\"explore_visualization_tab\"}", "version": 1, "type": "metrics",
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(ssj)},
        "visualization": json.dumps(viz)},
        "references": [{"id": PROM, "name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern"}]}


def md_panel(pid, _title, markdown):
    # Blank title so the panel chrome shows only the Markdown heading, not a title bar.
    vis = {"title": "", "type": "markdown",
           "params": {"markdown": markdown, "openLinksInNewTab": True, "fontSize": 14},
           "aggs": []}
    return {"id": pid, "type": "visualization", "attributes": {
        "title": "", "visState": json.dumps(vis), "uiStateJSON": "{}", "description": "", "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})}},
        "references": []}


def metric_params(base=BLUE, thresholds=None, calc="total", text="value_and_name"):
    return {"showTitle": True, "title": "", "showPercentage": False, "valueCalculation": calc,
            "thresholdOptions": {"baseColor": base, "thresholds": thresholds or []},
            "useThresholdColor": True, "textMode": text, "colorMode": "background_gradient"}


P_PIE = {"addTooltip": True, "addLegend": True, "legendPosition": "right", "legendTitle": "",
         "tooltipOptions": {"mode": "all"}, "exclusive": {"donut": True, "showValues": True, "showLabels": True, "truncate": 100}}
P_BARH = {"addLegend": False, "barBorderColor": "#000000", "barBorderWidth": 1, "barPadding": 0.1,
          "barSizeMode": "auto", "barWidth": 0.7, "legendPosition": "bottom", "legendTitle": "",
          "showBarBorder": False, "showFullTimeRange": False, "stackMode": "none",
          "switchAxes": True, "thresholdOptions": {"baseColor": BLUE, "thresholds": [], "thresholdStyle": "off"},
          "titleOptions": {"show": False, "titleName": ""}, "tooltipOptions": {"mode": "all"}}
_AXES = [{"position": "bottom", "show": True, "labels": {"show": True, "filter": True, "rotate": 0, "truncate": 100}, "title": {"text": ""}, "grid": {"showLines": False}, "axisRole": "x"},
         {"position": "left", "show": True, "labels": {"show": True, "filter": True, "rotate": 0, "truncate": 100}, "title": {"text": ""}, "grid": {"showLines": True}, "axisRole": "y"}]
P_LINE = {"addLegend": True, "legendTitle": "", "legendPosition": "bottom", "addTimeMarker": False,
          "lineStyle": "line", "lineMode": "smooth", "lineWidth": 2, "tooltipOptions": {"mode": "all"},
          "thresholdOptions": {"baseColor": GREEN, "thresholds": [], "thresholdStyle": "off"},
          "standardAxes": _AXES, "showFullTimeRange": False}
P_TABLE = {"pageSize": 20, "globalAlignment": "left", "showColumnFilter": False, "showFooter": False,
           "footerCalculations": [], "cellTypes": [], "thresholds": [], "baseColor": "#000000",
           "dataLinks": [], "visibleColumns": [], "hiddenColumns": []}


def dashboard(did, title, layout, variables=None):
    """layout: list of (obj, x, y, w, h)."""
    panels, refs = [], []
    for i, (obj, x, y, w, h) in enumerate(layout):
        name = f"panel_{i}"
        panels.append({"gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
                       "panelIndex": str(i), "version": "3.0.0", "panelRefName": name})
        refs.append({"id": obj["id"], "name": name, "type": obj["type"]})
    attrs = {"title": title, "description": "", "panelsJSON": json.dumps(panels),
             "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
             "version": 1, "timeRestore": True, "timeFrom": "now-24h", "timeTo": "now",
             "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "PPL"}, "filter": []})}}
    if variables:
        attrs["variablesJSON"] = json.dumps({"variables": variables})
    return {"id": did, "type": "dashboard", "attributes": attrs, "references": refs}


def create(ws, obj):
    body = {"attributes": obj["attributes"]}
    if obj.get("references") is not None:
        body["references"] = obj["references"]
    r = _req("POST", f"{wp(ws)}/api/saved_objects/{obj['type']}/{obj['id']}?overwrite=true", data=json.dumps(body))
    ok = r.status_code in (200, 201)
    print(f"  {'ok ' if ok else 'ERR'} {obj['type']}/{obj['id']} [{r.status_code}]" + ("" if ok else f" {r.text[:200]}"))
    return ok


def delete_demo_dashboards(ws):
    r = _req("GET", f"{wp(ws)}/api/saved_objects/_find?type=dashboard&per_page=100&fields=title")
    for o in r.json().get("saved_objects", []):
        if o["attributes"].get("title") in DEMO_TITLES:
            _req("DELETE", f"{wp(ws)}/api/saved_objects/dashboard/{o['id']}?force=true")
            print(f"  deleted demo dashboard {o['attributes'].get('title')!r}")


IN = "cast(`attributes.gen_ai.usage.input_tokens` as int)"
OUT = "cast(`attributes.gen_ai.usage.output_tokens` as int)"
OP = "`attributes.gen_ai.operation.name`"


def build(span_id):
    R = "acme-run"; E = "acme-eval"
    P = lambda *a, **k: ppl_panel(*a, span_id=span_id, **k)

    # ---- Run Details panels ----
    run = [
        (md_panel(f"{R}-h1", "hdr", "### Traffic & reliability"), 0, 0, 48, 3),
        (P(f"{R}-runs", "Agent runs", f"| where {OP}='invoke_agent' | stats count() as runs", "metric", metric_params(BLUE), {"value": ["runs"]}), 0, 3, 10, 8),
        (P(f"{R}-llm-calls", "LLM calls", f"| where {OP}='chat' | stats count() as `LLM calls`", "metric", metric_params(BLUE), {"value": ["LLM calls"]}), 10, 3, 9, 8),
        (P(f"{R}-success", "Success rate %", f"| where {OP}='invoke_agent' | eval ok=if(`status.code`=2,0.0,1.0) | stats avg(ok) as a | eval `success %`=round(a * 100, 1) | fields `success %`", "metric", metric_params(GREEN), {"value": ["success %"]}), 19, 3, 10, 8),
        (P(f"{R}-errrate", "Error rate %", f"| where {OP}='invoke_agent' | eval err=if(`status.code`=2,1.0,0.0) | stats avg(err) as a | eval `error %`=round(a * 100, 1) | fields `error %`", "metric", metric_params(RED), {"value": ["error %"]}), 29, 3, 10, 8),
        (P(f"{R}-sessions", "Sessions", "| where `attributes.gen_ai.conversation.id`!='' | stats dc(`attributes.gen_ai.conversation.id`) as sessions", "metric", metric_params(SLATE), {"value": ["sessions"]}), 39, 3, 9, 8),
        (P(f"{R}-outcome", "Success vs failure", f"| where {OP}='invoke_agent' | eval outcome=if(`status.code`=2,'failure','success') | stats count() as c by outcome", "pie", P_PIE, {"size": ["c"], "color": ["outcome"]}), 0, 11, 16, 14),
        (P(f"{R}-errtbl", "Recent error traces", f"| where `status.code`=2 | fields endTime, name, `events.attributes.exception.message` | sort - endTime | head 20", "table", P_TABLE, {}), 16, 11, 32, 14),
        (md_panel(f"{R}-h2", "hdr", "### Latency & cost"), 0, 25, 48, 3),
        (P(f"{R}-p50", "Latency P50 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,50) as p | eval `p50 s`=round(p/1000000000.0,2) | fields `p50 s`", "metric", metric_params(BLUE), {"value": ["p50 s"]}), 0, 28, 12, 8),
        (P(f"{R}-p95", "Latency P95 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,95) as p | eval `p95 s`=round(p/1000000000.0,2) | fields `p95 s`", "metric", metric_params(AMBER), {"value": ["p95 s"]}), 12, 28, 12, 8),
        (P(f"{R}-cost", "Est. cost $ (approx)", f"| stats sum({IN}) as ti, sum({OUT}) as to | eval `est $`=round(ti / 1000000.0 * 3 + to / 1000000.0 * 15, 3) | fields `est $`", "metric", metric_params(GREEN), {"value": ["est $"]}), 24, 28, 12, 8),
        (P(f"{R}-tokens", "Tokens in vs out", f"| stats sum({IN}) as `tokens in`, sum({OUT}) as `tokens out`", "table", P_TABLE, {}), 36, 28, 12, 8),
        (P(f"{R}-throughput", "Throughput (runs / 5m)", f"| where {OP}='invoke_agent' | stats count() as runs by span(endTime,5m)", "line", P_LINE, {"x": ["span(endTime,5m)"], "y": ["runs"]}), 0, 36, 24, 14),
        (P(f"{R}-tokens-time", "Tokens over time", f"| where cast(`attributes.gen_ai.usage.total_tokens` as int) > 0 | stats sum({IN}) as `in`, sum({OUT}) as `out` by span(endTime,5m)", "line", P_LINE, {"x": ["span(endTime,5m)"], "y": ["in", "out"]}), 24, 36, 24, 14),
        (md_panel(f"{R}-h3", "hdr", "### Models, tools & sessions"), 0, 50, 48, 3),
        (P(f"{R}-models", "LLM models used", "| where `attributes.gen_ai.request.model`!='' | stats count() as calls by `attributes.gen_ai.request.model` | sort - calls", "pie", P_PIE, {"size": ["calls"], "color": ["attributes.gen_ai.request.model"]}), 0, 53, 16, 15),
        (P(f"{R}-tools", "Tool usage", f"| where {OP}='execute_tool' | stats count() as calls by `attributes.gen_ai.tool.name` | sort - calls", "bar", P_BARH, {"x": ["attributes.gen_ai.tool.name"], "y": ["calls"]}), 16, 53, 16, 15),
        (P(f"{R}-session-tbl", "Sessions by token use", f"| where `attributes.gen_ai.conversation.id`!='' | stats count() as spans, sum({IN}) as in_tokens by `attributes.gen_ai.conversation.id` | sort - spans", "table", P_TABLE, {}), 32, 53, 16, 15),
        (md_panel(f"{R}-h4", "hdr", "### Telemetry pipeline (PromQL / Prometheus)"), 0, 68, 48, 3),
        (promql_panel(f"{R}-ingest", "Span ingest vs export rate", "sum(rate(otelcol_receiver_accepted_spans_total[5m])) or sum(rate(otelcol_exporter_sent_spans_total[5m]))", "line", P_LINE, {"x": ["Time"], "y": ["Value"], "color": ["Series"]}), 0, 71, 36, 12),
        (promql_panel(f"{R}-exfail", "Span export failures", "sum(otelcol_exporter_send_failed_spans_total) or on() vector(0)", "metric", metric_params(RED, calc="last"), {"value": ["Value"], "time": ["Time"]}), 36, 71, 12, 12),
    ]

    # ---- Evals panels ----
    EV = f"| where {OP}='evaluation'"
    ev = [
        (md_panel(f"{E}-h1", "hdr", "### Eval quality"), 0, 0, 48, 3),
        (P(f"{E}-runs", "Eval runs", f"| where {OP}='invoke_agent' and `attributes.gen_ai.agent.name`='eval_case' | stats count() as `eval runs`", "metric", metric_params(BLUE), {"value": ["eval runs"]}), 0, 3, 12, 8),
        (P(f"{E}-pass", "Overall pass %", f"{EV} | stats avg(`attributes.gen_ai.evaluation.score.value`) as a | eval `pass %`=round(a * 100, 1) | fields `pass %`", "metric", metric_params(GREEN), {"value": ["pass %"]}), 12, 3, 12, 8),
        (P(f"{E}-fails", "Failed checks", f"{EV} and `attributes.gen_ai.evaluation.score.value` < 1 | stats count() as fails", "metric", metric_params(RED), {"value": ["fails"]}), 24, 3, 12, 8),
        (P(f"{E}-events", "Score events", f"{EV} | stats count() as n", "metric", metric_params(SLATE), {"value": ["n"]}), 36, 3, 12, 8),
        (P(f"{E}-avg", "Avg score by metric", f"{EV} | stats avg(`attributes.gen_ai.evaluation.score.value`) as score by `attributes.gen_ai.evaluation.name` | sort - score", "bar", P_BARH, {"x": ["attributes.gen_ai.evaluation.name"], "y": ["score"]}), 0, 11, 24, 15),
        (P(f"{E}-failbymetric", "Failing checks by metric", f"{EV} and `attributes.gen_ai.evaluation.score.value` < 1 | stats count() as fails by `attributes.gen_ai.evaluation.name` | sort - fails", "bar", P_BARH, {"x": ["attributes.gen_ai.evaluation.name"], "y": ["fails"]}), 24, 11, 24, 15),
        (md_panel(f"{E}-h2", "hdr", "### Score trend"), 0, 26, 48, 3),
        (P(f"{E}-time", "Avg score over time", f"{EV} | stats avg(`attributes.gen_ai.evaluation.score.value`) as score by span(endTime,5m), `attributes.gen_ai.evaluation.name`", "line", P_LINE, {"x": ["span(endTime,5m)"], "y": ["score"], "color": ["attributes.gen_ai.evaluation.name"]}), 0, 29, 32, 15),
        (P(f"{E}-failtbl", "Failing checks by metric", f"{EV} and `attributes.gen_ai.evaluation.score.value` < 1 | stats count() as fails by `attributes.gen_ai.evaluation.name` | sort - fails", "table", P_TABLE, {}), 32, 29, 16, 15),
    ]

    d1 = dashboard("acme-agent-run-details", "Acme Agent - Run Details", run)
    d2 = dashboard("acme-agent-evals", "Acme Agent - Evals", ev)
    objs = [o for (o, *_g) in run] + [o for (o, *_g) in ev]
    return objs, [d1, d2]


def main():
    wait_for_osd()
    ws = find_workspace_id()
    span_id = find_index_pattern_id(ws, SPAN_PATTERN)
    print(f"workspace={ws} span_index_pattern={span_id}")
    delete_demo_dashboards(ws)
    objs, dashboards = build(span_id)
    print("creating panels:")
    for o in objs:
        create(ws, o)
    print("creating dashboards:")
    for d in dashboards:
        create(ws, d)
    print("done")


if __name__ == "__main__":
    main()
