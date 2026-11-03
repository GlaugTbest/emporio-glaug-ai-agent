"""Quick local Ollama readiness check (no cloud requests)."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.local_model import DEFAULT_MODEL, ensure_model, installed_models


def main():
    parser = argparse.ArgumentParser(description="Check local Ollama model availability")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    try:
        models = installed_models()
        print("Installed Ollama models:", ", ".join(models) if models else "none")
        ensure_model(args.model)
    except (RuntimeError, ValueError) as exc:
        parser.exit(2, f"Setup required: {exc}\n")
    print(f"Ready to run locally with {args.model}. No cloud account or API key is used.")


if __name__ == "__main__":
    main()
