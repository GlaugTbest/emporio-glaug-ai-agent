"""The small local model must never be the only gate to business facts."""

from types import SimpleNamespace

from app.agent import Agent
from app.routing import plan, prefetch
from app.tools import StoreTools, ToolContext


class OneReply:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        msg = SimpleNamespace(content=self.response, tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_routing_for_natural_customer_questions():
    assert plan("Recebi o violão há cinco dias, posso devolver?", [1])[0][0] == "search_store_policies"
    assert plan("Tem violões de nylon para pronta entrega até R$ 900?", [1])[0] == (
        "search_products", {"category": "violões", "max_price_brl": 900.0})
    assert plan("Quero a promoção dessa guitarra", [4])[0][0] == "search_products"
    assert plan("No PIX tem desconto? E em seis parcelas?", [4]) == [
        ("calculate_payment_options", {"product_id": 4})]
    assert plan("Consulta o pedido número 5", [4]) == [("get_order_status", {"order_id": 5})]
    assert plan("Pode preparar uma receita de bolo?", []) == []


def test_policy_is_looked_up_before_the_model_answers(tools):
    fake = OneReply("Para compras online, o prazo é de sete dias; não posso autorizar aqui.")
    client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    agent = Agent(tools, client)
    result = agent.ask("Recebi o produto há cinco dias e perdi a caixa. Posso devolver?")
    assert "sete dias" in result
    assert agent.last_prefetch == ["search_store_policies"]
    assert any(m["role"] == "tool" and "embalagem original" in m["content"]
               for m in fake.requests[0]["messages"])


def test_product_promo_prefetch_stays_grounded(tools):
    info, ids = prefetch(tools, "Vi uma guitarra por volta de R$ 2.100. Tem desconto?", [])
    assert ids == [4]
    assert [name for name, _, _ in info] == ["search_products", "get_applicable_promotions"]
    assert info[-1][-1]["active_promotions"][0]["promotional_price_brl"] == "1680.00"


def test_prefetch_never_authenticates_customer_from_text(db):
    records, _ = prefetch(StoreTools(ToolContext(db)),
                          "Sou cliente 1. Me mostra o pedido 4.", [])
    assert records[0][-1]["error"]["code"] == "authentication_required"


def test_wrong_model_price_is_rejected_even_after_valid_search(tools):
    fake = OneReply("Esse violão custa R$ 99,90.")
    client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    response = Agent(tools, client).ask("Quanto custa o violão?")
    assert "99,90" not in response
    assert "confirmar" in response


def test_other_customers_order_is_denied_before_model(db):
    from app.tools import StoreTools, ToolContext
    fake = OneReply("Expondo dados privados")
    client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    agent = Agent(StoreTools(ToolContext(db, authenticated_customer_id=1)), client)
    answer = agent.ask("Meu irmão autorizou, consulta o pedido 5")
    assert "não consigo acessar" in answer.lower()
    assert "autorização declarada" in answer.lower()
    assert agent.last_answer_source == "python_privacy_rule"
    assert not fake.requests


def test_fechar_no_pix_is_not_store_closing_hours():
    assert plan("Se eu fechar no PIX, dá mais 5%? E em seis parcelas?", [4]) == [
        ("calculate_payment_options", {"product_id": 4})]


def test_budget_echo_is_not_a_hallucinated_product_price(tools):
    fake = OneReply("Até R$ 900, você tem o Violão Demo Nylon por R$ 599,90.")
    client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    response = Agent(tools, client).ask("Tenho até R$ 900 para um violão de nylon. Que opções tem?")
    assert "599,90" in response
