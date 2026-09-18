const COLORS = {
  tw: { up: "#ff4757", down: "#2ed573" },
  intl: { up: "#2ed573", down: "#ff4757" },
};

export function buildCandlestickFigure(ohlc, { chartType, maSeries, bbands, subIndicator, twStyle }) {
  const palette = twStyle ? COLORS.tw : COLORS.intl;
  const data = [];

  if (chartType === "line") {
    data.push({
      type: "scatter", mode: "lines", x: ohlc.dates, y: ohlc.close,
      name: "收盤價", line: { color: "#2f3542", width: 2 }, xaxis: "x", yaxis: "y",
    });
  } else {
    data.push({
      type: "candlestick", x: ohlc.dates, open: ohlc.open, high: ohlc.high, low: ohlc.low, close: ohlc.close,
      name: "K線", increasing: { line: { color: palette.up } }, decreasing: { line: { color: palette.down } },
      xaxis: "x", yaxis: "y",
    });
  }

  for (const ma of maSeries) {
    data.push({ type: "scatter", mode: "lines", x: ohlc.dates, y: ma.values, name: `MA${ma.period}`, line: { width: 1.2 }, xaxis: "x", yaxis: "y" });
  }

  if (bbands) {
    data.push({ type: "scatter", mode: "lines", x: ohlc.dates, y: bbands.upper, name: "布林上軌", line: { color: "#a4b0be", dash: "dot" }, xaxis: "x", yaxis: "y" });
    data.push({ type: "scatter", mode: "lines", x: ohlc.dates, y: bbands.lower, name: "布林下軌", line: { color: "#a4b0be", dash: "dot" }, xaxis: "x", yaxis: "y" });
  }

  const layout = {
    height: subIndicator ? 640 : 480,
    xaxis: { rangeslider: { visible: false }, domain: [0, 1], anchor: subIndicator ? "y2" : undefined },
    yaxis: { domain: subIndicator ? [0.32, 1] : [0, 1], title: "價格" },
    margin: { l: 40, r: 20, t: 30, b: 30 },
    legend: { orientation: "h" },
  };

  if (subIndicator) {
    layout.yaxis2 = { domain: [0, 0.25], title: subIndicator.name };
    for (const [key, values] of Object.entries(subIndicator.series)) {
      data.push({ type: "scatter", mode: "lines", x: ohlc.dates, y: values, name: key.toUpperCase(), xaxis: "x", yaxis: "y2" });
    }
  }

  return { data, layout };
}

export function buildPayoffFigure(prices, payoffs, spot, breakevens, strategyName) {
  const data = [
    { type: "scatter", mode: "lines", x: prices, y: payoffs, name: "損益", line: { color: "#3867d6", width: 2 }, fill: "tozeroy" },
  ];
  const shapes = [
    { type: "line", x0: spot, x1: spot, y0: Math.min(...payoffs), y1: Math.max(...payoffs), line: { color: "#2c3e50", dash: "dash" } },
    { type: "line", x0: Math.min(...prices), x1: Math.max(...prices), y0: 0, y1: 0, line: { color: "#747d8c", width: 1 } },
  ];
  for (const be of breakevens) {
    shapes.push({ type: "line", x0: be, x1: be, y0: Math.min(...payoffs), y1: Math.max(...payoffs), line: { color: "#eb3b5a", dash: "dot" } });
  }
  const layout = {
    title: `${strategyName} 到期損益圖`,
    height: 420,
    xaxis: { title: "標的價格" },
    yaxis: { title: "損益 (NTD)" },
    shapes,
    margin: { l: 50, r: 20, t: 50, b: 40 },
  };
  return { data, layout };
}

export function buildEquityCurveFigure(dates, equityCurve, trades) {
  const dateIndex = new Map(dates.map((d, i) => [d, i]));
  const entryX = trades.map((t) => t.entry_date);
  const entryY = trades.map((t) => equityCurve[dateIndex.get(t.entry_date)]);
  const exitX = trades.map((t) => t.exit_date);
  const exitY = trades.map((t) => equityCurve[dateIndex.get(t.exit_date)]);

  const data = [
    { type: "scatter", mode: "lines", x: dates, y: equityCurve, name: "權益曲線", line: { color: "#3867d6", width: 2 } },
    { type: "scatter", mode: "markers", x: entryX, y: entryY, name: "進場", marker: { color: "#2ed573", size: 9, symbol: "triangle-up" } },
    { type: "scatter", mode: "markers", x: exitX, y: exitY, name: "出場", marker: { color: "#ff4757", size: 9, symbol: "triangle-down" } },
  ];
  const layout = {
    height: 420,
    xaxis: { title: "日期" },
    yaxis: { title: "帳戶權益 (NTD)" },
    margin: { l: 60, r: 20, t: 30, b: 40 },
    legend: { orientation: "h" },
  };
  return { data, layout };
}
