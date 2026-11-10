"""Leitura do retrato dos dados e normalização em uma tabela de fundos."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
TICKER_RE = re.compile(r"^[A-Z0-9]{4}1[1-5]B?$")

# nome da coluna na planilha -> nome no projeto (busca por nome EXATO, depois normalizado)
COLUNAS = {
    "Papel": "ticker",
    "Segmento": "segmento_fundamentus",
    "Cotação": "cotacao_fundamentus",
    "Último dividendo": "ultimo_rendimento",
    "Dividend Yield": "dy_12m",
    "P/VP": "pvp",
    "Liquidez": "liquidez_diaria",
    "Categoria": "categoria",
    "Tipo Status Invest": "tipo_statusinvest",
    "Preço B3 (GOOGLEFINANCE)": "preco_b3",
    "Segmento Funds Explorer (reserva)": "segmento_fundsexplorer",
    "Setor predominante": "setor_predominante",
    "Segmento ANBIMA": "segmento_anbima",
    "Div Status Invest": "rendimento_statusinvest",
    "DY Status Invest": "dy_statusinvest",
    "Exclusão": "motivo_exclusao",
}


def norm(s) -> str:
    """Remove acentos, passa para maiúsculas e tira espaços das pontas."""
    s = "" if s is None or (isinstance(s, float) and math.isnan(s)) else str(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


def numero_br(v) -> float:
    """Converte '1.234,56', '12,5%', '0.1648' ou números para float (NaN se vazio)."""
    if v is None:
        return math.nan
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or s == "-":
        return math.nan
    pct = "%" in s
    s = re.sub(r"[^\d,.\-]", "", s)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        n = float(s)
    except ValueError:
        return math.nan
    return n / 100 if pct else n


def ler_json(nome: str) -> dict:
    return json.loads((RAW / nome).read_text(encoding="utf-8"))


def carregar_fundos(caminho: Path | None = None) -> pd.DataFrame:
    """Lê o CSV da planilha e devolve uma linha por fundo negociado na B3.

    Regras (as mesmas do painel original):
    - ticker no formato de cota de FII/FIAGRO/FI-INFRA (XXXX11, XXXX11B ...);
    - fica fora quem não tem liquidez nem preço na B3 (fundos de balcão);
    - DY, cap rate e vacância acima de 1 vêm em pontos percentuais e viram fração.
    """
    bruto = pd.read_csv(caminho or RAW / "fiis_planilha.csv", dtype=str, keep_default_na=False)
    faltando = set(COLUNAS) - set(bruto.columns)
    if faltando:
        raise ValueError(f"colunas ausentes na planilha: {sorted(faltando)}")
    df = bruto[list(COLUNAS)].rename(columns=COLUNAS)
    df["ticker"] = df.ticker.str.upper().str.strip()
    df = df[df.ticker.map(lambda t: bool(TICKER_RE.match(t)))].copy()
    for c in ["cotacao_fundamentus", "ultimo_rendimento", "dy_12m", "pvp", "liquidez_diaria", "preco_b3"]:
        df[c] = df[c].map(numero_br)
    # colunas da Status Invest vêm com ponto decimal
    df["rendimento_statusinvest"] = pd.to_numeric(df.rendimento_statusinvest.replace("", None), errors="coerce")
    df["dy_statusinvest"] = pd.to_numeric(df.dy_statusinvest.replace("", None), errors="coerce") / 100
    df.loc[df.dy_12m > 1, "dy_12m"] = df.dy_12m / 100
    df["categoria"] = df.categoria.replace("", "FII").str.upper().str.strip()
    for c in ["tipo_statusinvest", "setor_predominante"]:
        df[c] = df[c].str.upper().str.strip()
    negociado = (df.liquidez_diaria > 0) | df.preco_b3.notna()
    df = df[negociado].drop_duplicates("ticker", keep="last")
    return df.set_index("ticker").sort_index()


def carregar_config() -> dict:
    """Prêmios de risco, Tesouro, histórico de rendimentos, saúde e ajustes manuais."""
    return {
        "premios": ler_json("premios_risco.json")["setores"],
        "tesouro": ler_json("tesouro.json"),
        "hist": ler_json("rendimentos_12m.json"),
        "saude": ler_json("saude_fundos.json").get("fundos", {}),
        "ajustes": ler_json("ajustes_rendimento.json").get("fundos", {}),
        "premissas": ler_json("premissas_fundos.json"),
        "meta": ler_json("metadados.json"),
    }
