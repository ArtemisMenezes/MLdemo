-- name: funnel
-- Funil: deals que alcançaram cada estágio, conversão vs. estágio anterior (LAG) e vs. o topo (FIRST_VALUE).
WITH ordem(stage, ord) AS (
  VALUES ('Novo', 1), ('Contato', 2), ('Reunião', 3), ('Proposta', 4), ('Ganho', 5)
),
alcancou AS (
  SELECT h.stage, COUNT(DISTINCT h.deal_id) AS deals
  FROM deal_stage_history h
  GROUP BY h.stage
)
SELECT o.stage,
       a.deals,
       ROUND(100.0 * a.deals / LAG(a.deals)        OVER (ORDER BY o.ord), 1) AS conv_etapa_anterior,
       ROUND(100.0 * a.deals / FIRST_VALUE(a.deals) OVER (ORDER BY o.ord), 1) AS conv_total
FROM ordem o JOIN alcancou a USING (stage)
ORDER BY o.ord;

-- name: sellers
-- Aceitação de recomendações por vendedor, com ranking (RANK) e média da equipe (AVG OVER).
WITH por_vendedor AS (
  SELECT s.nome AS vendedor,
         SUM(r.decision = 'accepted') AS aceitas,
         SUM(r.decision = 'rejected') AS rejeitadas,
         SUM(r.decision = 'ignored')  AS ignoradas,
         COUNT(*)                     AS total
  FROM recommendations r JOIN sellers s ON s.id = r.seller_id
  GROUP BY s.id
),
taxas AS (
  SELECT *, ROUND(100.0 * aceitas / NULLIF(aceitas + rejeitadas, 0), 1) AS taxa_aceitacao
  FROM por_vendedor
)
SELECT vendedor, aceitas, rejeitadas, ignoradas, total, taxa_aceitacao,
       RANK() OVER (ORDER BY taxa_aceitacao DESC)        AS ranking,
       ROUND(AVG(taxa_aceitacao) OVER (), 1)             AS media_equipe
FROM taxas
ORDER BY ranking;

-- name: stage_time
-- Tempo médio em cada estágio: LEAD() pega a data de entrada do estágio seguinte do mesmo deal.
WITH janelas AS (
  SELECT deal_id, stage, entered_at,
         LEAD(entered_at) OVER (PARTITION BY deal_id ORDER BY entered_at) AS saiu_em
  FROM deal_stage_history
)
SELECT stage,
       COUNT(*) AS amostra,
       ROUND(AVG(julianday(saiu_em) - julianday(entered_at)), 1) AS dias_medios
FROM janelas
WHERE saiu_em IS NOT NULL AND stage IN ('Novo', 'Contato', 'Reunião', 'Proposta')
GROUP BY stage
ORDER BY CASE stage WHEN 'Novo' THEN 1 WHEN 'Contato' THEN 2 WHEN 'Reunião' THEN 3 ELSE 4 END;

-- name: score_bands
-- Faixa de score na entrada vs. taxa de ganho (CORRELAÇÃO, não causalidade).
WITH faixas AS (
  SELECT d.id, d.stage,
         CASE WHEN d.score_at_entry >= 80 THEN '80-100'
              WHEN d.score_at_entry >= 60 THEN '60-79'
              WHEN d.score_at_entry >= 40 THEN '40-59'
              ELSE '0-39' END AS faixa
  FROM deals d
  WHERE d.score_at_entry IS NOT NULL
)
SELECT faixa,
       COUNT(*)                                        AS deals,
       SUM(stage = 'Ganho')                            AS ganhos,
       ROUND(100.0 * SUM(stage = 'Ganho') / COUNT(*), 1) AS taxa_ganho
FROM faixas
GROUP BY faixa
ORDER BY faixa DESC;

-- name: weekly_accepts
-- Recomendações aceitas por semana, com acumulado (SUM OVER) e variação semanal (LAG).
WITH semanal AS (
  SELECT strftime('%Y-W%W', decided_at) AS semana, COUNT(*) AS aceitas
  FROM recommendations
  WHERE decision = 'accepted'
  GROUP BY semana
)
SELECT semana, aceitas,
       SUM(aceitas) OVER (ORDER BY semana)                          AS acumulado,
       aceitas - LAG(aceitas) OVER (ORDER BY semana)                AS variacao
FROM semanal
ORDER BY semana;

-- name: seller_pipeline_top
-- Top 3 deals abertos por vendedor (maior score), com ROW_NUMBER por partição.
WITH abertos AS (
  SELECT s.nome AS vendedor, c.nome AS empresa, d.stage, d.score_at_entry AS score,
         ROW_NUMBER() OVER (PARTITION BY d.seller_id ORDER BY d.score_at_entry DESC, c.nome) AS pos
  FROM deals d
  JOIN sellers s   ON s.id = d.seller_id
  JOIN companies c ON c.cnpj = d.cnpj
  WHERE d.stage IN ('Novo', 'Contato', 'Reunião', 'Proposta') AND d.score_at_entry IS NOT NULL
)
SELECT vendedor, empresa, stage, score FROM abertos WHERE pos <= 3 ORDER BY vendedor, pos;
