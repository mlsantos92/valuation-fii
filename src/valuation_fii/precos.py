"""Fechamentos diários dos fundos (API brapi) e selo de situação do painel.

O retrato da planilha continua sendo a base dos testes. Quando o arquivo de
fechamentos existe, o pipeline troca o preço da B3 pelo último fechamento
e grava a data de cada cotação.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

BRT = ZoneInfo("America/Sao_Paulo")
URL = "https://brapi.dev/api/quote/{tickers}?token={token}"
LOTE = 20  # tamanho máximo de cada chamada à API


def ultimo_pregao(agora: datetime | None = None) -> date:
    """Último dia útil já encerrado, em Brasília. Feriados não são descontados."""
    agora = (agora or datetime.now(BRT)).astimezone(BRT)
    d = agora.date() if agora.hour >= 18 else agora.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _ler_lote(tickers: list[str], token: str) -> list[dict]:
    url = URL.format(tickers=",".join(tickers), token=token)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("results", [])


def buscar_fechamentos(tickers: list[str], token: str, ler=_ler_lote) -> pd.DataFrame:
    """Uma linha por ticker: preço e data do último negócio informado pela API."""
    linhas = []
    for i in range(0, len(tickers), LOTE):
        for r in ler(tickers[i:i + LOTE], token):
            preco = r.get("regularMarketPrice")
            quando = r.get("regularMarketTime")
            if preco is None or not quando:
                continue
            data = datetime.fromisoformat(quando.replace("Z", "+00:00")).astimezone(BRT).date()
            linhas.append({"ticker": r["symbol"].upper(), "data": data.isoformat(), "preco": float(preco)})
    return pd.DataFrame(linhas, columns=["ticker", "data", "preco"]).drop_duplicates("ticker", keep="last")


def aplicar_fechamentos(df: pd.DataFrame, fech: pd.DataFrame) -> pd.DataFrame:
    """Substitui preco_b3 pelo fechamento onde ele existe. Mantém o preço da planilha nos demais."""
    out = df.copy()
    mapa = fech.set_index("ticker")
    tem = out.index.isin(mapa.index)
    out["preco_fonte"] = "planilha"
    out.loc[tem, "preco_b3"] = mapa.loc[out.index[tem], "preco"].to_numpy()
    out.loc[tem, "preco_fonte"] = "fechamento"
    out["data_preco"] = None
    out.loc[tem, "data_preco"] = mapa.loc[out.index[tem], "data"].to_numpy()
    return out


def selo(fechamentos: pd.DataFrame | None, pregao: date, testes_ok: bool, falhas: int = 0) -> dict:
    """Verde: fechamentos do último pregão e testes passando.
    Amarelo: dado defasado (ou parte dos tickers sem cotação). Vermelho: atualização ou testes falharam."""
    if fechamentos is None or fechamentos.empty or not testes_ok:
        cor, motivo = "vermelho", "atualização ou testes falharam"
    else:
        datas = pd.to_datetime(fechamentos.data).dt.date
        atrasado = (datas < pregao).sum()
        if atrasado or falhas:
            cor, motivo = "amarelo", f"{atrasado} cotações antigas e {falhas} sem cotação"
        else:
            cor, motivo = "verde", "fechamentos do último pregão e testes passando"
    return {
        "cor": cor,
        "motivo": motivo,
        "pregao_esperado": pregao.isoformat(),
        "atualizado_em": datetime.now(BRT).strftime("%Y-%m-%d %H:%M"),
        "testes": "ok" if testes_ok else "falha",
    }
