"""Evals must actually assert answer facts rather than use empty lists."""

import json
from pathlib import Path


def test_eval_cases_have_fact_checks():
    cases = json.loads((Path(__file__).resolve().parents[1] / "evals/cases.json").read_text(encoding="utf-8"))
    assert 6 <= len(cases) <= 15
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["must_contain"] or case["must_not_contain"]
        assert case["expected_tool"] is None or isinstance(case["expected_tool"], str)
