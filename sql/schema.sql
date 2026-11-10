-- Banco do projeto Valuation FII (SQLite)

CREATE TABLE IF NOT EXISTS fundos (
    ticker               TEXT PRIMARY KEY,
    segmento_fonte       TEXT,
    categoria            TEXT,      -- FII, FIAGRO, FI-INFRA (ou mais de uma, separadas por ;)
    segmento_anbima      TEXT,
    setor_predominante   TEXT,      -- definido à mão quando a fonte classifica mal
    preco_b3             REAL,
    cotacao_fundamentus  REAL,
    ultimo_rendimento    REAL,
    dy_12m               REAL,
    pvp                  REAL,
    liquidez_diaria      REAL,
    rendimento_statusinvest REAL,
    dy_statusinvest      REAL,
    motivo_exclusao      TEXT
);

CREATE TABLE IF NOT EXISTS rendimentos (
    ticker  TEXT NOT NULL REFERENCES fundos(ticker),
    ordem   INTEGER NOT NULL,         -- 1 = pagamento mais recente
    valor   REAL NOT NULL,
    PRIMARY KEY (ticker, ordem)
);

CREATE TABLE IF NOT EXISTS premios_risco (
    setor   TEXT PRIMARY KEY,
    premio  REAL NOT NULL,            -- taxa de desconto = taxa básica × (1 + prêmio)
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS saude (
    ticker      TEXT PRIMARY KEY REFERENCES fundos(ticker),
    nota        TEXT,                 -- ok, at (atenção), al (alerta), nd (sem dados)
    vacancia    REAL,
    inadimplencia TEXT,
    observacao  TEXT,
    relatorio_ref TEXT
);

CREATE TABLE IF NOT EXISTS valuation (
    ticker            TEXT PRIMARY KEY REFERENCES fundos(ticker),
    tipo              TEXT,
    setor             TEXT,
    preco             REAL,
    rendimento_usado  REAL,
    premio            REAL,
    taxa_desconto     REAL,
    periodo           INTEGER,
    cap               REAL,
    vj_base           REAL,
    vj_otimista       REAL,
    vj_pessimista     REAL,
    faixa_min         REAL,
    faixa_base        REAL,
    faixa_max         REAL,
    posicao           TEXT,           -- abaixo, dentro, acima da faixa de preço justo
    desconto          REAL,           -- faixa_min / preço − 1
    conferencia       TEXT,           -- ok, divergente, sem_conferencia
    rank_oportunidade INTEGER
);

CREATE TABLE IF NOT EXISTS anomalias (
    ticker  TEXT NOT NULL,
    regra   TEXT NOT NULL,            -- exclusao, suspeito, conferencia
    detalhe TEXT
);
