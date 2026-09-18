import { test } from "node:test";
import assert from "node:assert/strict";
import { buildCandlestickFigure, buildPayoffFigure, buildEquityCurveFigure } from "../../docs/js/charts.js";

const ohlc = {
  dates: ["d0", "d1", "d2"],
  open: [10, 11, 12],
  high: [11, 12, 13],
  low: [9, 10, 11],
  close: [11, 12, 13],
};

test("candlestick figure uses Taiwan colors (red-up) by default", () => {
  const fig = buildCandlestickFigure(ohlc, { chartType: "candlestick", maSeries: [], bbands: null, subIndicator: null, twStyle: true });
  const candle = fig.data.find((t) => t.type === "candlestick");
  assert.ok(candle);
  assert.equal(candle.increasing.line.color, "#ff4757");
  assert.equal(candle.decreasing.line.color, "#2ed573");
});

test("international color style swaps up/down colors", () => {
  const fig = buildCandlestickFigure(ohlc, { chartType: "candlestick", maSeries: [], bbands: null, subIndicator: null, twStyle: false });
  const candle = fig.data.find((t) => t.type === "candlestick");
  assert.equal(candle.increasing.line.color, "#2ed573");
  assert.equal(candle.decreasing.line.color, "#ff4757");
});

test("line chart type produces a scatter trace instead of a candlestick", () => {
  const fig = buildCandlestickFigure(ohlc, { chartType: "line", maSeries: [], bbands: null, subIndicator: null, twStyle: true });
  assert.equal(fig.data.some((t) => t.type === "candlestick"), false);
  assert.ok(fig.data.some((t) => t.type === "scatter"));
});

test("moving averages and sub-indicator each add their own trace", () => {
  const fig = buildCandlestickFigure(ohlc, {
    chartType: "candlestick",
    maSeries: [{ period: 5, values: [10, 11, 12] }],
    bbands: null,
    subIndicator: { name: "RSI", series: { rsi: [40, 50, 60] } },
    twStyle: true,
  });
  assert.ok(fig.data.some((t) => t.name === "MA5"));
  assert.ok(fig.data.some((t) => t.name === "RSI"));
  assert.ok(fig.layout.grid || fig.layout.yaxis2); // sub-indicator needs its own axis/row
});

test("payoff figure marks the spot price with a vertical line", () => {
  const fig = buildPayoffFigure([90, 100, 110], [-500, 0, 500], 100, [100], "Long Call");
  assert.ok(fig.layout.shapes.some((s) => s.x0 === 100));
  assert.ok(fig.data.some((t) => t.name === "損益"));
});

test("equity curve figure plots the curve and marks trade entry/exit points", () => {
  const trades = [{ entry_date: "d1", exit_date: "d3" }];
  const fig = buildEquityCurveFigure(["d0", "d1", "d2", "d3"], [100000, 101000, 99000, 103000], trades);
  const curve = fig.data.find((t) => t.name === "權益曲線");
  assert.ok(curve);
  assert.equal(curve.y.length, 4);
  assert.ok(fig.data.some((t) => t.name === "進場"));
  assert.ok(fig.data.some((t) => t.name === "出場"));
});
