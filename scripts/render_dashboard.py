from __future__ import annotations

"""Render a small, auto-refreshing HTML dashboard from the structured JSONL log."""

import argparse
import html
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

import yaml

ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percent / 100 * len(ordered)) - 1)]


def bucket_values(events: list[dict], minutes: int, value) -> list[float]:
    """Aggregate recent events into twelve equal time buckets."""
    bucket_count = 12
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    buckets: list[list[float]] = [[] for _ in range(bucket_count)]
    for event in events:
        try:
            timestamp = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            offset = (timestamp - start).total_seconds()
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= offset < minutes * 60:
            index = min(bucket_count - 1, int(offset / (minutes * 60) * bucket_count))
            amount = value(event)
            if amount is not None:
                buckets[index].append(float(amount))
    return [sum(bucket) for bucket in buckets]


def bucket_means(events: list[dict], minutes: int, value) -> list[float]:
    """Average numeric event values in each time bucket."""
    bucket_count = 12
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    buckets: list[list[float]] = [[] for _ in range(bucket_count)]
    for event in events:
        try:
            timestamp = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            offset = (timestamp - start).total_seconds()
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= offset < minutes * 60:
            index = min(bucket_count - 1, int(offset / (minutes * 60) * bucket_count))
            amount = value(event)
            if amount is not None:
                buckets[index].append(float(amount))
    return [mean(bucket) if bucket else 0.0 for bucket in buckets]


def read_recent_logs(path: Path, minutes: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    events: list[dict] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
            timestamp = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if timestamp >= cutoff:
            events.append(event)
    return events


def sparkline(values: list[float], color: str = "#72e0bd") -> str:
    width, height = 440, 92
    if not values:
        values = [0]
    low, high = min(values), max(values)
    spread = max(high - low, 1)
    points = []
    for i, value in enumerate(values):
        x = 5 + i * (width - 10) / max(len(values) - 1, 1)
        y = height - 8 - ((value - low) / spread) * (height - 18)
        points.append(f"{x:.1f},{y:.1f}")
    return (f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="trend chart">'
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" '
            'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<line x1="0" y1="{height - 7}" x2="{width}" y2="{height - 7}" '
            'stroke="#263548"/></svg>')


def build_dashboard(events: list[dict], config: dict) -> str:
    dashboard = config["dashboard"]
    panels = {panel["id"]: panel for panel in dashboard["panels"]}
    requests = [e for e in events if e.get("event") == "request_received"]
    responses = [e for e in events if e.get("event") == "response_sent"]
    failures = [e for e in events if e.get("event") == "request_failed"]
    latency = [float(e["latency_ms"]) for e in responses if e.get("latency_ms") is not None]
    ttft = [float(e["ttft_ms"]) for e in responses if e.get("ttft_ms") is not None]
    success_values = [e.get("tool_success") for e in responses if e.get("tool_success") is not None]
    retrieval_success = 100 * sum(v is True for v in success_values) / len(success_values) if success_values else 0
    error_rate = 100 * len(failures) / len(requests) if requests else 0
    cost = sum(float(e.get("cost_usd", 0)) for e in responses)
    input_tokens = sum(int(e.get("tokens_in", 0)) for e in responses)
    output_tokens = sum(int(e.get("tokens_out", 0)) for e in responses)
    qualities = [float(e["quality_score"]) for e in responses if e.get("quality_score") is not None]

    range_minutes = int(dashboard["time_range_minutes"])
    latency_limit = float(panels["latency"]["threshold"]["value"])
    error_limit = float(panels["errors"]["threshold"]["value"])
    cost_limit = float(panels["cost"]["threshold"]["value"])
    token_limit = float(panels["tokens"]["threshold"]["value"])
    quality_limit = float(panels["quality"]["threshold"]["value"])
    retrieval_limit = float(panels["errors"].get("secondary_thresholds", {}).get("retrieval_success_rate_pct", 90))

    def card(panel_id: str, title: str, value: str, detail: str, chart: str, status: str = "Within threshold") -> str:
        panel = panels[panel_id]
        threshold = panel["threshold"]
        threshold_text = f'{threshold["aggregation"]} {threshold["operator"]} {threshold["value"]} {panel["unit"]}'
        if panel_id == "errors":
            threshold_text += f" | retrieval_success_rate gte {retrieval_limit:g}%"
        badge = "bad" if status == "Check threshold" else "good"
        return (f'<article class="card"><div class="card-top"><span>{html.escape(title)}</span>'
                f'<span class="badge {badge}">{html.escape(status)}</span></div>'
                f'<div class="value">{html.escape(value)}</div><div class="detail">{html.escape(detail)}</div>'
                f'{chart}<div class="threshold">Threshold · {html.escape(threshold_text)}</div></article>')

    latency_status = "Check threshold" if percentile(latency, 95) > latency_limit else "Within threshold"
    error_status = "Check threshold" if error_rate > error_limit else "Within threshold"
    latency_trend = bucket_means(responses, range_minutes, lambda event: event.get("latency_ms"))
    traffic_trend = bucket_values(requests, range_minutes, lambda _: 1)
    error_trend = bucket_values(failures, range_minutes, lambda _: 1)
    retrieval_trend = bucket_means(
        responses,
        range_minutes,
        lambda event: 100 if event.get("tool_success") is True else 0 if event.get("tool_success") is False else None,
    )
    cost_trend = bucket_values(responses, range_minutes, lambda event: event.get("cost_usd", 0))
    token_trend = bucket_values(
        responses,
        range_minutes,
        lambda event: int(event.get("tokens_in", 0)) + int(event.get("tokens_out", 0)),
    )
    quality_trend = bucket_means(responses, range_minutes, lambda event: event.get("quality_score"))
    cards = [
        card("latency", "Latency percentiles and TTFT", f'{percentile(latency, 50):.0f} / {percentile(latency, 95):.0f} / {percentile(latency, 99):.0f} ms',
             f'TTFT P95 {percentile(ttft, 95):.0f} ms ? {len(responses)} responses', sparkline(latency_trend, "#f1b866"), latency_status),
        card("traffic", "Request traffic", f'{len(requests)} requests', f'{len(requests) / max(1, range_minutes):.2f} requests/min over {range_minutes}m', sparkline(traffic_trend)),
        card("errors", "Errors and retrieval success", f'{error_rate:.1f}% errors', f'{retrieval_success:.1f}% retrieval success ? {len(failures)} failed', sparkline(error_trend, "#f17d8d"), "Check threshold" if error_rate > error_limit or (success_values and retrieval_success < retrieval_limit) else error_status),
        card("cost", "Cost over time", f'${cost:.4f}', f'{len(responses)} responses ? rolling {range_minutes}-minute total', sparkline(cost_trend, "#aa91ff"), "Check threshold" if cost > cost_limit else "Within threshold"),
        card("tokens", "Input and output tokens", f'{input_tokens:,} / {output_tokens:,}', 'input tokens / output tokens', sparkline(token_trend, "#75b7ff"), "Check threshold" if input_tokens + output_tokens > token_limit else "Within threshold"),
        card("quality", "Quality proxy", f'{mean(qualities):.2f}' if qualities else "0.00", f'{len(qualities)} scored responses ? target average ? {quality_limit:g}', sparkline(quality_trend, "#72e0bd"), "Check threshold" if qualities and mean(qualities) < quality_limit else "Within threshold"),
    ]
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    refresh = int(dashboard["refresh_seconds"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="{refresh}">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(dashboard["title"])}</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#0a111b;color:#eaf0f7;font:15px/1.45 Segoe UI,Arial,sans-serif}}
.wrap{{max-width:1440px;margin:0 auto;padding:38px 42px}} header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px}}
h1{{font-size:26px;margin:0 0 8px}} .sub,.detail,.threshold{{color:#9cabc0}} .sub{{font-size:13px}}
.live{{color:#72e0bd;border:1px solid #245746;border-radius:20px;padding:7px 12px;font-size:12px;white-space:nowrap}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}} .card{{min-height:235px;background:#111c2a;border:1px solid #263548;border-radius:14px;padding:18px 20px;box-shadow:0 8px 22px #0002}}
.card-top{{display:flex;justify-content:space-between;gap:8px;font-size:14px;font-weight:600}} .badge{{font-size:10px;border-radius:20px;padding:4px 8px;white-space:nowrap}} .good{{color:#72e0bd;background:#15362f}} .bad{{color:#ffb86b;background:#422d1b}}
.value{{font-size:26px;font-weight:650;letter-spacing:-.5px;margin:18px 0 3px}} .detail{{font-size:12px}} svg{{width:100%;height:75px;margin:8px 0 0}} .threshold{{font-size:11px;border-top:1px solid #263548;padding-top:10px}}
footer{{margin-top:22px;color:#7f90a7;font-size:12px}} @media(max-width:950px){{.grid{{grid-template-columns:repeat(2,1fr)}}}} @media(max-width:620px){{.wrap{{padding:22px 16px}}header{{display:block}}.live{{display:inline-block;margin-top:14px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main class="wrap"><header><div><h1>{html.escape(dashboard["title"])}</h1>
<div class="sub">Rolling {dashboard["time_range_minutes"]} minutes · source data/logs.jsonl · refresh every {refresh}s</div></div>
<div class="live">● LIVE · updated {html.escape(generated)}</div></header><section class="grid">{''.join(cards)}</section>
<footer>Values are calculated from sanitized structured logs. Correlation IDs and raw request text are intentionally not shown.</footer></main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the CP2 runtime dashboard from JSONL logs")
    parser.add_argument("--logs", type=Path, default=ROOT / "data/logs.jsonl")
    parser.add_argument("--config", type=Path, default=ROOT / "config/dashboard.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "submission/evidence/11-dashboard-overview.html")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    minutes = int(config["dashboard"]["time_range_minutes"])
    events = read_recent_logs(args.logs, minutes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_dashboard(events, config), encoding="utf-8")
    print(f"Dashboard rendered: {args.output} ({len(events)} events in last {minutes} minutes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
