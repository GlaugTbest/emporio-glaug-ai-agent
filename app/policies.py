"""Small page-based policy retrieval, without embeddings or a vector store."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

# Page-scoped titles also solve subsections that continue onto the next PDF page.
PAGE_TITLES = {
    1: "Capa e informações de contato",
    2: "Sobre a loja, endereço e horário de funcionamento",
    3: "Formas de pagamento e parcelamento",
    4: "Trocas, devoluções, arrependimento e entregas locais",
    5: "Envios, fretes, prazos e rastreamento",
    6: "Promoções, descontos, WhatsApp e atendimento",
    7: "Atendimento, reclamações, garantia e privacidade",
    8: "Privacidade, dados pessoais, LGPD e disposições finais",
}
ALIASES = {
    "arrependimento": "devolucoes troca 7 dias compra online",
    "arrepender": "devolucoes troca 7 dias compra online",
    "devolver": "devolucoes troca arrependimento",
    "endereco": "rua campo grande localizacao",
    "onde": "endereco loja campo grande",
    "abrem": "horario funcionamento sabado domingo",
    "abre": "horario funcionamento sabado domingo",
    "horario": "funcionamento segunda sabado",
    "sabado": "horario funcionamento semana",
    "aberto": "horario funcionamento sabado domingo",
    "horas": "horario funcionamento",
    "parcelar": "pagamento parcelamento cartao credito",
    "parcela": "pagamento parcelamento cartao credito",
    "juros": "parcelamento credito",
    "pix": "pagamento desconto cumulatividade",
    "desconto": "promocoes pagamento pix",
    "entrega": "frete prazo rastreamento",
    "rastreamento": "envios frete codigo",
    "defeito": "garantia trocas defeito",
    "acessorios": "catalogo instrumentos nao comercializamos",
    "dados": "privacidade lgpd exclusao",
    "privacidade": "lgpd dados pessoais exclusao",
    "excluir": "exclusao privacidade lgpd",
    "contato": "whatsapp telefone email",
    "reclamacao": "atendimento encaminhar",
}
STOPWORDS = set("a o as os de da do e em no na com para um uma eu meu minha voce vocês qual quanto como que por posso quero tem tem o me".split())


def fold(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.lower())
    return "".join(c for c in plain if not unicodedata.combining(c))


def tokens(value: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", fold(value)) if len(t) >= 3 and t not in STOPWORDS}


def query_tokens(query: str) -> set[str]:
    out = tokens(query)
    for term in list(out):
        for key, extra in ALIASES.items():
            if term.startswith(key[:5]):
                out.update(tokens(extra))
    return out


def retrieve_policy_pages(rows: list[dict], query: str, limit: int = 2) -> list[dict]:
    terms = query_tokens(query)
    scored = []
    for page in rows:
        title_tokens = tokens(page["title"])
        content_tokens = tokens(page["content"])
        # Title is weighted for relevant page categories, then body overlap.
        score = 4 * len(terms & title_tokens) + len(terms & content_tokens)
        if score:
            scored.append((score, -int(page["source_page"]), page))
    scored.sort(reverse=True, key=lambda item: item[:2])
    return [page for _, _, page in scored[:limit]]


def sections_from_pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    sections = []
    for i, page in enumerate(reader.pages, 1):
        raw = page.extract_text(extraction_mode="plain") or ""
        clean = re.sub(r"\s+", " ", raw).strip()
        if not clean:
            continue
        sections.append({
            "section_id": f"manual_page_{i}",
            "title": PAGE_TITLES.get(i, f"Manual, página {i}"),
            "content": clean,
            "source_page": i,
        })
    if len(sections) < 2:
        raise ValueError("Policy manual has insufficient searchable text")
    return sections


def sections_from_json(path: Path) -> list[dict]:
    sections = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(sections, list) or not sections:
        raise ValueError("Expected a non-empty policy section list")
    return sections
