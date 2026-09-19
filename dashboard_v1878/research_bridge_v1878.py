"""
research_bridge_v1878.py — 「併武 V18.78 FullMaster」↔ 6 人 AI 研究團隊 黏合層

v18.78 是單檔巨石(import 時就會執行整個 Streamlit app),所以**不能直接 import 它**。
先把純函式抽到 bw_core.py(見 README-v1878.md 第一節),本檔對 bw_core 相依。

放到與 v18.78 主程式同一層。提供:
  build_inputs_json_v1878(...)   用 bw_core 的引擎組出 inputs.json(含 strategy_signals)
  run_research(...) / poll_report(...) / make_workdir(...)   同 research_bridge.py(headless 觸發 + 輪詢)
"""
from __future__ import annotations

import os
import sys
import json
import time
import shutil
import datetime
import threading
import subprocess
from typing import Optional

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))          # dashboard_v1878/ 子目錄

# 全批(含平行 prep 執行緒)最多 2 個併發打 Yahoo,避免自我限流拖成每檔 60s+
_YAHOO_GATE = threading.Semaphore(int(os.environ.get("RESEARCH_YAHOO_CONCURRENCY", "2")))
_MACRO_LOCK = threading.Lock()


def _find_suite_root(start: str) -> str:
    """往上找含 .claude/skills/equity-research-team 的 monorepo 根;可用 MARKET_SUITE_ROOT 覆寫。"""
    env = os.environ.get("MARKET_SUITE_ROOT")
    if env and os.path.isdir(os.path.join(env, ".claude", "skills", "equity-research-team")):
        return os.path.abspath(env)
    d = start
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".claude", "skills", "equity-research-team")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return start


REPO_ROOT = _find_suite_root(_HERE)                         # monorepo 根(含共用 .claude/ 與 research/)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# --- 從抽出的核心模組匯入(bw_core.py 需與本檔同層) ---
try:
    from bw_core import (
        fetch_from_yahoo_chart_api,
        AdvancedWyckoffQuantEngine,
        estimate_active_chips,
        detect_rsi_divergence_active,
        evaluate_fibonacci_strategy,
        evaluate_macd_enhanced_strategy,
        scan_2560_strategy,
        scan_dual_bollinger_strategy,
        evaluate_box_tactics_rsi14,
        evaluate_escape_resonance_sop,
        fetch_global_us_dashboard_data,
        ZHTW_MAP,
        OTC_LIST,
        DEFAULT_TDCC_1000,
    )
    BW_CORE_OK = True
except Exception as _e:  # noqa
    BW_CORE_OK = False
    _IMPORT_ERR = _e

try:
    import logging as _logging
    for _n in ("yfinance", "urllib3", "peewee"):
        _logging.getLogger(_n).setLevel(_logging.CRITICAL)  # 消掉 .TW→.TWO 過程的 404 雜訊
    import yfinance as yf
except Exception:
    yf = None


# --------------------------------------------------------------------------- #
def _f(v, nd=2):
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return None


_MACRO_CACHE = {"t": 0.0, "data": {}}


def _cached_macro(ttl: int = 600) -> dict:
    """macro_ribbon 對所有台股相同 → 每個 process 最多每 10 分鐘打一次 Yahoo。
    平行 prep 時用 lock 擋住 thundering herd:只有第一個執行緒去抓,其餘等它。"""
    if time.time() - _MACRO_CACHE["t"] <= ttl and _MACRO_CACHE["data"]:
        return _MACRO_CACHE["data"]
    with _MACRO_LOCK:
        if time.time() - _MACRO_CACHE["t"] > ttl or not _MACRO_CACHE["data"]:
            try:
                with _YAHOO_GATE:
                    _MACRO_CACHE["data"] = fetch_global_us_dashboard_data() or {}
                _MACRO_CACHE["t"] = time.time()
            except Exception:
                pass
    return _MACRO_CACHE["data"]


def _yf_fundamentals(code: str, otc: bool = False) -> dict:
    """yf.Ticker(...).info 每次 3–10s,是 prep 第二大成本。
    只在硬性例外時才換後綴重試;抓到資料但沒基本面欄位就收手,不再花第二次 .info。"""
    if yf is None:
        return {}
    import contextlib, io
    order = (".TWO", ".TW") if otc else (".TW", ".TWO")
    for suff in order:
        try:
            with _YAHOO_GATE, contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                info = yf.Ticker(f"{code}{suff}").info or {}
        except Exception:
            continue                      # 只有真的丟例外才試下一個後綴
        if info.get("trailingPE") or info.get("marketCap"):
            dy = info.get("dividendYield")
            return {
                "pe": _f(info.get("trailingPE")),
                "pb": _f(info.get("priceToBook")),
                "roe_pct": _f((info.get("returnOnEquity") or 0) * 100),
                "eps_ttm": _f(info.get("trailingEps")),
                "dividend_yield_pct": _f(dy * 100 if dy and dy < 1 else dy),
                "rev_growth_yoy_pct": _f((info.get("revenueGrowth") or 0) * 100),
                "profit_margin_pct": _f((info.get("profitMargins") or 0) * 100),
                "market_cap": info.get("marketCap"),
            }
        break                            # 抓到了但無基本面 → skill 會自己 WebSearch 補,不值得再打一次
    return {}


def build_inputs_json_v1878(
    code: str,
    workdir: str,
    *,
    mode: str = "quick",
    user_focus: str = "",
    period: Optional[str] = None,
) -> str:
    """用 bw_core 引擎組出 inputs.json 並寫入 workdir。回傳路徑。"""
    if not BW_CORE_OK:
        raise RuntimeError(f"無法匯入 bw_core:{_IMPORT_ERR}. 請先依 README-v1878.md 抽出 bw_core.py")

    os.makedirs(workdir, exist_ok=True)
    code = code.strip().replace(".TW", "").replace(".TWO", "")
    name = ZHTW_MAP.get(code, f"個股{code}")
    now = datetime.date.today()
    q = (now.month - 1) // 3 or 4
    period = period or f"{now.year if q != 4 else now.year - 1}Q{q}"

    payload: dict = {
        "ticker": f"{code}.TWO" if code in OTC_LIST else f"{code}.TW",
        "market": "TW",
        "name": name,
        "period": period,
        "as_of": now.isoformat(),
        "mode": mode,
        "user_focus": user_focus or "",
    }

    # 逐段計時:設 RESEARCH_PREP_TIMING=1 就會印 [code] prep/<段> <秒>
    _timing = os.environ.get("RESEARCH_PREP_TIMING")
    _clk = [time.time()]

    def _lap(tag: str):
        if _timing:
            print(f"[{code}] prep/{tag} {time.time() - _clk[0]:.1f}s", flush=True)
        _clk[0] = time.time()

    df = None
    _tries = int(os.environ.get("RESEARCH_YAHOO_RETRIES", "2"))  # 內部已對 3 個後綴各重試,外層 2 次就夠
    for _try in range(_tries):
        with _YAHOO_GATE:                       # 全批最多 N 個併發打 Yahoo,避免自我限流
            df = fetch_from_yahoo_chart_api(code, "2y")
        if df is not None and not df.empty and len(df) >= 60:
            break
        if _try < _tries - 1:                   # 最後一圈失敗就直接放棄,不空等
            time.sleep(1 + _try)
    _lap("yahoo")
    if df is None or df.empty or len(df) < 60:
        raise RuntimeError(f"[{code}] 取不到足夠歷史資料(Yahoo 限流,已重試 {_tries} 次)")

    eng = AdvancedWyckoffQuantEngine().process(df)
    last, prev = eng.iloc[-1], eng.iloc[-2]
    close = float(last["Close"])

    payload["price"] = {
        "last": _f(close), "currency": "TWD",
        "chg": _f(close - float(prev["Close"])),
        "chg_pct": _f((close / float(prev["Close"]) - 1) * 100),
        "week52_high": _f(df["Close"].tail(252).max()),
        "week52_low": _f(df["Close"].tail(252).min()),
    }
    payload["ohlcv_summary"] = {
        "period_covered": "2y", "interval": "1d",
        "ma": {
            "20": _f(last.get("MA20")),
            "13": _f(last.get("MA_13")),
            "60": _f(df["Close"].rolling(60).mean().iloc[-1]),
            "240": _f(df["Close"].rolling(240).mean().iloc[-1]) if len(df) >= 240 else None,
        },
        "return_1m_pct": _f(df["Close"].pct_change(21).iloc[-1] * 100) if len(df) > 21 else None,
        "return_3m_pct": _f(df["Close"].pct_change(63).iloc[-1] * 100) if len(df) > 63 else None,
    }

    ma20 = float(last.get("MA20", close)) or close
    payload["indicators"] = {
        "kd": {"k": _f(last.get("k")), "d": _f(last.get("d")),
               "cross": ("golden" if (last.get("k", 0) > last.get("d", 0) and prev.get("k", 0) <= prev.get("d", 0))
                         else "dead" if (last.get("k", 0) < last.get("d", 0) and prev.get("k", 0) >= prev.get("d", 0))
                         else "none")},
        "rsi14": _f(last.get("RSI_14")),
        "macd": {"dif": _f(last.get("MACD_Line")), "hist": _f(last.get("MACD_Hist")),
                 "state": "bull" if float(last.get("MACD_Hist", 0)) > 0 else "bear"},
        "bias20_pct": _f((close - ma20) / ma20 * 100),
        "roc12": _f(last.get("ROC_12")),
    }

    _lap("engine")
    payload["fundamentals"] = _yf_fundamentals(code, otc=(code in OTC_LIST))
    _lap("yf_info")

    # ---- strategy_signals:v18.78 引擎的既有裁決 ----
    is_bull_div, is_bear_div = detect_rsi_divergence_active(eng)
    active_chips = float(estimate_active_chips(eng).iloc[-1])
    tdcc = float(DEFAULT_TDCC_1000.get(code, 60.0))
    rsi14 = float(last.get("RSI_14", 50.0))
    vol_ratio = float(last.get("Vol_Surge_Ratio", 1.0))
    mfi = float(last.get("MFI", 55.0))
    cyc20 = float(last.get("CYC20", close))

    box_tag, box_plan = evaluate_box_tactics_rsi14(
        close, float(last.get("MA_13", close * 0.95)), close * 0.90, rsi14,
        int(last.get("Squeeze_Pct", 75)), vol_ratio, 0, 0, 85,
        is_bull_div, is_bear_div, tdcc, active_chips, mfi, cyc20,
    )
    esc_tag, esc_plan = evaluate_escape_resonance_sop(
        close, float(last.get("ROC_12", 0)), float(last.get("ROC_MA6", 0)),
        float(last.get("MACD_Line", 0)), float(last.get("MACD_Hist", 0)),
        float(prev.get("MACD_Hist", 0)), float(last.get("CYC5", close)),
        float(prev.get("CYC5", close)), float(last.get("CYC13", close)), float(last.get("CYC34", close)),
    )
    fib = evaluate_fibonacci_strategy(df, lookback=60)
    macd_e = evaluate_macd_enhanced_strategy(df, df, min_risk_reward_ratio=2.0)
    _, s2560_buy, s2560_sl, s2560_tg = scan_2560_strategy(df)
    _, bb_buy, bb_sl = scan_dual_bollinger_strategy(df)

    payload["strategy_signals"] = {
        "_note": "v18.78 引擎既有裁決;技術面分析師交叉驗證與解讀,不重算",
        "wyckoff_box": box_tag, "wyckoff_box_plan": box_plan,
        "escape_resonance": esc_tag, "escape_plan": esc_plan,
        "fibonacci": {"valid": bool(fib.get("is_valid")),
                      "fib_0618": _f((fib.get("fib_levels") or {}).get("Fib_0618")),
                      "rsi14": fib.get("rsi_val")},
        "macd_enhanced": {"valid": bool(macd_e.get("is_valid_trade")),
                          "entry": macd_e.get("建議進場價"), "atr_stop": macd_e.get("ATR動態止損價"),
                          "target": macd_e.get("預期停利價"), "rr": macd_e.get("實測盈虧比"),
                          "daily_uptrend": bool(macd_e.get("大週期趨勢多頭"))},
        "s2560": {"is_buy": bool(s2560_buy), "stop": _f(s2560_sl), "target": _f(s2560_tg)},
        "dual_bollinger": {"is_buy": bool(bb_buy), "stop": _f(bb_sl)},
        "rsi_divergence": {"bullish": bool(is_bull_div), "bearish": bool(is_bear_div)},
        "active_chips_pct": _f(active_chips, 1),
        "tdcc_top1000_pct": _f(tdcc, 1),
    }

    _lap("signals")
    try:
        gd = _cached_macro()                    # 批次時各檔共用,不重打 Yahoo
        payload["macro_ribbon"] = {
            k: {"price": _f(v.get("price")), "chg_pct": _f(v.get("change"))}
            for k, v in gd.items()
        }
    except Exception:
        pass
    _lap("macro")

    out = os.path.join(workdir, "inputs.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, default=str)
    return out


# --------------------------------------------------------------------------- #
#  觸發 / 輪詢(與 research_bridge.py 同;此處自帶一份以便單檔投放)
# --------------------------------------------------------------------------- #
def _find_claude() -> Optional[str]:
    """優先序:明確指定 > 目前正在跑的 Claude Code 執行檔 > PATH 上的 claude。
    PATH 上常是舊的 npm 全域版(如 1.0.120),subagent / 模型解析行為過時會 404;
    CLAUDE_CODE_EXECPATH 是當前 session 的執行檔,版本一定對得上。"""
    for c in (os.environ.get("CLAUDE_CLI_PATH"),
              os.environ.get("CLAUDE_CODE_EXECPATH"),
              shutil.which("claude")):
        if c and os.path.isfile(c):
            return c
    return shutil.which("claude")  # 最後退路(讓後面拋出可讀的錯誤)


def make_workdir(code: str) -> str:
    # RESEARCH_WORKDIR_SUFFIX 讓不同引擎(如 Gemini 版設 "-gemini")各自落地,不互相覆蓋
    suf = os.environ.get("RESEARCH_WORKDIR_SUFFIX", "")
    d = os.path.join(REPO_ROOT, "research", f"{code}.TW-{datetime.date.today().isoformat()}{suf}")
    os.makedirs(d, exist_ok=True)
    return d


def run_research(workdir: str, code: str, name: str, mode: str = "quick",
                 *, model: Optional[str] = None, tw_context: str = "",
                 skip_pdf: bool = False) -> subprocess.Popen:
    """觸發 6 人團隊。批次加速可選:
      model      —— 傳給 claude 的 --model(如 haiku,分析更快、質化略淺)
      tw_context —— 台股總經 / 半導體產業共用背景;有值時各組直接引用,個股只查自己的新聞
      skip_pdf   —— 批次階段不出 PDF(排名後再對前 N 名補),省 Chrome 呼叫與競爭
    """
    claude = _find_claude()
    if not claude:
        raise RuntimeError("找不到 claude CLI;請安裝 Claude Code 或設 CLAUDE_CLI_PATH")
    rel = os.path.relpath(workdir, REPO_ROOT).replace("\\", "/")
    ctx_line = (
        f"台股總經與半導體產業共用背景(總經 / 產業段直接引用此框架,只有個股專屬事項才另行 WebSearch):"
        f"{tw_context}\n" if tw_context.strip() else
        "WebSearch 只補月營收、法說會、產業與政策等質化資訊。\n"
    )
    if mode == "screen":
        # 第一段漏斗:一人分析師超輕量快篩,不進 skill 完整 SOP、不寫 memo、不出 PDF
        prompt = (
            f"你是一人股票分析師,對 {name}({code}.TW) 做 60–90 秒快篩。\n"
            f"工作目錄 {rel}/ 有 inputs.json —— 價格 / 技術指標 / 基本面比率(fundamentals.pe、eps_ttm 等)/ "
            f"strategy_signals 皆為地面真相,直接用。\n" + ctx_line +
            f"最多 1 次 WebSearch 查該股「近月營收 YoY / 最近法說會重點 / 產業地位」。\n"
            f"判斷並只寫檔案 {rel}/screen.json,內容為 JSON 物件:\n"
            f'{{"code":"{code}","name":"{name}","rating":"買進|中立|賣出",'
            f'"target_base":<12 個月目標價 = 你預估的未來 12M EPS(以 eps_ttm 為底,套合理成長率)'
            f'× 合理目標本益比(參考 fundamentals.pe 與該股歷史區間、產業地位調整);'
            f'不要直接回推現價>,'
            f'"confidence":<0-100>,"bull":"一句話最強多方","bear":"一句話最大風險"}}\n'
            f"不要寫 memo、不要 report-data.json、不要 PDF、不要 SendUserFile。"
            f"完成後只輸出一行:SCREEN|<rating>|<target_base>。"
        )
    else:
        pdf_line = (
            "不要執行 build_pdf.py(批次階段略過 PDF)。" if skip_pdf else
            f"最後執行 scripts/build_pdf.py 產生 {rel}/report.pdf。"
        )
        prompt = (
            f"使用 equity-research-team skill。標的:{name}({code}.TW),市場:TW,模式:{mode}。\n"
            f"工作目錄 {rel}/ 已有 inputs.json,完全以它為數據來源(價格 / 指標 / 基本面 / "
            f"strategy_signals 皆為地面真相)。\n"
            + ctx_line +
            f"依 SKILL.md 的 {mode} 模式跑完,memo 與 report-data.json 寫進 {rel}/。"
            + pdf_line +
            "不要呼叫 SendUserFile。完成後只輸出一行:DONE|<評級>|<base目標價>。"
        )
    # 只有明確指定(--fast 或 RESEARCH_MODEL)才傳 --model;否則沿用該 CLI 自己設定好的預設,
    # 避免硬指一個 ID 在某些 CLI 版本 / 帳號方案下 subagent 解析不到而 404。
    _model = model or os.environ.get("RESEARCH_MODEL")
    # prompt 走 stdin,不放 argv:Windows 的 claude.CMD 對超長多行參數會打亂旗標(害 --model 失效)
    argv = [claude, "-p", "--permission-mode", "acceptEdits"]
    if _model:
        argv += ["--model", _model]
    log = open(os.path.join(workdir, "run.log"), "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(argv, cwd=REPO_ROOT, stdin=subprocess.PIPE,
                            stdout=log, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except Exception:
        pass
    return proc


def poll_report(workdir: str) -> dict:
    pdf = os.path.join(workdir, "report.pdf")
    dp = os.path.join(workdir, "report-data.json")
    out = {"pdf": os.path.isfile(pdf) and os.path.getsize(pdf) > 0, "data": None, "log_tail": ""}
    if os.path.isfile(dp):
        try:
            out["data"] = json.load(open(dp, encoding="utf-8"))
        except Exception:
            pass
    lg = os.path.join(workdir, "run.log")
    if os.path.isfile(lg):
        try:
            out["log_tail"] = "".join(open(lg, encoding="utf-8", errors="replace").readlines()[-15:])
        except Exception:
            pass
    return out
