"""Record actual fixture conversations or export exact verified evaluation turns."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent import Agent, build_client
from app.evaluation import require_demo_database
from app.local_model import DEFAULT_MODEL, ensure_model
from app.tools import StoreTools, ToolContext


def format_scenario(scenario: dict, turns: list[dict]) -> str:
    lines = [f"## Conversation {scenario['id']}: {scenario['title']}", "",
             f"*Purpose: {scenario['why_this_matters']}*", ""]
    if scenario.get("customer_context") is not None:
        lines += ["*Host context: simulated authenticated customer 1; this is not real authentication.*", ""]
    for turn in turns:
        lines += [f"**Customer:** {turn['user']}", "", f"**Agent:** {turn['response']}", "",
                  f"**Tools:** {', '.join(turn['tools']) or '(none)'}", "",
                  f"**Response source:** {turn['response_source']}", "",
                  f"**Model planning calls:** {turn['model_calls']}; **model error:** {turn['model_error']}; **seconds:** {turn['duration_seconds']}", ""]
    return "\n".join(lines)


def recorded_scenario(scenario: dict, evaluation: dict, model: str) -> str:
    if evaluation.get("dataset") != "public_fixtures" or evaluation.get("mode") != "REAL_OLLAMA_PLANNING_PYTHON_FACTS":
        raise ValueError("Only public real-run evaluation records can be exported")
    if evaluation.get("model") != model:
        raise ValueError("Recorded model differs from the selected model")
    by_id = {turn["case"]: turn for turn in evaluation["results"]}
    turns = []
    for ident, question in zip(scenario["case_ids"], scenario["turns"], strict=True):
        turn = by_id[ident]
        if turn["user"] != question:
            raise ValueError("Recorded question differs from the scenario question")
        if not turn["passed"] or turn.get("model_error") or turn.get("customer_context") != scenario.get("customer_context"):
            raise ValueError("Scenario needs a passed run with the same host context")
        turns.append(turn)
    return format_scenario(scenario, turns)


def run_scenario(scenario: dict, *, db: Path, model: str, client) -> str:
    tools = StoreTools(ToolContext(db, scenario.get("customer_context")))
    agent = Agent(tools, client, model=model)
    turns = []
    for question in scenario["turns"]:
        started = time.monotonic()
        answer = agent.ask(question)
        if agent.last_model_error:
            raise RuntimeError("The model failed; do not label fallback responses as a successful live run")
        turns.append({"user": question, "response": answer, "tools": [n for n, _, _ in agent.last_records],
                      "response_source": agent.last_answer_source, "model_calls": agent.last_model_calls,
                      "model_error": agent.last_model_error, "duration_seconds": round(time.monotonic() - started, 2)})
    return format_scenario(scenario, turns)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/demo.db"))
    parser.add_argument("--scenarios", type=Path, default=Path("evals/scenarios.json"))
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    parser.add_argument("--scenario", type=int, action="append")
    parser.add_argument("--out", type=Path, default=Path("examples/live_conversations.md"))
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--from-evals", type=Path, help="Export the exact questions/answers from a verified real evaluation, without another inference")
    args = parser.parse_args()
    require_demo_database(args.db)
    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    if args.scenario:
        if set(args.scenario) - {s["id"] for s in scenarios}:
            parser.error("Unknown scenario")
        scenarios = [s for s in scenarios if s["id"] in args.scenario]
    header = (f"# Verified local agent conversations\n\nModel: `{args.model}`. "
              "Ollama interprets requests and selects tools; Python formats all factual replies. "
              "A privacy denial may use zero model calls. Model prose is never published.\n"
              "Data: exact fictional public fixtures. No private challenge data.\n\n")
    if args.from_evals:
        evaluation = json.loads(args.from_evals.read_text(encoding="utf-8"))
        captured = [(s, recorded_scenario(s, evaluation, args.model)) for s in scenarios]
    else:
        ensure_model(args.model)
        client = build_client()
        captured = [(s, run_scenario(s, db=args.db, model=args.model, client=client)) for s in scenarios]
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        for scenario, text in captured:
            (args.out_dir / f"live_conversation_{scenario['id']}.md").write_text(header + text, encoding="utf-8")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(header + "\n".join(text for _, text in captured), encoding="utf-8")
    print(f"Saved {len(captured)} verified conversation(s)")


if __name__ == "__main__":
    main()
