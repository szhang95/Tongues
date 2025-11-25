from fastapi import FastAPI
import pandas as pd
import eikon as ek
from datetime import datetime

app = FastAPI()

ek.set_app_key("06dbeb8bdea345b49d0e9f917a1a124250aedf25")   # <<< 记得填你自己的 key

FIELDS = [
    "EXPIR_DATE",      # <---- 关键：到期日
    "PUTCALLIND",
    "STRIKE_PRC",
    "CF_BID",
    "CF_ASK",
    "CF_CLOSE",
    "IMP_VOLT",
]


@app.get("/fetch")
def fetch(symbol: str):

    try:
        # --------------------------
        # 1) 获取标的当前价格
        # --------------------------
        spot_df, _ = ek.get_data(f"{symbol}.O", ["TRDPRC_1"])
        spot = None
        if spot_df is not None and "TRDPRC_1" in spot_df.columns:
            vals = spot_df["TRDPRC_1"].dropna().values
            if len(vals) > 0:
                spot = float(vals[0])

        # --------------------------
        # 2) 获取期权链 (真实 Expiry)
        # --------------------------
        ric = f"0#{symbol.upper()}*.U"
        df, err = ek.get_data(ric, fields=FIELDS)

        if err:
            print("LSEG ERR:", err)

        if df is None or df.empty:
            return {"success": True, "symbol": symbol, "data": []}

        # --------------------------
        # 3) 数据清洗
        # --------------------------
        df = df.dropna(subset=["STRIKE_PRC", "EXPIR_DATE"], how="any")

        for col in ["CF_BID", "CF_ASK", "CF_CLOSE", "STRIKE_PRC", "IMP_VOLT"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["MID"] = df[["CF_BID", "CF_ASK"]].mean(axis=1)

        # PUTCALLIND → CALL/PUT
        df["OPTION_TYPE"] = (
            df["PUTCALLIND"]
            .astype(str)
            .str.strip()
            .str.upper()
            .apply(lambda x: "CALL" if x.startswith("C") else ("PUT" if x.startswith("P") else None))
        )

        # --------------------------
        # 4) 转换 Expiry → T（真实天数 / 年化）
        # --------------------------
        today = datetime.utcnow().date()

        def compute_T(exp_str):
            try:
                exp = datetime.strptime(exp_str, "%Y-%m-%d").date()
            except:
                return None, None

            days = (exp - today).days
            if days < 0:
                return None, None

            T_years = days / 365.0
            return days, T_years

        df["T_days"], df["T"] = zip(*df["EXPIR_DATE"].apply(compute_T))

        # 加上标的价格
        df["SPOT"] = spot

        # 最终输出
        return {
            "success": True,
            "symbol": symbol,
            "data": df.to_dict(orient="records")
        }

    except Exception as e:
        print("Worker EXCEPTION:", e)
        return {"success": False, "symbol": symbol, "error": str(e)}


fetch('AAPL')