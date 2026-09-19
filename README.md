# Monorepo:兩份儀表板共用一個 `.claude/` 研究團隊 skill

## 目標架構

```
market-suite/                          ← monorepo 根(= MARKET_SUITE_ROOT)
├── .claude/                           ← 共用,只有這一份
│   ├── agents/                        ← 6 個 subagent
│   │   research-director.md  macro-strategist.md  industry-analyst.md
│   │   fundamental-analyst.md  technical-analyst.md  devils-advocate.md
│   ├── skills/
│   │   └── equity-research-team/      ← SKILL.md / references/ / assets/ / scripts/
│   └── settings.json                  ← 權限白名單(python / Read,Write research/**)
│
├── research/                          ← 共用產出:research/<TICKER>-<DATE>/{inputs.json,*.md,report.pdf}
│
├── dashboard_modular/                 ← 第一份(app.py 系列)
│   ├── app.py  data_loader.py  indicators.py  charts.py  backtest.py
│   ├── shioaji_client.py  options.py
│   └── research_bridge.py             ← 複製自 dashboard-integration/
│
└── dashboard_v1878/                   ← 第二份(併武 FullMaster)
    ├── bw_ultimate_dashboard_v18.78_dashboard_FullMaster.py
    ├── bw_core.py                     ← 從巨石抽出的純函式層(見 README-v1878.md 第一節)
    └── research_bridge_v1878.py       ← 複製自 dashboard-integration/
```

## 兩支 bridge 如何找到共用 skill

`research_bridge.py` 與 `research_bridge_v1878.py` 都用 `_find_suite_root()`:
從自己所在的子目錄**往上最多 6 層**,找含 `.claude/skills/equity-research-team` 的目錄當 `REPO_ROOT`。
所以只要放在 `market-suite/` 底下任意深度都能自動對上。

保險起見可設環境變數(Docker / systemd / .streamlit/secrets):

```bash
export MARKET_SUITE_ROOT=/path/to/market-suite
```

`run_research()` 會用 `cwd=REPO_ROOT` 執行 `claude -p`,所以 `.claude/skills` 一定被 CLI 找到;
`make_workdir()` 一律寫到 `market-suite/research/`,兩份儀表板看到同一批研報。

## 組裝步驟

1. 建 `market-suite/`,把兩份儀表板各自 clone / 複製進 `dashboard_modular/`、`dashboard_v1878/`。
2. 把本專案的 `.claude/agents/` 和 `.claude/skills/equity-research-team/` 複製到 `market-suite/.claude/`。
3. `dashboard_modular/`:放 `research_bridge.py`,在 `app.py` 加分頁(見 `README-integration.md` 第二節)。
4. `dashboard_v1878/`:抽 `bw_core.py`(見 `README-v1878.md` 第一節),放 `research_bridge_v1878.py`,在 `col_sel` selectbox 加項(見 `README-v1878.md` 第四節)。
5. `market-suite/.claude/settings.json`:
   ```json
   { "permissions": { "allow": ["Bash(python:*)", "Read(./research/**)", "Write(./research/**)", "WebSearch", "WebFetch"] } }
   ```
6. 兩份儀表板分別 `streamlit run`,各自都有「🧠 6 人 AI 研究團隊」入口,產出的 PDF 都落在 `market-suite/research/`。

## 部署備註

- 執行環境要有 Claude Code CLI(`claude`)可執行 + `ANTHROPIC_API_KEY`;或設 `CLAUDE_CLI_PATH`。
- Chrome / Edge(`build_pdf.py` 產 PDF 用,會自動偵測)。
- 兩份儀表板可各自獨立部署(不同容器 / port),只要都掛載同一個 `market-suite/` volume,就共用 skill 與 `research/`。
- `equity-research-team` skill 只維護一份;改分析框架 / 反方協定 / PDF 版面,兩份儀表板同時生效。

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
