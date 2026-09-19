import { sma, bollingerBands, rsi, kd, macd, bias, diagnoseTrend, diagnoseKD, diagnoseRSI, diagnoseMACD } from "./indicators.js";
import { buildCandlestickFigure, buildPayoffFigure, buildEquityCurveFigure } from "./charts.js";
import { blackScholes, calculateStrategyPayoff } from "./options.js";
import { runBacktest } from "./backtest.js";

const PERIOD_DAYS = { "1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504, "5y": 100000 };

async function loadManifest() {
  const res = await fetch("data/manifest.json");
  return res.json();
}

async function loadSymbolData(file) {
  const res = await fetch(`data/${file}`);
  return res.json();
}

function periodStartIndex(symbolData, periodKey) {
  const n = PERIOD_DAYS[periodKey] ?? symbolData.dates.length;
  return Math.max(0, symbolData.dates.length - n);
}

function sliceRaw(symbolData, start) {
  const pick = (arr) => arr.slice(start);
  return {
    dates: pick(symbolData.dates), open: pick(symbolData.open), high: pick(symbolData.high),
    low: pick(symbolData.low), close: pick(symbolData.close), volume: pick(symbolData.volume),
  };
}

function sliceSeries(series, start) {
  return Object.fromEntries(Object.entries(series).map(([key, values]) => [key, values.slice(start)]));
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

function renderDiagnosis(symbolData) {
  // Always diagnose "today's" signal from the FULL history, regardless of the
  // chart's currently-selected display period — indicators like MACD/KD/RSI
  // need the full lead-in window to converge, and the diagnosis should not
  // change just because the user zoomed the chart to a shorter window.
  const i = symbolData.close.length - 1;
  const ma5 = sma(symbolData.close, 5)[i];
  const ma20 = sma(symbolData.close, 20)[i];
  const ma60 = sma(symbolData.close, 60)[i];
  const { k, d } = kd(symbolData.high, symbolData.low, symbolData.close, 9);
  const rsiSeries = rsi(symbolData.close, 6);
  const { hist } = macd(symbolData.close);
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
    const start = periodStartIndex(symbolData, periodSelect.value);
    const ohlc = sliceRaw(symbolData, start);

    // Compute indicators on the FULL history first (so EMAs/KD/RSI have a
    // proper lead-in to converge), then slice the results down to the
    // selected display window. Computing them directly on the sliced window
    // can flip sign for short periods (e.g. MACD on a 22-bar 1-month window).
    const maPeriods = Array.from(document.querySelectorAll(".tech-ma:checked")).map((el) => Number(el.value));
    const maSeriesFull = maPeriods.map((period) => ({ period, values: sma(symbolData.close, period) }));
    const bbandsFull = bbandsCheckbox.checked ? bollingerBands(symbolData.close, 20, 2) : null;
    const subName = subIndicatorSelect.value;
    const subIndicatorFull = subName === "NONE" ? null : buildSubIndicator(subName, symbolData);

    const maSeries = maSeriesFull.map((m) => ({ period: m.period, values: m.values.slice(start) }));
    const bbands = bbandsFull ? sliceSeries(bbandsFull, start) : null;
    const subIndicator = subIndicatorFull
      ? { name: subIndicatorFull.name, series: sliceSeries(subIndicatorFull.series, start) }
      : null;

    const fig = buildCandlestickFigure(ohlc, {
      chartType: chartTypeSelect.value, maSeries, bbands, subIndicator,
      twStyle: colorSelect.value === "tw",
    });
    Plotly.newPlot("tech-chart", fig.data, fig.layout, { responsive: true });

    renderMetrics(ohlc);
    renderDiagnosis(symbolData);
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

function renderGreeksTable() {
  const spot = Number(document.getElementById("bs-spot").value);
  const strike = Number(document.getElementById("bs-strike").value);
  const dte = Number(document.getElementById("bs-dte").value);
  const iv = Number(document.getElementById("bs-iv").value) / 100;
  const r = Number(document.getElementById("bs-r").value) / 100;

  if (!(spot > 0) || !(strike > 0) || !(dte > 0) || !(iv > 0)) {
    document.getElementById("bs-table").innerHTML = "<tr><td>請輸入有效的正數參數(現價、履約價、到期天數、IV 皆須大於 0)</td></tr>";
    return;
  }

  const call = blackScholes(spot, strike, dte, r, iv, "call");
  const put = blackScholes(spot, strike, dte, r, iv, "put");

  const rows = [
    ["理論權利金", `${call.price.toFixed(2)} 點`, `${put.price.toFixed(2)} 點`],
    ["Delta", call.delta.toFixed(3), put.delta.toFixed(3)],
    ["Gamma", call.gamma.toFixed(5), put.gamma.toFixed(5)],
    ["Theta (每日)", call.thetaPerDay.toFixed(2), put.thetaPerDay.toFixed(2)],
    ["Vega (每1% IV)", call.vegaPer1Pct.toFixed(2), put.vegaPer1Pct.toFixed(2)],
  ];
  document.getElementById("bs-table").innerHTML =
    "<tr><th>指標</th><th>Call</th><th>Put</th></tr>" +
    rows.map(([label, c, p]) => `<tr><td>${label}</td><td>${c}</td><td>${p}</td></tr>`).join("");
}

const PAYOFF_PARAM_FIELDS = {
  long_call: [["k1", "履約價 K", 17000], ["prem1", "權利金", 50]],
  long_put: [["k1", "履約價 K", 17000], ["prem1", "權利金", 50]],
  bull_call_spread: [["k1", "買進履約價 K1", 17000], ["k2", "賣出履約價 K2", 17200], ["prem1", "買進權利金", 80], ["prem2", "賣出權利金", 30]],
  bear_put_spread: [["k1", "買進履約價 K1", 17200], ["k2", "賣出履約價 K2", 17000], ["prem1", "買進權利金", 80], ["prem2", "賣出權利金", 30]],
  bull_put_spread: [["k1", "賣出履約價 K1", 17000], ["k2", "買進履約價 K2", 16800], ["prem1", "賣出權利金", 60], ["prem2", "買進權利金", 20]],
  iron_condor: [["put_sell", "賣出Put", 16800], ["put_buy", "買進Put", 16600], ["call_sell", "賣出Call", 17200], ["call_buy", "買進Call", 17400],
                ["prem_put_s", "賣Put權利金", 40], ["prem_put_b", "買Put權利金", 15], ["prem_call_s", "賣Call權利金", 40], ["prem_call_b", "買Call權利金", 15]],
  long_straddle: [["k1", "履約價 K", 17000], ["prem1", "Call權利金", 45], ["prem2", "Put權利金", 45]],
};

function renderPayoffParamInputs(strategyKey) {
  const container = document.getElementById("payoff-params");
  container.innerHTML = "";
  for (const [field, label, defaultValue] of PAYOFF_PARAM_FIELDS[strategyKey]) {
    const wrapper = document.createElement("label");
    wrapper.textContent = label + " ";
    const input = document.createElement("input");
    input.type = "number";
    input.dataset.field = field;
    input.value = defaultValue;
    input.className = "payoff-param";
    wrapper.appendChild(input);
    container.appendChild(wrapper);
  }
}

function readPayoffParams() {
  const params = {};
  document.querySelectorAll(".payoff-param").forEach((input) => {
    params[input.dataset.field] = Number(input.value);
  });
  return params;
}

function redrawPayoff() {
  const strategySelect = document.getElementById("payoff-strategy");
  const strategyKey = strategySelect.value;
  const params = readPayoffParams();
  const rawSpot = params.k1 ?? params.put_sell;
  const spot = Number.isFinite(rawSpot) && rawSpot > 0 ? rawSpot : 17000;
  const result = calculateStrategyPayoff(strategyKey, spot, params);

  if (result.prices.length === 0) {
    document.getElementById("payoff-chart").innerHTML = "<p>參數不合理,請輸入正數的履約價與現價。</p>";
    return;
  }

  document.getElementById("payoff-summary").innerHTML = `
    <div class="metric-card">策略摘要<br>${result.summary}</div>
    <div class="metric-card">最大獲利<br><strong>${result.maxProfit === "無限" ? "無限" : result.maxProfit.toLocaleString()}</strong></div>
    <div class="metric-card">最大風險<br><strong>${result.maxLoss === "無限" ? "無限" : result.maxLoss.toLocaleString()}</strong></div>
    <div class="metric-card">損益兩平點<br>${result.breakevens.map((b) => b.toFixed(0)).join(", ") || "—"}</div>
  `;

  const strategyLabel = strategySelect.options[strategySelect.selectedIndex].text;
  const fig = buildPayoffFigure(result.prices, result.payoffs, spot, result.breakevens, strategyLabel);
  Plotly.newPlot("payoff-chart", fig.data, fig.layout, { responsive: true });
}

function initOptionsTab() {
  renderGreeksTable();
  ["bs-spot", "bs-strike", "bs-dte", "bs-iv", "bs-r"].forEach((id) =>
    document.getElementById(id).addEventListener("input", renderGreeksTable)
  );

  const strategySelect = document.getElementById("payoff-strategy");
  strategySelect.addEventListener("change", () => {
    renderPayoffParamInputs(strategySelect.value);
    redrawPayoff();
  });
  document.getElementById("payoff-params").addEventListener("input", redrawPayoff);

  renderPayoffParamInputs(strategySelect.value);
  redrawPayoff();
}

const BT_PARAM_FIELDS = {
  dual_ma: [["fast_period", "快線週期", 5], ["slow_period", "慢線週期", 20]],
  rsi: [["rsi_period", "RSI週期", 14], ["buy_threshold", "超賣買進閾值", 30], ["sell_threshold", "超買賣出閾值", 70]],
  macd: [],
  bollinger: [],
};

function renderBtParamInputs(strategyKey) {
  const container = document.getElementById("bt-params");
  container.innerHTML = "";
  for (const [field, label, defaultValue] of BT_PARAM_FIELDS[strategyKey]) {
    const wrapper = document.createElement("label");
    wrapper.textContent = label + " ";
    const input = document.createElement("input");
    input.type = "number";
    input.dataset.field = field;
    input.value = defaultValue;
    input.className = "bt-param";
    wrapper.appendChild(input);
    container.appendChild(wrapper);
  }
}

function readBtParams() {
  const params = {};
  document.querySelectorAll(".bt-param").forEach((input) => {
    params[input.dataset.field] = Number(input.value);
  });
  return params;
}

function renderBacktestResult(ohlc, result) {
  const m = result.metrics;
  document.getElementById("bt-metrics").innerHTML = `
    <div class="metric-card">策略總報酬率<br><strong>${m.total_return_pct.toFixed(2)}%</strong> (買入持有: ${m.buy_hold_return_pct.toFixed(2)}%)</div>
    <div class="metric-card">年化報酬率 CAGR<br><strong>${m.cagr_pct.toFixed(2)}%</strong></div>
    <div class="metric-card">最大回撤 MDD<br><strong>${m.max_drawdown_pct.toFixed(2)}%</strong></div>
    <div class="metric-card">夏普比率<br><strong>${m.sharpe_ratio.toFixed(2)}</strong></div>
    <div class="metric-card">勝率<br><strong>${m.win_rate_pct.toFixed(1)}%</strong> (${m.total_trades} 筆)</div>
    <div class="metric-card">獲利因子<br><strong>${Number.isFinite(m.profit_factor) ? m.profit_factor.toFixed(2) : "∞"}</strong></div>
  `;

  const fig = buildEquityCurveFigure(ohlc.dates, result.equityCurve, result.trades);
  Plotly.newPlot("bt-chart", fig.data, fig.layout, { responsive: true });

  const rows = result.trades.map((t) => `
    <tr>
      <td>${t.entry_date}</td><td>${t.entry_price.toFixed(2)}</td>
      <td>${t.exit_date}</td><td>${t.exit_price.toFixed(2)}</td>
      <td>${t.return_pct >= 0 ? "+" : ""}${t.return_pct.toFixed(2)}%</td>
      <td>${t.holding_days} 天</td><td>${t.is_win ? "🟢 獲利" : "🔴 虧損"}</td>
    </tr>`).join("");
  document.getElementById("bt-trades").innerHTML =
    "<tr><th>進場日期</th><th>進場價</th><th>出場日期</th><th>出場價</th><th>單筆報酬</th><th>持股天數</th><th>結果</th></tr>" +
    (rows || "<tr><td colspan=\"7\">在此期間內策略未觸發任何完整進出場交易</td></tr>");
}

async function runBacktestNow(manifest) {
  const entry = manifest.symbols.find((s) => s.symbol === document.getElementById("bt-symbol").value);
  const symbolData = await loadSymbolData(entry.file);
  const strategyKey = document.getElementById("bt-strategy").value;
  const params = readBtParams();
  const capital = Number(document.getElementById("bt-capital").value);
  const result = runBacktest(symbolData, strategyKey, params, capital);
  renderBacktestResult(symbolData, result);
}

function initBacktestTab(manifest) {
  const symbolSelect = document.getElementById("bt-symbol");
  manifest.symbols
    .filter((s) => s.category === "tw_stock")
    .forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.symbol;
      opt.textContent = `${s.name} (${s.symbol})`;
      symbolSelect.appendChild(opt);
    });
  symbolSelect.value = "2330.TW";

  const strategySelect = document.getElementById("bt-strategy");
  renderBtParamInputs(strategySelect.value);
  strategySelect.addEventListener("change", () => renderBtParamInputs(strategySelect.value));

  document.getElementById("bt-run").addEventListener("click", () => runBacktestNow(manifest));
}

async function bootstrap() {
  const manifest = await loadManifest();
  await renderTechnicalTab(manifest);
  initOptionsTab();
  initBacktestTab(manifest);
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
