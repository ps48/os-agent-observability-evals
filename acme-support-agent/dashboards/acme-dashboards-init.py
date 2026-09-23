#!/usr/bin/env python3
"""Curated dashboard init for the Acme Support Agent.

Creates two agent dashboards ("Acme Agent - Run Details" and "Acme Agent - Evals")
from PPL + PromQL `explore` panels (plus Markdown headers/nav), and removes the
stack's demo dashboards so Dashboards shows only what this tutorial needs.

Feature set is modeled on Arize/Phoenix, Braintrust, LangSmith and Langfuse eval +
observability dashboards: RED metrics, cost/token per-model, latency percentiles +
distribution, pass/fail gauges, per-criterion quality bars, score/error timelines,
status "health" strip, tool analytics, and click-through drill-down to the trace.

Runs after the stack's own `opensearch-dashboards-init`. Idempotent (fixed ids,
`overwrite=true`).

Env: OSD_BASE_URL, OSD_USER, OSD_PASSWORD, WORKSPACE_NAME, SPAN_PATTERN.
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


# --- datasets ---------------------------------------------------------------

def _ppl_dataset(span_id):
    return {"id": span_id, "title": SPAN_PATTERN, "type": "INDEX_PATTERN", "timeFieldName": "endTime"}


def _prom_dataset():
    return {"id": PROM, "title": PROM, "type": "PROMETHEUS", "language": "PROMQL",
            "timeFieldName": "Time", "dataSource": {}, "signalType": "metrics"}


# --- panel builders ---------------------------------------------------------

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


def md_panel(pid, markdown):
    vis = {"title": "", "type": "markdown",
           "params": {"markdown": markdown, "openLinksInNewTab": True, "fontSize": 14}, "aggs": []}
    return {"id": pid, "type": "visualization", "attributes": {
        "title": "", "visState": json.dumps(vis), "uiStateJSON": "{}", "description": "", "version": 1,
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})}},
        "references": []}


def metric_params(base=BLUE, thresholds=None, calc="total", text="value_and_name", unit=None, solid=True):
    p = {"showTitle": True, "title": "", "showPercentage": False, "valueCalculation": calc,
         "thresholdOptions": {"baseColor": base, "thresholds": thresholds or []},
         "useThresholdColor": True, "textMode": text,
         "colorMode": "background_solid" if solid else "background_gradient"}
    if unit:
        p["unitId"] = unit
    return p


def gauge_params(thresholds, unit="percentage", calc="last"):
    return {"showTitle": True, "title": "", "thresholdOptions": {"thresholds": thresholds, "baseColor": RED},
            "useThresholdColor": False, "valueCalculation": calc, "unitId": unit}


def bargauge_params(thresholds):
    return {"tooltipOptions": {"mode": "all"},
            "exclusive": {"displayMode": "gradient", "valueDisplay": "valueColor", "showUnfilledArea": True},
            "thresholdOptions": {"thresholds": thresholds, "baseColor": GREEN}, "valueCalculation": "total"}


def histogram_params(base=BLUE):
    return {"tooltipOptions": {"mode": "all"}, "barSizeMode": "auto", "barWidth": 0.9, "barPadding": 0.05,
            "showBarBorder": False, "barBorderWidth": 1, "barBorderColor": "#000000",
            "thresholdOptions": {"baseColor": base, "thresholds": [], "thresholdStyle": "off"},
            "useThresholdColor": False, "standardAxes": [_AX_X], "bucket": {"aggregationType": "count"}}


def state_timeline_params(mappings):
    return {"tooltipOptions": {"mode": "all"}, "addLegend": True, "legendPosition": "right", "legendTitle": "",
            "exclusive": {"showValues": False, "rowHeight": 0.9,
                          "disconnectValues": {"disableMode": "never", "threshold": "1h"},
                          "connectNullValues": {"connectMode": "never", "threshold": "1h"}},
            "valueMappingOptions": {"valueMappings": mappings},
            "useThresholdColor": False, "thresholdOptions": {"baseColor": GREEN, "thresholds": []},
            "standardAxes": [_AX_X, _AX_Y]}


_AX_X = {"position": "bottom", "show": True, "labels": {"show": True, "filter": True, "rotate": 0, "truncate": 100}, "title": {"text": ""}, "grid": {"showLines": False}, "axisRole": "x"}
_AX_Y = {"position": "left", "show": True, "labels": {"show": True, "filter": True, "rotate": 0, "truncate": 100}, "title": {"text": ""}, "grid": {"showLines": True}, "axisRole": "y"}
P_PIE = {"addTooltip": True, "addLegend": True, "legendPosition": "right", "legendTitle": "",
         "tooltipOptions": {"mode": "all"}, "exclusive": {"donut": True, "showValues": True, "showLabels": True, "truncate": 100}}
P_BARH = {"addLegend": False, "barBorderColor": "#000000", "barBorderWidth": 1, "barPadding": 0.1,
          "barSizeMode": "auto", "barWidth": 0.7, "legendPosition": "bottom", "legendTitle": "",
          "showBarBorder": False, "showFullTimeRange": False, "stackMode": "none",
          "switchAxes": True, "thresholdOptions": {"baseColor": BLUE, "thresholds": [], "thresholdStyle": "off"},
          "titleOptions": {"show": False, "titleName": ""}, "tooltipOptions": {"mode": "all"}}
P_LINE = {"addLegend": True, "legendTitle": "", "legendPosition": "bottom", "addTimeMarker": True,
          "lineStyle": "line", "lineMode": "smooth", "lineWidth": 2, "tooltipOptions": {"mode": "all"},
          "thresholdOptions": {"baseColor": GREEN, "thresholds": [], "thresholdStyle": "off"},
          "standardAxes": [_AX_X, _AX_Y], "showFullTimeRange": False}
P_AREA = {**P_LINE, "stackMode": "stacked"}
P_TABLE = {"pageSize": 20, "globalAlignment": "left", "showColumnFilter": False, "showFooter": True,
           "footerCalculations": [], "cellTypes": [], "thresholds": [], "baseColor": "#000000",
           "dataLinks": [], "visibleColumns": [], "hiddenColumns": []}


def table_links(ws, span_id, field="field-0"):
    url = (f"/w/{ws}/app/explore/traces/traceDetails#/?_a=(dataset:(id:'{span_id}',"
           f"title:'otel-v1-apm-span*',type:'INDEX_PATTERN',timeFieldName:'endTime'),"
           f"traceId:'${{__value.text}}')")
    p = dict(P_TABLE)
    p["dataLinks"] = [{"id": "trace-link", "title": "Open trace", "url": url, "openInNewTab": True, "fields": [field]}]
    return p


def dashboard(did, title, layout, variables=None):
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
TOT = "cast(`attributes.gen_ai.usage.total_tokens` as int)"
OP = "`attributes.gen_ai.operation.name`"
MODEL = "`attributes.gen_ai.request.model`"
EVN = "`attributes.gen_ai.evaluation.name`"
EVV = "`attributes.gen_ai.evaluation.score.value`"


def build(ws, span_id):
    R = "acme-run"; E = "acme-eval"
    P = lambda *a, **k: ppl_panel(*a, span_id=span_id, **k)
    nav_run = ("**Acme Agent · Run Details**  —  "
               f"[Evals dashboard →](/w/{ws}/app/dashboards#/view/acme-agent-evals)  ·  "
               f"[Trace explorer →](/w/{ws}/app/agentTraces/traces)  ·  "
               f"[Spans →](/w/{ws}/app/agentTraces/spans)")
    nav_eval = ("**Acme Agent · Evals**  —  "
                f"[Run Details →](/w/{ws}/app/dashboards#/view/acme-agent-run-details)  ·  "
                f"[Trace explorer →](/w/{ws}/app/agentTraces/traces)")

    lat_bands = [{"value": 0, "color": GREEN}, {"value": 5, "color": AMBER}, {"value": 8, "color": RED}]
    run = [
        (md_panel(f"{R}-nav", nav_run), 0, 0, 48, 3),
        # health hero
        (P(f"{R}-health", "Agent health over time", f"| where {OP}='invoke_agent' | eval svc='acme-support-agent' | stats max(`status.code`) as st by span(endTime,10m), svc", "state_timeline",
           state_timeline_params([{"id": "ok", "type": "value", "value": "0", "displayText": "OK", "color": GREEN},
                                   {"id": "err", "type": "value", "value": "2", "displayText": "Error", "color": RED}]),
           {"x": "span(endTime,10m)", "y": "svc", "color": "st"}), 0, 3, 48, 8),
        # KPI row
        (P(f"{R}-runs", "Agent runs", f"| where {OP}='invoke_agent' | stats count() as runs", "metric", metric_params(BLUE), {"value": ["runs"]}), 0, 11, 9, 8),
        (P(f"{R}-success", "Success rate", f"| where {OP}='invoke_agent' | eval ok=if(`status.code`=2,0.0,1.0) | stats avg(ok) as a | eval `success %`=round(a * 100, 1) | fields `success %`", "gauge",
           gauge_params([{"value": 0, "color": RED}, {"value": 95, "color": AMBER}, {"value": 99, "color": GREEN}]), {"value": ["success %"]}), 9, 11, 12, 8),
        (P(f"{R}-errrate", "Error rate", f"| where {OP}='invoke_agent' | eval e=if(`status.code`=2,1.0,0.0) | stats avg(e) as a | eval `error %`=round(a * 100, 1) | fields `error %`", "metric", metric_params(RED, unit="percentage"), {"value": ["error %"]}), 21, 11, 9, 8),
        (P(f"{R}-p95kpi", "P95 latency", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,95) as p | eval `p95 s`=round(p / 1000000000.0, 2) | fields `p95 s`", "metric", metric_params(GREEN, thresholds=lat_bands, unit="seconds"), {"value": ["p95 s"]}), 30, 11, 9, 8),
        (P(f"{R}-cost", "Est. cost $", f"| stats sum({IN}) as ti, sum({OUT}) as to | eval `est $`=round(ti / 1000000.0 * 3 + to / 1000000.0 * 15, 3) | fields `est $`", "metric", metric_params(SLATE), {"value": ["est $"]}), 39, 11, 9, 8),
        # latency
        (md_panel(f"{R}-h-lat", "### Latency"), 0, 19, 48, 3),
        (P(f"{R}-p50", "P50 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,50) as p | eval s=round(p / 1000000000.0,2) | fields s", "metric", metric_params(BLUE, unit="seconds"), {"value": ["s"]}), 0, 22, 8, 7),
        (P(f"{R}-p95", "P95 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,95) as p | eval s=round(p / 1000000000.0,2) | fields s", "metric", metric_params(BLUE, unit="seconds"), {"value": ["s"]}), 8, 22, 8, 7),
        (P(f"{R}-p99", "P99 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,99) as p | eval s=round(p / 1000000000.0,2) | fields s", "metric", metric_params(BLUE, unit="seconds"), {"value": ["s"]}), 16, 22, 8, 7),
        (P(f"{R}-latdist", "Latency distribution (s)", f"| where {OP}='invoke_agent' | eval s=round(durationInNanos / 1000000000.0,1) | fields s", "histogram", histogram_params(BLUE), {"x": ["s"]}), 24, 22, 24, 15),
        # cost & tokens
        (md_panel(f"{R}-h-cost", "### Cost & tokens"), 0, 29, 24, 3),
        (P(f"{R}-tok-model", "Tokens by model", f"| where {MODEL}!='' | stats sum({TOT}) as tokens by {MODEL} | sort - tokens", "bar", P_BARH, {"x": [MODEL.strip('`')], "y": ["tokens"]}), 0, 32, 24, 15),
        (P(f"{R}-tok-time", "Tokens in vs out over time", f"| where {TOT} > 0 | stats sum({IN}) as `in`, sum({OUT}) as `out` by span(endTime,10m)", "area", P_AREA, {"x": ["span(endTime,10m)"], "y": ["in", "out"]}), 24, 37, 24, 15),
        # tools & throughput
        (md_panel(f"{R}-h-tools", "### Tools & throughput"), 24, 29, 24, 3),
        (P(f"{R}-tools", "Tool analytics", f"| where {OP}='execute_tool' and `attributes.gen_ai.tool.name`!='' | stats count() as calls, avg(durationInNanos) as d by `attributes.gen_ai.tool.name` | eval `avg ms`=round(d / 1000000.0,2) | fields `attributes.gen_ai.tool.name`, calls, `avg ms` | sort - calls", "table", P_TABLE, {}), 24, 32, 24, 8),
        (P(f"{R}-throughput", "Throughput (runs / 10m)", f"| where {OP}='invoke_agent' | stats count() as runs by span(endTime,10m)", "line", P_LINE, {"x": ["span(endTime,10m)"], "y": ["runs"]}), 0, 47, 24, 15),
        # errors (drill-down)
        (md_panel(f"{R}-h-err", "### Errors  ·  click a row's trace ID to open the trace"), 0, 62, 48, 3),
        (P(f"{R}-errtbl", "Recent error traces", f"| where `status.code`=2 | fields traceId, endTime, name, `events.attributes.exception.message` | sort - endTime | head 20", "table", table_links(ws, span_id), {}), 0, 65, 48, 15),
        # pipeline (PromQL)
        (md_panel(f"{R}-h-pipe", "### Telemetry pipeline (PromQL / Prometheus)"), 0, 80, 48, 3),
        (promql_panel(f"{R}-ingest", "Span ingest vs export rate", "sum(rate(otelcol_receiver_accepted_spans_total[5m])) or sum(rate(otelcol_exporter_sent_spans_total[5m]))", "line", P_LINE, {"x": ["Time"], "y": ["Value"], "color": ["Series"]}), 0, 83, 36, 12),
        (promql_panel(f"{R}-exfail", "Span export failures", "sum(otelcol_exporter_send_failed_spans_total) or on() vector(0)", "metric", metric_params(RED, calc="last"), {"value": ["Value"], "time": ["Time"]}), 36, 83, 12, 12),
    ]

    EV = f"| where {OP}='evaluation'"
    ev = [
        (md_panel(f"{E}-nav", nav_eval), 0, 0, 48, 3),
        (P(f"{E}-runs", "Eval runs", f"| where {OP}='invoke_agent' and `attributes.gen_ai.agent.name`='eval_case' | stats count() as `eval runs`", "metric", metric_params(BLUE), {"value": ["eval runs"]}), 0, 3, 12, 8),
        (P(f"{E}-pass", "Overall pass rate", f"{EV} | stats avg({EVV}) as a | eval `pass %`=round(a * 100, 1) | fields `pass %`", "gauge",
           gauge_params([{"value": 0, "color": RED}, {"value": 90, "color": AMBER}, {"value": 99, "color": GREEN}]), {"value": ["pass %"]}), 12, 3, 12, 8),
        (P(f"{E}-fails", "Failed checks", f"{EV} and {EVV} < 1 | stats count() as fails", "metric", metric_params(RED), {"value": ["fails"]}), 24, 3, 12, 8),
        (P(f"{E}-events", "Score events", f"{EV} | stats count() as n", "metric", metric_params(SLATE), {"value": ["n"]}), 36, 3, 12, 8),
        (md_panel(f"{E}-h-quality", "### Quality by check"), 0, 11, 48, 3),
        (P(f"{E}-bargauge", "Pass rate by check", f"{EV} | stats avg({EVV}) as score by {EVN} | sort - score", "bar_gauge",
           bargauge_params([{"value": 0, "color": RED}, {"value": 0.9, "color": AMBER}, {"value": 0.99, "color": GREEN}]), {"x": [EVN.strip('`')], "y": ["score"]}), 0, 14, 24, 15),
        (P(f"{E}-failbymetric", "Failing checks by metric", f"{EV} and {EVV} < 1 | stats count() as fails by {EVN} | sort - fails", "bar", P_BARH, {"x": [EVN.strip('`')], "y": ["fails"]}), 24, 14, 24, 15),
        (md_panel(f"{E}-h-trend", "### Score & failure trend"), 0, 29, 48, 3),
        (P(f"{E}-time", "Avg score over time", f"{EV} | stats avg({EVV}) as score by span(endTime,10m), {EVN}", "line", P_LINE, {"x": ["span(endTime,10m)"], "y": ["score"], "color": [EVN.strip('`')]}), 0, 32, 24, 15),
        (P(f"{E}-failtime", "Failing checks over time", f"{EV} and {EVV} < 1 | stats count() as fails by span(endTime,10m), {EVN}", "area", P_AREA, {"x": ["span(endTime,10m)"], "y": ["fails"], "color": [EVN.strip('`')]}), 24, 32, 24, 15),
        (md_panel(f"{E}-h-tbl", "### Failing checks"), 0, 47, 48, 3),
        (P(f"{E}-failtbl", "Failing checks by metric", f"{EV} and {EVV} < 1 | stats count() as fails by {EVN} | sort - fails", "table", P_TABLE, {}), 0, 50, 48, 12),
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
    objs, dashboards = build(ws, span_id)
    print("creating panels:")
    for o in objs:
        create(ws, o)
    print("creating dashboards:")
    for d in dashboards:
        create(ws, d)
    print("done")


if __name__ == "__main__":
    main()
