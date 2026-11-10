"""Busca os fechamentos dos fundos na brapi e grava data/raw/precos_fechamento.csv.

Uso:  BRAPI_TOKEN=... python scripts/atualizar_precos.py
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
from valuation_fii.precos import BRT, buscar_fechamentos  # noqa: E402

SAIDA = RAW / "precos_fechamento.csv"
STATUS = RAW / "precos_status.json"
LIQUIDEZ_MINIMA = 1_000_000


def main() -> int:
    token = os.environ.get("BRAPI_TOKEN", "").strip()
    if not token:
        print("BRAPI_TOKEN não definido", file=sys.stderr)
        return 1
    # só fundos com liquidez média de pelo menos R$ 1 mi por dia
    fundos = carregar_fundos()
    tickers = sorted(fundos.index[fundos.liquidez_diaria >= LIQUIDEZ_MINIMA])
    print(f"{len(tickers)} fundos com liquidez ≥ R$ 1 mi/dia")
    try:
        fech = buscar_fechamentos(tickers, token)
    except Exception as e:  # rede, limite de uso ou token inválido
        print(f"falha na busca: {e}", file=sys.stderr)
        STATUS.write_text(json.dumps({"status": "falha", "erro": str(e)[:200]}, ensure_ascii=False, indent=2))
        return 1
    fech.to_csv(SAIDA, index=False)
    STATUS.write_text(json.dumps({
        "status": "ok",
        "consultados": len(tickers),
        "com_cotacao": len(fech),
        "sem_cotacao": len(tickers) - len(fech),
        "data_mais_recente": fech.data.max() if len(fech) else None,
        "gerado_em": datetime.now(BRT).strftime("%Y-%m-%d %H:%M"),
    }, ensure_ascii=False, indent=2))
    print(f"{len(fech)} de {len(tickers)} tickers com cotação · data mais recente {fech.data.max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
