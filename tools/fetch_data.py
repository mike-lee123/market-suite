"""Generate docs/data/*.json from Yahoo Finance history for the market-suite
static frontend. Run manually: `python tools/fetch_data.py`."""

import json
import os
from datetime import datetime, timezone

import yfinance as yf


def history_to_symbol_json(symbol: str, name: str, history) -> dict:
    df = history.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
    return {
        "symbol": symbol,
        "name": name,
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "open": [round(float(v), 4) for v in df["Open"]],
        "high": [round(float(v), 4) for v in df["High"]],
        "low": [round(float(v), 4) for v in df["Low"]],
        "close": [round(float(v), 4) for v in df["Close"]],
        "volume": [int(v) for v in df["Volume"]],
    }


def build_manifest(entries: list[dict]) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbols": entries,
    }


TW_STOCKS = [
    {"symbol": "2330.TW", "name": "台積電", "sector": "半導體"},
    {"symbol": "2454.TW", "name": "聯發科", "sector": "半導體"},
    {"symbol": "2317.TW", "name": "鴻海", "sector": "電子代工"},
    {"symbol": "2308.TW", "name": "台達電", "sector": "電源供應"},
    {"symbol": "2382.TW", "name": "廣達", "sector": "電子代工"},
    {"symbol": "2412.TW", "name": "中華電", "sector": "電信"},
    {"symbol": "2881.TW", "name": "富邦金", "sector": "金融"},
    {"symbol": "2882.TW", "name": "國泰金", "sector": "金融"},
    {"symbol": "2891.TW", "name": "中信金", "sector": "金融"},
    {"symbol": "3711.TW", "name": "日月光投控", "sector": "封測"},
    {"symbol": "2303.TW", "name": "聯電", "sector": "半導體"},
    {"symbol": "1301.TW", "name": "台塑", "sector": "塑化"},
    {"symbol": "2603.TW", "name": "長榮", "sector": "航運"},
    {"symbol": "2609.TW", "name": "陽明", "sector": "航運"},
    {"symbol": "0050.TW", "name": "元大台灣50", "sector": "ETF"},
    {"symbol": "0056.TW", "name": "元大高股息", "sector": "ETF"},
    {"symbol": "00878.TW", "name": "國泰永續高股息", "sector": "ETF"},
]

MACRO_BENCHMARKS = [
    {"symbol": "^TWII", "name": "台股加權指數", "sector": "台股大盤"},
    {"symbol": "^DJI", "name": "道瓊工業指數", "sector": "美股"},
    {"symbol": "^GSPC", "name": "S&P 500", "sector": "美股"},
    {"symbol": "^IXIC", "name": "那斯達克指數", "sector": "美股"},
    {"symbol": "^SOX", "name": "費城半導體指數", "sector": "美股"},
    {"symbol": "^KS11", "name": "韓國 KOSPI", "sector": "亞股"},
    {"symbol": "TSM", "name": "台積電 ADR", "sector": "美股ADR"},
    {"symbol": "TWD=X", "name": "美元兌台幣匯率", "sector": "匯率"},
    {"symbol": "CL=F", "name": "原油期貨", "sector": "原物料"},
]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")


def fetch_symbol_history(symbol: str, period: str = "5y"):
    return yf.Ticker(symbol).history(period=period)


def safe_filename(symbol: str) -> str:
    return f"{symbol}.json"


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    manifest_entries = []

    for category, group in (("tw_stock", TW_STOCKS), ("macro", MACRO_BENCHMARKS)):
        for item in group:
            symbol, name, sector = item["symbol"], item["name"], item["sector"]
            print(f"抓取 {symbol} ({name}) ...")
            history = fetch_symbol_history(symbol)
            if history.empty:
                print(f"  ⚠️ 無資料,略過 {symbol}")
                continue
            payload = history_to_symbol_json(symbol, name, history)
            filename = safe_filename(symbol)
            with open(os.path.join(DATA_DIR, filename), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            manifest_entries.append({
                "symbol": symbol, "name": name, "category": category, "sector": sector,
                "file": filename,
                "start_date": payload["dates"][0] if payload["dates"] else None,
                "end_date": payload["dates"][-1] if payload["dates"] else None,
            })

    manifest = build_manifest(manifest_entries)
    with open(os.path.join(DATA_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"完成:{len(manifest_entries)} 檔標的,manifest.json 已產生於 {DATA_DIR}")


if __name__ == "__main__":
    main()
