"""Setor de cada fundo e o prêmio de risco que ele recebe."""
from __future__ import annotations

import math

from .carga import norm

# Segmento da Status Invest/Fundamentus -> setor da tabela de prêmios
SEG_MAP = {
    "LAJES CORPORATIVAS": "LAJES", "SHOPPINGS": "SHOPPING", "IMOVEIS INDUSTRIAIS E LOGISTICOS": "LOGÍSTICA",
    "LOGISTICA": "LOGÍSTICA", "PAPEIS": "PAPEL", "IMOVEIS COMERCIAIS - OUTROS": "RENDA URBANA", "VAREJO": "RENDA URBANA",
    "AGENCIAS DE BANCOS": "RENDA URBANA", "MISTO": "HÍBRIDO", "IMOVEIS RESIDENCIAIS": "RESIDENCIAL", "HOSPITALAR": "HOSPITAL",
    "HOTEIS": "HOTEL", "FUNDO DE FUNDOS": "FUNDO DE FUNDOS", "FUNDO DE DESENVOLVIMENTO": "DESENVOLVIMENTO",
    "INCORPORACOES": "DESENVOLVIMENTO", "FI-INFRA": "FI-INFRA", "AGRICULTURA": "FIAGRO", "INDEFINIDO": "NÃO CLASSIFICADO",
}
# Segmento ANBIMA (Funds Explorer) -> setor; vale para fundos de tijolo
ANB_MAP = {
    "SHOPPINGS": "SHOPPING", "LAJES CORPORATIVAS": "LAJES", "RESIDENCIAL": "RESIDENCIAL", "HIBRIDO": "HÍBRIDO",
    "TITULOS E VALORES MOBILIARIOS": "PAPEL", "LOGISTICA": "LOGÍSTICA", "HOTEL": "HOTEL", "HOSPITAL": "HOSPITAL",
}


def premio_de(setor: str, premios: list[dict]) -> float:
    for p in premios:
        if norm(p["nome"]) == norm(setor):
            return p["premio"]
    return math.nan


def setor_do_segmento(seg: str) -> str:
    n = norm(seg)
    return SEG_MAP.get(n, str(seg).upper().strip()) if n else ""


def setor_anbima(anb: str, seg: str) -> str:
    """Setor pela ANBIMA, exceto fundos de papel e FOFs, que mantêm a Status Invest."""
    a = ANB_MAP.get(norm(anb), "")
    if not a or norm(seg) in ("PAPEIS", "FUNDO DE FUNDOS"):
        return ""
    return a


def setor_automatico(f, premios: list[dict]) -> str:
    """Ordem: setor predominante definido à mão > ANBIMA > segmento da fonte.

    Se o fundo aparece como FIAGRO ou FI-INFRA em alguma lista, vale a categoria
    (ou o setor-base) de MAIOR prêmio de risco: na dúvida, o modelo é conservador.
    """
    flags = [x.strip() for x in str(f["categoria"] or "").split(";")]
    base = f["setor_predominante"] or setor_anbima(f["segmento_anbima"], f["segmento_fundamentus"]) or setor_do_segmento(f["segmento_fundamentus"])
    cands = [c for c in ("FIAGRO", "FI-INFRA") if c in flags]
    if not cands:
        return base
    if base and norm(base) not in ("NAO CLASSIFICADO", "OUTROS"):
        cands.append(base)
    best, bp = cands[0], -1.0
    for c in cands:
        pr = premio_de(c, premios)
        if not math.isnan(pr) and pr > bp:
            best, bp = c, pr
    return best


def tipo_do_setor(setor: str) -> str:
    s = norm(setor)
    return "FIAGRO" if s == "FIAGRO" else "FI-INFRA" if s == "FI-INFRA" else "FII"
