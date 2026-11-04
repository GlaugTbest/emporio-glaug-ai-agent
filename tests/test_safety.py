from pathlib import Path

import pytest

from app.tools import StoreTools, ToolContext


@pytest.mark.parametrize("tool,argument", [
    ("get_product_details", "product_id"),
    ("get_order_status", "order_id"),
    ("get_applicable_promotions", "product_id"),
    ("calculate_payment_options", "product_id"),
])
def test_oversized_id_is_rejected_before_database_access(tool, argument):
    tools = StoreTools(ToolContext(Path("does-not-exist.db")))
    assert tools.execute(tool, {argument: 10**30})["error"]["code"] == "tool_error"


def test_malformed_tool_name_is_a_controlled_error():
    tools = StoreTools(ToolContext(Path("does-not-exist.db")))
    assert tools.execute(["get_order_status"], {})["error"]["code"] == "unknown_tool"
