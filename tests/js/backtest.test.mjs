import { test } from "node:test";
import assert from "node:assert/strict";
import { simulateTrades, computeMetrics } from "../../docs/js/backtest.js";

const dates = ["d0", "d1", "d2", "d3", "d4"];
const closes = [100, 110, 121, 110, 121];

test("simulateTrades opens on the bar signal turns 1 and closes when it turns 0", () => {
  const signals = [0, 1, 1, 0, 0];
  const { trades, equityCurve } = simulateTrades(closes, dates, signals, 100000);
  assert.equal(trades.length, 1);
  assert.equal(trades[0].entry_price, 110);
  assert.equal(trades[0].exit_price, 110);
  assert.equal(trades[0].is_win, false); // flat entry/exit price -> no gain, not a win
  assert.equal(equityCurve.length, closes.length);
});

test("simulateTrades keeps a trade open through the end of the series if never closed", () => {
  const signals = [0, 1, 1, 1, 1];
  const { trades } = simulateTrades(closes, dates, signals, 100000);
  assert.equal(trades.length, 1);
  assert.equal(trades[0].exit_date, "d4");
  assert.equal(trades[0].is_win, true); // 110 -> 121
});

test("computeMetrics reports buy-and-hold return alongside the strategy return", () => {
  const signals = [0, 1, 1, 1, 1];
  const { equityCurve, trades } = simulateTrades(closes, dates, signals, 100000);
  const metrics = computeMetrics(closes, equityCurve, trades, 100000);
  const expectedBuyHold = ((closes[4] - closes[0]) / closes[0]) * 100;
  assert.ok(Math.abs(metrics.buy_hold_return_pct - expectedBuyHold) < 1e-6);
  assert.equal(metrics.total_trades, 1);
  assert.equal(metrics.win_rate_pct, 100);
});

test("computeMetrics max_drawdown_pct is non-negative and zero for a monotonically rising equity curve", () => {
  const metrics = computeMetrics(closes, [100000, 101000, 102000, 103000, 104000], [], 100000);
  assert.equal(metrics.max_drawdown_pct, 0);
});
