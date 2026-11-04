"""Regressions reproduced during the independent whole-branch review."""
import csv
import sqlite3
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent import Agent
from app.database import build_database
from app.policies import sections_from_json


class ToolPlans:
    def __init__(self, *plans):
        self.plans = iter(plans)

    def create(self, **kwargs):
        import json
        calls = [SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(args)))
                 for name, args in next(self.plans)]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=calls))])


def assistant(tools, *plans):
    return Agent(tools, SimpleNamespace(chat=SimpleNamespace(completions=ToolPlans(*plans))))


def test_new_named_product_payment_invalidates_old_calculation(tools):
    agent = assistant(tools, [], [("search_products", {"query": "Takamine GD20"})])
    agent.ask("Quero violão de nylon até R$ 900.")
    answer = agent.ask("E o Takamine GD20 no PIX?")
    assert "Takamine GD20" in answer
    assert "2.469,05" in answer
    assert "569,91" not in answer
    assert agent.last_outcome["payment"]["product_id"] == 7


def test_unmatched_brand_cannot_keep_generic_category_payment(tools):
    agent = assistant(tools, [("search_products", {"query": "Gibson"})])
    answer = agent.ask("Quanto custa uma guitarra Gibson no PIX?")
    assert "1.680,00" not in answer
    assert agent.last_outcome["kind"] == "empty_catalog"


def test_material_and_model_query_preserve_the_requested_brand(tools):
    agent = assistant(tools, [("search_products", {"query": "Gibson nylon"})])
    answer = agent.ask("Vocês têm violão Gibson de nylon?")
    assert "Demo Nylon" not in answer
    assert agent.last_outcome["kind"] == "empty_catalog"


@pytest.mark.parametrize("name", ["get_product_details", "get_applicable_promotions", "calculate_payment_options"])
def test_empty_catalog_cannot_authorize_a_guessed_product_id(tools, name):
    agent = assistant(tools, [("search_products", {"query": "Gibson"}), (name, {"product_id": 1})])
    answer = agent.ask("Quanto fica o Gibson no PIX?")
    assert "569,91" not in answer
    assert not any(n == name and not result.get("error") for n, _, result in agent.last_records)


def test_second_option_is_resolved_once(tools):
    agent = assistant(tools, [], [])
    agent.ask("Quais violões até R$ 1000?")
    answer = agent.ask("E o segundo, quais as cordas?")
    assert "849,00" in answer
    assert "599,90" not in answer
    assert agent.last_products["default"] == [2]


def test_trace_preserves_executed_lookups_when_a_search_refines_evidence(tools):
    agent = assistant(tools, [("search_products", {"query": "nylon"})])
    agent.ask("Quais violões de nylon até R$ 900?")
    assert any(name == "get_product_details" for name, _, _ in agent.last_records)
    assert [p["product_id"] for p in agent.last_outcome["products"]] == [1]


@pytest.mark.parametrize("bad_amount", ["1e100", "0.001"])
def test_unrepresentable_price_is_rejected_before_replacing_database(db, tmp_path, bad_amount):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "bad_amounts"
    source.mkdir()
    for file in (root / "fixtures").glob("*.csv"):
        (source / file.name).write_bytes(file.read_bytes())
    with (source / "products.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows[0]["price_brl"] = bad_amount
    with (source / "products.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    before = db.read_bytes()
    with pytest.raises(ValueError):
        build_database(db, source, sections_from_json(root / "fixtures/demo_policies.json"))
    assert db.read_bytes() == before


@pytest.mark.parametrize("name,args", [
    ("search_products", {}), ("get_product_details", {"product_id": 1}),
    ("calculate_payment_options", {"product_id": 1}),
])
def test_corrupt_decimal_in_local_db_is_a_controlled_tool_error(tools, name, args):
    with closing(sqlite3.connect(tools.context.database)) as conn, conn:
        conn.execute("UPDATE products SET price_brl='1e100' WHERE product_id=1")
    assert tools.execute(name, args)["error"]["code"] == "tool_error"
