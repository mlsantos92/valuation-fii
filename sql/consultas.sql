-- Consultas de análise sobre data/processed/valuation_fii.db

-- 1. Ranking de oportunidades: preço abaixo do preço justo mínimo, dados conferidos
SELECT v.rank_oportunidade, v.ticker, v.setor, v.preco, ROUND(v.faixa_min, 2) AS justo_min,
       ROUND(v.desconto * 100, 1) AS desconto_pct, f.liquidez_diaria
FROM valuation v JOIN fundos f USING (ticker)
WHERE v.rank_oportunidade IS NOT NULL
ORDER BY v.rank_oportunidade
LIMIT 20;

-- 2. Posição na faixa de preço justo por setor
SELECT setor,
       COUNT(*)                                        AS fundos,
       SUM(posicao = 'abaixo')                         AS abaixo,
       SUM(posicao = 'dentro')                         AS dentro,
       SUM(posicao = 'acima')                          AS acima,
       ROUND(AVG(premio) * 100, 1)                     AS premio_medio_pct
FROM valuation
WHERE posicao IS NOT NULL
GROUP BY setor
ORDER BY fundos DESC;

-- 3. Anomalias por regra
SELECT regra, COUNT(*) AS fundos FROM anomalias GROUP BY regra ORDER BY fundos DESC;

-- 4. Fundos com dado divergente da Status Invest e o motivo
SELECT a.ticker, a.detalhe, f.ultimo_rendimento, f.rendimento_statusinvest, f.dy_12m, f.dy_statusinvest
FROM anomalias a JOIN fundos f USING (ticker)
WHERE a.regra = 'conferencia'
ORDER BY a.ticker;

-- 5. Quanto o haircut reduziu o rendimento de cada fundo (maiores cortes)
SELECT v.ticker, f.ultimo_rendimento, ROUND(v.rendimento_usado, 4) AS rendimento_usado,
       ROUND((v.rendimento_usado / f.ultimo_rendimento - 1) * 100, 1) AS variacao_pct
FROM valuation v JOIN fundos f USING (ticker)
WHERE f.ultimo_rendimento > 0 AND v.rendimento_usado IS NOT NULL
ORDER BY variacao_pct
LIMIT 15;
