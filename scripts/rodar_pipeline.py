"""Roda o pipeline completo: carga -> classificação -> FCD -> banco SQLite -> saídas.

Uso:  python scripts/rodar_pipeline.py
"""
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from valuation_fii.banco import DB, exportar_painel, gravar  # noqa: E402
from valuation_fii.carga import carregar_config, carregar_fundos  # noqa: E402
from valuation_fii.pipeline import avaliar, taxa_basica  # noqa: E402

fundos = carregar_fundos()
cfg = carregar_config()
val = avaliar(fundos, cfg)

gravar(fundos, cfg, val)
val.to_csv(RAIZ / "data" / "processed" / "valuation.csv", float_format="%.6f")
exportar_painel(val, cfg, RAIZ / "docs" / "dados.json")

con = sqlite3.connect(DB)
n_anom = dict(con.execute("SELECT regra, COUNT(*) FROM anomalias GROUP BY regra").fetchall())
con.close()
print(f"Retrato de {cfg['meta']['retrato_em']} · taxa básica {taxa_basica(cfg['tesouro']):.2%}")
print(f"{len(fundos)} fundos negociados na B3 · {val.posicao.notna().sum()} avaliados")
print("Posição na faixa:", val.posicao.value_counts().to_dict())
print("Anomalias:", n_anom)
print("Ranking de oportunidades:", int(val.no_ranking.sum()), "fundos")
