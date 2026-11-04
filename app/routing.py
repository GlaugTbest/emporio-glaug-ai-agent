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


def search_filters(message: str, previous: dict | None = None) -> dict:
    text = fold(message)
    category = next((label for term, label in CATEGORIES if term in text), "")
    old = previous or {}
    filters = old.copy() if not category or category == old.get("category") else {}
    if category:
        filters["category"] = category
    if "sem limite" in text or "qualquer preco" in text:
        filters.pop("max_price_brl", None)
    budget = re.search(r"(?:ate|orcamento de|tenho)\s*(?:r\$\s*)?([\d.,]+)", text)
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
    if filters.get("category"):
        # Payment depends on this search's result, never on the previous product.
        return [("search_products", filters)]
    if product_ids and any(term in text for term in ("promoc", "descont", *PAYMENT_MARKERS)):
        if len(product_ids) == 1:
            name = "calculate_payment_options" if any(term in text for term in PAYMENT_MARKERS) else "get_applicable_promotions"
            return [(name, {"product_id": product_ids[0]})]
    if product_ids and any(term in text for term in ("nylon", "aco", "corda", "estoque", "primeiro", "segundo")):
        ids = product_ids[:3]
        if "primeiro" in text:
            ids = product_ids[:1]
        elif "segundo" in text:
            ids = product_ids[1:2]
        return [("get_product_details", {"product_id": pid}) for pid in ids]
    return []


def prefetch(tools: StoreTools, message: str, product_ids: list[int], filters: dict | None = None):
    records = []
    ids = product_ids.copy()
    for name, args in plan(message, product_ids):
        if name == "search_products" and filters:
            args = {**args, **filters}
        result = tools.execute(name, args)
        records.append((name, args, result))
        if name == "search_products":
            ids = [item["product_id"] for item in result.get("products", [])]
    text = fold(message)
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

