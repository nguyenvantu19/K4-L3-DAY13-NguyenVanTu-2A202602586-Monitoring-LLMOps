from __future__ import annotations

"""Start the local API with one explicit Langfuse prompt label for CP2."""

import argparse
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the API with a CP2 prompt label")
    parser.add_argument("--label", choices=("baseline", "candidate", "production"), required=True)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # Load API keys and other settings from the ignored .env file.
    load_dotenv(ROOT / ".env")
    # Set the selected label after loading .env so it cannot be overwritten.
    os.environ["LANGFUSE_PROMPT_LABEL"] = args.label
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
