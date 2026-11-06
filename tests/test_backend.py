import json
import subprocess
from copy import deepcopy

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import db
from backend.api import app
from backend.catalog import DEFAULT_ICP
from backend.scoring import score_frame

client = TestClient(app)
ICPS = {
    "padrao": DEFAULT_ICP,
    "exigente": {**deepcopy(DEFAULT_ICP), "cnaes": ["6201-5/00"], "ufs": ["CE"], "portes": ["EPP"], "minAge": 6.5,
                 "minCapital": 200000, "weights": {"cnae": 10, "uf": 40, "porte": 10, "idade": 20, "capital": 10, "contato": 10}},
}


@pytest.fixture(scope="module")
def con():
    c = db.connect()
    yield c
    c.close()


@pytest.fixture(scope="module")
def companies(con):
    return pd.read_sql("SELECT * FROM companies", con)


# ---------- qualidade dos dados ----------
def test_integridade_e_nulos(con, companies):
    assert companies["cnpj"].is_unique
    assert companies["cnpj"].str.match(r"^00\.\d{3}\.\d{3}/0001-00$").all()  # CNPJs claramente fictícios
    assert 0 < companies["capital"].isna().mean() < 0.2           # há lacunas, mas moderadas
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    # clientes só existem entre empresas ativas; deals "Ganho" só em clientes
    assert con.execute("SELECT COUNT(*) FROM customers c JOIN companies p USING(cnpj) WHERE p.situacao <> 'Ativa'").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM deals WHERE stage='Ganho' AND cnpj NOT IN (SELECT cnpj FROM customers)").fetchone()[0] == 0


def test_funil_nao_crescente(con):
    deals = [r["deals"] for r in db.run_named(con, "funnel")]
    assert deals == sorted(deals, reverse=True)


def test_ranking_de_vendedores(con):
    rows = db.run_named(con, "sellers")
    assert [r["ranking"] for r in rows] == sorted(r["ranking"] for r in rows)
    assert all(0 <= r["taxa_aceitacao"] <= 100 for r in rows)


# ---------- paridade: pandas × SQL × JS ----------
@pytest.mark.parametrize("nome", ICPS)
def test_paridade_pandas_sql(con, companies, nome):
    icp = ICPS[nome]
    expected = dict(zip(companies["cnpj"], score_frame(companies, icp)["score"]))
    got = {r["company"]["cnpj"]: r["ev"]["score"] for r in db.search(con, icp, limit=100000)["rows"]}
    assert got == expected


@pytest.mark.parametrize("nome", ICPS)
def test_paridade_js(companies, nome):
    icp = ICPS[nome]
    sample = companies.sample(1500, random_state=1)
    payload = json.dumps({"companies": json.loads(sample.to_json(orient="records")), "icp": icp})
    out = subprocess.run(["node", "tests/parity_js.cjs"], input=payload, capture_output=True, text=True, check=True)
    js = json.loads(out.stdout)
    py = dict(zip(sample["cnpj"], score_frame(sample, icp)["score"]))
    assert js == py


# ---------- API ----------
def test_api_search_ordenado_e_explicavel():
    r = client.post("/api/search", json={"icp": DEFAULT_ICP, "limit": 20, "min_score": 70}).json()
    scores = [x["ev"]["score"] for x in r["rows"]]
    assert scores == sorted(scores, reverse=True) and min(scores) >= 70
    crit = r["rows"][0]["ev"]["criteria"]
    assert {c["status"] for c in crit} <= {"met", "unmet", "unknown"} and len(crit) == 7
    assert r["total"] >= len(r["rows"])


def test_api_deterministica():
    body = {"icp": DEFAULT_ICP, "limit": 50}
    assert client.post("/api/search", json=body).json() == client.post("/api/search", json=body).json()


def test_api_validacoes():
    bad = {**DEFAULT_ICP, "weights": {k: 0 for k in DEFAULT_ICP["weights"]}}
    assert client.post("/api/search", json={"icp": bad}).status_code == 422
    assert client.post("/api/search", json={"icp": DEFAULT_ICP, "min_score": 101}).status_code == 422
    assert client.get("/api/metrics/inexistente").status_code == 404


def test_api_nao_expoe_o_banco():
    assert client.get("/data/leads.db").status_code == 404
    assert client.get("/backend/api.py").status_code == 404


def test_sql_injection_no_parametro_q():
    r = client.post("/api/search", json={"icp": DEFAULT_ICP, "q": "'; DROP TABLE companies; --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/api/health").json()["companies"] > 0


# ---------- ML ----------
def test_lookalike_exclui_clientes_e_ordena():
    r = client.get("/api/lookalike", params={"limit": 50}).json()
    scores = [x["score"] for x in r]
    assert scores == sorted(scores, reverse=True)
    c = db.connect()
    clientes = {x[0] for x in c.execute("SELECT cnpj FROM customers")}
    assert not clientes & {x["cnpj"] for x in r}
    assert all(0 < len(x["reasons"]) <= 3 for x in r)


def test_modelo_supera_o_acaso():
    m = client.get("/api/model").json()
    lg = m["metrics"]["logistic"]
    assert lg["auc"] > 0.65
    assert lg["precision@100"] > 2 * m["prevalence"]
    assert lg["auc_folds_std"] < 0.05
