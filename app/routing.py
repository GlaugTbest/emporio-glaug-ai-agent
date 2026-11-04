"""Small deterministic prefetch; Ollama handles other phrasings through tools."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.policies import fold
from app.tools import StoreTools

POLICY_MARKERS = ("devolu", "devolv", "troca", "arrepend", "garanti", "reembols", "embalagem",
                  "caixa", "etiqueta", "horario", "abert", "fechado", "que horas", "enderec",
                  "frete", "entrega", "whatsapp", "contato", "acessorio", "palhet", "pedal")
PAYMENT_MARKERS = ("pix", "parcela", "cartao", "vezes")
CATEGORIES = (("violao", "violões"), ("violoes", "violões"), ("guitarra", "guitarras"),
              ("baixo", "baixos"), ("bateria", "baterias"), ("teclado", "teclados"),
              ("ukulele", "ukuleles"), ("piano", "pianos"))
QUERY_FILLER = set("a o as os um uma uns umas de do da dos das e em no na nos nas com sem para por ate eu meu minha voce voces tem tenho quero queria quais qual quanto custa custam preco precos esta estao estar disponivel disponiveis estoque pronta entrega algum alguma alguns algumas modelo modelos opcoes opcao esses essas desse dessa desses dessas primeiro segundo oi ola estou comecando aprender tocar vi ela ele catalogo volta pix parcela parcelas seis vezes cartao promocao desconto descontos por cima so mesmo agora quanto fica ficaria cordas corda".split())
QUERY_CATEGORIES = {fold(label) for _, label in CATEGORIES} | {term for term, _ in CATEGORIES}
QUERY_FILLER.update({"se", "fechar", "mais", "que", "outro", "outra", "outros", "outras"})


def product_query(message: str) -> str:
    text = fold(message)
    text = re.sub(r"(?:ate|por volta|orcamento de|tenho)\s*(?:r\$\s*)?[\d.,]+", "", text)
    text = re.sub(r"r\$\s*[\d.,]+", "", text)
    text = re.sub(r"\d+(?:[.,]\d+)?\s*%", "", text)
    words = [word for word in re.findall(r"[a-z0-9]+", text)
             if word not in QUERY_FILLER and word not in QUERY_CATEGORIES]
    return " ".join(dict.fromkeys(words))


def search_filters(message: str, previous: dict | None = None) -> dict:
    text = fold(message)
    category = next((label for term, label in CATEGORIES if term in text), "")
    old = previous or {}
    query = product_query(message)
    product_intent = bool(category) or any(term in text for term in ("quanto custa", "preco", "no pix"))
    named = product_intent and query and any(word not in {"nylon", "aco"} for word in query.split())
    filters = old.copy() if not named and (not category or category == old.get("category")) else {}
    if category:
        filters["category"] = category
    if "sem limite" in text or "qualquer preco" in text:
        filters.pop("max_price_brl", None)
    budget = re.search(r"(?:ate|por volta|orcamento de|tenho)\s*(?:r\$\s*)?([\d.,]+)", text)
    if budget:
        value = budget.group(1).rstrip(".,")
        if "," in value:
            value = value.replace(".", "").replace(",", ".")
        elif "." in value and len(value.rsplit(".", 1)[1]) == 3:
            value = value.replace(".", "")
        try:
            maximum = Decimal(value)
            if maximum.is_finite() and 0 <= maximum <= 10**9:
                filters["max_price_brl"] = float(maximum)
        except InvalidOperation:
            pass
    for material in ("nylon", "aco"):
        if re.search(rf"\b{material}\b", text) and not re.search(rf"nao(?: quero)?\s+{material}", text):
            filters["query"] = material
    if product_intent and query:
        filters["query"] = query
    return filters


def plan(message: str, product_ids: list[int]) -> list[tuple[str, dict]]:
    text = fold(message)
    match = re.search(r"\bpedido\s*(?:e\s*o\s*)?(?:numero\s*|n[ºo.]\s*)?#?\s*(\d{1,18})\b", text)
    if match:
        return [("get_order_status", {"order_id": int(match.group(1))})]
    product_question = "pronta entrega" in text and any(term in text for term, _ in CATEGORIES)
    if any(marker in text for marker in POLICY_MARKERS) and not product_question:
        return [("search_store_policies", {"query": message[:300]})]
    filters = search_filters(message)
    if filters.get("category") or filters.get("query") and any(term in text for term in ("quanto custa", "preco", "no pix")):
        # Payment depends on this search's result, never on the previous product.
        return [("search_products", filters)]
    selected = product_ids[:1] if "primeiro" in text else product_ids[1:2] if "segundo" in text else product_ids
    if selected and any(term in text for term in ("promoc", "descont", *PAYMENT_MARKERS)):
        if len(selected) == 1:
            name = "calculate_payment_options" if any(term in text for term in PAYMENT_MARKERS) else "get_applicable_promotions"
            return [(name, {"product_id": selected[0]})]
    if product_ids and any(term in text for term in ("nylon", "aco", "corda", "estoque", "primeiro", "segundo")):
        ids = selected[:3]
        return [("get_product_details", {"product_id": pid}) for pid in ids]
    return []


def prefetch(tools: StoreTools, message: str, product_ids: list[int], filters: dict | None = None):
    records = []
    ids = product_ids.copy()
    text = fold(message)
    for name, args in plan(message, ids):
        if name == "search_products" and filters:
            args = {**args, **filters}
        result = tools.execute(name, args)
        records.append((name, args, result))
        if name == "search_products":
            ids = [item["product_id"] for item in result.get("products", [])]
        elif "primeiro" in text or "segundo" in text:
            ids = [args["product_id"]] if "product_id" in args else ids
    fresh_search = any(name == "search_products" for name, _, _ in records)
    if fresh_search and any(term in text for term in ("nylon", "aco")):
        for pid in ids[:3]:
            args = {"product_id": pid}
            records.append(("get_product_details", args, tools.execute("get_product_details", args)))
    if fresh_search and len(ids) == 1 and any(term in text for term in ("promoc", "descont", *PAYMENT_MARKERS)):
        name = "calculate_payment_options" if any(term in text for term in PAYMENT_MARKERS) else "get_applicable_promotions"
        args = {"product_id": ids[0]}
        records.append((name, args, tools.execute(name, args)))
    return records, ids
