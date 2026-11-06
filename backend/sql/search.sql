-- Busca + scoring do ICP direto em SQL (paridade com scoring.js e backend/scoring.py).
-- Parâmetros nomeados: :ref :cnaes :ufs :portes (JSON arrays) :min_age :min_capital
--   :w_cnae :w_uf :w_porte :w_idade :w_capital :w_contato :q :min_score :limit
-- k_* : 1 = atendido, 0 = não atendido, NULL = desconhecido
WITH base AS (
  SELECT c.*,
    CASE WHEN c.situacao IS NULL THEN NULL WHEN c.situacao = 'Ativa' THEN 1 ELSE 0 END AS k_situacao,
    CASE WHEN c.cnae  IS NULL THEN NULL WHEN c.cnae  IN (SELECT value FROM json_each(:cnaes))  THEN 1 ELSE 0 END AS k_cnae,
    CASE WHEN c.uf    IS NULL THEN NULL WHEN c.uf    IN (SELECT value FROM json_each(:ufs))    THEN 1 ELSE 0 END AS k_uf,
    CASE WHEN c.porte IS NULL THEN NULL WHEN c.porte IN (SELECT value FROM json_each(:portes)) THEN 1 ELSE 0 END AS k_porte,
    CASE WHEN c.abertura IS NULL THEN NULL
         WHEN (julianday(:ref) - julianday(c.abertura)) / 365.25 >= :min_age THEN 1 ELSE 0 END AS k_idade,
    CASE WHEN c.capital IS NULL THEN NULL WHEN c.capital >= :min_capital THEN 1 ELSE 0 END AS k_capital,
    CASE WHEN c.email IS NOT NULL OR c.telefone IS NOT NULL THEN 1 ELSE 0 END AS k_contato
  FROM companies c
),
scored AS (
  SELECT base.*,
    CASE WHEN k_situacao = 1 THEN
      CAST(ROUND(100.0 * (
          COALESCE(k_cnae, 0)    * :w_cnae   + COALESCE(k_uf, 0)      * :w_uf
        + COALESCE(k_porte, 0)   * :w_porte  + COALESCE(k_idade, 0)   * :w_idade
        + COALESCE(k_capital, 0) * :w_capital + k_contato             * :w_contato
      ) / (:w_cnae + :w_uf + :w_porte + :w_idade + :w_capital + :w_contato)) AS INTEGER)
    ELSE 0 END AS score,
    (k_situacao IS NULL) + (k_cnae IS NULL) + (k_uf IS NULL) + (k_porte IS NULL)
      + (k_idade IS NULL) + (k_capital IS NULL) AS unknown_count,
    (julianday(:ref) - julianday(abertura)) / 365.25 AS idade_anos
  FROM base
),
filtered AS (
  SELECT * FROM scored
  WHERE score >= :min_score
    AND (:q IS NULL OR :q = '' OR (nome || ' ' || cnpj || ' ' || COALESCE(cidade, '')) LIKE '%' || :q || '%')
)
SELECT filtered.*, COUNT(*) OVER () AS total
FROM filtered
ORDER BY score DESC, nome COLLATE NOCASE
LIMIT :limit;
