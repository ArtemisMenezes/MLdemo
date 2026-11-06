from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .catalog import (CITIES, CNAES, DEFAULT_ICP, FUNNEL, NORDESTE, PORTE_P, PORTES, REF_DATE,
                      SELLERS, TI_CNAES, UF_WEIGHTS)
from .scoring import score_frame

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261104
PREFIX = ["Aurora", "Vértice", "Nimbus", "Atlas", "Brisa", "Cobalto", "Delta", "Eclipse", "Faísca", "Girassol",
          "Horizonte", "Ícaro", "Jangada", "Kappa", "Lumen", "Mandacaru", "Névoa", "Órbita", "Prisma", "Quasar"]
SUFFIX = ["Digital", "Soluções", "Sistemas", "Consultoria", "Serviços", "Labs", "Group", "Tecnologia", "Partners", "Studio"]


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def build_companies(n: int, rng: np.random.Generator):
    """Retorna (df_com_nulos, df_verdade_sem_nulos, is_customer)."""
    cn = rng.choice(len(CNAES), n, p=np.array([c[2] for c in CNAES]) / sum(c[2] for c in CNAES))
    cnae = np.array([CNAES[i][0] for i in cn])
    desc = np.array([CNAES[i][1] for i in cn])

    ufs = list(UF_WEIGHTS)
    uf = rng.choice(ufs, n, p=np.array(list(UF_WEIGHTS.values())) / sum(UF_WEIGHTS.values()))
    cidade = np.array([rng.choice(CITIES[u]) for u in uf])

    porte = rng.choice(PORTES, n, p=PORTE_P)
    # idade: gamma; MEI mais jovens, Grande mais antigas
    age = rng.gamma(1.6, 5.0, n) * np.select([porte == "MEI", porte == "Grande"], [0.7, 1.6], 1.0)
    age = np.clip(age, 0.1, 34)
    abertura = [(REF_DATE - timedelta(days=int(a * 365.25))).isoformat() for a in age]

    p_baixada = 0.06 + 0.12 * np.exp(-age / 3)
    u = rng.random(n)
    situacao = np.where(u < p_baixada, "Baixada", np.where(u < p_baixada + 0.04, "Suspensa", "Ativa"))

    median = pd.Series(porte).map({"MEI": 5000, "ME": 30000, "EPP": 150000, "Médio": 800000, "Grande": 4_000_000}).to_numpy()
    capital = np.round(median * rng.lognormal(0, 0.7, n), -2)
    capital = np.where(porte == "MEI", np.minimum(capital, 81000), capital)

    emp = np.select(
        [porte == "MEI", porte == "ME", porte == "EPP", porte == "Médio"],
        [rng.integers(0, 2, n), rng.integers(1, 10, n), rng.integers(5, 50, n), rng.integers(50, 250, n)],
        np.exp(rng.uniform(np.log(250), np.log(2000), n)).astype(int))

    regime = np.select(
        [porte == "MEI", porte == "ME", porte == "EPP", porte == "Médio"],
        ["MEI", np.where(rng.random(n) < .9, "Simples", "Presumido"),
         np.where(rng.random(n) < .6, "Simples", "Presumido"),
         np.where(rng.random(n) < .6, "Presumido", "Real")], "Real")
    n_socios = 1 + rng.poisson(0.6 + 0.3 * np.isin(porte, ["EPP", "Médio", "Grande"]), n)

    is_ti = np.isin(cnae, list(TI_CNAES))
    p_site = 0.25 + 0.25 * is_ti + 0.10 * np.isin(porte, ["EPP", "Médio", "Grande"]) + 0.05 * np.minimum(age, 10) / 10
    tem_site = (rng.random(n) < p_site).astype(int)
    email_ok = rng.random(n) < 0.78
    fone_ok = rng.random(n) < 0.72

    # --- rótulo simulado "cliente conquistado" (verdade oculta que o modelo tenta recuperar) ---
    logit = (1.5 * is_ti + 0.7 * (cnae == "7020-4/00") + 0.3 * (cnae == "7311-4/00")
             + 0.7 * np.isin(uf, list(NORDESTE)) + 0.6 * np.isin(porte, ["ME", "EPP"]) + 0.9 * (porte == "Médio")
             + 0.04 * np.minimum(age, 12) + 0.5 * tem_site + 0.35 * np.log10(emp + 1)
             + rng.normal(0, 0.6, n))
    logit = np.where(situacao == "Ativa", logit, -np.inf)
    lo, hi = -15.0, 5.0  # bisseção do intercepto para prevalência-alvo de ~5%
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if sigmoid(logit + mid).mean() < 0.05 else (lo, mid)
    is_customer = rng.random(n) < sigmoid(logit + mid)

    idx = np.arange(n)
    df = pd.DataFrame({
        "cnpj": [f"00.{1 + i // 1000:03d}.{i % 1000:03d}/0001-00" for i in idx],
        "nome": [f"{rng.choice(PREFIX)} {rng.choice(SUFFIX)} {i + 1:05d}" for i in idx],
        "cnae": cnae, "cnae_desc": desc, "uf": uf, "cidade": cidade, "porte": porte,
        "abertura": abertura, "situacao": situacao, "capital": capital,
        "n_funcionarios": emp, "n_socios": n_socios, "regime": regime, "tem_site": tem_site,
        "email": [f"contato@empresa{i + 1:05d}.example" if ok else None for i, ok in zip(idx, email_ok)],
        "telefone": [f"(00) 0000-{i % 10000:04d}" if ok else None for i, ok in zip(idx, fone_ok)],
        "atualizado": [(REF_DATE - timedelta(days=int(d))).isoformat() for d in rng.integers(1, 90, n)],
        "fonte": "Base demo (sintética)",
    })
    truth = df.copy()

    # --- injeção de nulos (parte MNAR: MEIs têm mais lacunas) ---
    is_mei = (porte == "MEI")
    small = np.isin(porte, ["MEI", "ME"])
    nulls = {
        "abertura": 0.02 + 0.06 * is_mei, "capital": 0.04 + 0.08 * small, "n_funcionarios": 0.12,
        "regime": 0.06, "tem_site": 0.10, "uf": 0.005, "porte": 0.01, "cnae": 0.01,
    }
    for col, p in nulls.items():
        mask = rng.random(n) < p
        df[col] = df[col].astype("object").where(~mask, None)
        if col == "uf":
            df.loc[mask, "cidade"] = None
        if col == "cnae":
            df.loc[mask, "cnae_desc"] = None
    for col in ("n_funcionarios", "tem_site"):
        df[col] = pd.array(df[col], dtype="Int64")
    df["capital"] = pd.to_numeric(df["capital"])
    return df, truth, is_customer


def build_commercial(df: pd.DataFrame, is_customer: np.ndarray, rng: np.random.Generator):
    """customers, deals, deal_stage_history, recommendations."""
    scores = score_frame(df, DEFAULT_ICP)
    df = df.assign(score=scores["score"].to_numpy())
    cust_df = pd.DataFrame({
        "cnpj": df.loc[is_customer, "cnpj"].to_numpy(),
        "cliente_desde": [(REF_DATE - timedelta(days=int(d))).isoformat()
                          for d in rng.integers(30, 1100, int(is_customer.sum()))],
    })

    # --- deals: clientes conquistados são sobre-representados ---
    w = np.where(is_customer, 5.0, 1.0) * (df["situacao"] == "Ativa").to_numpy()
    n_deals = min(1500, int((w > 0).sum() // 2))
    pick = rng.choice(len(df), n_deals, replace=False, p=w / w.sum())
    deal_rows, hist_rows = [], []
    start = date(2026, 4, 1)
    seller_bias = rng.uniform(0.75, 1.2, len(SELLERS))  # "estilo" de cada vendedor
    for k, i in enumerate(pick, start=1):
        row = df.iloc[i]
        seller = int(rng.integers(0, len(SELLERS)))
        from_search = rng.random() < 0.7
        created = start + timedelta(days=int(rng.integers(0, 180)))
        sc = int(row["score"]) if from_search else None
        s = (row["score"] if from_search else 50) / 100
        if is_customer[i]:
            path = FUNNEL if rng.random() < 0.65 else FUNNEL[:int(rng.integers(1, 4))]
        else:  # não-clientes nunca chegam a "Ganho"
            reach = [0.85, 0.30 + 0.30 * s, 0.50, 0.0]
            path = ["Novo"]
            for st, p in zip(FUNNEL[1:], reach):
                if rng.random() < min(p * seller_bias[seller], 0.97):
                    path.append(st)
                else:
                    break
        t = created
        entered = []
        for st in path:
            entered.append((st, t))
            t = t + timedelta(days=int(rng.gamma(2.0, 3.5)) + 1)
            if t > REF_DATE:
                break
        stage = entered[-1][0]
        # deals que pararam antes do fim do funil: parte vira "Perdido"
        if stage not in ("Ganho",) and (entered[-1][1] + timedelta(days=21)) < REF_DATE and rng.random() < 0.55:
            entered.append(("Perdido", entered[-1][1] + timedelta(days=int(rng.integers(5, 21)))))
            stage = "Perdido"
        last = entered[-1][1] + (timedelta(days=int(rng.integers(0, 6))) if stage not in ("Ganho", "Perdido") else timedelta(0))
        last = min(last, REF_DATE)
        deal_rows.append((k, row["cnpj"], seller + 1, stage,
                          "Busca · Software e TI no Nordeste v1" if from_search else "Indicação",
                          1 if from_search else None, sc, created.isoformat(), last.isoformat()))
        hist_rows += [(k, st, d.isoformat()) for st, d in entered]
    deals = pd.DataFrame(deal_rows, columns=["id", "cnpj", "seller_id", "stage", "origin", "icp_version",
                                              "score_at_entry", "created_at", "last_activity_at"])
    history = pd.DataFrame(hist_rows, columns=["deal_id", "stage", "entered_at"])

    # --- recomendações: aceitas (viram deal), rejeitadas e ignoradas ---
    recs = []
    for _, d in deals[deals["origin"].str.startswith("Busca")].iterrows():
        recs.append((d["cnpj"], int(d["seller_id"]), 1, int(d["score_at_entry"]), "accepted", d["created_at"], d["created_at"]))
    pool = df[(df["score"] >= 40)].sample(frac=1, random_state=SEED)
    pool = pool[~pool["cnpj"].isin(deals["cnpj"])].head(3200)
    for _, r in pool.iterrows():
        seller = int(rng.integers(0, len(SELLERS)))
        shown = start + timedelta(days=int(rng.integers(0, 205)))
        p_rej = np.clip(0.75 - r["score"] / 160, 0.1, 0.8) / seller_bias[seller]
        # 35% das recomendações recebem uma decisão explícita; as demais ficam ignoradas
        dec = "rejected" if (rng.random() < 0.35 and rng.random() < p_rej) else "ignored"
        decided = (shown + timedelta(days=int(rng.integers(0, 3)))).isoformat() if dec == "rejected" else None
        recs.append((r["cnpj"], seller + 1, 1, int(r["score"]), dec, shown.isoformat(), decided))
    recommendations = pd.DataFrame(recs, columns=["cnpj", "seller_id", "icp_version", "score", "decision", "shown_at", "decided_at"])
    recommendations.insert(0, "id", np.arange(1, len(recommendations) + 1))
    return cust_df, deals, history, recommendations


def write_sqlite(path: Path, tables: dict[str, pd.DataFrame]):
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript((ROOT / "backend/sql/schema.sql").read_text(encoding="utf-8"))
    for name, frame in tables.items():
        frame = frame.astype(object).where(frame.notna(), None)  # NaN/NA -> NULL
        frame.to_sql(name, con, if_exists="append", index=False)
    con.commit()
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=ROOT / "data")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)

    companies, truth, is_customer = build_companies(a.n, rng)
    customers, deals, history, recs = build_commercial(companies, is_customer, rng)
    sellers = pd.DataFrame({"id": range(1, len(SELLERS) + 1), "nome": SELLERS})

    a.out.mkdir(parents=True, exist_ok=True)
    write_sqlite(a.out / "leads.db", {"companies": companies, "sellers": sellers, "customers": customers,
                                       "deals": deals, "deal_stage_history": history, "recommendations": recs})
    companies.to_csv(a.out / "companies.csv", index=False)
    sample = companies.head(200).astype(object).where(companies.head(200).notna(), None)
    (a.out / "companies_sample.json").write_text(
        json.dumps(sample.to_dict("records"), ensure_ascii=False, indent=1, default=int), encoding="utf-8")

    print(f"empresas={len(companies)} clientes={len(customers)} ({len(customers) / len(companies):.1%}) "
          f"deals={len(deals)} historico={len(history)} recomendacoes={len(recs)}")
    print("nulos (%):", (companies.isna().mean() * 100).round(1)[lambda s: s > 0].to_dict())


if __name__ == "__main__":
    main()
