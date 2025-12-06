# src/lseg_worker.py
from datetime import datetime, date

import eikon as ek
import pandas as pd
from fastapi import FastAPI

app = FastAPI()

# 🔑 这里填你的真实 APP KEY
ek.set_app_key("06dbeb8bdea345b49d0e9f917a1a124250aedf25")

FIELDS = [
    "PUTCALLIND",
    "STRIKE_PRC",
    "CF_BID",
    "CF_ASK",
    "CF_CLOSE",
    "IMP_VOLT",
    "EXPIR_DATE",   # 真实到期日
]


@app.get("/fetch")
def fetch(symbol: str):
    """
    对单个标的（如 AAPL）返回完整、清洗好的期权链 + 真实到期日 + T 等。
    """
    try:
        # ---------- 1. 标的现价 ----------
        spot_df, _ = ek.get_data(f"{symbol}.O", ["TRDPRC_1"])
        spot = None
        if spot_df is not None and "TRDPRC_1" in spot_df.columns:
            vals = spot_df["TRDPRC_1"].dropna().values
            if len(vals) > 0:
                spot = float(vals[0])

        # ---------- 2. 期权链 ----------
        ric = f"0#{symbol.upper()}*.U"
        df, err = ek.get_data(ric, fields=FIELDS)

        if err:
            print("Worker ERR:", err)

        if df is None or df.empty:
            return {"success": True, "symbol": symbol, "data": []}

        # ---------- 3. 清洗 ----------
        df = df.dropna(subset=["STRIKE_PRC"], how="any")

        num_cols = ["CF_BID", "CF_ASK", "CF_CLOSE", "STRIKE_PRC", "IMP_VOLT"]
        for c in num_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        # mid
        df["MID"] = df[["CF_BID", "CF_ASK"]].mean(axis=1)

        # 期权类型
        df["OPTION_TYPE"] = (
            df["PUTCALLIND"].astype(str).str.strip().str.upper().apply(
                lambda x: "CALL" if x in ["C", "CALL"] else
                          ("PUT" if x in ["P", "PUT"] else None)
            )
        )

        # 转到期日为日期
        today = date.today()
        if "EXPIR_DATE" in df.columns:
            df["EXPIR_DATE"] = pd.to_datetime(df["EXPIR_DATE"], errors="coerce").dt.date
            df["T_days"] = (df["EXPIR_DATE"] - today).apply(
                lambda d: d.days if pd.notna(d) else None
            )
            df["T"] = df["T_days"].apply(
                lambda x: x / 365.0 if x is not None and x > 0 else None
            )
        else:
            df["T_days"] = None
            df["T"] = None

        # 标的现价一列
        df["SPOT"] = spot

        return {
            "success": True,
            "symbol": symbol,
            "data": df.to_dict(orient="records"),
        }

    except Exception as e:
        print("Worker EXCEPTION:", e)
        return {"success": False, "symbol": symbol, "error": str(e)}
