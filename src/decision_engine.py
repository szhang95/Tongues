import math
from typing import Dict, Any, List
import numpy as np

RISK_FREE_RATE = 0.05
THRESHOLD = 0.02


def compute_implied_r(S, C, P, K, T):
    try:
        if T <= 0:
            return None
        numerator = S - (C - P)
        if numerator <= 0 or K <= 0:
            return None

        r = - (1.0 / T) * math.log(numerator / K)

        if np.isnan(r) or np.isinf(r):
            return None

        return float(r)
    except Exception:
        return None


def analyze_chain(records: list,
                  base_rate: float = RISK_FREE_RATE,
                  threshold: float = THRESHOLD) -> Dict[str, Any]:
    signals = []
    rows = []

    # Convert list of dicts into strike-expiry groups
    by_strike_expiry = {}
    for r in records:
        K = r.get("STRIKE_PRC")
        days_to_expiry = r.get("DAYS_TO_EXPIRY")
        expir_date = r.get("EXPIR_DATE")

        # 跳过无效数据
        if K is None or days_to_expiry is None or days_to_expiry <= 0:
            continue

        # 使用 strike 和 到期日 作为组合键
        key = (K, expir_date)

        if key not in by_strike_expiry:
            by_strike_expiry[key] = {
                "CALL": None,
                "PUT": None,
                "spot": r.get("TRDPRC_1"),
                "days_to_expiry": days_to_expiry,
                "expir_date": expir_date
            }

        opt_type = r.get("OPTION_TYPE")
        if opt_type in ["CALL", "PUT"]:
            by_strike_expiry[key][opt_type] = r

    # 按到期日和行权价排序
    sorted_keys = sorted(by_strike_expiry.keys(), key=lambda x: (x[1], x[0]))

    for key in sorted_keys:
        K, expir_date = key
        data = by_strike_expiry[key]
        call = data["CALL"]
        put = data["PUT"]
        S = data["spot"]
        days_to_expiry = data["days_to_expiry"]

        if call is None or put is None or S is None:
            continue

        C = call.get("MID")
        P = put.get("MID")

        # 使用真实的到期时间(年化)
        T = days_to_expiry / 365.0

        r = compute_implied_r(S, C, P, K, T)

        row = {
            "strike": K,
            "expiry_date": str(expir_date)[:10] if expir_date else None,  # 格式化日期
            "days_to_expiry": days_to_expiry,
            "call_mid": C,
            "put_mid": P,
            "implied_r": r,
            "signal": None
        }

        # arbitrage condition
        if r is not None:
            diff = r - base_rate

            if diff > threshold:
                row["signal"] = "Sell synthetic, buy stock"
                signals.append(row.copy())
            elif diff < -threshold:
                row["signal"] = "Buy synthetic, short stock"
                signals.append(row.copy())

        rows.append(row)

    return {
        "signals": signals,
        "rows": rows,
        "base_rate": base_rate,
        "threshold": threshold,
    }