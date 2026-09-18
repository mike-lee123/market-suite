# market-suite 靜態網站版 — 設計文件

日期:2026-09-19

## 背景與目標

`market-suite` 目前是兩份 Streamlit 儀表板(`dashboard_modular`、`dashboard_v1878`)+ 永豐 Shioaji 券商 API + 6 人 AI 研究團隊 skill 組成的 monorepo。使用者希望把其中「不依賴伺服器/憑證」的功能改寫成純前端靜態網站,發布到 GitHub Pages,並以此為教學過程,學會 GitHub Pages 的部署方式。

## 範圍

**納入(可純前端運作)**

1. 📈 技術分析:K線/收盤線圖、MA(5/10/20/60/120/240)、布林通道、副圖(KD/RSI/MACD/BIAS 擇一)、指標快篩文字診斷。
2. 🎯 選擇權策略中心:Black-Scholes 定價與 Greeks 計算機、7 種策略到期損益圖(Long Call/Put、牛市買權價差、熊市賣權價差、牛市賣權信用價差、Iron Condor、Long Straddle)。
3. 🧪 量化回測實驗室:4 種策略(雙均線交叉、RSI 超賣反彈、MACD 交叉、布林通道突破)對歷史資料回測,輸出總報酬/CAGR/MDD/Sharpe/勝率/獲利因子 + 權益曲線 + 交易明細。

**排除(需要伺服器或憑證,無法純前端)**

- 永豐 Shioaji 即時五檔/期貨(需要券商登入 + 伺服器端 SDK)
- 6 人 AI 研究團隊 PDF 產生(需要呼叫 Claude/Gemini API + subprocess + PDF 引擎)
- 全市場選股獵鷹、yfinance 即時基本面(需要伺服器批次抓取;可列為未來優化方向,改成排程產生靜態 JSON)

`dashboard_modular/`、`dashboard_v1878/`、`research/`、`.claude/` 維持原樣不動,新增的靜態網站與資料管線是獨立的新增內容,不影響現有 Python 專案運作。

## 架構

```
market-suite/                    ← git init 成為 repo 根目錄
├── docs/                        ← GitHub Pages 發布根目錄(Settings → Pages → /docs)
│   ├── index.html               ← 單頁 app,三個分頁籤(技術分析 / 選擇權 / 回測)
│   ├── css/style.css            ← 版面、配色(紅漲綠跌可切換,比照原 Streamlit 版)
│   ├── js/
│   │   ├── indicators.js        ← MA/BBands/KD/RSI/MACD/BIAS 計算(移植自 indicators.py 邏輯)
│   │   ├── charts.js            ← Plotly.js 畫 K 線 + 副圖 + 回測權益曲線
│   │   ├── options.js           ← Black-Scholes/Greeks/7 策略 Payoff(移植自 options.py 邏輯)
│   │   ├── backtest.js          ← 回測引擎(移植自 backtest.py 邏輯)
│   │   └── app.js               ← 讀取 manifest/JSON、UI 互動、串接以上模組
│   └── data/
│       ├── manifest.json        ← 標的清單(代碼/名稱/分類/資料期間)
│       └── {SYMBOL}.json        ← 個別標的 OHLCV 歷史資料
├── tools/
│   └── fetch_data.py            ← 用 yfinance 產生 docs/data/*.json 的腳本(手動執行)
└── specs/                       ← 設計文件(本檔案所在位置,不發布上網)
```

## 資料管線

- `tools/fetch_data.py` 內建標的清單:比照原 `dashboard_modular` 的 `POPULAR_TW_STOCKS`(熱門台股,約 15-20 檔)與 `MACRO_BENCHMARKS`(美股三大指數、費半、台積電 ADR、美元台幣匯率、原油等)。
- 對每檔呼叫 `yfinance`,抓 5 年日K,輸出:
  ```json
  {
    "symbol": "2330.TW", "name": "台積電", "sector": "半導體",
    "dates": ["2021-01-04", "..."],
    "open": [...], "high": [...], "low": [...], "close": [...], "volume": [...]
  }
  ```
- 同時輸出 `docs/data/manifest.json`,列出所有標的的代碼/名稱/分類/資料起訖日,前端下拉選單依此動態產生選項。
- 更新流程為手動:使用者執行 `python tools/fetch_data.py` → 檢查 `docs/data/` 有更新 → `git add/commit/push`。不設定 GitHub Actions 自動排程(先求流程跑通,之後可再加)。

## 前端功能細節

### 技術分析分頁
- 標的下拉選單(讀 manifest.json)、期間選單(1個月~5年/YTD)、K線週期暫時固定日K(資料只存日K)。
- 指標計算全部搬到 `indicators.js`:SMA、EMA、布林通道(20,2σ)、KD(9,3)、RSI(6)、MACD(12,26,9)、BIAS。
- Plotly K線圖(蠟燭圖/收盤線切換)+ 副圖(KD/RSI/MACD/BIAS 擇一顯示),配色可切換紅漲綠跌 vs 綠漲紅跌。
- 底部顯示均線排列狀態、KD 黃金/死亡交叉、RSI 強弱、MACD 柱狀圖狀態等文字診斷(邏輯移植自原 app.py 對應區塊)。

### 選擇權策略中心分頁
- Black-Scholes 計算機:輸入現價/履約價/到期天數/IV/無風險利率,即時算 Call/Put 的理論價、Delta/Gamma/Theta/Vega,純前端 JS 公式運算,不需要任何資料檔。
- Payoff 模擬器:7 種策略,依策略動態顯示對應輸入欄位(履約價、權利金),即時畫損益到期圖、標示最大獲利/風險/損益兩平點。

### 回測實驗室分頁
- 選標的(讀同一份歷史 JSON)、選策略(雙均線/RSI/MACD/布林通道)、可調參數(週期、閾值)、初始本金。
- `backtest.js` 對歷史資料跑迴圈模擬交易,輸出:總報酬率、買入持有報酬率對比、CAGR、MDD、Sharpe、勝率、獲利因子、交易明細表。
- Plotly 畫權益曲線 + 買賣點標記於價格圖上。

## 部署

1. `git init`(目前資料夾還不是 git repo),建立/檢查 `.gitignore`(排除 `__pycache__/`、`*.log`、既有 research 產出的大型二進位檔如需要)。
2. GitHub 新建 repo,`git remote add origin` + push。
3. Repo Settings → Pages → Source: Deploy from a branch → Branch: `main` → Folder: `/docs`。
4. 之後對 `docs/` 的任何 push 會在數十秒內自動反映到 `https://<帳號>.github.io/<repo>/`。

## 測試方式

- 本機 `python -m http.server` 在 `docs/` 內起服務,瀏覽器 `localhost:<port>` 直接測試,純靜態檔案不需要 npm/建置工具。
- 以台積電(2330.TW)資料驗證三個分頁功能可正常運作:技術分析圖表與指標渲染正確、選擇權計算機數值合理、回測跑得出結果與圖表。
- 之後手動檢查其他標的、切換配色/週期/策略等互動路徑。

## 不做的事(明確排除)

- 不做即時報價(所有資料皆為建置時的靜態快照)。
- 不還原 Shioaji、AI 研究團隊、選股獵鷹分頁。
- 不設定自動化資料更新(GitHub Actions),先手動執行 script。
- 不使用任何前端框架/建置工具(React/Vue/Webpack/npm),純 HTML/CSS/JS + Plotly CDN,降低教學與維護門檻。
