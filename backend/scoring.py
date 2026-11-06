from __future__ import annotations
import numpy as np
import pandas as pd
from .catalog import REF_DATE


def _flag(cond: pd.Series, known: pd.Series) -> pd.Series:
    """1.0 atendido, 0.0 não atendido, NaN desconhecido."""
    out = cond.astype(float)
    out[~known] = np.nan
    return out


def score_frame(df: pd.DataFrame, icp: dict, ref=REF_DATE) -> pd.DataFrame:
    w = icp["weights"]
    ab = pd.to_datetime(df["abertura"])
    age = (pd.Timestamp(ref) - ab).dt.days / 365.25
    k = pd.DataFrame(index=df.index)
    k["situacao"] = _flag(df["situacao"] == "Ativa", df["situacao"].notna())
    k["cnae"] = _flag(df["cnae"].isin(icp["cnaes"]), df["cnae"].notna())
    k["uf"] = _flag(df["uf"].isin(icp["ufs"]), df["uf"].notna())
    k["porte"] = _flag(df["porte"].isin(icp["portes"]), df["porte"].notna())
    k["idade"] = _flag(age >= icp["minAge"], age.notna())
    k["capital"] = _flag(df["capital"] >= icp["minCapital"], df["capital"].notna())
    k["contato"] = (df["email"].notna() | df["telefone"].notna()).astype(float)

    total = sum(w.values())
    earned = sum(k[c].fillna(0) * w[c] for c in w)
    eligible = k["situacao"] == 1.0
    # arredondamento "meio para cima" (igual a Math.round e a ROUND do SQLite)
    score = np.floor(100.0 * earned / total + 0.5).where(eligible, 0).astype(int)
    out = k.add_prefix("k_")
    out["score"] = score
    out["unknown_count"] = k.isna().sum(axis=1)
    return out
