"""Download the selected local model and prepare the fictional demo database."""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.local_model import DEFAULT_MODEL, ensure_model

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--skip-pull", action="store_true", help="Use an already-installed Ollama model")
    args = parser.parse_args()
    if not args.skip_pull:
        try:
            subprocess.run(["ollama", "pull", args.model], check=True)
        except FileNotFoundError:
            parser.exit(2, "Ollama is missing: install it from https://ollama.com/download first.\n")
        except subprocess.CalledProcessError as exc:
            parser.exit(2, f"Could not download model: {exc}\n")
    try:
        ensure_model(args.model)
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"Ollama setup failed: {exc}\n")
    subprocess.run([
        sys.executable, str(ROOT / "scripts" / "prepare_data.py"),
        "--source-dir", str(ROOT / "fixtures"),
        "--policy-json", str(ROOT / "fixtures" / "demo_policies.json"),
        "--db", str(ROOT / "data" / "demo.db"),
    ], check=True)
    print(f"Ready. Run: python main.py --db data/demo.db --model {args.model}")


if __name__ == "__main__":
    main()
