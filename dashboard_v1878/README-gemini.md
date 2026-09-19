# Gemini 引擎(省錢版 6 人投研 Pod)

Claude 版(`batch_research.py` → `claude -p` → equity-research-team skill)的替身:
用 **LangGraph + Gemini** 跑同一套 6 角色流程,吃同一份 `inputs.json`,吐同一個 `report-data.json` schema,走同一支 `build_pdf.py`。

```
inputs.json (bw_core 真 TA 引擎)
      │
      ▼
pod_graph.research_graph          總經→產業→基本面→技術→反方風控→總監  (Gemini,每節點注入 inputs.json 對應切片當地面真相)
      │
      ▼
gemini_engine._to_report_data     6 個 Pydantic 物件  →  report-data.json (SKILL.md schema)
      │
      ▼
build_pdf.py                      report.pdf
```

## 檔案

| 檔案 | |
|---|---|
| `pod_graph.py` | LangGraph 圖 + Pydantic 輸出結構 + `inputs.json` 切片注入。金鑰讀取吃 BOM 容錯 |
| `gemini_engine.py` | `run_report(code, wd)`:inputs.json → Pod → 映射 report-data.json + 寫 memo。也可單檔 CLI:`python gemini_engine.py 2330` |
| `batch_gemini.py` | 批次:ThreadPool 併發,沿用 `batch_research` 的 prep / score / 排行榜 |

輸出落地 `research/<code>.TW-<date>-gemini/`(靠 `RESEARCH_WORKDIR_SUFFIX=-gemini`,與 Claude 版分開,不互相覆蓋)。

## 用法

```powershell
cd "C:\Users\mikelee\Desktop\market-suite\dashboard_v1878"
$env:PYTHONUTF8 = "1"

python gemini_engine.py 2330                    # 單檔 + PDF
python batch_gemini.py 2330 2454 2317 --parallel 2   # 批次 + 排行榜
```

排行榜:`research/_batch/<時間>/leaderboard.{csv,json,xlsx}`

## 環境變數

| 變數 | 預設 | 說明 |
|---|---|---|
| `GEMINI_API_KEY` | — | 直接設環境變數;或放 `market-suite/.env` 一行 `GEMINI_API_KEY=...`(無 BOM);找不到才 fallback 去 `ai-research-pod/.env` |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | 最便宜、免費層額度獨立。要更強:`gemini-flash-latest` |
| `GEMINI_NODE_DELAY` | `2` | 節點間秒數。免費層 RPM 緊就調大(如 `4`) |
| `GEMINI_ENV_FILE` | — | 指定 .env 路徑 |
| `RESEARCH_WORKDIR_SUFFIX` | `-gemini`(本引擎自帶) | 落地目錄後綴 |

## ⚠️ 免費層額度

Gemini API 免費層:**每模型每天 20 次請求**(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`)。
**一份研報 = 6 次請求** → 免費層一天約 3 份。

要做批次(取代 Claude 省錢)必須在 Google Cloud 專案**開帳單(pay-as-you-go)**。
flash-lite 付費約 $0.10 / 1M input、$0.40 / 1M output —— 仍遠比 Claude Sonnet 便宜。

## 相依套件

```
langgraph  langchain-google-genai  pydantic  python-dotenv
```
(PDF 用 `build_pdf.py` 的 Chrome headless,不需要 Playwright / Jinja2。)

## 與 Claude 版的差異

| | Claude 版 | Gemini 版 |
|---|---|---|
| 觸發 | `claude -p` 子行程 | process 內呼叫 LangGraph |
| 平行 | full 模式四分析師真平行 | 圖是序列(節點間 sleep) |
| memo 長度 | 長 | flash-lite 較精簡 |
| 兩段漏斗 screen/funnel | 有 | 無(一律完整跑) |
| 成本 | 高 | 低(付費層) |
| 質化來源 | WebSearch 補新聞/法說 | 無外部來源,純靠 inputs.json + 模型知識 |
