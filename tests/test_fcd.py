"""Testes do modelo FCD contra a planilha original e contra o painel em JavaScript."""
import json
import math
from pathlib import Path

import pytest

from valuation_fii import fcd
from valuation_fii.carga import numero_br
from valuation_fii.pipeline import avaliar
from valuation_fii.qualidade import conferencia_statusinvest, motivos_suspeita
from valuation_fii.risco import haircut

AQUI = Path(__file__).parent
REF = json.loads((AQUI / "referencia_planilha.json").read_text(encoding="utf-8"))


def test_valor_justo_igual_a_planilha():
    c = fcd.cenarios(REF["dividendo_mensal"], REF["taxa_desconto"], REF["periodo"], REF["cap"])
    for k, v in REF["valor_justo"].items():
        assert c[k] == pytest.approx(v, abs=1e-6)


def test_matriz_de_sensibilidade_igual_a_planilha():
    s = REF["sensibilidade"]
    m = fcd.matriz_sensibilidade(REF["dividendo_mensal"], s["taxas"], REF["periodo"], REF["cap"], premio=0.0)
    for linha, esperado in zip(m, s["valores"]):
        assert linha == pytest.approx(esperado, abs=1e-6)


def test_saida_cai_no_ultimo_ano():
    f = fcd.fluxo(1.0, 0.10, 5, 0.08)
    assert f.renda[:4] == [12.0] * 4 and f.renda[4] == pytest.approx(12 + 12 / 0.08)


@pytest.mark.parametrize("txt,esperado", [("1.234,56", 1234.56), ("12,5%", 0.125), ("0,1648", 0.1648), ("94", 94.0), ("", math.nan)])
def test_numero_br(txt, esperado):
    v = numero_br(txt)
    assert (math.isnan(v) and math.isnan(esperado)) or v == pytest.approx(esperado)


def test_haircut_desconta_desvio_e_preserva_extra():
    h = haircut([1.0] * 11 + [2.2], 1.0, math.nan, 100.0)
    assert h.media == pytest.approx(1.1) and h.mediana == 1.0 and h.n_extra == 1
    assert h.rendimento == pytest.approx(1.1)  # sem oscilação até a mediana: desvio zero


def test_regras_de_qualidade():
    assert motivos_suspeita(math.nan, 10, 1e6) == ["sem rendimento"]
    assert "rendimento mensal" in motivos_suspeita(1.0, 10, 1e6)[0]
    _, why, st = conferencia_statusinvest(1.0, 100, 0.12, 0.9, 0.5, 0.12)
    assert st == "divergente" and "Status Invest" in why[0]


def test_paridade_com_painel_original():
    """O pipeline em Python reproduz o painel original fundo a fundo.

    Gere o arquivo de referência com: node tests/paridade/painel_original.js
    """
    arq = AQUI / "paridade" / "resultado_painel_original.json"
    if not arq.exists():
        pytest.skip("rode o harness em JavaScript antes")
    js = json.loads(arq.read_text())
    py = avaliar()
    assert set(js) == set(py.index)
    for tk, r in js.items():
        p = py.loc[tk]
        assert p.setor == r["setor"], tk
        assert bool(p.excluido) == r["excl"], tk
        if not r["excl"]:
            assert bool(p.suspeito) == r["susp"], tk
        if r["vmin"] is not None:
            assert p.faixa_min == pytest.approx(r["vmin"], rel=1e-9), tk
            assert p.faixa_max == pytest.approx(r["vmax"], rel=1e-9), tk
            assert {"below": "abaixo", "inside": "dentro", "above": "acima"}[r["st"]] == p.posicao, tk
            assert {"bad": "divergente", "ok": "ok", "na": "sem_conferencia"}[r["chk"]] == p.conferencia, tk
