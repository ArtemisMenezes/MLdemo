"""Lookalike Intelligence (US-09): encontra empresas parecidas com os clientes conquistados.

Modelo principal: regressão logística (explicável). Comparações: gradiente boosting e o score por regras do ICP.
Validação: 5-fold estratificado; métricas AUC, Average Precision, precision@k e lift@k sobre predições
out-of-fold (cada empresa é pontuada por um modelo que NÃO a viu no treino).

ATENÇÃO: os rótulos de "cliente" são SIMULADOS (ver backend/generate_data.py). Os números mostram que o
pipeline funciona, não o desempenho esperado com dados reais.

Uso:  python -m ml.lookalike
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from backend.catalog import CNAES, DEFAULT_ICP, NORDESTE, REF_DATE
from backend.db import DB_PATH, ROOT
from backend.scoring import score_frame

SEED = 42
NUM = ["idade_anos", "log_capital", "log_funcionarios", "n_socios", "tem_site", "tem_email", "tem_telefone", "nordeste"]
CAT = ["cnae", "porte", "regime"]
LABELS = {
    "idade_anos": "Idade da empresa", "log_capital": "Capital social (log)", "log_funcionarios": "Nº de funcionários (log)",
    "n_socios": "Nº de sócios", "tem_site": "Possui site", "tem_email": "Possui e-mail", "tem_telefone": "Possui telefone",
    "nordeste": "Está no Nordeste",
}
CNAE_DESC = {c[0]: c[1] for c in CNAES}


def load_frame(path: Path | str = DB_PATH) -> pd.DataFrame:
    """Empresas ativas (universo de candidatas) com rótulo y = já é cliente."""
    con = sqlite3.connect(str(path))
    df = pd.read_sql("SELECT * FROM companies WHERE situacao = 'Ativa'", con)
    cust = set(pd.read_sql("SELECT cnpj FROM customers", con)["cnpj"])
    con.close()
    df["y"] = df["cnpj"].isin(cust).astype(int)
    return df


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    ab = pd.to_datetime(df["abertura"])
    X = pd.DataFrame({
        "idade_anos": (pd.Timestamp(REF_DATE) - ab).dt.days / 365.25,
        "log_capital": np.log10(df["capital"].astype(float)),
        "log_funcionarios": np.log10(df["n_funcionarios"].astype(float) + 1),
        "n_socios": df["n_socios"].astype(float),
        "tem_site": df["tem_site"].astype(float),
        "tem_email": df["email"].notna().astype(float),
        "tem_telefone": df["telefone"].notna().astype(float),
        "nordeste": np.where(df["uf"].isna(), np.nan, df["uf"].isin(NORDESTE).astype(float)),
    })
    for c in CAT:  # string ausente -> NaN do numpy (o imputador troca por "desconhecido")
        X[c] = df[c].astype(object).where(df[c].notna(), np.nan)
    return X


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), NUM),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="desconhecido")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), CAT),
    ])


def logistic() -> Pipeline:
    return Pipeline([("prep", preprocessor()), ("clf", LogisticRegression(C=0.5, max_iter=2000))])


def boosting() -> Pipeline:
    return Pipeline([("prep", preprocessor()),
                     ("clf", HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, random_state=SEED))])


def precision_at_k(y: np.ndarray, s: np.ndarray, k: int) -> float:
    return float(y[np.argsort(-s, kind="stable")[:k]].mean())


def ranking_metrics(y, s, ks=(100, 500)) -> dict:
    prev = float(np.mean(y))
    out = {"auc": float(roc_auc_score(y, s)), "average_precision": float(average_precision_score(y, s))}
    for k in ks:
        p = precision_at_k(y, s, k)
        out[f"precision@{k}"] = p
        out[f"lift@{k}"] = p / prev
        out[f"recall@{k}"] = p * k / float(np.sum(y))
    return out


def feature_names(pipe: Pipeline) -> list[str]:
    return list(pipe.named_steps["prep"].get_feature_names_out())


def pretty(name: str) -> str:
    """'num__idade_anos' -> 'Idade da empresa'; 'cat__cnae_6201-5/00' -> 'CNAE 6201-5/00 · Desenvolvimento...'"""
    name = re.sub(r"^(num|cat)__", "", name)
    if name.startswith("missingindicator_"):
        return f"{LABELS.get(name.removeprefix('missingindicator_'), name)}: dado ausente"
    if name in LABELS:
        return LABELS[name]
    for col, label in (("cnae", "CNAE"), ("porte", "Porte"), ("regime", "Regime")):
        if name.startswith(col + "_"):
            v = name[len(col) + 1:]
            return f"{label} {v}" + (f" · {CNAE_DESC[v]}" if col == "cnae" and v in CNAE_DESC else "")
    return name


def evaluate(df: pd.DataFrame, n_splits: int = 5) -> dict:
    X, y = make_features(df), df["y"].to_numpy()
    cv = StratifiedKFold(n_splits, shuffle=True, random_state=SEED)
    oof = {name: cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
           for name, model in (("logistic", logistic()), ("boosting", boosting()))}
    rules = score_frame(df, DEFAULT_ICP)["score"].to_numpy().astype(float)
    metrics = {name: ranking_metrics(y, s) for name, s in oof.items()}
    metrics["icp_rules_baseline"] = ranking_metrics(y, rules + np.random.default_rng(SEED).random(len(y)) * 1e-6)
    metrics["random"] = {"auc": 0.5, "precision@100": float(y.mean()), "precision@500": float(y.mean())}
    # variabilidade entre folds (AUC da regressão logística)
    aucs = [roc_auc_score(y[te], oof["logistic"][te]) for _, te in cv.split(X, y)]
    metrics["logistic"]["auc_folds_mean"] = float(np.mean(aucs))
    metrics["logistic"]["auc_folds_std"] = float(np.std(aucs))
    return {"oof": oof, "metrics": metrics}


def explain(df: pd.DataFrame, model: Pipeline) -> dict:
    X, y = make_features(df), df["y"].to_numpy()
    names, coef = feature_names(model), model.named_steps["clf"].coef_[0]
    coefs = sorted(({"feature": pretty(n), "coef": float(c), "odds_ratio": float(np.exp(c))}
                    for n, c in zip(names, coef)), key=lambda d: -abs(d["coef"]))
    # importância por permutação em dados NÃO vistos no treino, por coluna original
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=SEED)
    m = logistic().fit(Xtr, ytr)
    pi = permutation_importance(m, Xte, yte, scoring="roc_auc", n_repeats=15, random_state=SEED)
    perm = sorted(({"feature": LABELS.get(c, c.upper() if c == "cnae" else c.capitalize()),
                    "auc_drop": float(a), "std": float(s)}
                   for c, a, s in zip(X.columns, pi.importances_mean, pi.importances_std)), key=lambda d: -d["auc_drop"])
    return {"coefficients": coefs, "permutation_importance": perm}


def reasons_for(df: pd.DataFrame, model: Pipeline, top: int = 3) -> list[list[dict]]:
    """Principais contribuições positivas (coef × valor padronizado) por empresa."""
    Xt = model.named_steps["prep"].transform(make_features(df))
    contrib = Xt * model.named_steps["clf"].coef_[0]
    names = [pretty(n) for n in feature_names(model)]
    out = []
    for row in contrib:
        idx = np.argsort(-row)[:top]
        out.append([{"feature": names[i], "contribution": round(float(row[i]), 3)} for i in idx if row[i] > 0])
    return out


def main():
    df = load_frame()
    ev = evaluate(df)
    final = logistic().fit(make_features(df), df["y"])
    exp = explain(df, final)

    # score out-of-fold para o ranking (nenhuma empresa é pontuada por um modelo que a viu no treino)
    scores = ev["oof"]["logistic"]
    reasons = reasons_for(df, final)
    out = pd.DataFrame({"cnpj": df["cnpj"], "score": scores, "reasons": [json.dumps(r, ensure_ascii=False) for r in reasons]})
    out["rank"] = out["score"].rank(ascending=False, method="first").astype(int)

    con = sqlite3.connect(str(DB_PATH))
    con.execute("DELETE FROM lookalike_scores")
    con.executemany("INSERT INTO lookalike_scores (cnpj, score, rank, reasons) VALUES (?,?,?,?)",
                    out[["cnpj", "score", "rank", "reasons"]].itertuples(index=False, name=None))
    con.commit()
    con.close()

    payload = {
        "note": "Rótulos de cliente SIMULADOS. Mede se o pipeline funciona, não o desempenho em dados reais.",
        "n_candidates": int(len(df)), "n_customers": int(df["y"].sum()), "prevalence": float(df["y"].mean()),
        "validation": "StratifiedKFold(5), métricas sobre predições out-of-fold",
        "metrics": ev["metrics"], **exp,
    }
    (ROOT / "data" / "model_metrics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump(final, ROOT / "data" / "lookalike_model.joblib")

    m = ev["metrics"]
    print(f"candidatas={len(df)} clientes={int(df['y'].sum())} prevalência={df['y'].mean():.1%}")
    for k in ("logistic", "boosting", "icp_rules_baseline"):
        print(f"{k:20s} AUC={m[k]['auc']:.3f}  AP={m[k]['average_precision']:.3f}  "
              f"P@100={m[k]['precision@100']:.2f}  P@500={m[k]['precision@500']:.2f}  lift@100={m[k]['lift@100']:.1f}x")
    print("AUC por fold: %.3f ± %.3f" % (m["logistic"]["auc_folds_mean"], m["logistic"]["auc_folds_std"]))
    print("Top variáveis:", [(d["feature"], round(d["auc_drop"], 3)) for d in exp["permutation_importance"][:5]])


if __name__ == "__main__":
    main()
