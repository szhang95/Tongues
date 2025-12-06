# src/app.py

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import requests
import pandas as pd

from src.decision_engine import analyze_chain

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

WATCH_LIST = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY"]


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/monitor")
def api_monitor():
    results = []

    for symbol in WATCH_LIST:
        print(f"\n===== Calling worker for {symbol} =====")

        entry = {"symbol": symbol, "signals": [], "rows": []}

        try:
            resp = requests.get(
                f"http://127.0.0.1:9001/fetch?symbol={symbol}",
                timeout=10
            )
            print("worker http status =", resp.status_code)

            worker_json = resp.json()
            print("worker_json keys:", worker_json.keys())

            if not worker_json.get("success"):
                entry["error"] = worker_json.get("error")
                results.append(entry)
                continue

            raw = worker_json["data"]
            df = pd.DataFrame(raw)

            analysis = analyze_chain(df)
            entry.update(analysis)

        except Exception as e:
            print("ERROR in /api/monitor:", e)
            entry["error"] = str(e)

        results.append(entry)

    return {"success": True, "symbols": results}
