"""Real Ollama planning plus deterministic semantic checks; fictional fixtures only."""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent import Agent, build_client
from app.evaluation import require_demo_database, score_case
from app.local_model import DEFAULT_MODEL, ensure_model, local_json
from app.tools import StoreTools, ToolContext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/demo.db")
    parser.add_argument("--cases", default="evals/cases.json")
    parser.add_argument("--output", default="evals/live_results.json")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    parser.add_argument("--case", action="append", dest="selected_cases")
    args = parser.parse_args()
    require_demo_database(args.db)
    ensure_model(args.model)
    root = Path(__file__).resolve().parents[1]
    implementation = hashlib.sha256()
    sources = (sorted((root / "app").glob("*.py")) + sorted((root / "fixtures").glob("*"))
               + [Path(__file__).resolve(), root / "scripts/capture_examples.py", root / "evals/cases.json"])
    for source in sources:
        implementation.update(str(source.relative_to(root)).replace("\\", "/").encode())
        implementation.update(source.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode("utf-8"))
    model_digest = next((m.get("digest") for m in local_json(None, "tags", timeout=3)["models"]
                         if m["name"] == args.model), None)
    client = build_client()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.selected_cases:
        unknown = set(args.selected_cases) - {c["id"] for c in cases}
        if unknown:
            parser.error(f"Unknown cases: {sorted(unknown)}")
        cases = [c for c in cases if c["id"] in args.selected_cases]
    if not cases:
        parser.error("No cases selected")
    sessions = {}
    details = []
    for case in cases:
        key = case["session_id"]
        if key not in sessions:
            sessions[key] = Agent(StoreTools(ToolContext(Path(args.db), case.get("customer_context"))), client, model=args.model)
        agent = sessions[key]
        if agent.tools.context.authenticated_customer_id != case.get("customer_context"):
            parser.error("Identity must remain host-controlled and constant within a session")
        print(f"Evaluating {case['id']}", flush=True)
        started = time.monotonic()
        answer = agent.ask(case["user"], session_id=key)
        checks = score_case(case, answer, agent)
        details.append({"case": case["id"], "user": case["user"], "session_id": key,
                        "customer_context": case.get("customer_context"), **checks,
                        "tools": [name for name, _, _ in agent.last_records],
                        "calls": [{"tool": n, "arguments": a} for n, a, _ in agent.last_records],
                        "response": answer, "response_source": agent.last_answer_source,
                        "model_calls": agent.last_model_calls, "model_error": agent.last_model_error,
                        "duration_seconds": round(time.monotonic() - started, 2)})
        print(f"{case['id']}: passed={checks['passed']}; model_calls={agent.last_model_calls}; seconds={details[-1]['duration_seconds']}", flush=True)
    passed = sum(r["passed"] for r in details)
    output = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "mode": "REAL_OLLAMA_PLANNING_PYTHON_FACTS", "dataset": "public_fixtures",
              "implementation_sha256": implementation.hexdigest(), "model_digest": model_digest,
              "model": args.model, "cases": len(details), "passed": passed,
              "pass_rate_percent": round(100 * passed / len(details), 2), "results": details}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{passed}/{len(details)} passed; saved {path}")
    if passed != len(details):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
