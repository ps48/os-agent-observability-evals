#!/usr/bin/env python3
"""Curated dashboard init for the Acme Support Agent.

Creates two agent dashboards ("Acme Agent - Run Details" and "Acme Agent - Evals")
from PPL + PromQL `explore` panels (plus Markdown overview/nav), and removes the
stack's demo dashboards so Dashboards shows only what this tutorial needs.

Modeled on Arize/Phoenix, Braintrust, LangSmith and Langfuse eval + observability
dashboards: RED metrics, cost/token per-model, latency percentiles + distribution,
pass/fail gauges, per-criterion quality bars, score/error timelines, a status
"health" strip, tool analytics, KPI cards with trend sparklines, filter variables,
and click-through drill-down to the trace.

Runs after the stack's own `opensearch-dashboards-init`. Idempotent (fixed ids,
`overwrite=true`).

Env:
  OSD_BASE_URL   default http://localhost:5601   (container: http://opensearch-dashboards:5601)
  OSD_USER / OSD_PASSWORD
  WORKSPACE_NAME default "Observability Stack"
  SPAN_PATTERN   default otel-v1-apm-span*
  OSD_PUBLIC_URL browser-facing base for nav links + trace drill-down (default http://localhost:5601)
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
PUBLIC = os.environ.get("OSD_PUBLIC_URL", "http://localhost:5601").rstrip("/")
OS_URL = os.environ.get("OPENSEARCH_URL", "https://localhost:9200").rstrip("/")
GTIME = "_g=(time:(from:now-24h,to:now))"
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


# --- axes / param blocks ----------------------------------------------------

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


def metric_params(base=BLUE, thresholds=None, calc="total", text="value", unit=None):
    p = {"showTitle": True, "title": "", "showPercentage": False, "valueCalculation": calc,
         "thresholdOptions": {"baseColor": base, "thresholds": thresholds or []},
         "useThresholdColor": True, "textMode": text, "colorMode": "background_solid"}
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


def table_links(ws, span_id):
    url = (f"{PUBLIC}/w/{ws}/app/explore/traces/traceDetails#/?_a=(dataset:(id:'{span_id}',"
           f"title:'otel-v1-apm-span*',type:'INDEX_PATTERN',timeFieldName:'endTime'),"
           f"traceId:'${{__value.text}}')")
    p = dict(P_TABLE)
    p["dataLinks"] = [{"id": "trace-link", "title": "Open trace", "url": url, "openInNewTab": True, "fields": ["traceId"]}]
    return p


def distinct_values(field):
    """Terms-agg the raw (un-backticked) field so the variable can default to All.

    OSD query-variables reset to the first alphabetical option when `current` is
    absent; baking every value into `current` (which survives load) is the only
    way to open on "All". Best-effort: on any failure we return [] and fall back
    to OSD's first-option default.
    """
    raw = field.strip("`")
    body = {"size": 0, "query": {"bool": {"filter": [{"exists": {"field": raw}}]}},
            "aggs": {"v": {"terms": {"field": raw, "size": 200}}}}
    try:
        r = S.post(f"{OS_URL}/{SPAN_PATTERN}/_search", data=json.dumps(body),
                   headers={"Content-Type": "application/json"}, timeout=15)
        buckets = r.json().get("aggregations", {}).get("v", {}).get("buckets", [])
        return sorted(str(b["key"]) for b in buckets if b.get("key") not in (None, ""))
    except Exception as e:
        print(f"  warn: distinct_values({raw}) failed ({e}); variable defaults to first option", file=sys.stderr)
        return []


def query_var(name, label, field, span_id):
    v = {"name": name, "label": label, "type": "query", "language": "PPL",
         "query": f"| where {field}!='' | stats count() by {field} | fields {field}",
         "dataset": _ppl_dataset(span_id), "multi": True, "includeAll": True,
         "sort": "alphabetical-asc", "useTimeFilter": True}
    values = distinct_values(field)
    if values:
        v["current"] = values  # every value selected == "All" by default
    return v


def dashboard(did, title, layout, variables=None, description=""):
    panels, refs = [], []
    for i, (obj, x, y, w, h) in enumerate(layout):
        name = f"panel_{i}"
        panels.append({"gridData": {"x": x, "y": y, "w": w, "h": h, "i": str(i)},
                       "panelIndex": str(i), "version": "3.0.0", "panelRefName": name})
        refs.append({"id": obj["id"], "name": name, "type": obj["type"]})
    attrs = {"title": title, "description": description, "panelsJSON": json.dumps(panels),
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
# case-level fields rolled onto the eval_case invoke_agent span (see evals/run_evals.py)
EQ = "`attributes.eval_question`"       # readable case label
CSCORE = "`attributes.eval_case_score`"  # per-case mean score (0-1)
EPASS = "`attributes.eval_passed`"       # 1 pass / 0 fail
SPAN10 = "span(endTime,10m)"
NAV_H = 10  # nav/overview panel height; content below is authored against y>=8 and shifted


def _shift(layout):
    """Shift every panel below the nav so a taller nav doesn't overlap them.

    Layouts below are authored assuming an 8-row nav (content starts at y=8);
    bumping NAV_H taller here keeps a single source of truth for the offset.
    """
    dy = NAV_H - 8
    return [(obj, x, (y + dy if y >= 8 else y), w, h) for (obj, x, y, w, h) in layout]


def build(ws, span_id):
    R = "acme-run"; E = "acme-eval"
    P = lambda *a, **k: ppl_panel(*a, span_id=span_id, **k)
    MF = f"and {MODEL} IN $model"   # model filter (model-bearing panels only)
    CF = f"and {EVN} IN $check"     # eval-check filter

    nav_run = ("### Acme Agent — Run Details\n"
               "Live health, latency, cost and error triage for the Acme Support Agent, from its OpenTelemetry traces.\n\n"
               "**How to use:** filter cost/token panels by **Model** (top-left) · click a **trace ID** in *Recent error traces* "
               "to open the span waterfall · set the window with the time picker (top-right).\n\n"
               f"**Go to:** [Evals dashboard →]({PUBLIC}/w/{ws}/app/dashboards#/view/acme-agent-evals?{GTIME})"
               f" &nbsp;·&nbsp; [Trace explorer →]({PUBLIC}/w/{ws}/app/agentTraces/traces/#?{GTIME})"
               f" &nbsp;·&nbsp; [Spans →]({PUBLIC}/w/{ws}/app/agentTraces/spans/#?{GTIME})")
    nav_eval = ("### Acme Agent — Evals\n"
                "Automated eval quality for the Acme Support Agent: pass rate, per-check scores and regression trends "
                "from `evaluation` spans (correctness, right tool, cost, latency, loops, trajectory).\n\n"
                "**How to use:** filter by **Check** (top-left) to focus one metric · watch the trend charts for regressions · "
                "adjust the time window (top-right).\n\n"
                f"**Go to:** [Run Details →]({PUBLIC}/w/{ws}/app/dashboards#/view/acme-agent-run-details?{GTIME})"
                f" &nbsp;·&nbsp; [Trace explorer →]({PUBLIC}/w/{ws}/app/agentTraces/traces/#?{GTIME})")

    lat_bands = [{"value": 0, "color": GREEN}, {"value": 5, "color": AMBER}, {"value": 8, "color": RED}]
    run = [
        (md_panel(f"{R}-nav", nav_run), 0, 0, 48, NAV_H),
        # health hero
        (P(f"{R}-health", "Agent health over time", f"| where {OP}='invoke_agent' | eval svc='acme-support-agent' | stats max(`status.code`) as st by {SPAN10}, svc", "state_timeline",
           state_timeline_params([{"id": "ok", "type": "value", "value": "0", "displayText": "OK", "color": GREEN},
                                   {"id": "err", "type": "value", "value": "2", "displayText": "Error", "color": RED}]),
           {"x": SPAN10, "y": "svc", "color": "st"}), 0, 8, 48, 8),
        # KPI row (trend sparklines via time axis) + gauge
        (P(f"{R}-runs", "Agent runs", f"| where {OP}='invoke_agent' | stats count() as runs by {SPAN10}", "metric", metric_params(BLUE, calc="total"), {"value": ["runs"], "time": [SPAN10]}), 0, 16, 9, 8),
        (P(f"{R}-success", "Success rate", f"| where {OP}='invoke_agent' | eval ok=if(`status.code`=2,0.0,1.0) | stats avg(ok) as a | eval `success %`=round(a * 100, 1) | fields `success %`", "gauge",
           gauge_params([{"value": 0, "color": RED}, {"value": 95, "color": AMBER}, {"value": 99, "color": GREEN}]), {"value": ["success %"]}), 9, 16, 12, 8),
        (P(f"{R}-errrate", "Error rate", f"| where {OP}='invoke_agent' | eval e=if(`status.code`=2,1.0,0.0) | stats avg(e) as a by {SPAN10} | eval `error %`=round(a * 100, 1)", "metric", metric_params(RED, calc="mean", unit="percentage"), {"value": ["error %"], "time": [SPAN10]}), 21, 16, 9, 8),
        (P(f"{R}-p95kpi", "P95 latency", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,95) as p by {SPAN10} | eval `p95 s`=round(p / 1000000000.0, 2)", "metric", metric_params(GREEN, thresholds=lat_bands, calc="mean", unit="seconds"), {"value": ["p95 s"], "time": [SPAN10]}), 30, 16, 9, 8),
        (P(f"{R}-cost", "Est. cost $", f"| where {MODEL}!='' {MF} | stats sum({IN}) as ti, sum({OUT}) as to by {SPAN10} | eval `est $`=round(ti / 1000000.0 * 3 + to / 1000000.0 * 15, 3)", "metric", metric_params(SLATE, calc="total"), {"value": ["est $"], "time": [SPAN10]}), 39, 16, 9, 8),
        # latency
        (md_panel(f"{R}-h-lat", "### Latency"), 0, 24, 48, 3),
        (P(f"{R}-p50", "P50 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,50) as p by {SPAN10} | eval s=round(p / 1000000000.0,2)", "metric", metric_params(BLUE, calc="mean", unit="seconds"), {"value": ["s"], "time": [SPAN10]}), 0, 27, 8, 7),
        (P(f"{R}-p95", "P95 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,95) as p by {SPAN10} | eval s=round(p / 1000000000.0,2)", "metric", metric_params(BLUE, calc="mean", unit="seconds"), {"value": ["s"], "time": [SPAN10]}), 8, 27, 8, 7),
        (P(f"{R}-p99", "P99 (s)", f"| where {OP}='invoke_agent' | stats percentile(durationInNanos,99) as p by {SPAN10} | eval s=round(p / 1000000000.0,2)", "metric", metric_params(BLUE, calc="mean", unit="seconds"), {"value": ["s"], "time": [SPAN10]}), 16, 27, 8, 7),
        (P(f"{R}-latdist", "Latency distribution (s)", f"| where {OP}='invoke_agent' | eval s=round(durationInNanos / 1000000000.0,1) | fields s", "histogram", histogram_params(BLUE), {"x": ["s"]}), 24, 27, 24, 15),
        # cost & tokens
        (md_panel(f"{R}-h-cost", "### Cost & tokens"), 0, 34, 24, 3),
        (P(f"{R}-tok-model", "Tokens by model", f"| where {MODEL}!='' {MF} | stats sum({TOT}) as tokens by {MODEL} | sort - tokens", "bar", P_BARH, {"x": [MODEL.strip('`')], "y": ["tokens"]}), 0, 37, 24, 15),
        (P(f"{R}-tok-time", "Tokens in vs out over time", f"| where {TOT} > 0 {MF} | stats sum({IN}) as `in`, sum({OUT}) as `out` by {SPAN10}", "area", P_AREA, {"x": [SPAN10], "y": ["in", "out"]}), 24, 42, 24, 15),
        # tools & throughput
        (md_panel(f"{R}-h-tools", "### Tools & throughput"), 24, 34, 24, 3),
        (P(f"{R}-tools", "Tool analytics", f"| where {OP}='execute_tool' and isnotnull(`attributes.gen_ai.tool.name`) and `attributes.gen_ai.tool.name`!='' | stats count() as calls, avg(durationInNanos) as d by `attributes.gen_ai.tool.name` | eval `avg ms`=round(d / 1000000.0,2) | fields `attributes.gen_ai.tool.name`, calls, `avg ms` | sort - calls", "table", P_TABLE, {}), 24, 37, 24, 8),
        (P(f"{R}-throughput", "Throughput (runs / 10m)", f"| where {OP}='invoke_agent' | stats count() as runs by {SPAN10}", "line", P_LINE, {"x": [SPAN10], "y": ["runs"]}), 0, 52, 24, 15),
        # errors (drill-down)
        (md_panel(f"{R}-h-err", "### Errors  ·  click a row's trace ID to open the trace"), 0, 67, 48, 3),
        (P(f"{R}-errtbl", "Recent error traces", f"| where `status.code`=2 | fields traceId, endTime, name, `events.attributes.exception.message` | sort - endTime | head 20", "table", table_links(ws, span_id), {}), 0, 70, 48, 15),
        # pipeline (PromQL)
        (md_panel(f"{R}-h-pipe", "### Telemetry pipeline (PromQL / Prometheus)"), 0, 85, 48, 3),
        (promql_panel(f"{R}-ingest", "Span ingest vs export rate", "sum(rate(otelcol_receiver_accepted_spans_total[5m])) or sum(rate(otelcol_exporter_sent_spans_total[5m]))", "line", P_LINE, {"x": ["Time"], "y": ["Value"], "color": ["Series"]}), 0, 88, 36, 12),
        (promql_panel(f"{R}-exfail", "Span export failures", "sum(otelcol_exporter_send_failed_spans_total) or on() vector(0)", "metric", metric_params(RED, calc="last"), {"value": ["Value"], "time": ["Time"]}), 36, 88, 12, 12),
    ]

    EV = f"| where {OP}='evaluation'"
    EC = f"| where {OP}='invoke_agent' and `attributes.gen_ai.agent.name`='eval_case'"  # one row per eval case
    score_bands = [{"value": 0, "color": RED}, {"value": 0.9, "color": AMBER}, {"value": 1, "color": GREEN}]
    ev = [
        (md_panel(f"{E}-nav", nav_eval), 0, 0, 48, NAV_H),
        # KPI row — case-level headline numbers (+ check-level pass-rate dial)
        (P(f"{E}-total", "Total cases", f"{EC} | stats count() as cases by {SPAN10}", "metric", metric_params(BLUE, calc="total"), {"value": ["cases"], "time": [SPAN10]}), 0, 8, 10, 8),
        (P(f"{E}-passed", "Cases passed", f"{EC} and {EPASS}=1 | stats count() as passed by {SPAN10}", "metric", metric_params(GREEN, calc="total"), {"value": ["passed"], "time": [SPAN10]}), 10, 8, 10, 8),
        (P(f"{E}-mean", "Mean judge score", f"{EC} | stats avg({CSCORE}) as score by {SPAN10}", "metric", metric_params(SLATE, thresholds=score_bands, calc="mean"), {"value": ["score"], "time": [SPAN10]}), 20, 8, 9, 8),
        (P(f"{E}-min", "Min judge score", f"{EC} | stats min({CSCORE}) as score", "metric", metric_params(RED, thresholds=score_bands, calc="last"), {"value": ["score"]}), 29, 8, 9, 8),
        (P(f"{E}-pass", "Overall pass rate", f"{EV} {CF} | stats avg({EVV}) as a | eval `pass %`=round(a * 100, 1) | fields `pass %`", "gauge",
           gauge_params([{"value": 0, "color": RED}, {"value": 90, "color": AMBER}, {"value": 99, "color": GREEN}]), {"value": ["pass %"]}), 38, 8, 10, 8),
        # outcome mix + per-case scores
        (md_panel(f"{E}-h-out", "### Outcomes  ·  by eval case"), 0, 16, 48, 3),
        (P(f"{E}-donut", "Outcome breakdown", f"{EC} | eval outcome=if({EPASS}=1,'passed','failed') | stats count() as cases by outcome", "pie", P_PIE, {"size": ["cases"], "color": ["outcome"]}), 0, 19, 24, 15),
        (P(f"{E}-bycase", "Judge score by case", f"{EC} | stats avg({CSCORE}) as score by {EQ} | sort - score", "bar", P_BARH, {"x": [EQ.strip('`')], "y": ["score"]}), 24, 19, 24, 15),
        # per-criterion quality (check-level, $check-filtered)
        (md_panel(f"{E}-h-quality", "### Quality by check"), 0, 34, 48, 3),
        (P(f"{E}-bargauge", "Pass rate by check", f"{EV} {CF} | stats avg({EVV}) as score by {EVN} | sort - score", "bar_gauge",
           bargauge_params(score_bands), {"x": [EVN.strip('`')], "y": ["score"]}), 0, 37, 24, 15),
        (P(f"{E}-failbymetric", "Failing checks by metric", f"{EV} {CF} and {EVV} < 1 | stats count() as fails by {EVN} | sort - fails", "bar", P_BARH, {"x": [EVN.strip('`')], "y": ["fails"]}), 24, 37, 24, 15),
        # trends
        (md_panel(f"{E}-h-trend", "### Trends"), 0, 52, 48, 3),
        (P(f"{E}-scoretrend", "Mean judge score trend", f"{EC} | stats avg({CSCORE}) as score by {SPAN10}", "line", P_LINE, {"x": [SPAN10], "y": ["score"]}), 0, 55, 24, 15),
        (P(f"{E}-passph", "Cases passed / 10m", f"{EC} and {EPASS}=1 | stats count() as passed by {SPAN10}", "line", P_LINE, {"x": [SPAN10], "y": ["passed"]}), 24, 55, 24, 15),
        (P(f"{E}-caseruns", "Per-case score over runs", f"{EC} | stats avg({CSCORE}) as score by {SPAN10}, {EQ}", "line", P_LINE, {"x": [SPAN10], "y": ["score"], "color": [EQ.strip('`')]}), 0, 70, 24, 15),
        (P(f"{E}-failtime", "Failing checks over time", f"{EV} {CF} and {EVV} < 1 | stats count() as fails by {SPAN10}, {EVN}", "area", P_AREA, {"x": [SPAN10], "y": ["fails"], "color": [EVN.strip('`')]}), 24, 70, 24, 15),
        # detail tables
        (md_panel(f"{E}-h-tbl", "### Detail"), 0, 85, 48, 3),
        (P(f"{E}-casetbl", "Per-case detail", f"{EC} | eval case={EQ}, score={CSCORE}, `latency s`=round(durationInNanos / 1000000000.0,2), model={MODEL}, tool=`attributes.expected_tool` | fields case, score, `latency s`, model, tool | sort score", "table", P_TABLE, {}), 0, 88, 24, 12),
        (P(f"{E}-failtbl", "Failing checks", f"{EV} {CF} and {EVV} < 1 | stats count() as fails by {EVN} | eval check={EVN} | fields check, fails | sort - fails", "table", P_TABLE, {}), 24, 88, 24, 12),
    ]

    run = _shift(run)
    ev = _shift(ev)
    run_vars = [query_var("model", "Model", MODEL, span_id)]
    eval_vars = [query_var("check", "Eval check", EVN, span_id)]
    d1 = dashboard("acme-agent-run-details", "Acme Agent - Run Details", run, variables=run_vars,
                   description="Live health, latency, cost and error triage for the Acme Support Agent, from OpenTelemetry traces (otel-v1-apm-span*). Filter by model; trace IDs deep-link to the span waterfall.")
    d2 = dashboard("acme-agent-evals", "Acme Agent - Evals", ev, variables=eval_vars,
                   description="Automated eval quality for the Acme Support Agent: pass rate, per-check scores and regression trends from evaluation spans. Filter by check.")
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
