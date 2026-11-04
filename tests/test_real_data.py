"""Optional contract checks against the private assignment snapshot (never committed)."""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.database import build_database, read_only_connection
from app.policies import sections_from_pdf
from app.tools import StoreTools, ToolContext


@pytest.fixture(scope="module")
def original_tools(tmp_path_factory):
    source, manual = os.getenv("ARTEFACT_SOURCE_DIR"), os.getenv("ARTEFACT_POLICY_PDF")
    if not source or not manual:
        pytest.skip("Set ARTEFACT_SOURCE_DIR and ARTEFACT_POLICY_PDF for private dataset tests")
    db = tmp_path_factory.mktemp("original") / "store.db"
    counts = build_database(db, Path(source), sections_from_pdf(Path(manual)))
    assert counts == {"categories": 9, "products": 65, "customers": 50, "orders": 20,
                      "order_items": 22, "promotions": 25, "policies": 8}
    with read_only_connection(db) as conn:
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    return StoreTools(ToolContext(db))


def test_takamine_price_stock_from_assignment(original_tools):
    result = original_tools.search_products(query="Takamine GD20")
    assert result["match_count"] == 1
    found = result["products"][0]
    assert found["price_brl"] == "2199.00"
    assert found["stock_quantity"] == 5
    assert found["available"] is True


def test_budget_search_excludes_unavailable(original_tools):
    r = original_tools.search_products(category="violões", max_price_brl=1000)
    assert r["match_count"] == 12
    assert r["excluded_unavailable_count"] == 2
    assert all(p["available"] and Decimal(p["price_brl"]) <= 1000 for p in r["products"])


def test_original_document_payment_and_privacy_retrieval(original_tools):
    pages = original_tools.search_store_policies("Quais os limites para parcelar no cartão?")["sections"]
    assert pages[0]["source_page"] == 3
    privacy = original_tools.search_store_policies("Como solicitar exclusão dos meus dados LGPD?")["sections"]
    assert any(page["source_page"] == 8 for page in privacy)


def test_original_promotions_are_not_assumed_time_valid(original_tools):
    result = original_tools.get_applicable_promotions(127)
    assert result["active_promotions"][0]["discount_percent"] == "10"
    assert "No date range" in result["note"]


def test_original_orders_require_authentication(original_tools):
    assert original_tools.get_order_status(1)["error"]["code"] == "authentication_required"


def original_agent(tools):
    from types import SimpleNamespace
    from app.agent import Agent
    class NoProse:
        def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[]))])
    return Agent(tools, SimpleNamespace(chat=SimpleNamespace(completions=NoProse())))


def test_original_contact_conflicts_are_disclosed(original_tools):
    answer = original_agent(original_tools).ask("Qual o WhatsApp de contato?")
    assert "divergentes" in answer


def test_original_return_guidance_keeps_human_eligibility_review(original_tools):
    answer = original_agent(original_tools).ask("Recebi online há cinco dias e perdi a embalagem. Posso devolver?")
    assert "7 dias" in answer
    assert "humano" in answer
    assert "não aprovo nem nego" in answer.lower()


def test_original_saturday_hours_come_from_policy(original_tools):
    answer = original_agent(original_tools).ask("Qual o horário de funcionamento no sábado?")
    assert "09:00" in answer
    assert "13:00" in answer
