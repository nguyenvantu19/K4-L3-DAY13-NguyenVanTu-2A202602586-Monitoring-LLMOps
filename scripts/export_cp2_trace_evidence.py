from __future__ import annotations

"""Read back safe CP2 trace facts using Langfuse Observations API v2."""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from langfuse import get_client

ROOT = Path(__file__).resolve().parents[1]


def duration_ms(observation) -> int | None:
    """Return observation duration without exporting input or output content."""
    started = getattr(observation, "start_time", None)
    ended = getattr(observation, "end_time", None)
    if started is None or ended is None:
        return None
    return round((ended - started).total_seconds() * 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export safe CP2 trace IDs and span summaries")
    parser.add_argument("--output", type=Path, default=ROOT / "submission/evidence/06-trace-list.txt")
    parser.add_argument(
        "--correlation-id",
        action="append",
        default=[],
        help="Export one or more exact correlation IDs instead of the CP2 req-c020 prefix.",
    )
    args = parser.parse_args()

    load_dotenv()
    client = get_client()
    now = datetime.now(timezone.utc)
    # Always use a bounded time range; only summary fields are exported below.
    response = client.api.observations.get_many(
        from_start_time=now - timedelta(hours=2),
        to_start_time=now,
        fields="core,basic,metadata,model,usage,prompt",
        limit=1000,
    )

    traces: dict[tuple[str, str], list] = {}
    for observation in response.data:
        metadata = getattr(observation, "metadata", None) or {}
        correlation_id = metadata.get("correlation_id") if isinstance(metadata, dict) else None
        if not isinstance(correlation_id, str):
            continue
        if args.correlation_id and correlation_id not in args.correlation_id:
            continue
        if not args.correlation_id and not correlation_id.startswith("req-c020"):
            continue
        key = (correlation_id, observation.trace_id)
        traces.setdefault(key, []).append(observation)

    lines = [f"Verified Langfuse traces: {len(traces)}", "Observation data: Langfuse v2 API"]
    for (correlation_id, trace_id), observations in sorted(traces.items()):
        by_name = {getattr(item, "name", ""): item for item in observations}
        names = sorted(name for name in by_name if name)
        root = by_name.get("lab-agent-run")
        metadata = getattr(root, "metadata", None) or {} if root else {}
        retrieval = by_name.get("retrieval")
        generation = by_name.get("llm-generation")
        if generation:
            usage = getattr(generation, "usage_details", None) or {}
            cost = getattr(generation, "cost_details", None) or {}
            model = getattr(generation, "model", "") or ""
            generation_summary = (
                f"model={model}, input_tokens={usage.get('input', '')}, "
                f"output_tokens={usage.get('output', '')}, cost_usd={cost.get('total', '')}"
            )
        else:
            generation_summary = "generation=missing"
        retrieval_duration = duration_ms(retrieval) if retrieval else None
        retrieval_summary = (
            f"retrieval_duration_ms={retrieval_duration}"
            if retrieval_duration is not None
            else "retrieval=missing"
        )
        prompt_summary = ""
        if isinstance(metadata, dict):
            prompt_summary = ", ".join(
                f"{key}={metadata[key]}"
                for key in ("prompt_name", "prompt_label", "prompt_version", "prompt_source")
                if key in metadata
            )
        lines.append(
            f"{correlation_id} trace_id={trace_id} spans={','.join(names)} "
            f"{retrieval_summary} {generation_summary} {prompt_summary}".rstrip()
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
