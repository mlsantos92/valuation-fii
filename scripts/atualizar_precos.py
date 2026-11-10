"""Busca os fechamentos dos fundos na brapi e grava data/raw/precos_fechamento.csv.

Uso:  BRAPI_TOKEN=... python scripts/atualizar_precos.py
Grava data/raw/precos_fechamento.csv, data/raw/precos_status.json e docs/cotacoes.json (todos os fundos).
Sem token ou com falha total, o arquivo anterior fica como está e o status vai como "falha".
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from valuation_fii.carga import RAW, carregar_fundos  # noqa: E402
from valuation_fii.precos import BRT, buscar_fechamentos, buscar_fechamentos_hg, cotacoes_para_busca, so_liquidos  # noqa: E402
import pandas as pd  # noqa: E402

SAIDA = RAW / "precos_fechamento.csv"
STATUS = RAW / "precos_status.json"
COTACOES = RAIZ / "docs" / "cotacoes.json"  # lido pelo campo de consulta do painel


def main() -> int:
    token = os.environ.get("BRAPI_TOKEN", "").strip()
    if not token:
        print("BRAPI_TOKEN não definido", file=sys.stderr)
        return 1
    # todos os fundos negociados: o painel mostra só os líquidos, mas a consulta aceita qualquer código
    fundos = carregar_fundos()
    tickers = sorted(fundos.index)
    liquidos = set(so_liquidos(fundos).index)
    try:
        fech = buscar_fechamentos(tickers, token)
    except Exception as e:  # rede, limite de uso ou token inválido
        print(f"falha na busca: {e}", file=sys.stderr)
        STATUS.write_text(json.dumps({"status": "falha", "erro": str(e)[:200]}, ensure_ascii=False, indent=2))
        return 1
    fech["fonte"] = "brapi"
    # fonte reserva: fundos do painel que a brapi não cotou (uma chamada para todos)
    faltam = sorted(liquidos - set(fech.ticker))
    key_hg = os.environ.get("HG_TOKEN", "").strip()
    if faltam and key_hg:
        try:
            extra = buscar_fechamentos_hg(faltam, key_hg)
            extra["fonte"] = "hg"
            fech = pd.concat([fech, extra], ignore_index=True)
            print(f"reserva HG: {len(extra)} de {len(faltam)} fundos sem cotação na brapi")
        except Exception as e:  # sem detalhes da chave em mensagens de erro
            print("falha na reserva HG: " + str(e).replace(key_hg, "***")[:200], file=sys.stderr)
    fech.to_csv(SAIDA, index=False)
    COTACOES.write_text(json.dumps(cotacoes_para_busca(fech), ensure_ascii=False), encoding="utf-8")
    com_liquidos = set(fech.ticker) & liquidos
    STATUS.write_text(json.dumps({
        "status": "ok",
        "consultados": len(tickers),
        "com_cotacao": len(fech),
        "liquidos": len(liquidos),
        "sem_cotacao_liquidos": len(liquidos - com_liquidos),
        "via_hg": int((fech.fonte == "hg").sum()) if "fonte" in fech else 0,
        "data_mais_recente": fech.data.max() if len(fech) else None,
        "gerado_em": datetime.now(BRT).strftime("%Y-%m-%d %H:%M"),
    }, ensure_ascii=False, indent=2))
    print(f"{len(fech)} de {len(tickers)} tickers com cotação · data mais recente {fech.data.max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
