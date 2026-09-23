#!/usr/bin/env python3
"""Curated dashboard init for the Acme Support Agent.

Creates two agent dashboards ("Acme Agent - Run Details" and "Acme Agent - Evals")
from PPL + PromQL `explore` panels, and removes the stack's demo dashboards so the
Dashboards home shows only what this tutorial needs.

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

# Demo dashboards to remove ("keep only what we need").
DEMO_TITLES = {"Astronomy Shop", "Astronomy shop - service telemetry"}


def _req(method, path, **kw):
    r = S.request(method, f"{BASE}{path}", headers=H, timeout=30, **kw)
    return r


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
    return None  # default workspace


def wp(ws):  # workspace path prefix
    return f"/w/{ws}" if ws else ""


def find_index_pattern_id(ws, title):
    r = _req("GET", f"{wp(ws)}/api/saved_objects/_find?type=index-pattern&per_page=100&fields=title")
    for o in r.json().get("saved_objects", []):
        if o["attributes"].get("title") == title:
            return o["id"]
    raise SystemExit(f"index-pattern {title!r} not found - is the stack init done?")


# --- explore panel builders -------------------------------------------------

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


# reusable viz param blocks (copied from the stack's own sample panels)
P_METRIC = {"showTitle": True, "title": "", "showPercentage": False, "valueCalculation": "total",
            "thresholdOptions": {"baseColor": "#0a65c6", "thresholds": []}, "useThresholdColor": False,
            "textMode": "value_and_name", "colorMode": "none"}
P_METRIC_LAST = {**P_METRIC, "valueCalculation": "last"}
P_PIE = {"addTooltip": True, "addLegend": True, "legendPosition": "right", "legendTitle": "",
         "tooltipOptions": {"mode": "all"}, "exclusive": {"donut": True, "showValues": True, "showLabels": True, "truncate": 100}}
P_BARH = {"addLegend": False, "barBorderColor": "#000000", "barBorderWidth": 1, "barPadding": 0.1,
          "barSizeMode": "auto", "barWidth": 0.7, "legendPosition": "bottom", "legendTitle": "",
          "showBarBorder": False, "showFullTimeRange": False, "stackMode": "none",
          "switchAxes": True, "thresholdOptions": {"baseColor": "#0a65c6", "thresholds": [], "thresholdStyle": "off"},
          "titleOptions": {"show": False, "titleName": ""}, "tooltipOptions": {"mode": "all"}}
_AXES = [{"position": "bottom", "show": True, "labels": {"show": True, "filter": True, "rotate": 0, "truncate": 100}, "title": {"text": ""}, "grid": {"showLines": False}, "axisRole": "x"},
         {"position": "left", "show": True, "labels": {"show": True, "filter": True, "rotate": 0, "truncate": 100}, "title": {"text": ""}, "grid": {"showLines": True}, "axisRole": "y"}]
P_LINE = {"addLegend": True, "legendTitle": "", "legendPosition": "bottom", "addTimeMarker": False,
          "lineStyle": "line", "lineMode": "smooth", "lineWidth": 2, "tooltipOptions": {"mode": "all"},
          "thresholdOptions": {"baseColor": "#00BD6B", "thresholds": [], "thresholdStyle": "off"},
          "standardAxes": _AXES, "showFullTimeRange": False}
P_TABLE = {"pageSize": 20, "globalAlignment": "left", "showColumnFilter": False, "showFooter": False,
           "footerCalculations": [], "cellTypes": [], "thresholds": [], "baseColor": "#000000",
           "dataLinks": [], "visibleColumns": [], "hiddenColumns": []}


def dashboard(did, title, panel_ids, gridspec, variables=None):
    panels, refs = [], []
    for i, (pid, x, y, w, h) in enumerate(zip(panel_ids, *zip(*gridspec)) if False else _zip_grid(panel_ids, gridspec)):
        name = f"panel_{i}"
        panels.append({"gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
                       "panelIndex": str(i), "version": "3.0.0", "panelRefName": name})
        refs.append({"id": pid, "name": name, "type": "explore"})
    attrs = {"title": title, "description": "", "panelsJSON": json.dumps(panels),
             "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
             "version": 1, "timeRestore": True, "timeFrom": "now-24h", "timeTo": "now",
             "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "PPL"}, "filter": []})}}
    if variables:
        attrs["variablesJSON"] = json.dumps({"variables": variables})
    return {"id": did, "type": "dashboard", "attributes": attrs, "references": refs}


def _zip_grid(panel_ids, gridspec):
    out = []
    for pid, (x, y, w, h) in zip(panel_ids, gridspec):
        out.append((pid, x, y, w, h))
    return out


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
            d = _req("DELETE", f"{wp(ws)}/api/saved_objects/dashboard/{o['id']}?force=true")
            print(f"  deleted demo dashboard {o['attributes'].get('title')!r} [{d.status_code}]")


def build(span_id):
    R = "acme-run"; E = "acme-eval"
    run_panels = [
        ppl_panel(f"{R}-llm-calls", "LLM calls", "| where `attributes.gen_ai.operation.name`='chat' | stats count() as `LLM calls`", "metric", P_METRIC, {"value": ["LLM calls"]}, span_id),
        ppl_panel(f"{R}-agent-runs", "Agent runs", "| where `attributes.gen_ai.operation.name`='invoke_agent' | stats count() as runs", "metric", P_METRIC, {"value": ["runs"]}, span_id),
        ppl_panel(f"{R}-sessions", "Sessions", "| where `attributes.gen_ai.conversation.id`!='' | stats dc(`attributes.gen_ai.conversation.id`) as sessions", "metric", P_METRIC, {"value": ["sessions"]}, span_id),
        ppl_panel(f"{R}-tokens", "Tokens in vs out", "| stats sum(cast(`attributes.gen_ai.usage.input_tokens` as int)) as `tokens in`, sum(cast(`attributes.gen_ai.usage.output_tokens` as int)) as `tokens out`", "table", P_TABLE, {}, span_id),
        ppl_panel(f"{R}-models", "LLM models used", "| where `attributes.gen_ai.request.model`!='' | stats count() as calls by `attributes.gen_ai.request.model` | sort - calls", "pie", P_PIE, {"size": ["calls"], "color": ["attributes.gen_ai.request.model"]}, span_id),
        ppl_panel(f"{R}-outcome", "Success vs failure", "| where `attributes.gen_ai.operation.name`='invoke_agent' | eval outcome=if(`status.code`=2,'failure','success') | stats count() as c by outcome", "pie", P_PIE, {"size": ["c"], "color": ["outcome"]}, span_id),
        ppl_panel(f"{R}-tokens-time", "Tokens over time", "| where cast(`attributes.gen_ai.usage.total_tokens` as int) > 0 | stats sum(cast(`attributes.gen_ai.usage.input_tokens` as int)) as `in`, sum(cast(`attributes.gen_ai.usage.output_tokens` as int)) as `out` by span(endTime,5m)", "line", P_LINE, {"x": ["span(endTime,5m)"], "y": ["in", "out"]}, span_id),
        ppl_panel(f"{R}-session-tbl", "Sessions by token use", "| where `attributes.gen_ai.conversation.id`!='' | stats count() as spans, sum(cast(`attributes.gen_ai.usage.input_tokens` as int)) as in_tokens by `attributes.gen_ai.conversation.id` | sort - spans", "table", P_TABLE, {}, span_id),
        promql_panel(f"{R}-ingest-rate", "Span ingest vs export rate", "sum(rate(otelcol_receiver_accepted_spans_total[5m])) or sum(rate(otelcol_exporter_sent_spans_total[5m]))", "line", P_LINE, {"x": ["Time"], "y": ["Value"], "color": ["Series"]}),
        promql_panel(f"{R}-export-fail", "Span export failures", "sum(otelcol_exporter_send_failed_spans_total) or on() vector(0)", "metric", P_METRIC_LAST, {"value": ["Value"], "time": ["Time"]}),
    ]
    run_grid = [(0,0,12,8),(12,0,12,8),(24,0,12,8),(36,0,12,8),
                (0,8,16,15),(16,8,16,15),(32,8,16,15),
                (0,23,24,15),(24,23,24,15),(0,38,12,8)]

    eval_panels = [
        ppl_panel(f"{E}-runs", "Eval runs", "| where `attributes.gen_ai.operation.name`='invoke_agent' and `attributes.gen_ai.agent.name`='eval_case' | stats count() as `eval runs`", "metric", P_METRIC, {"value": ["eval runs"]}, span_id),
        ppl_panel(f"{E}-passpct", "Overall pass %", "| where `attributes.gen_ai.operation.name`='evaluation' | stats avg(`attributes.gen_ai.evaluation.score.value`) as avg_score | eval `pass %` = round(avg_score * 100, 1) | fields `pass %`", "metric", P_METRIC, {"value": ["pass %"]}, span_id),
        ppl_panel(f"{E}-score-events", "Score events", "| where `attributes.gen_ai.operation.name`='evaluation' | stats count() as n", "metric", P_METRIC, {"value": ["n"]}, span_id),
        ppl_panel(f"{E}-avg-by-metric", "Avg score by metric", "| where `attributes.gen_ai.operation.name`='evaluation' | stats avg(`attributes.gen_ai.evaluation.score.value`) as score by `attributes.gen_ai.evaluation.name` | sort - score", "bar", P_BARH, {"x": ["attributes.gen_ai.evaluation.name"], "y": ["score"]}, span_id),
        ppl_panel(f"{E}-count-by-metric", "Score events by metric", "| where `attributes.gen_ai.operation.name`='evaluation' | stats count() as n by `attributes.gen_ai.evaluation.name` | sort - n", "bar", P_BARH, {"x": ["attributes.gen_ai.evaluation.name"], "y": ["n"]}, span_id),
        ppl_panel(f"{E}-scores-time", "Avg score over time", "| where `attributes.gen_ai.operation.name`='evaluation' | stats avg(`attributes.gen_ai.evaluation.score.value`) as score by span(endTime,5m), `attributes.gen_ai.evaluation.name`", "line", P_LINE, {"x": ["span(endTime,5m)"], "y": ["score"], "color": ["attributes.gen_ai.evaluation.name"]}, span_id),
        ppl_panel(f"{E}-fails", "Failing evals by metric", "| where `attributes.gen_ai.operation.name`='evaluation' and `attributes.gen_ai.evaluation.score.value` < 1 | stats count() as fails by `attributes.gen_ai.evaluation.name` | sort - fails", "table", P_TABLE, {}, span_id),
    ]
    eval_grid = [(0,0,16,8),(16,0,16,8),(32,0,16,8),
                 (0,8,24,15),(24,8,24,15),
                 (0,23,32,15),(32,23,16,15)]

    d1 = dashboard("acme-agent-run-details", "Acme Agent - Run Details", [p["id"] for p in run_panels], run_grid)
    d2 = dashboard("acme-agent-evals", "Acme Agent - Evals", [p["id"] for p in eval_panels], eval_grid)
    return run_panels + eval_panels, [d1, d2]


def main():
    wait_for_osd()
    ws = find_workspace_id()
    span_id = find_index_pattern_id(ws, SPAN_PATTERN)
    print(f"workspace={ws} span_index_pattern={span_id}")
    delete_demo_dashboards(ws)
    panels, dashboards = build(span_id)
    print("creating panels:")
    for p in panels:
        create(ws, p)
    print("creating dashboards:")
    for d in dashboards:
        create(ws, d)
    print("done")


if __name__ == "__main__":
    main()
