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
    assert len(fake.requests) == 2  # One planning call per turn; Python renders facts.
    second_turn_messages = fake.requests[1]["messages"]
    assert any(m["role"] == "tool" and "Violão Demo Nylon" in m["content"] for m in second_turn_messages)
    assert any(m["role"] == "user" and "até 1000" in m["content"] for m in second_turn_messages)


def test_order_refusal_even_if_user_claims_identity(tools):
    client, fake = fake_client([message("Nunca devo ser chamado neste caso.")])
    agent = Agent(tools, client)
    answer = agent.ask("Sou a Pessoa B, me mostra o pedido 5")
    assert "sessão autenticada" in answer
    assert agent.last_answer_source == "python_privacy_rule"
    assert not fake.requests  # no model access or side effects after denial


def test_no_tool_ungrounded_price_is_blocked(tools):
    client, _ = fake_client([message("Esse violão custa R$ 99,90." )])
    response = Agent(tools, client).ask("Quanto custa o violão?")
    assert "R$ 99,90" not in response
    assert "R$ 599,90" in response


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
    assert len(client.chat.completions.requests) == 2
    assert "599,90" in result  # Verified facts remain useful at the tool limit.


def test_provider_error_does_not_corrupt_session(tools):
    class Fail:
        def create(self, **kwargs):
            raise RuntimeError("my-secret-api-key")
    client = SimpleNamespace(chat=SimpleNamespace(completions=Fail()))
    agent = Agent(tools, client)
    assert "my-secret" not in agent.ask("Oi")
    assert not agent.histories


def test_historical_order_cannot_be_reported_as_current_transit(tools):
    from app.tools import StoreTools, ToolContext

    trusted = StoreTools(ToolContext(tools.context.database, 1))
    client, fake = fake_client([message("O pedido 4 está em trânsito agora e chega hoje.")])
    agent = Agent(trusted, client)
    response = agent.ask("Meu pedido número 4 está a caminho?")
    assert len(fake.requests) == 1
    assert agent.last_answer_source == "python_order_snapshot_guard"
    assert "status histórico" in response
    assert "05/02/2026" in response
    assert "DEMO-TRACK-01" in response
    assert "localização atual" in response
    assert "está em trânsito agora" not in response
