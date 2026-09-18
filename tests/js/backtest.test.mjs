import { test } from "node:test";
import assert from "node:assert/strict";
import { simulateTrades, computeMetrics } from "../../docs/js/backtest.js";
import { runBacktest } from "../../docs/js/backtest.js";

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

function makeTrendReversalSeries() {
  // 30 bars rising then 30 bars falling — enough history for MA60-scale params to matter less;
  // we use short periods below so the crossovers are guaranteed to fire.
  const dates = [];
  const close = [];
  let price = 100;
  for (let i = 0; i < 30; i++) { price += 2; close.push(price); dates.push(`up${i}`); }
  for (let i = 0; i < 30; i++) { price -= 2; close.push(price); dates.push(`down${i}`); }
  const high = close.map((c) => c + 1);
  const low = close.map((c) => c - 1);
  return { dates, high, low, close };
}

test("dual_ma strategy goes long on a fast/slow golden cross and produces at least one trade", () => {
  const ohlc = makeTrendReversalSeries();
  const result = runBacktest(ohlc, "dual_ma", { fast_period: 3, slow_period: 8 }, 100000);
  assert.ok(result.trades.length >= 1);
  assert.equal(result.equityCurve.length, ohlc.close.length);
  assert.ok("sharpe_ratio" in result.metrics);
});

test("bollinger strategy runs end to end on the same series", () => {
  const ohlc = makeTrendReversalSeries();
  const result = runBacktest(ohlc, "bollinger", {}, 100000);
  assert.ok(Array.isArray(result.trades));
  assert.equal(result.equityCurve.length, ohlc.close.length);
});

test("macd strategy runs end to end on the same series", () => {
  const ohlc = makeTrendReversalSeries();
  const result = runBacktest(ohlc, "macd", {}, 100000);
  assert.equal(result.equityCurve.length, ohlc.close.length);
});

test("rsi strategy respects custom buy/sell thresholds without throwing", () => {
  const ohlc = makeTrendReversalSeries();
  const result = runBacktest(ohlc, "rsi", { rsi_period: 6, buy_threshold: 30, sell_threshold: 70 }, 100000);
  assert.equal(result.equityCurve.length, ohlc.close.length);
});

test("runBacktest rejects an unknown strategy key", () => {
  const ohlc = makeTrendReversalSeries();
  assert.throws(() => runBacktest(ohlc, "not_a_strategy", {}, 100000));
});
