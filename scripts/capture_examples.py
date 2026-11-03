"""Run and preserve genuine Ollama customer conversations using only fictitious data.

This script never invents an answer. Each selected scenario is independent, so a
slow/failed model run does not erase the other transcripts.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import Agent, build_client
from app.local_model import DEFAULT_MODEL, ensure_model
from app.tools import StoreTools, ToolContext


class RecordingTools(StoreTools):
    def __init__(self, context):
        super().__init__(context)
        self.calls = []

    def execute(self, tool_name, args):
        self.calls.append({"name": tool_name, "arguments": args})
        return super().execute(tool_name, args)


def run_scenario(scenario: dict, *, db: Path, model: str, client) -> str:
    # Identity comes from the host test scenario, never the customer's words.
    customer_id = scenario.get("customer_context")
    tools = RecordingTools(ToolContext(db, customer_id))
    agent = Agent(tools=tools, client=client, model=model)
    lines = [f"## Conversation {scenario['id']}: {scenario['title']}", "",
             f"*Purpose: {scenario['why_this_matters']}*", ""]
    if customer_id is not None:
        lines.extend(["*Test context: simulated trusted customer 1, not real authentication.*", ""])
    for index, question in enumerate(scenario["turns"], 1):
        before = len(tools.calls)
        print(f"Scenario {scenario['id']} turn {index}: asking model", flush=True)
        answer = agent.ask(question)
        if answer.startswith("Não consegui consultar o assistente agora"):
            raise RuntimeError(f"Local model could not answer scenario {scenario['id']} turn {index}")
        used = [call["name"] for call in tools.calls[before:]]
        print(f"Scenario {scenario['id']} turn {index}: tools={used}; chars={len(answer)}", flush=True)
        lines += [f"**Customer:** {question}", "", f"**Agent:** {answer}", "",
                  f"**Tools:** {', '.join(used) if used else '(none)'}", "",
                  f"**Response source:** {agent.last_answer_source}", ""]
    if not tools.calls:
        raise RuntimeError(f"Scenario {scenario['id']} never used a tool; inspect before submitting")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/demo.db"))
    parser.add_argument("--scenarios", type=Path, default=Path("evals/scenarios.json"))
    parser.add_argument("--out", type=Path, default=Path("examples/live_conversations.md"))
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    parser.add_argument("--scenario", type=int, action="append", help="Scenario number (repeatable)")
    args = parser.parse_args()
    ensure_model(args.model)
    data = json.loads(args.scenarios.read_text(encoding="utf-8"))
    if args.scenario:
        missing = sorted(set(args.scenario) - {s["id"] for s in data})
        if missing:
            parser.error(f"Unknown scenario(s): {missing}")
        data = [s for s in data if s["id"] in args.scenario]
    client = build_client()
    lines = ["# Real agent conversations — local Ollama", "",
             f"Model: `{args.model}`. Captured during real local inference; individual answers may be model text or Python safety guards.",
             "Data: publicly shareable fictional fixtures, not the private recruitment data.", ""]
    for s in data:
        lines.append(run_scenario(s, db=args.db, model=args.model, client=client))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(data)} actual scenario(s) to {args.out}", flush=True)


if __name__ == "__main__":
    main()
