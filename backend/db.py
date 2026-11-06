"""Acesso ao SQLite: conexão, carregamento de consultas nomeadas e montagem do resultado de busca."""
from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from .catalog import REF_DATE

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "leads.db"
SQL_DIR = Path(__file__).resolve().parent / "sql"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(str(path or DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@lru_cache(maxsize=None)
def named_queries() -> dict[str, str]:
    """Divide metrics.sql em consultas por marcadores '-- name: xxx'."""
    text = (SQL_DIR / "metrics.sql").read_text(encoding="utf-8")
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run_named(con: sqlite3.Connection, name: str) -> list[dict]:
    return [dict(r) for r in con.execute(named_queries()[name])]


def _fmt_age(v):  
    return f"{v:.1f}"


def _criteria(r: dict, icp: dict) -> list[dict]:
    """Monta a lista de critérios no mesmo formato do evaluate() do front."""
    w = icp["weights"]
    st = lambda v: "unknown" if v is None else ("met" if v == 1 else "unmet")
    brl = lambda v: f"{v:,.0f}".replace(",", ".")
    return [
        dict(key="situacao", label="Situação cadastral ativa", weight=0, required=True, status=st(r["k_situacao"]),
             detail="Situação não informada" if r["situacao"] is None else f"Situação: {r['situacao']}"),
        dict(key="cnae", label="Atividade (CNAE) desejada", weight=w["cnae"], required=False, status=st(r["k_cnae"]),
             detail="CNAE não informado" if r["cnae"] is None else f"{r['cnae']} · {r['cnae_desc']}"),
        dict(key="uf", label="Região (UF) desejada", weight=w["uf"], required=False, status=st(r["k_uf"]),
             detail="UF não informada" if r["uf"] is None else f"{r['cidade']}/{r['uf']}"),
        dict(key="porte", label="Porte desejado", weight=w["porte"], required=False, status=st(r["k_porte"]),
             detail="Porte não informado" if r["porte"] is None else f"Porte: {r['porte']}"),
        dict(key="idade", label=f"Idade mínima ({icp['minAge']:g} anos)", weight=w["idade"], required=False,
             status=st(r["k_idade"]),
             detail="Data de abertura não informada" if r["abertura"] is None else f"Aberta há {_fmt_age(r['idade_anos'])} anos"),
        dict(key="capital", label="Capital social mínimo", weight=w["capital"], required=False, status=st(r["k_capital"]),
             detail="Capital social não informado" if r["capital"] is None else f"Capital: R$ {brl(r['capital'])}"),
        dict(key="contato", label="Possui contato disponível", weight=w["contato"], required=False,
             status=st(r["k_contato"]), detail="Contato na base" if r["k_contato"] else "Sem e-mail ou telefone"),
    ]


def search(con: sqlite3.Connection, icp: dict, q: str | None = None, min_score: int = 0, limit: int = 100) -> dict:
    sql = (SQL_DIR / "search.sql").read_text(encoding="utf-8")
    w = icp["weights"]
    params = dict(
        ref=REF_DATE.isoformat(), cnaes=json.dumps(icp["cnaes"]), ufs=json.dumps(icp["ufs"]),
        portes=json.dumps(icp["portes"]), min_age=icp["minAge"], min_capital=icp["minCapital"],
        w_cnae=w["cnae"], w_uf=w["uf"], w_porte=w["porte"], w_idade=w["idade"], w_capital=w["capital"],
        w_contato=w["contato"], q=q, min_score=min_score, limit=limit,
    )
    rows = [dict(r) for r in con.execute(sql, params)]
    out = []
    for r in rows:
        company = {k: r[k] for k in ("cnpj", "nome", "cnae", "uf", "cidade", "porte", "abertura", "situacao",
                                      "capital", "email", "telefone", "atualizado", "fonte")}
        company["cnaeDesc"] = r["cnae_desc"]
        ev = dict(cnpj=r["cnpj"], score=r["score"], eligible=r["k_situacao"] == 1, unknownCount=r["unknown_count"],
                  criteria=_criteria(r, icp), icpId=icp.get("id"), icpVersion=icp.get("version"))
        out.append({"company": company, "ev": ev})
    return {"total": rows[0]["total"] if rows else 0, "rows": out}
