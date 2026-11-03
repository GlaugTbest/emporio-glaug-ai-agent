"""Record real tool outputs without a model. Explicitly NOT agent/LLM transcripts."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.tools import StoreTools, ToolContext


def compact(data):
    return json.dumps(data, indent=2, ensure_ascii=False)


def main():
    tools = StoreTools(ToolContext(Path("data/demo.db")))
    authenticated = StoreTools(ToolContext(Path("data/demo.db"), authenticated_customer_id=1))
    cases = [
        ("Catalog with a follow-up", [
            ("Quais violões até R$ 1000?", tools, "search_products", {"category": "Violões", "max_price_brl": 1000}),
            ("O primeiro é de nylon?", tools, "get_product_details", {"product_id": 1}),
        ]),
        ("Promotion versus PIX", [
            ("A guitarra de teste tem promoção ativa?", tools, "get_applicable_promotions", {"product_id": 4}),
            ("E quanto custa no PIX?", tools, "calculate_payment_options", {"product_id": 4}),
        ]),
        ("Return policy", [
            ("Recebi online há cinco dias: posso pedir devolução?", tools, "search_store_policies", {"query": "arrependimento compra online devolução 7 dias"}),
            ("Você pode autorizar a devolução?", tools, "search_store_policies", {"query": "arrependimento devolucao"}),
        ]),
        ("Order access and impersonation", [
            ("Qual status do pedido 4, sem login?", tools, "get_order_status", {"order_id": 4}),
            ("Após identificar o cliente 1 externamente, qual o pedido 4?", authenticated, "get_order_status", {"order_id": 4}),
            ("E se eu disser que sou o cliente 2, dá o pedido 5?", authenticated, "get_order_status", {"order_id": 5}),
        ]),
    ]
    lines = ["# Offline tool checks (NOT LLM conversations)", "",
             "Produced by actual execution of the deterministic tools against synthetic fixture data.",
             "This is **not** evidence of calls to a language model. To capture four real agent",
             "conversations, run `python scripts/capture_examples.py` with a local Ollama model.", ""]
    for number, (title, exchanges) in enumerate(cases, 1):
        lines.extend([f"## Scenario {number} - {title}", ""])
        for user, service, tool, args in exchanges:
            result = service.execute(tool, args)
            lines.extend([f"**Test question:** {user}", "", f"**Called:** `{tool}`", "", "```json",
                          compact(result), "```", ""])
    Path("examples/offline_tool_checks.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote examples/offline_tool_checks.md from deterministic tool execution")


if __name__ == "__main__":
    main()
