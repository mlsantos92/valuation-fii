"""Fluxo de caixa descontado de uma cota de FII.

Modelo (o mesmo da planilha original):
    renda anual  = rendimento mensal × 12, constante por `periodo` anos
    saída        = renda anual ÷ CAP rate de saída, recebida no último ano
    valor justo  = Σ renda/(1+taxa)^t  +  saída/(1+taxa)^n
"""
from __future__ import annotations

from dataclasses import dataclass

PASSO = 0.005  # 0,5 p.p. entre os cenários


@dataclass
class Fluxo:
    anos: list[int]
    renda: list[float]
    valor_presente: list[float]
    saida: float
    total: float


def fluxo(rendimento_mensal: float, taxa: float, periodo: int, cap: float) -> Fluxo:
    anual = rendimento_mensal * 12
    n = max(1, round(periodo))
    saida = anual / cap
    anos, renda, vp = [], [], []
    for t in range(1, n + 1):
        r = anual + saida if t == n else anual
        anos.append(t)
        renda.append(r)
        vp.append(r / (1 + taxa) ** t)
    return Fluxo(anos, renda, vp, saida, sum(vp))


def valor_justo(rendimento_mensal: float, taxa: float, periodo: int, cap: float) -> float:
    return fluxo(rendimento_mensal, taxa, periodo, cap).total


def cenarios(rendimento_mensal: float, taxa: float, periodo: int, cap: float) -> dict[str, float]:
    """Base, otimista (CAP de saída 0,5 p.p. menor) e pessimista (0,5 p.p. maior)."""
    return {
        "base": valor_justo(rendimento_mensal, taxa, periodo, cap),
        "otimista": valor_justo(rendimento_mensal, taxa, periodo, cap - PASSO),
        "pessimista": valor_justo(rendimento_mensal, taxa, periodo, cap + PASSO),
    }


def matriz_sensibilidade(rendimento_mensal: float, taxas: list[float], periodo: int, cap: float,
                         premio: float = 0.0) -> list[list[float]]:
    """Linhas: CAP −0,5 / CAP / CAP +0,5 p.p.; colunas: cada taxa × (1 + prêmio)."""
    return [[valor_justo(rendimento_mensal, t * (1 + premio), periodo, cap + dc) for t in taxas]
            for dc in (-PASSO, 0.0, PASSO)]


def faixa(matriz: list[list[float]]) -> tuple[float, float, float]:
    """(mínimo, centro, máximo) da matriz 3×3."""
    vals = [v for linha in matriz for v in linha]
    return min(vals), matriz[1][1], max(vals)


def posicao(preco: float, vmin: float, vmax: float) -> str:
    if preco < vmin:
        return "abaixo"
    if preco > vmax:
        return "acima"
    return "dentro"
