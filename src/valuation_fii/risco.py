"""Rendimento usado no fluxo (com haircut) e ajuste de risco por fundo."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field

RISCO_PADRAO = {
    "on": True,
    "vacMin": 0.05,     # vacância isenta até 5%
    "vacPP": 1.0,       # cada ponto de vacância acima soma 1 p.p. de prêmio
    "vacMax": 0.20,     # teto da penalidade de vacância
    "hy1": 0.02, "hyPen1": 0.0,   # papel com DY acima da mediana dos fundos de papel
    "hy2": 0.05, "hyPen2": 0.0,
    "atPen": 0.10,      # saúde "Atenção" nos relatórios gerenciais
    "setoresHY": ["PAPEL"],
    "hcOn": True,       # aplicar haircut no rendimento
    "hcK": 1.0,         # quantos desvios padrão descontar
    "setorNoRank": True,
}


def mediana(v: list[float]) -> float:
    return statistics.median(v) if v else math.nan


@dataclass
class Haircut:
    rendimento: float
    media: float
    desvio: float = 0.0
    fonte: str = "último rendimento"
    meses: int = 0
    mediana: float = math.nan
    extra_mes: float = 0.0
    n_extra: int = 0


def haircut(hist: list[float] | None, rendimento_normal: float, dy_statusinvest: float, preco: float,
            ajuste: dict | None = None, cfg: dict = RISCO_PADRAO) -> Haircut:
    """Rendimento conservador a partir dos últimos 12 pagamentos.

    média dos 12 meses (inclui pagamentos extras, como o complemento anual da regra dos 95%)
    menos k desvios padrão da oscilação dos pagamentos até a mediana.
    """
    if ajuste and ajuste.get("fixo") and _ok(ajuste.get("div")):
        return Haircut(ajuste["div"], ajuste["div"], fonte="rendimento recorrente conferido no gestor")
    if not cfg["hcOn"]:
        return Haircut(rendimento_normal, rendimento_normal)
    v = [x for x in (hist or []) if _ok(x) and x > 0][:12]
    if len(v) >= 6:
        media = sum(v) / len(v)
        med = mediana(v)
        reg = [min(x, med) for x in v]
        m = sum(reg) / len(reg)
        sd = math.sqrt(sum((x - m) ** 2 for x in reg) / max(1, len(reg) - 1))
        return Haircut(max(0.0, media - cfg["hcK"] * sd), media, sd, "média 12m − desvio até a mediana", len(v), med,
                       max(0.0, media - med), sum(x > med + 1e-9 for x in v))
    if _ok(dy_statusinvest) and 0 < dy_statusinvest <= 0.4 and _ok(preco) and preco > 0:
        r = dy_statusinvest * preco / 12
        return Haircut(r, r, fonte="DY 12m da Status Invest ÷ 12")
    return Haircut(rendimento_normal, rendimento_normal)


@dataclass
class AjusteRisco:
    vacancia: float = 0.0
    high_yield: float = 0.0
    atencao: float = 0.0
    vac_pct: float = math.nan
    notas: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return self.vacancia + self.high_yield + self.atencao


def ajuste_risco(saude: dict | None, setor: str, dy: float, mediana_dy_papel: float, cfg: dict = RISCO_PADRAO) -> AjusteRisco:
    r = AjusteRisco()
    if not cfg["on"]:
        return r
    if saude and _ok(saude.get("vacP")):
        r.vac_pct = saude["vacP"]
        if saude["vacP"] > cfg["vacMin"]:
            r.vacancia = min(cfg["vacMax"], (saude["vacP"] - cfg["vacMin"]) * cfg["vacPP"])
            r.notas.append(f"vacância {saude['vacP']:.1%}")
    if setor in cfg["setoresHY"] and _ok(dy) and _ok(mediana_dy_papel):
        spread = dy - mediana_dy_papel
        if spread > cfg["hy2"]:
            r.high_yield = cfg["hyPen2"]
        elif spread > cfg["hy1"]:
            r.high_yield = cfg["hyPen1"]
    if saude and saude.get("n") == "at":
        r.atencao = cfg["atPen"]
        r.notas.append("saúde em Atenção")
    return r


def _ok(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)
