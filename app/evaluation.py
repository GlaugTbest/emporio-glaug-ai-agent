"""Deterministic evaluation of arguments, structured facts and displayed values."""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

from app.database import FIELDS, _read_csv, read_only_connection
from app.policies import sections_from_json
from app.responses import brl


def require_demo_database(path: str | Path) -> None:
    """Public recording scripts refuse customer data that differs from fixtures."""
    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    with read_only_connection(path) as conn:
        for table, fields in FIELDS.items():
            actual = [dict(r) for r in conn.execute(f"SELECT {','.join(fields)} FROM {table}")]
            expected = _read_csv(fixtures / f"{table}.csv", fields)
            def canonical(rows):
                return sorted(json.dumps(row, sort_keys=True) for row in rows)
            if canonical(actual) != canonical(expected):
                raise ValueError("Public recording requires the exact fictional fixture dataset")
        actual = [dict(r) for r in conn.execute("SELECT section_id,title,content,source_page FROM policies")]
        if sorted(actual, key=lambda p: p["section_id"]) != sorted(sections_from_json(fixtures / "demo_policies.json"), key=lambda p: p["section_id"]):
            raise ValueError("Public recording requires fictional demo policies")


def score_case(case: dict, answer: str, agent) -> dict:
    used = [name for name, _, _ in agent.last_records]
    tool_ok = case["expected_tool"] in used if case["expected_tool"] else not used
    for required in case.get("required_calls", []):
        tool_ok &= any(name == required["tool"] and all(args.get(k) == v for k, v in required["arguments"].items())
                       and not result.get("error") for name, args, result in agent.last_records)
    outcome = agent.last_outcome
    facts_ok = outcome.get("kind") == case["expected_kind"]
    if "expected_ids" in case:
        facts_ok &= sorted(p["product_id"] for p in outcome.get("products", [])) == sorted(case["expected_ids"])
    for key, value in case.get("expected_payment", {}).items():
        facts_ok &= outcome.get("payment", {}).get(key) == value
    if "expected_order_id" in case:
        facts_ok &= outcome.get("order", {}).get("order_id") == case["expected_order_id"]
    if "expected_pages" in case:
        facts_ok &= bool(set(case["expected_pages"]) & set(outcome.get("pages", [])))
    text_ok = all(term.lower() in answer.lower() for term in case.get("must_contain", []))
    if case.get("must_contain_any"):
        text_ok &= any(term.lower() in answer.lower() for term in case["must_contain_any"])
    safe_ok = all(term.lower() not in answer.lower() for term in case.get("must_not_contain", []))
    allowed = {Decimal(v) for v in case.get("expected_amounts", [])}
    amounts = re.findall(r"R\$\s*([\d.]+,\d{2})", answer)
    money_ok = all(Decimal(v.replace(".", "").replace(",", ".")) in allowed for v in amounts)
    for product, value in case.get("product_prices", {}).items():
        # The right price must be on the line of the right product.
        money_ok &= any(product.lower() in line.lower() and f"R$ {brl(value)}" in line for line in answer.splitlines())
    model_ok = not agent.last_model_error and (not case.get("require_model", True) or agent.last_model_calls > 0)
    checks = {"tool_selection_pass": bool(tool_ok), "facts_check_pass": bool(facts_ok and text_ok and money_ok),
              "forbidden_response_check_pass": safe_ok, "model_execution_pass": model_ok}
    return {"passed": all(checks.values()), **checks}
