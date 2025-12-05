# src/lseg_client.py
from typing import Optional

import pandas as pd
import requests

WORKER_URL = "http://127.0.0.1:9001/fetch"


def get_option_chain(symbol: str) -> Optional[pd.DataFrame]:
    """
    调用本地 9001 端口的 lseg_worker，拿到 JSON，
    转成 pandas DataFrame，给 decision_engine 用。
    """
    try:
        resp = requests.get(WORKER_URL, params={"symbol": symbol}, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data or not data.get("success"):
            print("Worker error:", data)
            return None

        rows = data.get("data", [])
        if not rows:
            return None

        df = pd.DataFrame(rows)
        return df

    except Exception as e:
        print(f"Client Exception while fetching {symbol}: {e}")
        return None
