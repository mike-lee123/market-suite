# dashboard_v1878 雲端部署(Streamlit Community Cloud)— 設計文件

日期:2026-09-19

## 背景與目標

`market-suite/docs/` 的 GitHub Pages 靜態網站已完成部署,但明確排除了 Shioaji 即時盤口與即時 Yahoo 行情,因為靜態網站沒有伺服器。使用者希望把 `dashboard_v1878/dashboard.py`(併武台股量化交易系統 V18.78,原本只在本機執行的 Streamlit app)部署到一台真正能長期執行 Python 的伺服器上,讓 Shioaji API 與即時 Yahoo 資料真的能動起來。

## 範圍與限制(使用者已確認)

- **預算**:先用 Streamlit Community Cloud 免費方案試,不租付費 VPS。
- **功能取捨**:免費方案裝不了 Claude Code CLI,所以「🧠 6 人 AI 研究團隊」分頁在雲端會不能用;其餘所有分頁(Shioaji 即時盤口、Yahoo 即時資料、技術指標、多週期共振、Fibonacci、2560 戰法、雙重布林等)都要能正常運作。
- **風險評估**:永豐證券的交易 API 是否對國外(Streamlit Community Cloud 伺服器多半在美國)IP 連線有限制或行為不一致,目前未知——所以先做最小改動的可行性測試,確認能連線後才進行完整部署的收尾工作。

## 已勘查的技術事實

- `dashboard_v1878/dashboard.py` 的 Shioaji 登入邏輯(`get_global_shioaji_client`,`dashboard.py:360-364`)已經是「側邊欄 `st.text_input(type="password")` 讓使用者自行輸入 API Key/Secret」的設計(`dashboard.py:544-547`),金鑰不落地、不寫死在程式碼裡,部署到雲端不需要改這部分。
- Shioaji 用戶端寫死 `simulation=True`(`dashboard.py:363`),只會連模擬環境,不會有真實下單風險。
- 「🧠 6 人 AI 研究團隊」分頁的 `research_bridge_v1878` 是**延遲 import**(只在 `elif col_sel == "🧠 6 人 AI 研究團隊":` 分支內,`dashboard.py:1242`),不是在檔案頂部——代表雲端環境缺少 `claude` CLI 只會讓「進到這個分頁、按下執行」時噴錯,不會讓整個 app 在啟動時就崩潰。點擊研報按鈕的呼叫路徑已經有 `try/except RuntimeError` 並用 `st.error()` 顯示,不是未捕捉的例外。
- `dashboard_v1878/requirements.txt` 目前只有套件名稱、沒有版本鎖定(`streamlit numpy pandas plotly requests yfinance shioaji`)。

## 兩階段計畫

### 階段一:可行性測試(零程式碼改動)

目的:單純確認「Streamlit Community Cloud 的國外主機能不能連上永豐 Shioaji 模擬環境」,不處理其他任何問題。

步驟(使用者在瀏覽器操作,由 assistant 從旁指導/協助排除障礙):

1. 到 https://share.streamlit.io 用 GitHub 帳號(`mike-lee123`)登入並授權 Streamlit 存取 `market-suite` repo。
2. 建立新 app:
   - Repository: `mike-lee123/market-suite`
   - Branch: `main`
   - Main file path: `dashboard_v1878/dashboard.py`
3. 等待建置完成(Streamlit Cloud 會讀 `dashboard_v1878/requirements.txt` 安裝套件——若因為根目錄找不到 requirements.txt 而建置失敗,才需要調整設定或搬移檔案,屆時再處理)。
4. 建置成功後,在側邊欄貼上使用者自己的永豐**模擬環境**API Key/Secret,確認畫面顯示「🟢 Shioaji 實戰通道已連線 (模擬模式)」而不是連線失敗或逾時。

**判定結果:**
- ✅ 能連線 → 進入階段二。
- ❌ 連不上/逾時/永豐端拒絕 → 記錄下實際錯誤訊息,重新評估(可能需要改用台灣本地的 VPS,或接受這個功能只能在本機使用)。

### 階段二:完整部署收尾(僅在階段一成功後進行)

1. **`requirements.txt` 版本鎖定**:避免未來 Streamlit Cloud 重建時因套件更新造成不相容,固定目前測試通過的版本號。
2. **AI 研究團隊分頁優雅降級**:目前點擊執行按鈕才會噴錯;改成在分頁一開始就偵測 `claude` CLI 是否存在(如 `shutil.which("claude")`),不存在就顯示提示訊息(例如「此功能需要在本機執行環境使用,雲端版本暫不支援」)並隱藏執行按鈕,而不是等使用者點下去才看到錯誤。
3. **Streamlit 設定檔**(如需要):視實際部署時遇到的問題決定是否需要 `dashboard_v1878/.streamlit/config.toml`(例如調整 theme 或關閉某些警告)。
4. 更新 `README.md`,補上「雲端版 dashboard_v1878(Shioaji + 即時 Yahoo)」的部署與使用說明,和目前 GitHub Pages 靜態網站的段落並列,說明兩者是獨立、互不影響的部署。

## 不做的事

- 不在免費方案上想辦法讓「AI 研究團隊」分頁可用(需要付費 VPS 才能裝 CLI,超出目前預算範圍)。
- 不改動 Shioaji 連線邏輯本身(維持模擬環境、使用者自行輸入金鑰的設計)。
- 不影響、不修改現有的 `docs/` GitHub Pages 靜態網站——兩者是同一個 repo 下完全獨立的兩個部署目標。
