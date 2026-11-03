from decimal import Decimal

from app.tools import StoreTools, ToolContext


def test_product_search_and_contextual_filters(tools):
    result = tools.search_products(category="violões", max_price_brl=1000)
    assert [p["product_id"] for p in result["products"]] == [1, 2]
    assert all(p["available"] for p in result["products"])
    assert tools.search_products(query="Não Existe")["products"] == []
    assert tools.search_products(query="Demo Sem Estoque")["excluded_unavailable_count"] == 1


def test_active_status_is_not_sufficient(tools):
    assert tools.get_product_details(3)["product"]["available"] is False
    assert tools.get_product_details(5)["product"]["available"] is False
    assert tools.get_product_details(6)["product"]["available"] is False
    assert tools.search_products(available_only=False)["match_count"] == 7


def test_tool_allowlist_and_validation(tools):
    assert tools.execute("execute_sql", {"sql": "DROP TABLE products"})["error"]["code"] == "unknown_tool"
    assert tools.execute("search_products", {"query": "'; DROP TABLE products;--"})["products"] == []
    assert tools.execute("search_products", {"limit": 100})["error"]["code"] == "tool_error"
    assert tools.execute("search_products", {"limit": 2, "customer_id": 1})["error"]["code"] == "invalid_arguments"
    assert tools.execute("get_product_details", {"product_id": True})["error"]["code"] == "tool_error"


def test_active_inactive_and_non_cumulative_promotions(tools):
    promo = tools.get_applicable_promotions(4)
    assert promo["active_promotions"][0]["original_price_brl"] == "2100.00"
    assert promo["active_promotions"][0]["promotional_price_brl"] == "1680.00"
    assert tools.get_applicable_promotions(7)["active_promotions"] == []
    assert tools.get_applicable_promotions(3)["active_promotions"] == []
    pay = tools.calculate_payment_options(4)
    assert pay["purchase_price_brl"] == "1680.00"
    assert pay["pix_price_brl"] == "1680.00"  # no cumulative PIX
    assert pay["pix_extra_discount_applied"] is False
    assert tools.calculate_payment_options(1)["pix_price_brl"] == "569.91"


def test_credit_boundaries_and_sum(tools):
    for product in [1, 2, 4, 7]:
        pay = tools.calculate_payment_options(product)
        for option in pay["credit_interest_free_options"]:
            number = option["count"]
            value = Decimal(option["first_installments_brl"])
            last = Decimal(option["last_installment_brl"])
            total = Decimal(option["total_brl"])
            assert value * (number - 1) + last == total
            threshold = 50 if number <= 3 else 80 if number <= 6 else 100
            assert value >= threshold and last >= threshold
    assert tools.calculate_payment_options(3)["error"]["code"] == "unavailable"


def test_order_identity_cannot_be_changed_by_model(db):
    anonymous = StoreTools(ToolContext(db))
    first_customer = StoreTools(ToolContext(db, authenticated_customer_id=1))
    assert anonymous.get_order_status(4)["error"]["code"] == "authentication_required"
    assert first_customer.get_order_status(4)["order"]["status"] == "shipped"
    assert first_customer.get_order_status(5)["error"]["code"] == "not_found"
    assert first_customer.execute("get_order_status", {"order_id": 5, "customer_id": 2})["error"]["code"] == "invalid_arguments"
    assert "email" not in str(first_customer.get_order_status(4))


def test_policy_retrieval_with_source(tools):
    return_pages = tools.search_store_policies("me arrependi de uma compra online, posso devolver?")["sections"]
    assert return_pages and any("arrependimento" in r["content"].lower() for r in return_pages)
    assert any("source_page" in r for r in return_pages)
    assert tools.search_store_policies("qual horário abre aos sábados?")["sections"]
