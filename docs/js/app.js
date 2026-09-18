import { sma, bollingerBands, rsi, kd, macd, bias, diagnoseTrend, diagnoseKD, diagnoseRSI, diagnoseMACD } from "./indicators.js";
import { buildCandlestickFigure } from "./charts.js";

const PERIOD_DAYS = { "1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504, "5y": 100000 };

async function loadManifest() {
  const res = await fetch("data/manifest.json");
  return res.json();
}

async function loadSymbolData(file) {
  const res = await fetch(`data/${file}`);
  return res.json();
}

function sliceByPeriod(symbolData, periodKey) {
  const n = PERIOD_DAYS[periodKey] ?? symbolData.dates.length;
  const start = Math.max(0, symbolData.dates.length - n);
  const pick = (arr) => arr.slice(start);
  return {
    dates: pick(symbolData.dates), open: pick(symbolData.open), high: pick(symbolData.high),
    low: pick(symbolData.low), close: pick(symbolData.close), volume: pick(symbolData.volume),
  };
}

function buildSubIndicator(name, ohlc) {
  if (name === "KD") { const { k, d } = kd(ohlc.high, ohlc.low, ohlc.close, 9); return { name: "KD", series: { K: k, D: d } }; }
  if (name === "RSI") return { name: "RSI", series: { RSI: rsi(ohlc.close, 6) } };
  if (name === "MACD") { const { dif, dea, hist } = macd(ohlc.close); return { name: "MACD", series: { DIF: dif, DEA: dea, HIST: hist } }; }
  if (name === "BIAS") return { name: "BIAS", series: { BIAS: bias(ohlc.close, 20) } };
  return null;
}

function renderMetrics(ohlc) {
  const i = ohlc.close.length - 1;
  const prev = Math.max(0, i - 1);
  const change = ohlc.close[i] - ohlc.close[prev];
  const pct = prev !== i ? (change / ohlc.close[prev]) * 100 : 0;
  const el = document.getElementById("tech-metrics");
  el.innerHTML = `
    <div class="metric-card">最新收盤價<br><strong>${ohlc.close[i].toFixed(2)}</strong> (${change >= 0 ? "+" : ""}${change.toFixed(2)}, ${pct.toFixed(2)}%)</div>
    <div class="metric-card">開盤價<br><strong>${ohlc.open[i].toFixed(2)}</strong></div>
    <div class="metric-card">最高價<br><strong>${ohlc.high[i].toFixed(2)}</strong></div>
    <div class="metric-card">最低價<br><strong>${ohlc.low[i].toFixed(2)}</strong></div>
    <div class="metric-card">成交量<br><strong>${ohlc.volume[i].toLocaleString()}</strong></div>
  `;
}

function renderDiagnosis(ohlc) {
  const i = ohlc.close.length - 1;
  const ma5 = sma(ohlc.close, 5)[i];
  const ma20 = sma(ohlc.close, 20)[i];
  const ma60 = sma(ohlc.close, 60)[i];
  const { k, d } = kd(ohlc.high, ohlc.low, ohlc.close, 9);
  const rsiSeries = rsi(ohlc.close, 6);
  const { hist } = macd(ohlc.close);
  const el = document.getElementById("tech-diagnosis");
  el.innerHTML = `
    <div class="metric-card">均線趨勢<br>${ma5 && ma20 && ma60 ? diagnoseTrend(ma5, ma20, ma60) : "資料不足"}</div>
    <div class="metric-card">KD(9,3)<br>K: ${k[i].toFixed(1)} / D: ${d[i].toFixed(1)}<br>${diagnoseKD(k[i], d[i], k[i - 1] ?? k[i], d[i - 1] ?? d[i])}</div>
    <div class="metric-card">RSI(6)<br>${rsiSeries[i].toFixed(1)}<br>${diagnoseRSI(rsiSeries[i])}</div>
    <div class="metric-card">MACD<br>${hist[i].toFixed(2)}<br>${diagnoseMACD(hist[i])}</div>
  `;
}

async function renderTechnicalTab(manifest) {
  const symbolSelect = document.getElementById("tech-symbol");
  const periodSelect = document.getElementById("tech-period");
  const chartTypeSelect = document.getElementById("tech-chart-type");
  const colorSelect = document.getElementById("tech-color-style");
  const bbandsCheckbox = document.getElementById("tech-bbands");
  const subIndicatorSelect = document.getElementById("tech-sub-indicator");

  async function redraw() {
    const entry = manifest.symbols.find((s) => s.symbol === symbolSelect.value);
    const symbolData = await loadSymbolData(entry.file);
    const ohlc = sliceByPeriod(symbolData, periodSelect.value);

    const maPeriods = Array.from(document.querySelectorAll(".tech-ma:checked")).map((el) => Number(el.value));
    const maSeries = maPeriods.map((period) => ({ period, values: sma(ohlc.close, period) }));
    const bbands = bbandsCheckbox.checked ? bollingerBands(ohlc.close, 20, 2) : null;
    const subName = subIndicatorSelect.value;
    const subIndicator = subName === "NONE" ? null : buildSubIndicator(subName, ohlc);

    const fig = buildCandlestickFigure(ohlc, {
      chartType: chartTypeSelect.value, maSeries, bbands, subIndicator,
      twStyle: colorSelect.value === "tw",
    });
    Plotly.newPlot("tech-chart", fig.data, fig.layout, { responsive: true });

    renderMetrics(ohlc);
    renderDiagnosis(ohlc);
  }

  manifest.symbols.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.symbol;
    opt.textContent = `${s.name} (${s.symbol})`;
    symbolSelect.appendChild(opt);
  });
  symbolSelect.value = "2330.TW";

  [symbolSelect, periodSelect, chartTypeSelect, colorSelect, bbandsCheckbox, subIndicatorSelect].forEach((el) =>
    el.addEventListener("change", redraw)
  );
  document.querySelectorAll(".tech-ma").forEach((el) => el.addEventListener("change", redraw));

  await redraw();
}

async function bootstrap() {
  const manifest = await loadManifest();
  await renderTechnicalTab(manifest);
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

bootstrap();
