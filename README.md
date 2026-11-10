# Valuation FII

Preço justo por **fluxo de caixa descontado (FCD)** para todos os fundos imobiliários, FIAGROs e FI-INFRAs negociados na B3, com um pipeline em Python que trata os erros das fontes de dados antes de calcular.

**Pergunta:** quais fundos negociam abaixo de uma faixa conservadora de preço justo, depois de limpar e conferir os dados?

> Material didático. Nenhum resultado deste repositório é recomendação de compra ou de venda.

## Resultados (retrato de 10/11/2026, após ajustes de código)

| | |
|---|---|
| Fundos negociados na B3 (planilha, após ajustes de código) | 490 |
| Avaliados (dados completos e plausíveis) | 403 |
| Preço abaixo / dentro / acima da faixa de preço justo | 234 / 41 / 128 |
| Fora da análise por exclusão ou dado suspeito | 87 |
| Calculados, mas fora do ranking por divergência entre fontes | 103 |
| Fundos no ranking de oportunidades | 134 |
| **Painel publicado (liquidez ≥ R$ 1 mi/dia)** | **103 fundos, 42 no ranking** |

- O teste de estabilidade do ranking (taxa base de 10% ou 12%, haircut dobrado) foi feito sobre o retrato anterior, com 501 fundos. Reexecute o notebook para atualizá-lo ao retrato atual.
- Fundos de papel e FIAGROs concentram os casos “abaixo da faixa”. O motivo é uma limitação do modelo, não necessariamente oportunidade: o FCD supõe rendimento constante, e esses fundos acompanham CDI e risco de crédito.

A análise completa está em [`notebooks/analise_valuation_fii.ipynb`](notebooks/analise_valuation_fii.ipynb). O painel interativo fica em [`docs/index.html`](docs/index.html).

## Pipeline

```
planilha (5 fontes)  →  carga e normalização  →  classificação de setor  →  regras de qualidade
                                                                                   ↓
     painel (docs/)  ←  SQLite + CSV  ←  ranking  ←  sensibilidade 3×3  ←  FCD por fundo
```

| Etapa | Código |
|---|---|
| Leitura e normalização (números em formato brasileiro, tickers válidos, fundos de balcão fora) | `src/valuation_fii/carga.py` |
| Setor e prêmio de risco (setor manual → ANBIMA → segmento da fonte; FIAGRO/FI-INFRA ficam com o maior prêmio) | `classificacao.py` |
| Rendimento com haircut e ajuste de risco por vacância e saúde do fundo | `risco.py` |
| Regras de qualidade de dados | `qualidade.py` |
| Modelo FCD, cenários e matriz de sensibilidade | `fcd.py` |
| Orquestração e ranking | `pipeline.py` |
| Banco SQLite (`sql/schema.sql`) e saídas | `banco.py`, `scripts/rodar_pipeline.py` |
| Consultas de análise em SQL | `sql/consultas.sql` |

## Qualidade dos dados

Os dados vêm de uma planilha Google que junta Fundamentus, Status Invest, Funds Explorer, Investidor10 e GOOGLEFINANCE. Cada fonte tem erros próprios, tratados em três níveis:

| Nível | Regra | Fundos |
|---|---|---|
| Exclusão | encerrado, sem dados ou sem rendimento em 2026 | 56 |
| Suspeito | sem rendimento, sem preço, rendimento mensal > 4% do preço, liquidez > R$ 500 mi/dia | 31 |
| Conferência | rendimento > 25% diferente da Status Invest, DY irreal, rendimento anualizado muito acima do DY 12m, P/VP > 1,5 | 103 |

Exemplos encontrados no retrato:

- **PRTS11** aparece com cotação de R$ 18 mil e liquidez de R$ 4,4 bilhões/dia.
- **JCIN11** aparece com último rendimento de R$ 7.082,94 para uma cota de R$ 148,90.
- O segmento ANBIMA do **MXRF11**, um fundo de papel, aparece como Logística.

**Um erro no painel original, encontrado na reescrita.** O painel anterior buscava as colunas da planilha pelo início do nome. Por isso pegava “Setor predominante (edite para incluir)”, a lista de edição, no lugar de “Setor predominante”, o valor de cada fundo. Com isso, 22 fundos recebiam o setor de outro ticker, e 3 mudavam de posição na faixa. **Ajustes de código e fundos fora do painel.** Os códigos ARCT11, SDIL11 e SHOP11 mudaram para RZAT11, TRBL11 e SHPH11, e a planilha já traz os novos códigos em linhas separadas. Ficam com a linha nova e saem da antiga. Também saem do painel os fundos liquidados (BLMR11, COPP11, GURB11, PRTS11, VVPR11) e os incorporados ou consolidados (MGFF11, RBRR11, VCJR11). A lista está em [`data/raw/ajustes_tickers.json`](data/raw/ajustes_tickers.json). Após esses ajustes, a planilha tem 490 fundos.

O detalhe do setor está em [`data/processed/correcao_setor_predominante.csv`](data/processed/correcao_setor_predominante.csv). Este projeto busca as colunas pelo nome exato.

## Modelo

Para rendimento mensal $d$, horizonte de $n$ anos, taxa de desconto $r$ e CAP rate de saída $c$:

$$VJ = \sum_{t=1}^{n} \frac{12d}{(1+r)^t} + \frac{12d / c}{(1+r)^n}$$

**Taxa de desconto**
- É a taxa básica × (1 + prêmio).
- A taxa básica é a média do Tesouro IPCA+ e do Prefixado mais curtos.
- O prêmio é o do setor ou o ajuste de risco do fundo, o que for maior.
- O ajuste do fundo vem da vacância acima de 5% e da saúde “Atenção” nos relatórios gerenciais.

**Rendimento**
- É a média dos últimos 12 pagamentos menos 1 desvio padrão da oscilação até a mediana.
- Assim, um pagamento extraordinário não é projetado por 10 anos.

**Faixa de preço justo**
- Vai do mínimo ao máximo de uma matriz 3×3.
- As colunas são as taxas de 10,5%, 11% e 11,5%, cada uma × (1 + prêmio).
- As linhas são o CAP de saída −0,5 p.p., o CAP e o CAP +0,5 p.p.

**Ranking**
- Entram só fundos com preço abaixo do mínimo da faixa, dados conferidos, DY não zerado e saúde diferente de “Alerta” ou “Sem dados”.
- A ordem segue o desconto sobre o preço justo mínimo.

## Validação

`pytest` roda 11 testes:

- **Contra a planilha original:** o valor justo base, otimista e pessimista e a matriz de sensibilidade do TRXF11 batem com a aba “Cenários Preço Justo” até a 6ª casa decimal.
- **Contra o painel original (paridade):** `tests/paridade/painel_original.js` executa as funções de cálculo do painel anterior, em JavaScript, sobre o mesmo retrato de dados. O teste confere fundo a fundo os seguintes itens, e os 501 fundos batem:
  - setor;
  - exclusões e dados suspeitos;
  - faixa de preço justo;
  - posição na faixa;
  - status da conferência.
- **Regras de qualidade e conversão de números:** testes unitários.

## Como rodar

```bash
pip install -r requirements.txt
python scripts/rodar_pipeline.py          # gera data/processed/ e docs/dados.json
pytest                                    # testes (a paridade usa: node tests/paridade/painel_original.js)
cd docs && python -m http.server          # painel em http://localhost:8000
```

## Estrutura

```
data/raw/          retrato dos dados (planilha em CSV, rendimentos, saúde, prêmios, Tesouro)
data/processed/    valuation.csv, valuation_fii.db (gerado), correção do setor predominante
src/valuation_fii/ pacote Python
sql/               schema e consultas
notebooks/         análise executada
docs/              painel estático (lê docs/dados.json)
tests/             testes, referência da planilha e paridade com o painel anterior
```

## Limitações

- O rendimento é suposto constante, uma hipótese fraca para fundos de papel e FIAGROs.
- Os prêmios de risco por setor são premissas do autor, não estimativas de mercado.
- Os dados são um retrato único. A coleta ainda passa pela planilha, e o próximo passo é automatizá-la em Python.
- A avaliação de saúde (vacância e inadimplência) cobre 73 fundos (P/VP < 0,8 e liquidez ≥ R$ 1 mi), lidos nos relatórios gerenciais do FNET.

**Próximos passos:**
- coleta automatizada direto das fontes;
- histórico diário de preços para backtest do ranking;
- prêmios de risco estimados por spread de mercado.

## Uso de IA

O modelo FCD é o da planilha do autor. As premissas (prêmios por setor, CAP, horizonte) e as regras de qualidade foram definidas pelo autor. Na escrita do código, na leitura dos relatórios gerenciais e na revisão houve apoio de IA (Claude). Todos os números foram conferidos pelos testes descritos acima.

Autor: Marcus Lima
