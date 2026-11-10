from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from valuation_fii.precos import BRT, aplicar_fechamentos, buscar_fechamentos, selo, ultimo_pregao


def test_ultimo_pregao_pula_fim_de_semana():
    # terça 10/11/2026 às 10h: último pregão encerrado é segunda 09/11
    assert ultimo_pregao(datetime(2026, 11, 10, 10, 0, tzinfo=BRT)) == date(2026, 11, 9)
    # segunda 09/11 às 10h: pregão de sexta 06/11
    assert ultimo_pregao(datetime(2026, 11, 9, 10, 0, tzinfo=BRT)) == date(2026, 11, 6)


def test_buscar_fechamentos_converte_data_para_brasilia_e_ignora_sem_preco():
    def falso(tickers, token):
        return [
            {"symbol": "HGLG11", "regularMarketPrice": 160.5, "regularMarketTime": "2026-11-09T21:00:00.000Z"},
            {"symbol": "XPML11", "regularMarketPrice": None, "regularMarketTime": "2026-11-09T21:00:00.000Z"},
        ]

    out = buscar_fechamentos(["HGLG11", "XPML11"], "tok", ler=falso)
    assert list(out.ticker) == ["HGLG11"]
    assert out.iloc[0].data == "2026-11-09"
    assert out.iloc[0].preco == 160.5


def test_buscar_fechamentos_divide_em_lotes_de_vinte():
    chamadas = []

    def falso(tickers, token):
        chamadas.append(len(tickers))
        return []

    buscar_fechamentos([f"AAAA{i:02d}11" for i in range(45)], "tok", ler=falso)
    assert chamadas == [20, 20, 5]


def test_aplicar_fechamentos_troca_so_os_tickers_com_cotacao():
    df = pd.DataFrame({"preco_b3": [10.0, 20.0]}, index=pd.Index(["AAAA11", "BBBB11"], name="ticker"))
    fech = pd.DataFrame({"ticker": ["AAAA11"], "data": ["2026-11-09"], "preco": [11.5]})
    out = aplicar_fechamentos(df, fech)
    assert out.loc["AAAA11", "preco_b3"] == 11.5
    assert out.loc["BBBB11", "preco_b3"] == 20.0
    assert out.loc["AAAA11", "preco_fonte"] == "fechamento"
    assert out.loc["BBBB11", "preco_fonte"] == "planilha"


def test_selo_verde_quando_fechamentos_do_ultimo_pregao_e_testes_ok():
    fech = pd.DataFrame({"ticker": ["A"], "data": ["2026-11-09"], "preco": [1.0]})
    assert selo(fech, date(2026, 11, 9), True)["cor"] == "verde"


def test_selo_amarelo_com_dado_defasado_ou_sem_cotacao():
    fech = pd.DataFrame({"ticker": ["A"], "data": ["2026-11-06"], "preco": [1.0]})
    assert selo(fech, date(2026, 11, 9), True)["cor"] == "amarelo"
    fech2 = pd.DataFrame({"ticker": ["A"], "data": ["2026-11-09"], "preco": [1.0]})
    assert selo(fech2, date(2026, 11, 9), True, falhas=3)["cor"] == "amarelo"


def test_selo_vermelho_se_atualizacao_ou_testes_falharem():
    fech = pd.DataFrame({"ticker": ["A"], "data": ["2026-11-09"], "preco": [1.0]})
    assert selo(None, date(2026, 11, 9), True)["cor"] == "vermelho"
    assert selo(fech, date(2026, 11, 9), False)["cor"] == "vermelho"
