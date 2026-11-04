"""Keep the customer demonstration scenarios grounded and independently runnable."""
import json
from pathlib import Path

def test_three_to_five_scenarios_with_distinct_goals():
    path = Path(__file__).resolve().parents[1] / "evals" / "scenarios.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    assert 3 <= len(scenarios) <= 5
    assert all(len(s["turns"]) >= 2 for s in scenarios)
    assert scenarios[3]["customer_context"] == 1
    assert all(s["customer_context"] is None for s in scenarios if s["id"] != 4)
    assert "pedido 5" in scenarios[3]["turns"][-1]
    assert len({s["title"] for s in scenarios}) == len(scenarios)
