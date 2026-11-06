"""API FastAPI da demo. Executar:  uvicorn backend.api:app --reload
Serve também o front estático (somente os arquivos da interface, nunca o banco)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import db
from .catalog import DEFAULT_ICP

ROOT = db.ROOT
app = FastAPI(title="Leads Search Intelligence · Demo", version="1.0",
              description="API de demonstração com dados 100% sintéticos.")


def get_con():
    if not db.DB_PATH.exists():
        raise HTTPException(503, "Banco não encontrado. Rode: python -m backend.generate_data")
    con = db.connect()
    try:
        yield con
    finally:
        con.close()


class Weights(BaseModel):
    cnae: int = Field(30, ge=0); uf: int = Field(20, ge=0); porte: int = Field(15, ge=0)
    idade: int = Field(10, ge=0); capital: int = Field(15, ge=0); contato: int = Field(10, ge=0)


class ICP(BaseModel):
    id: str = "icp"; name: str = "ICP"; version: int = 1
    cnaes: list[str]; ufs: list[str]; portes: list[str]
    minAge: float = 2; minCapital: float = 0
    weights: Weights = Weights()


class SearchRequest(BaseModel):
    icp: ICP
    q: str | None = None
    min_score: int = Field(0, ge=0, le=100)
    limit: int = Field(100, ge=1, le=500)


@app.get("/api/health")
def health(con: sqlite3.Connection = Depends(get_con)):
    n = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    return {"status": "ok", "companies": n, "synthetic": True}


@app.get("/api/icp/default")
def default_icp():
    return DEFAULT_ICP


@app.post("/api/search")
def search(req: SearchRequest, con: sqlite3.Connection = Depends(get_con)):
    icp = req.icp.model_dump()
    if sum(icp["weights"].values()) <= 0:
        raise HTTPException(422, "A soma dos pesos deve ser maior que zero.")
    return db.search(con, icp, q=req.q, min_score=req.min_score, limit=req.limit)


@app.get("/api/metrics/{name}")
def metrics(name: str, con: sqlite3.Connection = Depends(get_con)):
    allowed = db.named_queries()
    if name not in allowed:
        raise HTTPException(404, f"Métrica desconhecida. Disponíveis: {sorted(allowed)}")
    return db.run_named(con, name)


@app.get("/api/model")
def model_info():
    p = ROOT / "data" / "model_metrics.json"
    if not p.exists():
        raise HTTPException(503, "Modelo não treinado. Rode: python -m ml.lookalike")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/lookalike")
def lookalike(limit: int = Query(20, ge=1, le=200), uf: str | None = None,
              con: sqlite3.Connection = Depends(get_con)):
    """Empresas mais parecidas com os clientes conquistados."""
    try:
        rows = con.execute(
            """SELECT c.cnpj, c.nome, c.cnae_desc, c.uf, c.cidade, c.porte, l.score, l.rank, l.reasons
               FROM lookalike_scores l
               JOIN companies c ON c.cnpj = l.cnpj
               WHERE l.cnpj NOT IN (SELECT cnpj FROM customers)
                 AND c.situacao = 'Ativa' AND (:uf IS NULL OR c.uf = :uf)
               ORDER BY l.score DESC LIMIT :limit""", {"uf": uf, "limit": limit}).fetchall()
    except sqlite3.OperationalError:
        raise HTTPException(503, "Modelo não treinado. Rode: python -m ml.lookalike")
    return [{**dict(r), "reasons": json.loads(r["reasons"])} for r in rows]


for _name, _type in [("index.html", "text/html"), ("styles.css", "text/css"), ("app.js", "text/javascript"),
                     ("data.js", "text/javascript"), ("scoring.js", "text/javascript")]:
    def _make(path: Path, media: str):
        async def serve():
            return FileResponse(path, media_type=media)
        return serve
    app.add_api_route("/" if _name == "index.html" else f"/{_name}", _make(ROOT / _name, _type), include_in_schema=False)
