"""Conservative deterministic lookups for recurring customer-service intents.

A small local model may skip tool calls. Obvious business questions are therefore
pre-fetched in Python; ambiguous follow-ups can still use model tool calling.
"""

from __future__ import annotations

import re
import unicodedata

from app.tools import StoreTools


def _plain(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.lower())
                   if not unicodedata.combining(ch))


def plan(message: str, product_ids: list[int]) -> list[tuple[str, dict]]:
    text = _plain(message)
    operations: list[tuple[str, dict]] = []

    # A user's assertion of identity is never accepted. The order tool enforces
    # ownership against the host-provided identity in its SQL predicate.
    match = re.search(r"\bpedido\s*(?:e\s*o\s*)?(?:numero\s*|n[ºo.]\s*)?#?\s*(\d{1,8})\b", text)
    if match:
        return [("get_order_status", {"order_id": int(match.group(1))})]

    policy_markers = ("devolu", "devolv", "troca", "arrepend", "garanti", "reembols", "embalagem", "caixa",
                      "etiqueta", "horario", "abert", "fechado", "que horas", "enderec", "frete",
                      "entrega", "whatsapp", "contato", "acessorio", "palhet", "pedal")
    product_question = "pronta entrega" in text and any(t in text for t in ("violao", "violoes", "guitarra"))
    if any(marker in text for marker in policy_markers) and not product_question:
        return [("search_store_policies", {"query": message[:300]})]

    category = "violões" if "violao" in text or "violoes" in text else (
        "guitarras" if "guitarra" in text else "")
    budget = re.search(r"r\$\s*([\d.]+)(?:,(\d{2}))?", text)
    limit = None
    if budget and ("ate " in text or "por volta" in text or "por ate" in text):
        try:
            limit = float(budget.group(1).replace(".", "") + "." + (budget.group(2) or "00"))
        except ValueError:
            pass
    if category:
        params: dict = {"category": category}
        if limit is not None:
            params["max_price_brl"] = limit
        operations.append(("search_products", params))

    payment_intent = any(t in text for t in ("promoc", "descont", "pix", "parcela", "cartao", "vezes"))
    if payment_intent and product_ids:
        pid = product_ids[0]
        operations.append(("calculate_payment_options" if any(t in text for t in
                           ("pix", "parcela", "cartao", "vezes")) else
                           "get_applicable_promotions", {"product_id": pid}))
    if not operations and product_ids and any(t in text for t in ("nylon", "aco", "corda", "estoque")):
        for pid in product_ids[:3]:
            operations.append(("get_product_details", {"product_id": pid}))
    return operations


def prefetch(tools: StoreTools, message: str, product_ids: list[int]):
    """Return only actual Python tool results, never invented model responses."""
    records = []
    ids = product_ids.copy()
    for name, args in plan(message, product_ids):
        result = tools.execute(name, args)
        records.append((name, args, result))
        if name == "search_products" and result.get("products"):
            ids = [item["product_id"] for item in result["products"]]
    # Specifications such as nylon versus steel are not included in the list
    # results, so fetch the actual product details instead of guessing.
    if records and records[0][0] == "search_products" and ids and "nylon" in _plain(message):
        for pid in ids[:3]:
            args = {"product_id": pid}
            records.append(("get_product_details", args, tools.execute("get_product_details", args)))
    # A promotion question with just one matching guitar can be resolved in the
    # same turn without the model guessing its product ID.
    if records and records[0][0] == "search_products" and ids and len(ids) == 1:
        lowered = _plain(message)
        if "promoc" in lowered or "descont" in lowered:
            args = {"product_id": ids[0]}
            records.append(("get_applicable_promotions", args,
                            tools.execute("get_applicable_promotions", args)))
    return records, ids
