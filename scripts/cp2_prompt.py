from __future__ import annotations

"""Create and move the day13-chat prompt labels required by CP2."""

import argparse
import os

from dotenv import load_dotenv
from langfuse import get_client

BASELINE = "Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}"
CANDIDATE = (
    "Answer the user's question using the context when it is relevant.\n"
    "Feature={{feature}}\nContext={{docs}}\nQuestion={{message}}\n"
    "Keep the answer clear and concise."
)


def get_labeled_prompt(client, name: str, label: str):
    return client.get_prompt(
        name,
        label=label,
        type="text",
        cache_ttl_seconds=0,
        fetch_timeout_seconds=10,
        max_retries=0,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage CP2 day13-chat prompt labels")
    parser.add_argument("action", choices=("setup", "promote", "rollback"))
    args = parser.parse_args()
    load_dotenv()
    client = get_client()
    name = os.getenv("LANGFUSE_PROMPT_NAME", "day13-chat")

    if args.action == "setup":
        try:
            baseline = get_labeled_prompt(client, name, "baseline")
        except Exception as exc:
            if type(exc).__name__ != "NotFoundError":
                raise
            # First prompt version is the baseline and initially serves production.
            baseline = client.create_prompt(
                name=name,
                type="text",
                prompt=BASELINE,
                labels=["baseline", "production"],
                commit_message="CP2 baseline template",
            )
        try:
            candidate = get_labeled_prompt(client, name, "candidate")
        except Exception as exc:
            if type(exc).__name__ != "NotFoundError":
                raise
            # Version 2 changes only instructions and retains all required variables.
            candidate = client.create_prompt(
                name=name,
                type="text",
                prompt=CANDIDATE,
                labels=["candidate"],
                commit_message="CP2 candidate: clarify concise context-grounded answers",
            )
        print(f"{name}: baseline=v{baseline.version}, candidate=v{candidate.version}")
        return 0

    label = "candidate" if args.action == "promote" else "baseline"
    target = get_labeled_prompt(client, name, label)
    labels = [label, "production"]
    client.update_prompt(name=name, version=target.version, new_labels=labels)
    # Read the pointer again so the output reflects the saved project state.
    production = get_labeled_prompt(client, name, "production")
    print(f"{name}: production=v{production.version} ({args.action})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
