# market-suite 靜態網站版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the technical-analysis, options-calculator, and backtest features of the market-suite Streamlit dashboards as a static HTML/CSS/JS site under `docs/`, deployable to GitHub Pages, with historical price data pre-generated as JSON by a Python script.

**Architecture:** Pure client-side app — no build tool, no npm, no framework. Pricing/indicator/backtest math lives in plain ES modules (`docs/js/*.js`) that are pure functions (no DOM access), so they can be unit-tested with Node's built-in test runner (`node --test`) exactly as written for the browser. `app.js` is the only module that touches the DOM and Plotly; it is verified by hand in a browser rather than by automated test. Historical OHLCV data is generated once by `tools/fetch_data.py` (yfinance) into `docs/data/*.json` + `docs/data/manifest.json`, which the page fetches at runtime.

**Tech Stack:** HTML5, vanilla JS (ES modules), Plotly.js (CDN), Python 3 + yfinance (data generation only, not shipped to the browser), Node.js built-in test runner (`node:test`, `node:assert/strict`), Python `unittest` (stdlib).

**Spec:** `specs/2026-09-19-market-suite-web-design.md`

## Global Constraints

- No frontend build tooling: no npm install, no webpack/vite, no React/Vue. `docs/` must be servable as-is by any static file server.
- UI language: Traditional Chinese, matching the original Streamlit wording where equivalent features exist.
- Colors: 紅漲綠跌 (Taiwan convention) as default, with a toggle to 綠漲紅跌 (international convention) — matches original `tw_color_style` toggle.
- Excluded features (do not build): Shioaji live quotes, 6-person AI research team / PDF generation, market-wide stock screener, live yfinance fundamentals. These require a server or credentials.
- `dashboard_modular/`, `dashboard_v1878/`, `research/`, `.claude/` are not to be modified.
- Data update is manual: running `python tools/fetch_data.py` regenerates `docs/data/`; there is no CI/scheduled job in this plan.
- A root `package.json` with `{"type": "module"}` is permitted (needed so Node can `import` the same `.js` files the browser loads as ES modules) — it carries no dependencies and is never `npm install`ed by the site itself.

---

## Shared Data Contracts (all tasks below implement to these exact shapes)

**`docs/data/manifest.json`**
```json
{
  "generated_at": "2026-09-19T00:00:00Z",
  "symbols": [
    {
      "symbol": "2330.TW",
      "name": "台積電",
      "category": "tw_stock",
      "sector": "半導體",
      "file": "2330.TW.json",
      "start_date": "2021-01-04",
      "end_date": "2026-09-18"
    }
  ]
}
```
`category` is one of `"tw_stock"` or `"macro"`.

**`docs/data/{file}`** (e.g. `docs/data/2330.TW.json`)
```json
{
  "symbol": "2330.TW",
  "name": "台積電",
  "dates": ["2021-01-04", "2021-01-05"],
  "open": [530.0, 531.0],
  "high": [532.0, 533.0],
  "low": [528.0, 529.0],
  "close": [531.0, 532.5],
  "volume": [25000000, 18000000]
}
```
Arrays are all the same length and index-aligned to `dates`. No `null`/`NaN` rows (dropped at generation time).

---

## Task 1: Static site skeleton + local server smoke test

**Files:**
- Create: `docs/index.html`
- Create: `docs/css/style.css`
- Create: `docs/js/app.js` (empty stub, just a `console.log` for now)
- Create: `package.json` (repo root)
- Test: `tests/smoke.test.mjs`

**Interfaces:**
- Produces: three tab containers in `index.html` with ids `#tab-technical`, `#tab-options`, `#tab-backtest`, and a nav with `data-tab` buttons — later tasks fill these in, this task just establishes the ids that `app.js` will query.

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "market-suite-web",
  "private": true,
  "type": "module",
  "description": "Static frontend + data tooling for market-suite (not shipped, dev/test only)"
}
```

- [ ] **Step 2: Write `docs/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>台股與選擇權分析工具(純前端版)</title>
  <link rel="stylesheet" href="css/style.css">
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
</head>
<body>
  <header class="app-header">
    <h1>📊 台股技術分析 / 選擇權 / 回測工具</h1>
    <p class="subtitle">純前端靜態版 · 資料為建置時快照,非即時行情</p>
  </header>

  <nav class="tab-nav">
    <button class="tab-btn active" data-tab="tab-technical">📈 技術分析</button>
    <button class="tab-btn" data-tab="tab-options">🎯 選擇權策略中心</button>
    <button class="tab-btn" data-tab="tab-backtest">🧪 回測實驗室</button>
  </nav>

  <main>
    <section id="tab-technical" class="tab-panel active"></section>
    <section id="tab-options" class="tab-panel"></section>
    <section id="tab-backtest" class="tab-panel"></section>
  </main>

  <footer class="app-footer">
    <p>資料來源:Yahoo Finance(yfinance)· 僅供量化分析與學術研究參考,不構成投資建議。</p>
  </footer>

  <script type="module" src="js/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `docs/css/style.css`**

```css
:root {
  --color-up: #ff4757;
  --color-down: #2ed573;
  --color-accent: #3867d6;
  --color-bg: #f8f9fa;
  --color-text: #2c3e50;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: "Noto Sans TC", "Segoe UI", sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
}

.app-header { padding: 16px 24px; border-bottom: 2px solid #e2e8f0; }
.app-header h1 { margin: 0 0 4px; font-size: 1.4rem; }
.subtitle { margin: 0; color: #747d8c; font-size: 0.85rem; }

.tab-nav { display: flex; gap: 8px; padding: 12px 24px 0; }
.tab-btn {
  padding: 10px 16px;
  border: none;
  border-radius: 6px 6px 0 0;
  background: #f1f2f6;
  font-weight: 600;
  cursor: pointer;
}
.tab-btn.active { background: var(--color-accent); color: white; }

main { padding: 24px; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }

.metric-card {
  background: white;
  border-left: 4px solid var(--color-accent);
  border-radius: 8px;
  padding: 10px 14px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.app-footer { padding: 16px 24px; color: #888; font-size: 0.8rem; text-align: center; }
```

- [ ] **Step 4: Write stub `docs/js/app.js`**

```javascript
console.log("market-suite-web app.js loaded");

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});
```

- [ ] **Step 5: Write the smoke test**

```javascript
// tests/smoke.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("index.html declares the three required tab panels", () => {
  const html = readFileSync(new URL("../docs/index.html", import.meta.url), "utf8");
  assert.match(html, /id="tab-technical"/);
  assert.match(html, /id="tab-options"/);
  assert.match(html, /id="tab-backtest"/);
  assert.match(html, /js\/app\.js/);
});
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `node --test tests/smoke.test.mjs`
Expected: 1 pass.

- [ ] **Step 7: Manual browser check**

Run: `python -m http.server 8000 --directory docs` then open `http://localhost:8000/` in a browser. Confirm the three tab buttons switch panels (all empty for now) and the header/footer render. Stop the server (Ctrl+C) when done.

- [ ] **Step 8: Commit**

```bash
git add package.json docs/index.html docs/css/style.css docs/js/app.js tests/smoke.test.mjs
git commit -m "Add static site skeleton with tab navigation"
```

---

## Task 2: `indicators.js` — moving averages & Bollinger Bands

**Files:**
- Create: `docs/js/indicators.js`
- Test: `tests/js/indicators.test.mjs`

**Interfaces:**
- Produces:
  - `sma(values: number[], period: number): (number|null)[]`
  - `ema(values: number[], period: number): number[]`
  - `bollingerBands(values: number[], period=20, numStd=2): {upper:(number|null)[], middle:(number|null)[], lower:(number|null)[]}`

- [ ] **Step 1: Write failing tests**

```javascript
// tests/js/indicators.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { sma, ema, bollingerBands } from "../../docs/js/indicators.js";

test("sma returns null before period is reached, then the rolling mean", () => {
  const result = sma([1, 2, 3, 4, 5], 3);
  assert.equal(result[0], null);
  assert.equal(result[1], null);
  assert.equal(result[2], 2);   // mean(1,2,3)
  assert.equal(result[3], 3);   // mean(2,3,4)
  assert.equal(result[4], 4);   // mean(3,4,5)
});

test("ema seeds with the first value and decays by the standard alpha", () => {
  const result = ema([10, 12, 14], 3); // alpha = 2/(3+1) = 0.5
  assert.equal(result[0], 10);
  assert.equal(result[1], 11);          // 0.5*12 + 0.5*10
  assert.equal(result[2], 12.5);        // 0.5*14 + 0.5*11
});

test("bollingerBands middle band matches sma and bands widen with volatility", () => {
  const values = [10, 10, 10, 10, 20, 10, 10, 10, 10, 10,
                   10, 10, 10, 10, 10, 10, 10, 10, 10, 10];
  const { upper, middle, lower } = bollingerBands(values, 20, 2);
  assert.equal(middle[19], sma(values, 20)[19]);
  assert.ok(upper[19] > middle[19]);
  assert.ok(lower[19] < middle[19]);
  assert.equal(upper[18], null); // fewer than `period` points yet
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/indicators.test.mjs`
Expected: FAIL — `Cannot find module '../../docs/js/indicators.js'`.

- [ ] **Step 3: Implement `docs/js/indicators.js`**

```javascript
export function sma(values, period) {
  const out = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

export function ema(values, period) {
  const alpha = 2 / (period + 1);
  const out = new Array(values.length);
  out[0] = values[0];
  for (let i = 1; i < values.length; i++) {
    out[i] = alpha * values[i] + (1 - alpha) * out[i - 1];
  }
  return out;
}

export function bollingerBands(values, period = 20, numStd = 2) {
  const middle = sma(values, period);
  const upper = new Array(values.length).fill(null);
  const lower = new Array(values.length).fill(null);
  for (let i = period - 1; i < values.length; i++) {
    const window = values.slice(i - period + 1, i + 1);
    const mean = middle[i];
    const variance = window.reduce((acc, v) => acc + (v - mean) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    upper[i] = mean + numStd * std;
    lower[i] = mean - numStd * std;
  }
  return { upper, middle, lower };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/indicators.test.mjs`
Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add docs/js/indicators.js tests/js/indicators.test.mjs
git commit -m "Add SMA/EMA/Bollinger Band indicators"
```

---

## Task 3: `indicators.js` — RSI, KD, MACD, BIAS + text diagnostics

**Files:**
- Modify: `docs/js/indicators.js`
- Test: `tests/js/indicators.test.mjs` (append)

**Interfaces:**
- Consumes: nothing new from Task 2 (independent functions in the same file).
- Produces:
  - `rsi(closes: number[], period=6): (number|null)[]`
  - `kd(highs: number[], lows: number[], closes: number[], period=9): {k:number[], d:number[]}`
  - `macd(closes: number[], fast=12, slow=26, signalPeriod=9): {dif:number[], dea:number[], hist:number[]}`
  - `bias(closes: number[], period=20): (number|null)[]`
  - `diagnoseTrend(ma5:number, ma20:number, ma60:number): string`
  - `diagnoseKD(k:number, d:number, prevK:number, prevD:number): string`
  - `diagnoseRSI(rsiValue:number): string`
  - `diagnoseMACD(hist:number): string`

- [ ] **Step 1: Write failing tests**

```javascript
// append to tests/js/indicators.test.mjs
import { rsi, kd, macd, bias, diagnoseTrend, diagnoseKD, diagnoseRSI, diagnoseMACD } from "../../docs/js/indicators.js";

test("rsi is 100 when there are no losses in the window", () => {
  const result = rsi([10, 11, 12, 13, 14, 15, 16], 6);
  assert.equal(result[6], 100);
});

test("rsi is 0 when there are no gains in the window", () => {
  const result = rsi([16, 15, 14, 13, 12, 11, 10], 6);
  assert.equal(result[6], 0);
});

test("kd starts smoothing from 50 and moves toward the RSV", () => {
  const highs = [10, 10, 10, 10, 10, 10, 10, 10, 10, 20];
  const lows  = [ 5,  5,  5,  5,  5,  5,  5,  5,  5,  5];
  const closes= [ 8,  8,  8,  8,  8,  8,  8,  8,  8, 20]; // RSV jumps to 100 on the last bar
  const { k, d } = kd(highs, lows, closes, 9);
  assert.equal(k.length, 10);
  assert.equal(d.length, 10);
  assert.ok(k[9] > k[8]); // K should rise toward the new high RSV
  assert.ok(k[9] < 100);  // but smoothing keeps it below the raw RSV
});

test("macd hist is twice the gap between DIF and DEA", () => {
  const closes = Array.from({ length: 40 }, (_, i) => 100 + i);
  const { dif, dea, hist } = macd(closes, 12, 26, 9);
  const lastIdx = closes.length - 1;
  assert.ok(Math.abs(hist[lastIdx] - 2 * (dif[lastIdx] - dea[lastIdx])) < 1e-9);
});

test("bias is zero when price equals its moving average", () => {
  const flat = new Array(25).fill(100);
  const result = bias(flat, 20);
  assert.equal(result[24], 0);
});

test("diagnoseTrend recognizes bullish and bearish alignment", () => {
  assert.equal(diagnoseTrend(30, 20, 10), "多頭排列 (MA5 > MA20 > MA60)");
  assert.equal(diagnoseTrend(10, 20, 30), "空頭排列 (MA5 < MA20 < MA60)");
  assert.equal(diagnoseTrend(20, 20, 20), "均線糾結/震盪整理");
});

test("diagnoseKD flags golden and death crosses before falling back to zone labels", () => {
  assert.equal(diagnoseKD(55, 50, 48, 50), "黃金交叉 (K向上突破D)");
  assert.equal(diagnoseKD(45, 50, 52, 50), "死亡交叉 (K向下跌破D)");
  assert.equal(diagnoseKD(85, 60, 84, 60), "超買區 (>80)");
  assert.equal(diagnoseKD(15, 40, 16, 40), "超賣區 (<20)");
});

test("diagnoseRSI and diagnoseMACD label zones", () => {
  assert.equal(diagnoseRSI(80), "超買警戒區 (>75)");
  assert.equal(diagnoseRSI(10), "超賣反彈區 (<25)");
  assert.equal(diagnoseRSI(50), "正常波動區");
  assert.equal(diagnoseMACD(1.5), "柱狀圖轉正 (紅柱擴大)");
  assert.equal(diagnoseMACD(-1.5), "柱狀圖為負 (綠柱擴大)");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/indicators.test.mjs`
Expected: FAIL — `rsi is not a function` etc.

- [ ] **Step 3: Implement the functions (append to `docs/js/indicators.js`)**

```javascript
export function rsi(closes, period = 6) {
  const out = new Array(closes.length).fill(null);
  const gains = new Array(closes.length).fill(0);
  const losses = new Array(closes.length).fill(0);
  for (let i = 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    gains[i] = delta > 0 ? delta : 0;
    losses[i] = delta < 0 ? -delta : 0;
  }
  for (let i = 0; i < closes.length; i++) {
    const start = Math.max(0, i - period + 1);
    const windowGains = gains.slice(start, i + 1);
    const windowLosses = losses.slice(start, i + 1);
    const avgGain = windowGains.reduce((a, b) => a + b, 0) / windowGains.length;
    const avgLoss = windowLosses.reduce((a, b) => a + b, 0) / windowLosses.length;
    const rs = avgGain / (avgLoss + 1e-8);
    out[i] = 100 - 100 / (1 + rs);
  }
  return out;
}

export function kd(highs, lows, closes, period = 9) {
  const k = new Array(closes.length);
  const d = new Array(closes.length);
  let lastK = 50;
  let lastD = 50;
  for (let i = 0; i < closes.length; i++) {
    const start = Math.max(0, i - period + 1);
    const highMax = Math.max(...highs.slice(start, i + 1));
    const lowMin = Math.min(...lows.slice(start, i + 1));
    const denom = highMax - lowMin;
    const rsv = denom === 0 ? 50 : ((closes[i] - lowMin) / denom) * 100;
    const currentK = (2 / 3) * lastK + (1 / 3) * rsv;
    const currentD = (2 / 3) * lastD + (1 / 3) * currentK;
    k[i] = currentK;
    d[i] = currentD;
    lastK = currentK;
    lastD = currentD;
  }
  return { k, d };
}

export function macd(closes, fast = 12, slow = 26, signalPeriod = 9) {
  const emaFast = ema(closes, fast);
  const emaSlow = ema(closes, slow);
  const dif = closes.map((_, i) => emaFast[i] - emaSlow[i]);
  const dea = ema(dif, signalPeriod);
  const hist = dif.map((v, i) => (v - dea[i]) * 2);
  return { dif, dea, hist };
}

export function bias(closes, period = 20) {
  const ma = sma(closes, period);
  return closes.map((c, i) => (ma[i] === null ? null : ((c - ma[i]) / ma[i]) * 100));
}

export function diagnoseTrend(ma5, ma20, ma60) {
  if (ma5 > ma20 && ma20 > ma60) return "多頭排列 (MA5 > MA20 > MA60)";
  if (ma5 < ma20 && ma20 < ma60) return "空頭排列 (MA5 < MA20 < MA60)";
  return "均線糾結/震盪整理";
}

export function diagnoseKD(k, d, prevK, prevD) {
  if (k > d && prevK <= prevD) return "黃金交叉 (K向上突破D)";
  if (k < d && prevK >= prevD) return "死亡交叉 (K向下跌破D)";
  if (k > 80) return "超買區 (>80)";
  if (k < 20) return "超賣區 (<20)";
  return "中性區域";
}

export function diagnoseRSI(rsiValue) {
  if (rsiValue > 75) return "超買警戒區 (>75)";
  if (rsiValue < 25) return "超賣反彈區 (<25)";
  return "正常波動區";
}

export function diagnoseMACD(hist) {
  return hist > 0 ? "柱狀圖轉正 (紅柱擴大)" : "柱狀圖為負 (綠柱擴大)";
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/indicators.test.mjs`
Expected: all pass (10 tests total from Tasks 2+3).

- [ ] **Step 5: Commit**

```bash
git add docs/js/indicators.js tests/js/indicators.test.mjs
git commit -m "Add RSI/KD/MACD/BIAS indicators and text diagnostics"
```

---

## Task 4: `options.js` — Black-Scholes pricing & Greeks

**Files:**
- Create: `docs/js/options.js`
- Test: `tests/js/options.test.mjs`

**Interfaces:**
- Produces:
  - `normCdf(x: number): number`
  - `blackScholes(spot, strike, dteDays, riskFreeRate, iv, optionType: "call"|"put"): {price:number, delta:number, gamma:number, thetaPerDay:number, vegaPer1Pct:number}`

- [ ] **Step 1: Write failing tests (reference values from Hull, *Options, Futures and Other Derivatives*, the standard S=42,K=40,r=10%,σ=20%,T=0.5yr example)**

```javascript
// tests/js/options.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { normCdf, blackScholes } from "../../docs/js/options.js";

test("normCdf matches known standard-normal values", () => {
  assert.ok(Math.abs(normCdf(0) - 0.5) < 1e-6);
  assert.ok(Math.abs(normCdf(1.96) - 0.975) < 1e-3);
});

test("blackScholes call price matches the textbook Hull example (~4.76)", () => {
  const result = blackScholes(42, 40, 182.5, 0.10, 0.20, "call");
  assert.ok(Math.abs(result.price - 4.76) < 0.05);
  assert.ok(result.delta > 0.6 && result.delta < 0.8);
});

test("blackScholes put price matches the textbook Hull example (~0.81)", () => {
  const result = blackScholes(42, 40, 182.5, 0.10, 0.20, "put");
  assert.ok(Math.abs(result.price - 0.81) < 0.05);
  assert.ok(result.delta < -0.1 && result.delta > -0.4);
});

test("call and put share the same gamma and vega (put-call parity)", () => {
  const call = blackScholes(100, 100, 30, 0.02, 0.25, "call");
  const put = blackScholes(100, 100, 30, 0.02, 0.25, "put");
  assert.ok(Math.abs(call.gamma - put.gamma) < 1e-9);
  assert.ok(Math.abs(call.vegaPer1Pct - put.vegaPer1Pct) < 1e-9);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/options.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `docs/js/options.js`**

```javascript
function erf(x) {
  // Abramowitz-Stegun 7.1.26 approximation, accurate to ~1.5e-7
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
  const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const t = 1 / (1 + p * x);
  const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return sign * y;
}

export function normCdf(x) {
  return 0.5 * (1 + erf(x / Math.SQRT2));
}

function normPdf(x) {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
}

export function blackScholes(spot, strike, dteDays, riskFreeRate, iv, optionType) {
  const t = dteDays / 365;
  const d1 = (Math.log(spot / strike) + (riskFreeRate + 0.5 * iv * iv) * t) / (iv * Math.sqrt(t));
  const d2 = d1 - iv * Math.sqrt(t);
  const discount = Math.exp(-riskFreeRate * t);

  let price, delta;
  if (optionType === "call") {
    price = spot * normCdf(d1) - strike * discount * normCdf(d2);
    delta = normCdf(d1);
  } else {
    price = strike * discount * normCdf(-d2) - spot * normCdf(-d1);
    delta = normCdf(d1) - 1;
  }

  const gamma = normPdf(d1) / (spot * iv * Math.sqrt(t));
  const vegaPer1Pct = spot * normPdf(d1) * Math.sqrt(t) * 0.01;

  const thetaAnnualCall = -(spot * normPdf(d1) * iv) / (2 * Math.sqrt(t)) - riskFreeRate * strike * discount * normCdf(d2);
  const thetaAnnualPut = -(spot * normPdf(d1) * iv) / (2 * Math.sqrt(t)) + riskFreeRate * strike * discount * normCdf(-d2);
  const thetaPerDay = (optionType === "call" ? thetaAnnualCall : thetaAnnualPut) / 365;

  return { price, delta, gamma, thetaPerDay, vegaPer1Pct };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/options.test.mjs`
Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
git add docs/js/options.js tests/js/options.test.mjs
git commit -m "Add Black-Scholes pricing and Greeks"
```

---

## Task 5: `options.js` — strategy payoff diagrams

**Files:**
- Modify: `docs/js/options.js`
- Test: `tests/js/options.test.mjs` (append)

**Interfaces:**
- Consumes: nothing from Task 4 (payoff math is independent of Black-Scholes).
- Produces:
  - `calculateStrategyPayoff(strategyKey: string, spot: number, params: object): {prices:number[], payoffs:number[], maxProfit:number|"無限", maxLoss:number|"無限", breakevens:number[], summary:string}`
  - Valid `strategyKey` values: `"long_call"`, `"long_put"`, `"bull_call_spread"`, `"bear_put_spread"`, `"bull_put_spread"`, `"iron_condor"`, `"long_straddle"`. Point value is fixed at 50 (TAIEX options multiplier), matching the original dashboard.

- [ ] **Step 1: Write failing tests**

```javascript
// append to tests/js/options.test.mjs
import { calculateStrategyPayoff } from "../../docs/js/options.js";

test("long_call: capped loss at the premium, unlimited upside", () => {
  const r = calculateStrategyPayoff("long_call", 17000, { k1: 17000, prem1: 50 });
  assert.equal(r.maxLoss, 50 * 50); // premium * point value
  assert.equal(r.maxProfit, "無限");
  assert.ok(r.breakevens.some((b) => Math.abs(b - 17050) < 1));
});

test("long_put: capped loss at the premium, capped-but-large downside profit", () => {
  const r = calculateStrategyPayoff("long_put", 17000, { k1: 17000, prem1: 50 });
  assert.equal(r.maxLoss, 50 * 50);
  assert.ok(r.breakevens.some((b) => Math.abs(b - 16950) < 1));
});

test("bull_call_spread: max profit and max loss are both capped", () => {
  const r = calculateStrategyPayoff("bull_call_spread", 17000, { k1: 17000, k2: 17200, prem1: 80, prem2: 30 });
  assert.equal(r.maxLoss, (80 - 30) * 50);
  assert.equal(r.maxProfit, ((17200 - 17000) - (80 - 30)) * 50);
});

test("iron_condor: max profit is the net credit, both wings cap the loss", () => {
  const r = calculateStrategyPayoff("iron_condor", 17000, {
    put_sell: 16800, put_buy: 16600, call_sell: 17200, call_buy: 17400,
    prem_put_s: 40, prem_put_b: 15, prem_call_s: 40, prem_call_b: 15,
  });
  const netCredit = (40 - 15) + (40 - 15);
  assert.equal(r.maxProfit, netCredit * 50);
});

test("long_straddle: loses both premiums at the strike, profits either direction", () => {
  const r = calculateStrategyPayoff("long_straddle", 17000, { k1: 17000, prem1: 45, prem2: 45 });
  assert.equal(r.maxLoss, (45 + 45) * 50);
  assert.equal(r.maxProfit, "無限");
  const atStrikeIdx = r.prices.findIndex((p) => p === 17000);
  assert.ok(Math.abs(r.payoffs[atStrikeIdx] - (-(45 + 45) * 50)) < 1);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/options.test.mjs`
Expected: FAIL — `calculateStrategyPayoff is not a function`.

- [ ] **Step 3: Implement (append to `docs/js/options.js`)**

```javascript
const POINT_VALUE = 50;

function priceRange(spot) {
  const span = spot * 0.1;
  const step = span / 100;
  const prices = [];
  for (let p = spot - span; p <= spot + span; p += step) prices.push(Math.round(p));
  return prices;
}

function findBreakevens(prices, payoffs) {
  const breakevens = [];
  for (let i = 1; i < payoffs.length; i++) {
    if ((payoffs[i - 1] < 0 && payoffs[i] >= 0) || (payoffs[i - 1] > 0 && payoffs[i] <= 0)) {
      breakevens.push(prices[i]);
    }
  }
  return breakevens;
}

export function calculateStrategyPayoff(strategyKey, spot, params) {
  const prices = priceRange(spot);
  let payoffs;
  let maxProfit;
  let maxLoss;
  let summary;

  const callPayoff = (price, k) => Math.max(price - k, 0);
  const putPayoff = (price, k) => Math.max(k - price, 0);

  if (strategyKey === "long_call") {
    payoffs = prices.map((p) => (callPayoff(p, params.k1) - params.prem1) * POINT_VALUE);
    maxProfit = "無限";
    maxLoss = params.prem1 * POINT_VALUE;
    summary = `買進履約價 ${params.k1} 的買權,付出權利金 ${params.prem1} 點`;
  } else if (strategyKey === "long_put") {
    payoffs = prices.map((p) => (putPayoff(p, params.k1) - params.prem1) * POINT_VALUE);
    maxProfit = (params.k1 - params.prem1) * POINT_VALUE;
    maxLoss = params.prem1 * POINT_VALUE;
    summary = `買進履約價 ${params.k1} 的賣權,付出權利金 ${params.prem1} 點`;
  } else if (strategyKey === "bull_call_spread") {
    payoffs = prices.map((p) =>
      (callPayoff(p, params.k1) - callPayoff(p, params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE
    );
    maxLoss = (params.prem1 - params.prem2) * POINT_VALUE;
    maxProfit = ((params.k2 - params.k1) - (params.prem1 - params.prem2)) * POINT_VALUE;
    summary = `買進 ${params.k1} 買權、賣出 ${params.k2} 買權`;
  } else if (strategyKey === "bear_put_spread") {
    payoffs = prices.map((p) =>
      (putPayoff(p, params.k1) - putPayoff(p, params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE
    );
    maxLoss = (params.prem1 - params.prem2) * POINT_VALUE;
    maxProfit = ((params.k1 - params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE;
    summary = `買進 ${params.k1} 賣權、賣出 ${params.k2} 賣權`;
  } else if (strategyKey === "bull_put_spread") {
    payoffs = prices.map((p) =>
      (params.prem1 - params.prem2 - putPayoff(p, params.k1) + putPayoff(p, params.k2)) * POINT_VALUE
    );
    maxProfit = (params.prem1 - params.prem2) * POINT_VALUE;
    maxLoss = ((params.k1 - params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE;
    summary = `賣出 ${params.k1} 賣權、買進保護 ${params.k2} 賣權`;
  } else if (strategyKey === "iron_condor") {
    const netCredit = (params.prem_put_s - params.prem_put_b) + (params.prem_call_s - params.prem_call_b);
    payoffs = prices.map((p) => {
      const putLeg = -putPayoff(p, params.put_sell) + putPayoff(p, params.put_buy);
      const callLeg = -callPayoff(p, params.call_sell) + callPayoff(p, params.call_buy);
      return (netCredit + putLeg + callLeg) * POINT_VALUE;
    });
    maxProfit = netCredit * POINT_VALUE;
    const putWing = params.put_sell - params.put_buy;
    const callWing = params.call_buy - params.call_sell;
    maxLoss = (Math.max(putWing, callWing) - netCredit) * POINT_VALUE;
    summary = `賣出 ${params.put_sell}/${params.call_sell} 履約價、兩側買進保護 ${params.put_buy}/${params.call_buy}`;
  } else if (strategyKey === "long_straddle") {
    payoffs = prices.map((p) =>
      (callPayoff(p, params.k1) + putPayoff(p, params.k1) - params.prem1 - params.prem2) * POINT_VALUE
    );
    maxProfit = "無限";
    maxLoss = (params.prem1 + params.prem2) * POINT_VALUE;
    summary = `同時買進履約價 ${params.k1} 的買權與賣權`;
  } else {
    throw new Error(`未知策略: ${strategyKey}`);
  }

  return { prices, payoffs, maxProfit, maxLoss, breakevens: findBreakevens(prices, payoffs), summary };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/options.test.mjs`
Expected: all pass (9 tests total from Tasks 4+5).

- [ ] **Step 5: Commit**

```bash
git add docs/js/options.js tests/js/options.test.mjs
git commit -m "Add 7-strategy options payoff calculator"
```

---

## Task 6: `backtest.js` — engine core (trade simulation + metrics)

**Files:**
- Create: `docs/js/backtest.js`
- Test: `tests/js/backtest.test.mjs`

**Interfaces:**
- Produces:
  - `simulateTrades(closes: number[], dates: string[], signals: (1|-1|0)[], initialCapital: number): {equityCurve:number[], trades:Array<{entry_date, entry_price, exit_date, exit_price, return_pct, holding_days, is_win}>}`
    - `signals[i]` is the position to hold *after* bar `i` closes: `1` = long, `0` = flat. (Strategies in Task 7 only ever go long/flat, matching the original dashboard's four strategies.)
  - `computeMetrics(closes: number[], equityCurve: number[], trades: Array, initialCapital: number): {total_return_pct, buy_hold_return_pct, cagr_pct, max_drawdown_pct, sharpe_ratio, win_rate_pct, total_trades, profit_factor}`

- [ ] **Step 1: Write failing tests**

```javascript
// tests/js/backtest.test.mjs
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/backtest.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `docs/js/backtest.js`**

```javascript
export function simulateTrades(closes, dates, signals, initialCapital) {
  const trades = [];
  const equityCurve = new Array(closes.length);
  let cash = initialCapital;
  let position = 0; // shares-equivalent, expressed as a capital fraction of 1.0 when in a trade
  let entryPrice = null;
  let entryDate = null;
  let entryIndex = null;

  for (let i = 0; i < closes.length; i++) {
    const wantLong = signals[i] === 1;
    if (wantLong && position === 0) {
      position = 1;
      entryPrice = closes[i];
      entryDate = dates[i];
      entryIndex = i;
    } else if (!wantLong && position === 1) {
      const returnPct = ((closes[i] - entryPrice) / entryPrice) * 100;
      trades.push({
        entry_date: entryDate,
        entry_price: entryPrice,
        exit_date: dates[i],
        exit_price: closes[i],
        return_pct: returnPct,
        holding_days: i - entryIndex,
        is_win: closes[i] > entryPrice,
      });
      cash = cash * (1 + returnPct / 100);
      position = 0;
      entryPrice = null;
    }
    equityCurve[i] = position === 1 ? cash * (closes[i] / entryPrice) : cash;
  }

  if (position === 1) {
    const lastIdx = closes.length - 1;
    const returnPct = ((closes[lastIdx] - entryPrice) / entryPrice) * 100;
    trades.push({
      entry_date: entryDate,
      entry_price: entryPrice,
      exit_date: dates[lastIdx],
      exit_price: closes[lastIdx],
      return_pct: returnPct,
      holding_days: lastIdx - entryIndex,
      is_win: closes[lastIdx] > entryPrice,
    });
  }

  return { equityCurve, trades };
}

export function computeMetrics(closes, equityCurve, trades, initialCapital) {
  const finalEquity = equityCurve[equityCurve.length - 1];
  const totalReturnPct = ((finalEquity - initialCapital) / initialCapital) * 100;
  const buyHoldReturnPct = ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100;

  const years = closes.length / 252;
  const cagrPct = years > 0 ? (Math.pow(finalEquity / initialCapital, 1 / years) - 1) * 100 : 0;

  let peak = equityCurve[0];
  let maxDrawdownPct = 0;
  for (const value of equityCurve) {
    if (value > peak) peak = value;
    const drawdown = ((peak - value) / peak) * 100;
    if (drawdown > maxDrawdownPct) maxDrawdownPct = drawdown;
  }

  const dailyReturns = [];
  for (let i = 1; i < equityCurve.length; i++) {
    dailyReturns.push((equityCurve[i] - equityCurve[i - 1]) / equityCurve[i - 1]);
  }
  const meanReturn = dailyReturns.reduce((a, b) => a + b, 0) / (dailyReturns.length || 1);
  const variance = dailyReturns.reduce((a, b) => a + (b - meanReturn) ** 2, 0) / (dailyReturns.length || 1);
  const stdReturn = Math.sqrt(variance);
  const sharpeRatio = stdReturn > 0 ? (meanReturn / stdReturn) * Math.sqrt(252) : 0;

  const wins = trades.filter((t) => t.is_win);
  const losses = trades.filter((t) => !t.is_win);
  const winRatePct = trades.length > 0 ? (wins.length / trades.length) * 100 : 0;
  const grossProfit = wins.reduce((a, t) => a + Math.max(t.return_pct, 0), 0);
  const grossLoss = Math.abs(losses.reduce((a, t) => a + Math.min(t.return_pct, 0), 0));
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);

  return {
    total_return_pct: totalReturnPct,
    buy_hold_return_pct: buyHoldReturnPct,
    cagr_pct: cagrPct,
    max_drawdown_pct: maxDrawdownPct,
    sharpe_ratio: sharpeRatio,
    win_rate_pct: winRatePct,
    total_trades: trades.length,
    profit_factor: profitFactor,
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/backtest.test.mjs`
Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
git add docs/js/backtest.js tests/js/backtest.test.mjs
git commit -m "Add backtest trade simulation engine and performance metrics"
```

---

## Task 7: `backtest.js` — the four strategies

**Files:**
- Modify: `docs/js/backtest.js`
- Test: `tests/js/backtest.test.mjs` (append)

**Interfaces:**
- Consumes: `sma`, `rsi`, `macd`, `bollingerBands` from `docs/js/indicators.js` (Tasks 2-3); `simulateTrades`, `computeMetrics` from Task 6.
- Produces:
  - `runBacktest(ohlc: {dates:string[], high:number[], low:number[], close:number[]}, strategyKey: "dual_ma"|"rsi"|"macd"|"bollinger", params: object, initialCapital: number): {metrics: object, equityCurve: number[], trades: Array}`

- [ ] **Step 1: Write failing tests**

```javascript
// append to tests/js/backtest.test.mjs
import { runBacktest } from "../../docs/js/backtest.js";

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/backtest.test.mjs`
Expected: FAIL — `runBacktest is not a function`.

- [ ] **Step 3: Implement (append to `docs/js/backtest.js`)**

```javascript
import { sma, rsi as calcRsi, macd as calcMacd, bollingerBands } from "./indicators.js";

function dualMaSignals(closes, { fast_period = 5, slow_period = 20 } = {}) {
  const fast = sma(closes, fast_period);
  const slow = sma(closes, slow_period);
  return closes.map((_, i) => (fast[i] !== null && slow[i] !== null && fast[i] > slow[i] ? 1 : 0));
}

function rsiSignals(closes, { rsi_period = 14, buy_threshold = 30, sell_threshold = 70 } = {}) {
  const values = calcRsi(closes, rsi_period);
  const signals = new Array(closes.length).fill(0);
  let holding = false;
  for (let i = 0; i < closes.length; i++) {
    if (!holding && values[i] !== null && values[i] < buy_threshold) holding = true;
    else if (holding && values[i] !== null && values[i] > sell_threshold) holding = false;
    signals[i] = holding ? 1 : 0;
  }
  return signals;
}

function macdSignals(closes) {
  const { dif, dea } = calcMacd(closes);
  return closes.map((_, i) => (dif[i] > dea[i] ? 1 : 0));
}

function bollingerSignals(closes) {
  const { lower, middle } = bollingerBands(closes, 20, 2);
  const signals = new Array(closes.length).fill(0);
  let holding = false;
  for (let i = 0; i < closes.length; i++) {
    if (lower[i] === null) { signals[i] = 0; continue; }
    if (!holding && closes[i] <= lower[i]) holding = true;
    else if (holding && closes[i] >= middle[i]) holding = false;
    signals[i] = holding ? 1 : 0;
  }
  return signals;
}

export function runBacktest(ohlc, strategyKey, params, initialCapital) {
  const { dates, close } = ohlc;
  let signals;
  if (strategyKey === "dual_ma") signals = dualMaSignals(close, params);
  else if (strategyKey === "rsi") signals = rsiSignals(close, params);
  else if (strategyKey === "macd") signals = macdSignals(close);
  else if (strategyKey === "bollinger") signals = bollingerSignals(close);
  else throw new Error(`未知回測策略: ${strategyKey}`);

  const { equityCurve, trades } = simulateTrades(close, dates, signals, initialCapital);
  const metrics = computeMetrics(close, equityCurve, trades, initialCapital);
  return { metrics, equityCurve, trades };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/backtest.test.mjs`
Expected: all pass (9 tests total from Tasks 6+7).

- [ ] **Step 5: Commit**

```bash
git add docs/js/backtest.js tests/js/backtest.test.mjs
git commit -m "Add dual-MA/RSI/MACD/Bollinger backtest strategies"
```

---

## Task 8: `charts.js` — candlestick + indicator overlay figure builder

**Files:**
- Create: `docs/js/charts.js`
- Test: `tests/js/charts.test.mjs`

**Interfaces:**
- Consumes: nothing (pure data-shaping; callers pass in already-computed indicator arrays from Tasks 2-3).
- Produces:
  - `buildCandlestickFigure(ohlc: {dates, open, high, low, close}, options: {chartType:"candlestick"|"line", maSeries: {period:number, values:number[]}[], bbands: {upper,middle,lower}|null, subIndicator: {name:string, series:object}|null, twStyle:boolean}): {data: object[], layout: object}`

- [ ] **Step 1: Write failing tests**

```javascript
// tests/js/charts.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildCandlestickFigure } from "../../docs/js/charts.js";

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/charts.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `docs/js/charts.js`**

```javascript
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/charts.test.mjs`
Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
git add docs/js/charts.js tests/js/charts.test.mjs
git commit -m "Add candlestick+indicator Plotly figure builder"
```

---

## Task 9: `charts.js` — payoff diagram + equity curve figure builders

**Files:**
- Modify: `docs/js/charts.js`
- Test: `tests/js/charts.test.mjs` (append)

**Interfaces:**
- Produces:
  - `buildPayoffFigure(prices:number[], payoffs:number[], spot:number, breakevens:number[], strategyName:string): {data, layout}`
  - `buildEquityCurveFigure(dates:string[], equityCurve:number[], trades:Array<{entry_date,exit_date}>): {data, layout}`

- [ ] **Step 1: Write failing tests**

```javascript
// append to tests/js/charts.test.mjs
import { buildPayoffFigure, buildEquityCurveFigure } from "../../docs/js/charts.js";

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --test tests/js/charts.test.mjs`
Expected: FAIL — `buildPayoffFigure is not a function`.

- [ ] **Step 3: Implement (append to `docs/js/charts.js`)**

```javascript
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test tests/js/charts.test.mjs`
Expected: all pass (6 tests total from Tasks 8+9).

- [ ] **Step 5: Commit**

```bash
git add docs/js/charts.js tests/js/charts.test.mjs
git commit -m "Add options-payoff and equity-curve figure builders"
```

---

## Task 10: `tools/fetch_data.py` — pure JSON-shaping logic (no network)

**Files:**
- Create: `tools/fetch_data.py`
- Test: `tests/python/test_fetch_data.py`

**Interfaces:**
- Produces (pure functions, no I/O):
  - `history_to_symbol_json(symbol: str, name: str, history: "pandas.DataFrame") -> dict` — `history` has a `DatetimeIndex` and columns `Open, High, Low, Close, Volume`; returns the exact `{symbol, name, dates, open, high, low, close, volume}` schema from the spec, with any row containing `NaN` in `Close` dropped, and dates formatted `YYYY-MM-DD`.
  - `build_manifest(entries: list[dict]) -> dict` — each entry is `{symbol, name, category, sector, file, start_date, end_date}`; returns `{generated_at: <UTC ISO8601 string>, symbols: entries}`.

- [ ] **Step 1: Write failing tests**

```python
# tests/python/test_fetch_data.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.python.test_fetch_data -v` (run from the repo root; add empty `tests/__init__.py` and `tests/python/__init__.py` if `unittest` can't find the package — create them as empty files first)
Expected: FAIL — `ModuleNotFoundError: No module named 'fetch_data'`.

- [ ] **Step 3: Implement `tools/fetch_data.py` (this task only — the transform functions, not the network call yet)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.python.test_fetch_data -v`
Expected: 3 pass.

- [ ] **Step 5: Commit**

```bash
git add tools/fetch_data.py tests/python/test_fetch_data.py tests/python/__init__.py tests/__init__.py
git commit -m "Add pure JSON-shaping logic for the data pipeline"
```

---

## Task 11: `tools/fetch_data.py` — symbol list + yfinance fetch + CLI entrypoint

**Files:**
- Modify: `tools/fetch_data.py`

**Interfaces:**
- Consumes: `history_to_symbol_json`, `build_manifest` from Task 10.
- Produces: `fetch_symbol_history(symbol: str, period="5y") -> pandas.DataFrame` (thin wrapper over `yfinance.Ticker(symbol).history(period=period)`, isolated so it's the only network-touching function in the file) and a `main()` CLI entrypoint. No automated test (network-dependent) — verified by actually running it in Step 3.

- [ ] **Step 1: Append the symbol list and fetch/CLI code to `tools/fetch_data.py`**

```python
import json
import os

import yfinance as yf

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
```

- [ ] **Step 2: Run it for real**

Run: `python tools/fetch_data.py`
Expected: prints one line per symbol, ends with `完成:N 檔標的...`; `docs/data/` now contains one `.json` per symbol plus `manifest.json`.

- [ ] **Step 3: Spot-check the output**

Run: `python -c "import json; d = json.load(open('docs/data/2330.TW.json', encoding='utf-8')); print(d['symbol'], d['name'], len(d['dates']), d['dates'][-1])"`
Expected: prints `2330.TW 台積電 <N> <today's or last trading date>` with `N` in the hundreds (5 years of daily bars).

- [ ] **Step 4: Re-run the unit tests to confirm nothing broke**

Run: `python -m unittest tests.python.test_fetch_data -v`
Expected: still 3 pass (Task 10's tests only exercise the pure functions, unaffected by this task's additions).

- [ ] **Step 5: Commit**

```bash
git add tools/fetch_data.py docs/data/
git commit -m "Fetch 5y history for popular TW stocks and macro benchmarks via yfinance"
```

---

## Task 12: `app.js` — manifest loading + 技術分析 tab wiring

**Files:**
- Modify: `docs/js/app.js`
- Modify: `docs/index.html` (fill in `#tab-technical`'s markup)

**Interfaces:**
- Consumes: `manifest.json`/`{symbol}.json` (Task 11), `sma`/`bollingerBands`/`rsi`/`kd`/`macd`/`bias`/`diagnose*` (Tasks 2-3), `buildCandlestickFigure` (Task 8). Uses the global `Plotly` from the CDN `<script>` tag in `index.html`.
- Produces: `initTechnicalTab(manifest)` (called from the app's bootstrap `DOMContentLoaded` handler), no other module imports this — it is a leaf wired directly to the DOM.

- [ ] **Step 1: Fill in `#tab-technical` markup in `docs/index.html`**

```html
<section id="tab-technical" class="tab-panel active">
  <div class="controls-row">
    <label>標的
      <select id="tech-symbol"></select>
    </label>
    <label>期間
      <select id="tech-period">
        <option value="1mo">1個月</option>
        <option value="3mo">3個月</option>
        <option value="6mo">6個月</option>
        <option value="1y" selected>1年</option>
        <option value="2y">2年</option>
        <option value="5y">5年(全部)</option>
      </select>
    </label>
    <label>主圖類型
      <select id="tech-chart-type">
        <option value="candlestick" selected>K線</option>
        <option value="line">收盤線</option>
      </select>
    </label>
    <label>配色
      <select id="tech-color-style">
        <option value="tw" selected>紅漲綠跌(台股慣用)</option>
        <option value="intl">綠漲紅跌(國際慣用)</option>
      </select>
    </label>
  </div>
  <div class="controls-row">
    <span>均線:</span>
    <label><input type="checkbox" class="tech-ma" value="5" checked> MA5</label>
    <label><input type="checkbox" class="tech-ma" value="10"> MA10</label>
    <label><input type="checkbox" class="tech-ma" value="20" checked> MA20</label>
    <label><input type="checkbox" class="tech-ma" value="60" checked> MA60</label>
    <label><input type="checkbox" id="tech-bbands"> 布林通道</label>
    <label>副圖
      <select id="tech-sub-indicator">
        <option value="KD" selected>KD</option>
        <option value="RSI">RSI</option>
        <option value="MACD">MACD</option>
        <option value="BIAS">BIAS</option>
        <option value="NONE">無</option>
      </select>
    </label>
  </div>
  <div id="tech-metrics" class="metric-grid"></div>
  <div id="tech-chart"></div>
  <div id="tech-diagnosis" class="metric-grid"></div>
</section>
```

- [ ] **Step 2: Add minimal layout CSS to `docs/css/style.css`**

```css
.controls-row { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; margin-bottom: 12px; }
.controls-row label { font-size: 0.85rem; display: flex; align-items: center; gap: 4px; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin: 12px 0; }
```

- [ ] **Step 3: Implement the technical tab wiring in `docs/js/app.js`**

```javascript
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
```

- [ ] **Step 4: Manual browser verification**

Run: `python -m http.server 8000 --directory docs`, open `http://localhost:8000/`. Confirm: the 標的 dropdown lists all symbols from `manifest.json`; the K-line chart renders for 台積電 (2330.TW); switching 期間/主圖類型/配色/副圖 redraws the chart; toggling MA checkboxes adds/removes lines; the metric cards and diagnosis cards show numbers, not `NaN`/`undefined`.

- [ ] **Step 5: Commit**

```bash
git add docs/index.html docs/css/style.css docs/js/app.js
git commit -m "Wire up the technical analysis tab against real data"
```

---

## Task 13: `app.js` — 選擇權策略中心 tab wiring

**Files:**
- Modify: `docs/js/app.js`
- Modify: `docs/index.html` (fill in `#tab-options`)

**Interfaces:**
- Consumes: `blackScholes`, `calculateStrategyPayoff` (Tasks 4-5), `buildPayoffFigure` (Task 9).
- Produces: `initOptionsTab()`, called from `bootstrap()`.

- [ ] **Step 1: Fill in `#tab-options` markup in `docs/index.html`**

```html
<section id="tab-options" class="tab-panel">
  <div class="sub-header-title">🧮 Black-Scholes 定價與 Greeks 計算機</div>
  <div class="controls-row">
    <label>現價 S <input type="number" id="bs-spot" value="17000" step="10"></label>
    <label>履約價 K <input type="number" id="bs-strike" value="17000" step="100"></label>
    <label>到期天數 <input type="number" id="bs-dte" value="5" min="1"></label>
    <label>IV (%) <input type="number" id="bs-iv" value="18" step="0.5"></label>
    <label>無風險利率 r (%) <input type="number" id="bs-r" value="1.5" step="0.1"></label>
  </div>
  <table id="bs-table" class="data-table"></table>

  <div class="sub-header-title">📈 策略到期損益模擬圖</div>
  <div class="controls-row">
    <label>策略
      <select id="payoff-strategy">
        <option value="long_call">Long Call (買進買權)</option>
        <option value="long_put">Long Put (買進賣權)</option>
        <option value="bull_call_spread">Bull Call Spread (買權牛市價差)</option>
        <option value="bear_put_spread">Bear Put Spread (賣權熊市價差)</option>
        <option value="bull_put_spread">Bull Put Spread (賣權牛市信用價差)</option>
        <option value="iron_condor">Iron Condor (鐵鷹價差)</option>
        <option value="long_straddle">Long Straddle (買進跨式)</option>
      </select>
    </label>
  </div>
  <div id="payoff-params" class="controls-row"></div>
  <div id="payoff-summary" class="metric-grid"></div>
  <div id="payoff-chart"></div>
</section>
```

- [ ] **Step 2: Implement options tab wiring in `docs/js/app.js` (append near the technical tab code)**

```javascript
import { blackScholes, calculateStrategyPayoff } from "./options.js";
import { buildPayoffFigure } from "./charts.js";

function renderGreeksTable() {
  const spot = Number(document.getElementById("bs-spot").value);
  const strike = Number(document.getElementById("bs-strike").value);
  const dte = Number(document.getElementById("bs-dte").value);
  const iv = Number(document.getElementById("bs-iv").value) / 100;
  const r = Number(document.getElementById("bs-r").value) / 100;

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
  long_call: [["k1", "履約價 K"], ["prem1", "權利金"]],
  long_put: [["k1", "履約價 K"], ["prem1", "權利金"]],
  bull_call_spread: [["k1", "買進履約價 K1"], ["k2", "賣出履約價 K2"], ["prem1", "買進權利金"], ["prem2", "賣出權利金"]],
  bear_put_spread: [["k1", "買進履約價 K1"], ["k2", "賣出履約價 K2"], ["prem1", "買進權利金"], ["prem2", "賣出權利金"]],
  bull_put_spread: [["k1", "賣出履約價 K1"], ["k2", "買進履約價 K2"], ["prem1", "賣出權利金"], ["prem2", "買進權利金"]],
  iron_condor: [["put_sell", "賣出Put"], ["put_buy", "買進Put"], ["call_sell", "賣出Call"], ["call_buy", "買進Call"],
                ["prem_put_s", "賣Put權利金"], ["prem_put_b", "買Put權利金"], ["prem_call_s", "賣Call權利金"], ["prem_call_b", "買Call權利金"]],
  long_straddle: [["k1", "履約價 K"], ["prem1", "Call權利金"], ["prem2", "Put權利金"]],
};

const PAYOFF_DEFAULTS = {
  k1: 17000, k2: 17200, prem1: 60, prem2: 30,
  put_sell: 16800, put_buy: 16600, call_sell: 17200, call_buy: 17400,
  prem_put_s: 40, prem_put_b: 15, prem_call_s: 40, prem_call_b: 15,
};

function renderPayoffParamInputs(strategyKey) {
  const container = document.getElementById("payoff-params");
  container.innerHTML = "";
  for (const [field, label] of PAYOFF_PARAM_FIELDS[strategyKey]) {
    const wrapper = document.createElement("label");
    wrapper.textContent = label + " ";
    const input = document.createElement("input");
    input.type = "number";
    input.dataset.field = field;
    input.value = PAYOFF_DEFAULTS[field];
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
  const strategyKey = document.getElementById("payoff-strategy").value;
  const params = readPayoffParams();
  const spot = params.k1 ?? params.put_sell ?? 17000;
  const result = calculateStrategyPayoff(strategyKey, spot, params);

  document.getElementById("payoff-summary").innerHTML = `
    <div class="metric-card">策略摘要<br>${result.summary}</div>
    <div class="metric-card">最大獲利<br><strong>${result.maxProfit === "無限" ? "無限" : result.maxProfit.toLocaleString()}</strong></div>
    <div class="metric-card">最大風險<br><strong>${result.maxLoss === "無限" ? "無限" : result.maxLoss.toLocaleString()}</strong></div>
    <div class="metric-card">損益兩平點<br>${result.breakevens.map((b) => b.toFixed(0)).join(", ") || "—"}</div>
  `;

  const fig = buildPayoffFigure(result.prices, result.payoffs, spot, result.breakevens, strategyKey);
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
```

- [ ] **Step 3: Call `initOptionsTab()` from `bootstrap()`**

```javascript
async function bootstrap() {
  const manifest = await loadManifest();
  await renderTechnicalTab(manifest);
  initOptionsTab();
}
```

- [ ] **Step 4: Add a data-table style to `docs/css/style.css`**

```css
.data-table { width: 100%; border-collapse: collapse; margin: 12px 0; }
.data-table th, .data-table td { border: 1px solid #e2e8f0; padding: 6px 10px; text-align: left; font-size: 0.85rem; }
.data-table th { background: #f1f2f6; }
.sub-header-title { font-size: 1.1rem; font-weight: 700; margin: 20px 0 10px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; }
```

- [ ] **Step 5: Manual browser verification**

Reload `http://localhost:8000/`, click 🎯 選擇權策略中心. Confirm: changing S/K/DTE/IV/r updates the Greeks table live; switching the payoff strategy dropdown swaps the parameter inputs and redraws the chart; editing a parameter input redraws the chart; Iron Condor and Long Straddle (the two multi-leg strategies) render sensible curves (W-shape and flat-top-with-two-legs respectively).

- [ ] **Step 6: Commit**

```bash
git add docs/index.html docs/css/style.css docs/js/app.js
git commit -m "Wire up the options strategy center tab"
```

---

## Task 14: `app.js` — 回測實驗室 tab wiring

**Files:**
- Modify: `docs/js/app.js`
- Modify: `docs/index.html` (fill in `#tab-backtest`)

**Interfaces:**
- Consumes: `runBacktest` (Task 7), `buildEquityCurveFigure` (Task 9), the same `manifest`/`loadSymbolData` helpers from Task 12.
- Produces: `initBacktestTab(manifest)`, called from `bootstrap()`.

- [ ] **Step 1: Fill in `#tab-backtest` markup in `docs/index.html`**

```html
<section id="tab-backtest" class="tab-panel">
  <div class="controls-row">
    <label>標的 <select id="bt-symbol"></select></label>
    <label>策略
      <select id="bt-strategy">
        <option value="dual_ma">雙均線黃金/死亡交叉</option>
        <option value="rsi">RSI 超賣反彈與超買停利</option>
        <option value="macd">MACD 柱狀與快慢線交叉</option>
        <option value="bollinger">布林通道破底翻逆勢策略</option>
      </select>
    </label>
    <label>初始本金 <input type="number" id="bt-capital" value="100000" step="10000"></label>
  </div>
  <div id="bt-params" class="controls-row"></div>
  <button id="bt-run">🔍 執行回測</button>

  <div id="bt-metrics" class="metric-grid"></div>
  <div id="bt-chart"></div>
  <table id="bt-trades" class="data-table"></table>
</section>
```

- [ ] **Step 2: Implement backtest tab wiring in `docs/js/app.js`**

```javascript
import { runBacktest } from "./backtest.js";
import { buildEquityCurveFigure } from "./charts.js";

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
```

- [ ] **Step 3: Call `initBacktestTab(manifest)` from `bootstrap()`**

```javascript
async function bootstrap() {
  const manifest = await loadManifest();
  await renderTechnicalTab(manifest);
  initOptionsTab();
  initBacktestTab(manifest);
}
```

- [ ] **Step 4: Manual browser verification**

Reload, click 🧪 回測實驗室. Confirm: symbol dropdown only lists `tw_stock` entries (not macro benchmarks); switching strategy swaps the parameter inputs (dual_ma/rsi show inputs, macd/bollinger show none); clicking 執行回測 populates the metric cards, draws the equity curve with entry/exit markers, and fills the trade log table (or shows the "no trades" row if the strategy never fired).

- [ ] **Step 5: Commit**

```bash
git add docs/index.html docs/js/app.js
git commit -m "Wire up the backtest lab tab"
```

---

## Task 15: End-to-end polish pass + full test suite run

**Files:**
- Modify: `docs/css/style.css` (only if the manual pass below finds a real layout problem — do not add speculative styling)

**Interfaces:** none new — this task is verification, not new surface area.

- [ ] **Step 1: Run every automated test in one pass**

Run: `node --test tests/js/`
Expected: all JS tests pass (indicators, options, backtest, charts — ~29 tests across Tasks 2-9).

Run: `python -m unittest discover -s tests/python -v`
Expected: all Python tests pass (Task 10 — 3 tests).

- [ ] **Step 2: Full manual walkthrough in a real browser**

Run: `python -m http.server 8000 --directory docs`, open `http://localhost:8000/`, and go through all three tabs for at least two different symbols (e.g. 2330.TW and 0050.TW) and at least two backtest strategies. Confirm no browser console errors (open DevTools → Console) and no visible `NaN`/`undefined` text anywhere in the UI.

- [ ] **Step 3: Fix anything the walkthrough surfaces**

If a real bug or layout break turns up, fix it in the relevant file from Tasks 1-14 (not a new file) and re-run that file's test suite before moving on. If nothing turns up, skip this step.

- [ ] **Step 4: Commit (only if Step 3 changed anything)**

```bash
git add -A
git commit -m "Fix issues found during end-to-end walkthrough"
```

---

## Task 16: GitHub Pages deployment guide (for the user to execute)

**Files:**
- Modify: `README.md` (append a new section; do not rewrite the existing monorepo documentation above it)

**Interfaces:** none — this is documentation only, no code.

- [ ] **Step 1: Append a deployment section to `README.md`**

```markdown

## 靜態網站版(GitHub Pages)

`docs/` 底下是可獨立發布的純前端網站(技術分析 / 選擇權策略中心 / 回測實驗室),資料來自 `tools/fetch_data.py` 產生的 `docs/data/*.json`。

### 首次發布

1. 到 GitHub 建立一個新 repo(空的,不要初始化 README/.gitignore)。
2. 在這個資料夾執行:
   ```bash
   git remote add origin https://github.com/<你的帳號>/<repo名稱>.git
   git branch -M main
   git push -u origin main
   ```
3. 到 repo 的 Settings → Pages:
   - Source 選 **Deploy from a branch**
   - Branch 選 **main**,資料夾選 **/docs**
   - 儲存後等 1-2 分鐘,頁面會顯示發布網址(`https://<帳號>.github.io/<repo名稱>/`)。

### 之後更新資料

```bash
python tools/fetch_data.py   # 重新抓最新歷史股價,覆蓋 docs/data/*.json
git add docs/data
git commit -m "Update market data snapshot"
git push
```

push 後數十秒到一分鐘,GitHub Pages 會自動用新資料重新部署,不需要在 Settings 重新設定。

### 本機開發測試

```bash
python -m http.server 8000 --directory docs
# 開瀏覽器到 http://localhost:8000/
```

純靜態檔案,不需要 npm install 或任何建置步驟。
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "Document GitHub Pages deployment steps"
```

- [ ] **Step 3: Hand off to the user**

Tell the user the repo is ready to push, and that Task 16's README section walks them through: creating the GitHub repo, `git remote add`/`push`, and the Settings → Pages configuration — since those require their GitHub account and are the parts they wanted to do themselves.

---

## Self-Review Notes

- **Spec coverage:** 技術分析 (Tasks 2,3,8,12), 選擇權策略中心 (Tasks 4,5,9,13), 回測實驗室 (Tasks 6,7,9,14), 資料管線 (Tasks 10,11), 部署 (Task 16), 測試方式 (Task 15) — every spec section maps to at least one task.
- **Type consistency checked:** `ohlc` shape (`{dates, open, high, low, close, volume}`) is identical across Tasks 8, 12, 14; `strategyKey` string values are identical across Tasks 5/13 (options) and 7/14 (backtest); `manifest.symbols[].file`/`.category` fields defined in Task 11 are exactly what Tasks 12 and 14 read.
- **No placeholders:** every step has literal, runnable code or an exact shell command; no "add error handling" style steps remain.
