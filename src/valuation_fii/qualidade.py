"""Regras de qualidade de dados: o que fica fora da análise e o que é conferido.

Cada regra devolve um motivo legível, gravado no banco (tabela `anomalias`) para auditoria.
"""
from __future__ import annotations

import math

LIQ_SUSPEITA = 5e8          # liquidez diária acima de R$ 500 mi: erro de fonte
RENDIMENTO_MAX_PRECO = 0.04  # rendimento mensal acima de 4% do preço: não recorrente ou erro
PVP_MAX = 1.5
DY_NAO_RECORRENTE = 0.25
DY_IRREAL = 0.40
DIVERGENCIA_SI = 0.25


def ok(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def motivos_suspeita(rendimento: float, preco: float, liquidez: float) -> list[str]:
    """Dados que impedem o cálculo ou que são claramente errados (fundo sai da análise)."""
    m = []
    if not (ok(rendimento) and rendimento > 0):
        m.append("sem rendimento")
    if not (ok(preco) and preco > 0):
        m.append("sem cotação")
    if not m and rendimento / preco > RENDIMENTO_MAX_PRECO:
        m.append(f"rendimento mensal de {rendimento / preco:.1%} do preço")
    if ok(liquidez) and liquidez > LIQ_SUSPEITA:
        m.append(f"liquidez diária de R$ {liquidez / 1e6:,.0f} mi")
    return m


def conferencia_statusinvest(rend_normal: float, preco: float, dy: float, pvp: float,
                             rend_si: float, dy_si: float) -> tuple[bool, list[str], str]:
    """Compara os dados de entrada com uma segunda fonte (Status Invest).

    Devolve (dy_zerado, motivos, status) com status 'ok', 'divergente' ou 'sem_conferencia'.
    Fundos 'divergente' ou com DY zerado ficam fora do ranking de oportunidades.
    """
    why = []
    dy_zero = not (ok(dy) and dy > 0) or (ok(dy_si) and dy_si <= 0)
    if dy_zero:
        why.append("DY 12m zerado")
    if ok(pvp) and pvp > PVP_MAX:
        why.append(f"P/VP {pvp:.2f} muito acima de 1")
    dyx = max(dy_si if ok(dy_si) else 0, dy if ok(dy) else 0)
    if dyx > DY_NAO_RECORRENTE and not (ok(dy_si) and dy_si > DY_IRREAL):
        why.append(f"DY 12m de {dyx:.0%} sugere rendimento não recorrente")
    if ok(dy_si) and dy_si > DY_IRREAL:
        why.append(f"DY 12m irreal na Status Invest ({dy_si:.0%})")
    if ok(rend_si) and rend_si > 0 and abs(rend_normal - rend_si) / rend_si > DIVERGENCIA_SI:
        why.append(f"rendimento {rend_normal:.2f} diferente da Status Invest ({rend_si:.2f})")
    y = rend_normal * 12 / preco
    if ok(dy_si) and 0 < dy_si <= DY_IRREAL and y > dy_si * 1.5 and y - dy_si > 0.04:
        why.append(f"rendimento anualizado {y:.1%} muito acima do DY 12m {dy_si:.1%}")
    status = "divergente" if why else ("ok" if ok(rend_si) or ok(dy_si) else "sem_conferencia")
    return dy_zero, why, status
