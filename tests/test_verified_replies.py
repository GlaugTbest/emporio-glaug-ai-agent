from types import SimpleNamespace

import pytest

from app.agent import Agent
from app.tools import StoreTools


class Replies:
    def __init__(self, *answers):
        self.answers = iter(answers)

    def create(self, **kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=next(self.answers), tool_calls=[]))])


def agent(tools, *answers):
    return Agent(tools, SimpleNamespace(chat=SimpleNamespace(completions=Replies(*answers))))


def test_payment_after_changing_instrument_uses_new_product(db):
    class Traced(StoreTools):
        def __init__(self, context):
            super().__init__(context)
            self.payments = []

        def calculate_payment_options(self, product_id):
            self.payments.append(product_id)
            return super().calculate_payment_options(product_id)

    from app.tools import ToolContext
    tools = Traced(ToolContext(db))
    assistant = agent(tools, "O nylon custa R$ 599,90.", "A guitarra fica por R$ 569,91 no PIX.")
    assistant.ask("Quais violões até R$ 900?")
    answer = assistant.ask("E a Guitarra Demo Promocional, quanto fica no PIX?")
    assert tools.payments == [4]
    assert "1.680,00" in answer
    assert "569,91" not in answer


@pytest.mark.parametrize("untrusted", [
    "O Violão Demo Nylon custa R$ 900.",
    "O Violão Demo Nylon custa R$ 849,00.",
    "O Violão Demo Nylon custa 1 real.",
    "Todos os violões têm 99% de desconto no PIX.",
    "Já reservei o instrumento e cobrei seu cartão.",
])
def test_model_prose_cannot_change_catalog_facts_or_claim_actions(tools, untrusted):
    answer = agent(tools, untrusted).ask("Quero só violão de nylon até R$ 900.")
    assert "599,90" in answer
    assert "849,00" not in answer
    assert "custa 1 real" not in answer
    assert "99%" not in answer
    assert "reservei" not in answer
    assert "R$ 900" not in answer


def test_new_search_does_not_forget_same_category_material_and_budget(tools):
    assistant = agent(tools, "opções", "opções")
    assistant.ask("Quero só violão de nylon até R$ 900.")
    answer = assistant.ask("E outros violões disponíveis?")
    assert "599,90" in answer
    assert "849,00" not in answer
    assert "2.599,00" not in answer


def test_out_of_scope_is_not_accepted_as_free_model_prose(tools):
    answer = agent(tools, "O placar de futebol de hoje é 3 a 0.").ask("Me conte notícias de futebol de hoje.")
    assert "3 a 0" not in answer
    assert "instrumentos" in answer.lower()


def test_returns_are_guidance_not_an_automated_eligibility_decision(tools):
    answer = agent(tools, "Sua devolução foi negada definitivamente.").ask(
        "Comprei online há cinco dias, toquei e perdi a caixa. Posso devolver?")
    assert "sete dias" in answer.lower() or "7 dias" in answer.lower()
    assert "humano" in answer.lower()
    assert "negada definitivamente" not in answer


def test_model_failure_still_returns_already_verified_catalog(tools):
    class Offline:
        def create(self, **kwargs):
            raise OSError("unavailable")
    assistant = Agent(tools, SimpleNamespace(chat=SimpleNamespace(completions=Offline())))
    answer = assistant.ask("Quais violões de nylon até R$ 900?")
    assert "599,90" in answer


def test_conflicting_contacts_are_not_silently_selected(tools):
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(tools.context.database)) as conn, conn:
        conn.executemany("INSERT INTO policies VALUES (?,?,?,?)", [
            ("phone_a", "Contato WhatsApp", "WhatsApp (11) 1111-1111.", 10),
            ("phone_b", "Contato WhatsApp", "WhatsApp (22) 2222-2222.", 11),
        ])
    answer = agent(tools, "Use o primeiro telefone.").ask("Qual o WhatsApp de contato?")
    assert "divergentes" in answer.lower()
    assert "1111-1111" not in answer
    assert "2222-2222" not in answer


def test_material_filter_in_followup_removes_nonmatching_previous_options(tools):
    assistant = agent(tools, "opções", "opções")
    assistant.ask("Quais violões até R$ 1000?")
    answer = assistant.ask("E quais desses são de nylon?")
    assert "599,90" in answer
    assert "849,00" not in answer
    assert assistant.last_products["default"] == [1]


def test_unrequested_model_payment_call_does_not_replace_catalog_answer(tools):
    class UnrelatedTool:
        def create(self, **kwargs):
            call = SimpleNamespace(function=SimpleNamespace(
                name="calculate_payment_options", arguments='{"product_id": 1}'))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content="", tool_calls=[call]))])
    assistant = Agent(tools, SimpleNamespace(chat=SimpleNamespace(completions=UnrelatedTool())))
    answer = assistant.ask("Quais violões de nylon até R$ 900 estão em estoque?")
    assert "5 em estoque" in answer
    assert "569,91" not in answer
    assert assistant.last_outcome["kind"] == "catalog"


def test_ambiguous_payment_does_not_pick_first_of_several_products(tools):
    class Payment:
        def create(self, **kwargs):
            call = SimpleNamespace(function=SimpleNamespace(
                name="calculate_payment_options", arguments='{"product_id": 1}'))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))])
    assistant = agent(tools, "opções")
    assistant.ask("Quais violões até R$ 1000?")
    assistant.client = SimpleNamespace(chat=SimpleNamespace(completions=Payment()))
    answer = assistant.ask("E quanto fica no PIX?")
    assert "569,91" not in answer
    assert assistant.last_outcome["kind"] == "unconfirmed"


def test_explicit_first_option_can_be_used_for_payment(tools):
    assistant = agent(tools, "opções", "pagamento")
    assistant.ask("Quais violões até R$ 1000?")
    answer = assistant.ask("E o primeiro no PIX?")
    assert "569,91" in answer


def test_new_named_product_does_not_inherit_old_budget_and_material(tools):
    class NamedSearch:
        def create(self, **kwargs):
            call = SimpleNamespace(function=SimpleNamespace(
                name="search_products", arguments='{"query": "Takamine GD20"}'))
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[call]))])
    assistant = agent(tools, "opções")
    assistant.ask("Quero violão de nylon até R$ 900.")
    assistant.client = SimpleNamespace(chat=SimpleNamespace(completions=NamedSearch()))
    answer = assistant.ask("Quanto custa o Takamine GD20?")
    assert "2.599,00" in answer
