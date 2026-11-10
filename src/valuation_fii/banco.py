"""Grava o banco SQLite e as saídas do pipeline."""
from __future__ import annotations

import json
import math
import sqlite3

import pandas as pd

from .carga import RAIZ

DB = RAIZ / "data" / "processed" / "valuation_fii.db"


def _limpo(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def gravar(fundos: pd.DataFrame, cfg: dict, val: pd.DataFrame, caminho=DB) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        caminho.unlink()
    con = sqlite3.connect(caminho)
    con.executescript((RAIZ / "sql" / "schema.sql").read_text(encoding="utf-8"))
    cols = ["segmento_fundamentus", "categoria", "segmento_anbima", "setor_predominante", "preco_b3", "cotacao_fundamentus",
            "ultimo_rendimento", "dy_12m", "pvp", "liquidez_diaria", "rendimento_statusinvest", "dy_statusinvest", "motivo_exclusao"]
    con.executemany("INSERT INTO fundos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(tk, *[_limpo(f[c]) for c in cols]) for tk, f in fundos.iterrows()])
    con.executemany("INSERT INTO rendimentos VALUES (?,?,?)",
                    [(tk, i + 1, v) for tk, vs in cfg["hist"].get("fundos", {}).items() if tk in fundos.index
                     for i, v in enumerate(vs) if v is not None])
    con.executemany("INSERT INTO premios_risco VALUES (?,?,?)", [(p["nome"], p["premio"], p.get("desc")) for p in cfg["premios"]])
    con.executemany("INSERT INTO saude VALUES (?,?,?,?,?,?)",
                    [(tk, s.get("n"), s.get("vacP"), s.get("inad"), s.get("obs"), s.get("ref")) for tk, s in cfg["saude"].items()])
    vcols = ["tipo", "setor", "preco", "rendimento_usado", "premio", "taxa_desconto", "periodo", "cap", "vj_base", "vj_otimista",
             "vj_pessimista", "faixa_min", "faixa_base", "faixa_max", "posicao", "desconto", "conferencia", "rank_oportunidade"]
    con.executemany(f"INSERT INTO valuation VALUES ({','.join('?' * (len(vcols) + 1))})",
                    [(tk, *[_limpo(r[c]) if c != "rank_oportunidade" or pd.isna(r[c]) else int(r[c]) for c in vcols])
                     for tk, r in val.iterrows()])
    anom = []
    for tk, r in val.iterrows():
        if r.excluido:
            anom.append((tk, "exclusao", r.excluido))
        elif r.suspeito:
            anom.append((tk, "suspeito", r.suspeito))
        elif r.get("conferencia") == "divergente":
            anom.append((tk, "conferencia", r.conferencia_motivos))
    con.executemany("INSERT INTO anomalias VALUES (?,?,?)", anom)
    con.commit()
    con.close()


def exportar_painel(val: pd.DataFrame, cfg: dict, destino) -> None:
    """JSON lido pelo painel estático em docs/."""
    keep = ["tipo", "setor", "segmento_fonte", "preco", "rendimento_ultimo", "rendimento_usado", "rendimento_media_12m", "rendimento_desvio",
            "dy_12m", "pvp", "liquidez_diaria", "premio_setor", "ajuste_risco", "premio", "taxa_desconto", "periodo", "cap", "saude",
            "excluido", "suspeito", "vj_base", "vj_otimista", "vj_pessimista", "faixa_min", "faixa_base", "faixa_max", "posicao",
            "desconto", "margem_base", "conferencia", "conferencia_motivos", "rank_oportunidade"]
    fundos = {tk: {k: _limpo(r[k]) for k in keep} for tk, r in val.iterrows()}
    hist = {tk: v for tk, v in cfg["hist"].get("fundos", {}).items() if tk in fundos}
    out = {"meta": cfg["meta"], "tesouro": cfg["tesouro"], "premios": cfg["premios"], "fundos": fundos, "rendimentos": hist}
    destino.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), default=float), encoding="utf-8")
