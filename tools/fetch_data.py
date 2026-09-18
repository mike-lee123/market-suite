"""Generate docs/data/*.json from Yahoo Finance history for the market-suite
static frontend. Run manually: `python tools/fetch_data.py`."""

from datetime import datetime, timezone


def history_to_symbol_json(symbol: str, name: str, history) -> dict:
    df = history.dropna(subset=["Close"])
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
