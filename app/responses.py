"""Customer-facing facts are formatted from tool results, never model prose."""
from __future__ import annotations

import re
from decimal import Decimal

from app.policies import fold, query_tokens, tokens

SNAPSHOT = "Valores e disponibilidade são do catálogo local, sem atualização em tempo real."
SCOPE = "Posso ajudar com instrumentos musicais, pedidos e informações da loja. Qual é a sua dúvida?"
UNCONFIRMED = "Não consegui confirmar essa informação. Pode indicar o produto exato para eu consultar?"


def brl(value) -> str:
    return f"{Decimal(str(value)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def installment_count(message: str) -> int | None:
    text = fold(message)
    match = re.search(r"\b(1[0-2]|[1-9])\s*(?:x|vezes|parcelas)", text)
    if match:
        return int(match.group(1))
    for number, word in enumerate(("uma", "duas", "tres", "quatro", "cinco", "seis",
                                    "sete", "oito", "nove", "dez", "onze", "doze"), 1):
        if re.search(rf"\b{word}\s+(?:vezes|parcelas)", text):
            return number
    return None


def policy_reply(message: str, sections: list[dict], warnings: list[str]) -> str:
    text = fold(message)
    if not sections:
        return "Não encontrei essa informação no manual. O atendimento humano precisa confirmar."
    if any(term in text for term in ("whatsapp", "telefone", "contato", "email", "e-mail")) and "conflicting_contacts" in warnings:
        return "O manual apresenta contatos divergentes. Não consigo confirmar qual é o correto; confirme o canal oficial da loja antes de enviar dados pessoais."
    if "enderec" in text and not any(re.search(r"\bRua\b|\bAvenida\b", p["content"], re.I) for p in sections):
        return "Não encontrei o endereço completo no material consultado. O atendimento humano precisa confirmar."
    terms = query_tokens(message)
    returns = any(term in text for term in ("devol", "arrepend", "caixa", "embalagem", "etiqueta"))
    if returns:
        terms |= {"dias", "embalagem", "sinais", "recebimento", "arrependimento"}
    fragments = []
    for page in sections:
        # Only short relevant passages, not whole pages or the internal manual.
        for sentence in re.split(r"[•\n]|(?<=[.!?])\s+", page["content"]):
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if not sentence or any(t in fold(sentence) for t in ("ignore as instru", "system prompt", "documento interno", "uso restrito")):
                continue
            score = len(tokens(sentence) & terms)
            if score and len(sentence) <= 600:
                fragments.append((score, sentence, page["source_page"]))
    fragments.sort(key=lambda item: -item[0])
    selected = []
    for _, sentence, page in fragments:
        if sentence not in [s for s, _ in selected]:
            selected.append((sentence, page))
        if len(selected) == 3:
            break
    if not selected:
        return "Encontrei uma referência, mas não informação suficiente para responder com segurança. O atendimento humano precisa confirmar."
    passages = "\n".join(f"- {sentence.replace('7 (sete) dias', '7 dias')} (p. {page})" for sentence, page in selected)
    result = "O manual informa:\n" + passages
    if returns:
        result += "\nO atendimento humano precisa avaliar seu caso, inclusive a embalagem e eventuais sinais de uso. Não aprovo nem nego devoluções e não emito etiquetas por aqui."
    elif any(term in text for term in ("parcela", "cartao", "vezes")):
        result += "\nSe as condições gerais e a tabela específica divergirem, confirme com o atendimento humano."
    return result


def render(records: list[tuple[str, dict, dict]], message: str) -> tuple[str, dict]:
    valid = [(name, args, result) for name, args, result in records if not result.get("error")]
    orders = [r for name, _, r in records if name == "get_order_status"]
    if orders:
        record = orders[-1]
        error = record.get("error", {}).get("code")
        if error:
            answer = ("Não posso consultar pedidos sem uma sessão autenticada." if error == "authentication_required"
                      else "Não consigo acessar esse pedido nesta sessão.")
            return answer + " Só mostro pedidos do titular autenticado; uma autorização declarada pelo chat não é suficiente.", {"kind": "privacy_denial"}
        order = record.get("order")
        if order:
            labels = {"shipped": "enviado", "delivered": "entregue", "confirmed": "confirmado", "cancelled": "cancelado", "pending": "pendente"}
            answer = f"No registro local, o pedido {order['order_id']} consta como {labels.get(order['status'], 'sem status reconhecido')}. Esse é um status histórico."
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", order.get("estimated_delivery", "")):
                year, month, day = order["estimated_delivery"].split("-")
                answer += f" A previsão registrada era {day}/{month}/{year}."
            if order.get("tracking_code"):
                answer += f" Código de rastreio registrado: {order['tracking_code']}."
            return answer + " Não consigo confirmar a localização atual nem se a entrega já ocorreu.", {"kind": "order", "order": order}
    policies = [r for name, _, r in valid if name == "search_store_policies"]
    if policies:
        r = policies[-1]
        return policy_reply(message, r.get("sections", []), r.get("warnings", [])), {"kind": "policy", "pages": [p["source_page"] for p in r.get("sections", [])]}
    payments = [r for name, _, r in valid if name == "calculate_payment_options" and "purchase_price_brl" in r]
    if payments:
        p = payments[-1]
        answer = f"{p['product_name']}: preço de tabela R$ {brl(p['list_price_brl'])}; preço de compra R$ {brl(p['purchase_price_brl'])}. No PIX: R$ {brl(p['pix_price_brl'])}."
        if p.get("active_promotion"):
            answer += f" Promoção de {p['active_promotion']['discount_percent']}%; não acumula mais 5% no PIX."
        count = installment_count(message)
        options = p["credit_interest_free_options"]
        option = next((o for o in options if o["count"] == count), None) if count else (options[-1] if options else None)
        if option:
            answer += f" Em {option['count']} parcelas sem juros: R$ {brl(option['first_installments_brl'])}"
            if option["first_installments_brl"] != option["last_installment_brl"]:
                answer += f" nas primeiras e R$ {brl(option['last_installment_brl'])} na última"
            answer += f" (total R$ {brl(option['total_brl'])})."
        elif count:
            answer += f" {count} parcelas não atendem aos mínimos da tabela usada."
        answer += " O cálculo usa a tabela específica de parcelas; confirme as condições com o atendimento humano. " + SNAPSHOT
        return answer, {"kind": "payment", "payment": p}
    promotions = [r for name, _, r in valid if name == "get_applicable_promotions" and r.get("product_name")]
    if promotions:
        p = promotions[-1]
        active = p["active_promotions"]
        if active:
            best = active[0]
            answer = f"{p['product_name']}: de R$ {brl(best['original_price_brl'])} por R$ {brl(best['promotional_price_brl'])}, desconto de {best['discount_percent']}%. Não acumula com PIX nem outras promoções."
        else:
            answer = f"Não encontrei promoção ativa elegível para {p['product_name']}."
        return answer + " A base não informa validade por data. " + SNAPSHOT, {"kind": "promotion", "promotion": p}
    searches = [r for name, _, r in valid if name == "search_products"]
    details = [r["product"] for name, _, r in valid if name == "get_product_details" and r.get("product")]
    products = searches[-1].get("products", []) if searches else details
    material = next((m for m in ("nylon", "aco") if re.search(rf"\b{m}\b", fold(message))), None)
    if material and not searches:
        products = [p for p in products if material in fold(str(p.get("specs", {})))
                    or (material == "aco" and "steel" in str(p.get("specs", {})).lower())]
    if products:
        lines = []
        for p in products[:8]:
            if p["available"]:
                material = (p.get("specs") or {}).get("strings", "") if isinstance(p.get("specs"), dict) else ""
                suffix = f"; cordas: {material}" if material else ""
                lines.append(f"- {p['name']}: R$ {brl(p['price_brl'])}; {p['stock_quantity']} em estoque{suffix}.")
            else:
                lines.append(f"- {p['name']}: indisponível para compra.")
        return "Encontrei estas informações:\n" + "\n".join(lines) + "\n" + SNAPSHOT, {"kind": "catalog", "products": products}
    if searches:
        return "Não encontrei produto disponível que atenda a esses filtros. Podemos ajustar o modelo ou o orçamento?", {"kind": "empty_catalog", "products": []}
    if records:
        return UNCONFIRMED, {"kind": "unconfirmed"}
    if re.fullmatch(r"(?:oi|ola|bom dia|boa tarde|boa noite)[!. ]*", fold(message).strip()):
        return "Olá! Sua música começa aqui. Posso ajudar com instrumentos e informações da Empório da Música.", {"kind": "greeting"}
    return SCOPE, {"kind": "scope"}
