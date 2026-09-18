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
      data.push({ type: "scatter", mode: "lines", x: ohlc.dates, y: values, name: subIndicator.name === "MACD" ? key.toUpperCase() : subIndicator.name, xaxis: "x", yaxis: "y2" });
    }
  }

  return { data, layout };
}
