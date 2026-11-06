PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS v_deals_enriched;
DROP TABLE IF EXISTS lookalike_scores;
DROP TABLE IF EXISTS recommendations;
DROP TABLE IF EXISTS deal_stage_history;
DROP TABLE IF EXISTS deals;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS companies;

CREATE TABLE companies (
  cnpj            TEXT PRIMARY KEY,
  nome            TEXT NOT NULL,
  cnae            TEXT,
  cnae_desc       TEXT,
  uf              TEXT,
  cidade          TEXT,
  porte           TEXT,
  abertura        TEXT,           -- ISO yyyy-mm-dd
  situacao        TEXT,
  capital         REAL,
  n_funcionarios  INTEGER,
  n_socios        INTEGER,
  regime          TEXT,
  tem_site        INTEGER,        -- 0/1, NULL = desconhecido
  email           TEXT,
  telefone        TEXT,
  atualizado      TEXT,
  fonte           TEXT NOT NULL
);
CREATE INDEX ix_companies_cnae ON companies(cnae);
CREATE INDEX ix_companies_uf   ON companies(uf);

CREATE TABLE sellers (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE);

-- Rótulo simulado para o modelo lookalike (clientes já conquistados)
CREATE TABLE customers (
  cnpj          TEXT PRIMARY KEY REFERENCES companies(cnpj),
  cliente_desde TEXT NOT NULL
);

CREATE TABLE deals (
  id               INTEGER PRIMARY KEY,
  cnpj             TEXT NOT NULL REFERENCES companies(cnpj),
  seller_id        INTEGER NOT NULL REFERENCES sellers(id),
  stage            TEXT NOT NULL,      -- estágio atual
  origin           TEXT NOT NULL,
  icp_version      INTEGER,
  score_at_entry   INTEGER,
  created_at       TEXT NOT NULL,
  last_activity_at TEXT NOT NULL
);
CREATE INDEX ix_deals_seller ON deals(seller_id);

CREATE TABLE deal_stage_history (
  deal_id    INTEGER NOT NULL REFERENCES deals(id),
  stage      TEXT NOT NULL,
  entered_at TEXT NOT NULL,
  PRIMARY KEY (deal_id, stage)
);

CREATE TABLE recommendations (
  id          INTEGER PRIMARY KEY,
  cnpj        TEXT NOT NULL REFERENCES companies(cnpj),
  seller_id   INTEGER NOT NULL REFERENCES sellers(id),
  icp_version INTEGER NOT NULL,
  score       INTEGER NOT NULL,
  decision    TEXT NOT NULL CHECK (decision IN ('accepted','rejected','ignored')),
  shown_at    TEXT NOT NULL,
  decided_at  TEXT                     -- NULL quando ignorada
);
CREATE INDEX ix_reco_seller ON recommendations(seller_id);

CREATE TABLE lookalike_scores (
  cnpj    TEXT PRIMARY KEY REFERENCES companies(cnpj),
  score   REAL NOT NULL,               -- probabilidade out-of-fold (0..1)
  rank    INTEGER NOT NULL,
  reasons TEXT NOT NULL                -- JSON: principais variáveis que puxaram o score
);
