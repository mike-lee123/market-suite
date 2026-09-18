import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from fetch_data import history_to_symbol_json, build_manifest  # noqa: E402


class TestHistoryToSymbolJson(unittest.TestCase):
    def test_drops_rows_with_nan_close_and_formats_dates(self):
        idx = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04"])
        df = pd.DataFrame(
            {
                "Open": [100.0, 101.0, float("nan")],
                "High": [102.0, 103.0, float("nan")],
                "Low": [99.0, 100.0, float("nan")],
                "Close": [101.0, 102.0, float("nan")],
                "Volume": [1000, 2000, 0],
            },
            index=idx,
        )
        result = history_to_symbol_json("2330.TW", "台積電", df)
        self.assertEqual(result["symbol"], "2330.TW")
        self.assertEqual(result["name"], "台積電")
        self.assertEqual(result["dates"], ["2026-01-02", "2026-01-03"])
        self.assertEqual(result["close"], [101.0, 102.0])
        self.assertEqual(len(result["open"]), 2)
        self.assertEqual(len(result["volume"]), 2)

    def test_empty_history_produces_empty_arrays(self):
        df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        result = history_to_symbol_json("TEST", "測試", df)
        self.assertEqual(result["dates"], [])
        self.assertEqual(result["close"], [])

    def test_drops_rows_with_partial_nan_even_when_close_is_valid(self):
        idx = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04"])
        df = pd.DataFrame(
            {
                "Open": [100.0, float("nan"), 102.0],
                "High": [102.0, 103.0, 104.0],
                "Low": [99.0, 100.0, 101.0],
                "Close": [101.0, 102.0, 103.0],
                "Volume": [1000, 2000, float("nan")],
            },
            index=idx,
        )
        result = history_to_symbol_json("2330.TW", "台積電", df)
        # Row 0 (2026-01-02) is the only fully-clean row; rows 1 and 2 each have
        # one NaN field (Open, then Volume respectively) despite valid Close.
        self.assertEqual(result["dates"], ["2026-01-02"])
        self.assertEqual(result["close"], [101.0])


class TestBuildManifest(unittest.TestCase):
    def test_wraps_entries_with_a_generated_at_timestamp(self):
        entries = [
            {"symbol": "2330.TW", "name": "台積電", "category": "tw_stock", "sector": "半導體",
             "file": "2330.TW.json", "start_date": "2021-01-04", "end_date": "2026-09-18"},
        ]
        manifest = build_manifest(entries)
        self.assertIn("generated_at", manifest)
        self.assertEqual(manifest["symbols"], entries)


if __name__ == "__main__":
    unittest.main()
