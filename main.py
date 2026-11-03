"""Interactive Portuguese customer-service CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.agent import Agent, build_client
from app.local_model import DEFAULT_MODEL, ensure_model
from app.database import read_only_connection
from app.tools import StoreTools, ToolContext


def main() -> None:
    parser = argparse.ArgumentParser(description="Empório da Música - CLI agent")
    parser.add_argument("--db", default="data/emporio.db", help="Local imported SQLite snapshot")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    parser.add_argument("--demo-customer-id", type=int, default=None,
                        help="UNSAFE for deployment: simulate an externally authenticated customer for local demos only")
    args = parser.parse_args()
    try:
        with read_only_connection(args.db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        ensure_model(args.model)
        client = build_client()
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        parser.exit(2, f"Setup error: {exc}\n")
    if args.demo_customer_id is not None and args.demo_customer_id <= 0:
        parser.exit(2, "--demo-customer-id must be positive\n")
    tools = StoreTools(ToolContext(Path(args.db), args.demo_customer_id))
    agent = Agent(tools=tools, client=client, model=args.model)
    print(f"Empório da Música | {count} catalog items loaded | Ollama local model: {args.model}")
    if args.demo_customer_id is not None:
        print("WARNING: --demo-customer-id is an INSECURE test simulation; NOT real authentication.")
    else:
        print("Order lookup disabled: no authenticated customer context.")
    print("Digite 'sair' para encerrar.\n")
    while True:
        try:
            message = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté mais!")
            return
        if message.lower() in {"sair", "exit", "quit"}:
            print("Até mais!")
            return
        if not message:
            continue
        print("Empório: " + agent.ask(message))


if __name__ == "__main__":
    main()
