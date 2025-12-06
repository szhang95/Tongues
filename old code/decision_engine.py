# src/decision_engine.py

import math
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

RISK_FREE_RATE = 0.05
THRESHOLD = 0.001   # 允许极小误差 → 保证出现 signal


def clean_float(x):
    """Remove NaN / inf / out-of-range numbers → return None"""
    try:
        if x is None:
            return None
        if isinstance(x, float):
            if math.isnan(x) or math.isinf(x):
                return None
        return float(x)
    except Exception:
        return None


def compute_implied_r(S, C, P, K, T):
    """
    C − P = S − K e^{-rT}
    r = -(1/T) ln( (S - (C-P)) / K )
    """
    try:
        if T <= 0 or K <= 0:
            return None

        numerator = S - (C - P)
        if numerator <= 0:
            return None

        r = -(1 / T) * math.log(numerator / K)
        return clean_float(r)

    except:
        return None


def analyze_chain(df, base_rate=RISK_FREE_RATE, threshold=THRESHOLD):
    if df is None or len(df) == 0:
        return {"signals": [], "rows": [], "base_rate": base_rate, "threshold": threshold}

    df = pd.DataFrame(df)

    # ---- Determine spot ----
    spot_col = "SPOT" if "SPOT" in df.columns else None

    # ---- T ----
    if "T" not in df.columns:
        df["T"] = 30 / 365

    strikes = sorted(df["STRIKE_PRC"].dropna().unique())

    signals = []
    rows = []

    for K in strikes:
        call = df[(df["STRIKE_PRC"] == K) & (df["OPTION_TYPE"] == "CALL")]
        put = df[(df["STRIKE_PRC"] == K) & (df["OPTION_TYPE"] == "PUT")]
        if call.empty or put.empty:
            continue

        C = float(call["MID"].values[0])
        P = float(put["MID"].values[0])
        T = float(call["T"].values[0])
        S = float(call[spot_col].values[0]) if spot_col else None

        if S is None:
            continue

        r = compute_implied_r(S, C, P, K, T)

        row = {
            "strike": K,
            "expiry_date": call.get("EXPIR_DATE", pd.Series(["-"])).values[0],
            "days_to_expiry": call.get("T_days", pd.Series([None])).values[0],
            "call_mid": C,
            "put_mid": P,
            "implied_r": r,
            "signal": None,
        }

        # ---- decide signal ----
        if r is not None:
            diff = r - base_rate

            if diff > threshold:
                row["signal"] = "Sell synthetic, buy stock"
            elif diff < -threshold:
                row["signal"] = "Buy synthetic, short stock"

        if row["signal"]:
            signals.append(row)

        rows.append(row)

    return {
        "signals": signals,
        "rows": rows,
        "base_rate": base_rate,
        "threshold": threshold,
    }
