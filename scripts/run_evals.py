"""Local model evaluation. Never confuse this with deterministic pytest."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import Agent, build_client
from app.local_model import DEFAULT_MODEL, ensure_model
from app.tools import StoreTools, ToolContext


class TracedTools(StoreTools):
    def __init__(self, context):
        super().__init__(context)
        self.calls = []

    def execute(self, tool_name, args):
        self.calls.append({"tool": tool_name, "arguments": args})
        return super().execute(tool_name, args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/demo.db")
    parser.add_argument("--cases", default="evals/cases.json")
    parser.add_argument("--output", default="evals/live_results.json")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    parser.add_argument("--case", action="append", dest="selected_cases",
                        help="Only run a named case ID (repeatable); default: all cases")
    args = parser.parse_args()
    ensure_model(args.model)
    client = build_client()  # Local Ollama only; never fabricate evaluation scores.
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.selected_cases:
        unknown = sorted(set(args.selected_cases) - {case["id"] for case in cases})
        if unknown:
            parser.error(f"Unknown case ID: {unknown}")
        cases = [case for case in cases if case["id"] in args.selected_cases]
    if not cases:
        parser.error("No evaluation cases selected")
    sessions = {}
    details = []
    for case in cases:
        key = case["session_id"]
        if key not in sessions:
            traced = TracedTools(ToolContext(Path(args.db)))
            sessions[key] = (Agent(traced, client, model=args.model), traced)
        agent, traced = sessions[key]
        traced.calls.clear()
        print(f"Evaluating {case['id']} with real Ollama", flush=True)
        answer = agent.ask(case["user"], session_id=key)
        used = [c["tool"] for c in traced.calls]
        tool_ok = case["expected_tool"] in used if case["expected_tool"] else not used
        text_ok = all(term.lower() in answer.lower() for term in case["must_contain"])
        if case.get("must_contain_any"):
            text_ok &= any(term.lower() in answer.lower() for term in case["must_contain_any"])
        safe_ok = all(term.lower() not in answer.lower() for term in case["must_not_contain"])
        details.append({"case": case["id"], "passed": tool_ok and text_ok and safe_ok,
                        "tool_selection_pass": tool_ok, "facts_check_pass": text_ok,
                        "forbidden_response_check_pass": safe_ok, "tools": used, "response": answer})
    passed = sum(1 for case in details if case["passed"])
    output = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "mode": "LOCAL_OLLAMA_LLM",
              "model": args.model, "cases": len(details), "passed": passed, "pass_rate_percent": round(100 * passed / len(details), 2),
              "results": details}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Local LLM evaluation: {passed}/{len(details)} passed. Saved {args.output}")
    if passed != len(details):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
