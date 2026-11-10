"""Monta premissas de cada fundo, roda o FCD e a sensibilidade de todo o universo."""
from __future__ import annotations

import math

import pandas as pd

from . import fcd
from .carga import carregar_config, carregar_fundos, norm
from .classificacao import premio_de, setor_automatico, tipo_do_setor
from .qualidade import conferencia_statusinvest, motivos_suspeita, ok
from .risco import RISCO_PADRAO, ajuste_risco, haircut, mediana

PERIODO_PADRAO = 10
CAP_PADRAO = 0.09
TAXA_SENS_BASE = 0.11   # matriz de sensibilidade: 10,5% / 11% / 11,5% (como na planilha original)
LIQ_CORTE = 1e6


def taxas_sensibilidade(base: float = TAXA_SENS_BASE) -> list[float]:
    return [base - fcd.PASSO, base, base + fcd.PASSO]


def taxa_basica(tesouro: dict) -> float:
    """Média simples das taxas de compra do Tesouro IPCA+ e do Prefixado mais curtos."""
    return (tesouro["ipca"]["taxa"] + tesouro["pre"]["taxa"]) / 2


def avaliar(fundos: pd.DataFrame | None = None, cfg: dict | None = None, taxa_sens: float = TAXA_SENS_BASE,
            risco: dict = RISCO_PADRAO) -> pd.DataFrame:
    fundos = carregar_fundos() if fundos is None else fundos
    cfg = carregar_config() if cfg is None else cfg
    premios, hist = cfg["premios"], cfg["hist"].get("fundos", {})
    base = taxa_basica(cfg["tesouro"])
    taxas = taxas_sensibilidade(taxa_sens)

    setores = {tk: (cfg["premissas"].get(tk, {}).get("setor") or setor_automatico(f, premios)) for tk, f in fundos.iterrows()}
    papel = [f.dy_12m for tk, f in fundos.iterrows() if not f.motivo_exclusao and ok(f.dy_12m) and 0 < f.dy_12m <= 0.4
             and norm(setores[tk]) in risco["setoresHY"]]
    med_papel = mediana(papel)

    linhas = []
    for tk, f in fundos.iterrows():
        o = cfg["premissas"].get(tk, {})
        preco = f.preco_b3 if ok(f.preco_b3) else f.cotacao_fundamentus
        rend_auto = f.ultimo_rendimento if ok(f.ultimo_rendimento) and f.ultimo_rendimento > 0 else (
            f.dy_12m * f.cotacao_fundamentus / 12 if ok(f.dy_12m) and ok(f.cotacao_fundamentus) else math.nan)
        aj = cfg["ajustes"].get(tk)
        rend_normal = aj["div"] if aj and ok(aj.get("div")) and aj["div"] > 0 else rend_auto
        hc = haircut(hist.get(tk), rend_normal, f.dy_statusinvest, preco, aj, risco)
        setor = setores[tk]
        pr_setor = premio_de(setor, premios)
        rk = ajuste_risco(cfg["saude"].get(tk), norm(setor), f.dy_12m, med_papel, risco)
        premio = max(pr_setor, rk.total) if ok(pr_setor) else (rk.total if rk.total > 0 else pr_setor)
        periodo = o.get("periodo", PERIODO_PADRAO)
        cap = o.get("cap", CAP_PADRAO)
        taxa = base * (1 + (premio if ok(premio) else 0))
        susp = motivos_suspeita(hc.rendimento, preco, f.liquidez_diaria)
        r = dict(ticker=tk, tipo=tipo_do_setor(setor), setor=setor or "SEM SETOR", segmento_fonte=f.segmento_fundamentus,
                 preco=preco, rendimento_ultimo=rend_auto, rendimento_normalizado=rend_normal, rendimento_usado=hc.rendimento,
                 rendimento_media_12m=hc.media, rendimento_desvio=hc.desvio, rendimento_fonte=hc.fonte, dy_12m=f.dy_12m,
                 pvp=f.pvp, liquidez_diaria=f.liquidez_diaria, premio_setor=pr_setor, ajuste_risco=rk.total, premio=premio,
                 taxa_desconto=taxa, periodo=periodo, cap=cap, saude=(cfg["saude"].get(tk) or {}).get("n"),
                 excluido=f.motivo_exclusao or "", suspeito="; ".join(susp))
        if not r["excluido"] and not susp and hc.rendimento > 0 and cap > 0.006:
            c = fcd.cenarios(hc.rendimento, taxa, periodo, cap)
            r.update(vj_base=c["base"], vj_otimista=c["otimista"], vj_pessimista=c["pessimista"])
            pr_rank = premio if (risco["setorNoRank"] and ok(premio)) else rk.total
            m = fcd.matriz_sensibilidade(hc.rendimento, taxas, periodo, cap, pr_rank)
            vmin, vcen, vmax = fcd.faixa(m)
            dyz, why, chk = conferencia_statusinvest(rend_normal, preco, f.dy_12m, f.pvp, f.rendimento_statusinvest, f.dy_statusinvest)
            r.update(faixa_min=vmin, faixa_base=vcen, faixa_max=vmax, posicao=fcd.posicao(preco, vmin, vmax),
                     desconto=vmin / preco - 1, margem_base=vcen / preco - 1, premio_sobre_max=preco / vmax - 1,
                     dy_zerado=dyz, conferencia=chk, conferencia_motivos="; ".join(why))
        linhas.append(r)
    df = pd.DataFrame(linhas).set_index("ticker")
    df["no_ranking"] = ranking_elegivel(df)
    df["rank_oportunidade"] = ordenar_ranking(df)
    return df


def ranking_elegivel(df: pd.DataFrame, tipos=("FII",)) -> pd.Series:
    """Abaixo da faixa, dados conferidos, DY não zerado e saúde diferente de Alerta/Sem dados."""
    return ((df.posicao == "abaixo") & df.desconto.notna() & (df.dy_zerado == False) & (df.conferencia != "divergente")
            & df.tipo.isin(tipos) & ~df.saude.isin(["al", "nd"]))


def ordenar_ranking(df: pd.DataFrame) -> pd.Series:
    """Maior desconto sobre o preço justo mínimo; liquidez < R$ 1 mi e saúde 'Atenção' vão para o fim."""
    e = df[df.no_ranking].assign(baixa=lambda x: ~(x.liquidez_diaria >= LIQ_CORTE), at=lambda x: x.saude == "at")
    e = e.sort_values(["baixa", "at", "desconto"], ascending=[True, True, False], kind="stable")
    return pd.Series(range(1, len(e) + 1), index=e.index).reindex(df.index)
