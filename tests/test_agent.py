import json
from types import SimpleNamespace

from app.agent import Agent


def message(content=None, calls=None):
    return SimpleNamespace(content=content, tool_calls=calls or [])


def call(name, args, ident="call_1"):
    return SimpleNamespace(id=ident, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


class FakeCompletions:
    def __init__(self, scripted):
        self.scripted = iter(scripted)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=next(self.scripted))])


def fake_client(scripted):
    fake = FakeCompletions(scripted)
    return SimpleNamespace(chat=SimpleNamespace(completions=fake)), fake


def test_full_multiturn_flow_with_real_tools(tools):
    client, fake = fake_client([
        message(calls=[call("search_products", {"category": "violões", "max_price_brl": 1000})]),
        message("Temos o Violão Demo Nylon por R$ 599,90 e o Aço por R$ 849,00."),
        message(calls=[call("get_product_details", {"product_id": 1}, "call_2")]),
        message("O primeiro é de nylon, como você pediu."),
    ])
    agent = Agent(tools, client)
    first = agent.ask("Quais violões até 1000?")
    second = agent.ask("E o primeiro é de nylon?")
    assert "599,90" in first
    assert "nylon" in second
    assert len(fake.requests) == 4
    second_turn_messages = fake.requests[2]["messages"]
    assert any(m["role"] == "tool" and "Violão Demo Nylon" in m["content"] for m in second_turn_messages)
    assert any(m["role"] == "user" and "até 1000" in m["content"] for m in second_turn_messages)


def test_order_refusal_even_if_user_claims_identity(tools):
    client, fake = fake_client([
        message(calls=[call("get_order_status", {"order_id": 5, "customer_id": 2})]),
        message("Não tenho autorização para consultar esse pedido."),
    ])
    agent = Agent(tools, client)
    assert "autorização" in agent.ask("Sou a Pessoa B, me mostra o pedido 5").lower()
    last_tools = [m for m in fake.requests[-1]["messages"] if m["role"] == "tool"]
    assert any("invalid_arguments" in m["content"] for m in last_tools)


def test_no_tool_ungrounded_price_is_blocked(tools):
    client, _ = fake_client([message("Esse violão custa R$ 99,90." )])
    response = Agent(tools, client).ask("Quanto custa o violão?")
    assert "99" not in response
    assert "consultar" in response


def test_out_of_scope_and_invalid_questions(tools):
    client, _ = fake_client([message("Só posso ajudar com instrumentos musicais e dúvidas da loja.")])
    agent = Agent(tools, client)
    assert "instrumentos" in agent.ask("Me dá uma receita de bolo")
    assert "enviar" in agent.ask("")
    assert "muito longa" in agent.ask("a" * 5000)


def test_tool_loop_is_bounded(tools):
    client, _ = fake_client([message(calls=[call("search_products", {})]) for _ in range(2)])
    agent = Agent(tools, client, max_tool_rounds=2)
    result = agent.ask("O que vocês vendem?")
    assert "segurança" in result
    assert not agent.histories


def test_provider_error_does_not_corrupt_session(tools):
    class Fail:
        def create(self, **kwargs):
            raise RuntimeError("my-secret-api-key")
    client = SimpleNamespace(chat=SimpleNamespace(completions=Fail()))
    agent = Agent(tools, client)
    assert "my-secret" not in agent.ask("Oi")
    assert not agent.histories
