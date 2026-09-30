from __future__ import annotations

"""Create safe synthetic requests for CP2 trace-tree evidence."""

import argparse
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

QUESTIONS = [
    "Explain how metrics, logs, and traces work together.",
    "Summarize the refund policy from the available context.",
    "What information should never be stored in application logs?",
    "Describe a useful symptom-based latency alert.",
    "Explain the purpose of a correlation ID.",
    "What is the difference between a trace and a span?",
    "Summarize the safe logging policy.",
    "How can an operator investigate a slow request?",
    "Explain how a retrieval step helps answer a question.",
    "Give a short explanation of prompt version rollback.",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send 10 PII-free CP2 trace requests")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--count", type=int, default=len(QUESTIONS), help="How many safe requests to send")
    parser.add_argument("--start", type=int, default=1, help="Synthetic ID number for the first request")
    parser.add_argument("--message", default=None, help="Reuse one safe message for prompt version comparisons")
    args = parser.parse_args()
    if args.count < 1 or args.count > 100 or args.start < 1:
        parser.error("--count must be 1..100 and --start must be positive")

    # Identifiers and messages here are synthetic; none identify a real person.
    with httpx.Client(timeout=30.0) as client:
        for offset in range(args.count):
            number = args.start + offset
            message = args.message or QUESTIONS[(number - 1) % len(QUESTIONS)]
            correlation_id = f"req-c020{number:04x}"
            response = client.post(
                f"{args.base_url.rstrip('/')}/chat",
                headers={"x-request-id": correlation_id},
                json={
                    "user_id": f"synthetic-user-{number:02d}",
                    "session_id": f"cp2-session-{number:02d}",
                    "feature": "qa",
                    "message": message,
                },
            )
            print(f"{response.status_code} {correlation_id}")
            response.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
