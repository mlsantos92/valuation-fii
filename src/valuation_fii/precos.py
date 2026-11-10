"""Fechamentos diários dos fundos (API brapi) e selo de situação do painel.

O retrato da planilha continua sendo a base dos testes. Quando o arquivo de
fechamentos existe, o pipeline troca o preço da B3 pelo último fechamento
e grava a data de cada cotação.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

BRT = ZoneInfo("America/Sao_Paulo")
URL = "https://brapi.dev/api/quote/{tickers}?token={token}"
LOTE = 1  # plano gratuito da brapi aceita 1 ticker por chamada
LIQUIDEZ_MINIMA = 1_000_000  # R$ por dia: fundos abaixo disso saem do painel


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
        lote = tickers[i:i + LOTE]
        try:
            resultados = ler(lote, token)
        except (urllib.error.URLError, ValueError):
            # um código inexistente (404) ou falha pontual não derruba os demais
            continue
        for r in resultados:
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


def so_liquidos(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém só os fundos com liquidez média de pelo menos LIQUIDEZ_MINIMA por dia."""
    return df[df.liquidez_diaria >= LIQUIDEZ_MINIMA]


def cotacoes_para_busca(fech: pd.DataFrame) -> dict:
    """Mapa ticker -> preço e data, para o campo de consulta do painel (inclui fundos fora do painel)."""
    return {r.ticker: {"preco": r.preco, "data": r.data} for r in fech.itertuples()}


HG_URL = "https://api.hgbrasil.com/v2/finance/quotes?tickers={tickers}&key={key}"
HG_LOTE = 20  # a documentação aceita vários tickers por chamada


def _ler_hg(tickers: list[str], key: str) -> list[dict]:
    url = HG_URL.format(tickers=",".join(f"B3:{t}" for t in tickers), key=key)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("results", [])


def buscar_fechamentos_hg(tickers: list[str], key: str, ler=_ler_hg) -> pd.DataFrame:
    """Fonte reserva: cotação e data do último negócio pela HG Brasil (uma chamada para vários tickers)."""
    linhas = []
    for i in range(0, len(tickers), HG_LOTE):
        lote = tickers[i:i + HG_LOTE]
        try:
            resultados = ler(lote, key)
        except (urllib.error.URLError, ValueError):
            continue  # não deixa a chave vazar em mensagens de erro e segue
        for r in resultados:
            q = r.get("quote") or {}
            preco = q.get("value")
            quando = q.get("updated_at")
            if preco is None or not quando:
                continue
            data = datetime.fromisoformat(quando).astimezone(BRT).date()
            linhas.append({"ticker": r["symbol"].upper(), "data": data.isoformat(), "preco": float(preco)})
    return pd.DataFrame(linhas, columns=["ticker", "data", "preco"]).drop_duplicates("ticker", keep="last")
