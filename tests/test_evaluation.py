from types import SimpleNamespace

from app.agent import Agent
from app.evaluation import score_case


def catalog_answer(tools):
    class Reply:
        def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[]))])
    agent = Agent(tools, SimpleNamespace(chat=SimpleNamespace(completions=Reply())))
    return agent.ask("Quero só violão de nylon até R$ 900."), agent


CASE = {"expected_tool": "search_products", "expected_kind": "catalog", "expected_ids": [1],
        "expected_amounts": ["599.90"], "product_prices": {"Violão Demo Nylon": "599.90"},
        "must_contain": [], "must_not_contain": ["Violão Demo Aço"], "require_model": True}


def test_evaluation_accepts_verified_matching_product(tools):
    answer, agent = catalog_answer(tools)
    assert score_case(CASE, answer, agent)["passed"]


def test_evaluation_rejects_price_from_another_product(tools):
    answer, agent = catalog_answer(tools)
    assert not score_case(CASE, answer.replace("599,90", "849,00"), agent)["passed"]


def test_evaluation_rejects_nylon_answer_recommending_steel(tools):
    answer, agent = catalog_answer(tools)
    answer += " Recomendo o Violão Demo Aço para sua preferência por nylon."
    assert not score_case(CASE, answer, agent)["passed"]


def test_evaluation_rejects_unverified_product_even_if_text_matches(tools):
    answer, agent = catalog_answer(tools)
    agent.last_outcome["products"] = []
    assert not score_case(CASE, answer, agent)["passed"]


def test_evaluation_does_not_count_model_failure_as_live_success(tools):
    answer, agent = catalog_answer(tools)
    agent.last_model_error = True
    assert not score_case(CASE, answer, agent)["passed"]


def test_unknown_brand_evaluation_does_not_confuse_podemos_with_demo(tools):
    import json
    from pathlib import Path
    class Reply:
        def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[]))])
    cases = json.loads((Path(__file__).resolve().parents[1] / "evals/cases.json").read_text(encoding="utf-8"))
    case = next(c for c in cases if c["id"] == "unknown_brand")
    agent = Agent(tools, SimpleNamespace(chat=SimpleNamespace(completions=Reply())))
    answer = agent.ask(case["user"])
    assert score_case(case, answer, agent)["passed"]
