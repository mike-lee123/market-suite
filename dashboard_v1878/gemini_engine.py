"""
gemini_engine.py — 用 Gemini Pod(pod_graph)產出一檔研報,輸出格式與 Claude 版一致

對外:
  run_report(code, wd, *, focus="") -> dict     跑完整 6 節點,寫 memo + report-data.json,回傳 report-data dict

report-data.json schema 見 .claude/skills/equity-research-team/SKILL.md,直接餵 build_pdf.py。

單檔用法:
  python gemini_engine.py 2330
"""
from __future__ import annotations

import os
import sys
import json
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# Gemini 版落地到 research/<code>.TW-<date>-gemini/,永不與 Claude 版同目錄互相覆蓋
os.environ.setdefault("RESEARCH_WORKDIR_SUFFIX", "-gemini")

import research_bridge_v1878 as rb          # make_workdir / build_inputs_json_v1878 / REPO_ROOT
from pod_graph import research_graph

DISCLAIMER = "本報告由 AI 研究團隊(Gemini 引擎)產生,僅供教育與研究用途,不構成投資建議。"
ANALYSTS = ["投研總監", "總經策略師", "產業分析師", "基本面分析師", "量化技術分析師", "反方風控官"]

# 英文評級 → 專案中文桶(對得上 batch_research._RATING)
_RATING_MAP = {
    "Strong Buy": "買進", "Overweight": "買進(分批)", "Neutral": "中立",
    "Underweight": "偏空", "Strong Sell": "賣出",
}
_ALERT_GATE = {"Low": "PASS", "Medium": "PASS", "High": "CONDITIONAL PASS", "Critical": "BLOCK"}


# --------------------------------------------------------------------------- #
def _num(v, d=0.0):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return d


def _stance_from_signals(sig: dict) -> str:
    if not sig:
        return "neutral"
    bull = bool((sig.get("macd_enhanced") or {}).get("valid")) or bool((sig.get("s2560") or {}).get("is_buy"))
    bear = bool((sig.get("rsi_divergence") or {}).get("bearish"))
    if bull and not bear:
        return "bullish"
    if bear and not bull:
        return "bearish"
    return "neutral"


def _clip(v, lo, hi):
    return max(lo, min(hi, v))


def _first_sentence(s: str, n: int = 40) -> str:
    s = (s or "").strip().replace("\n", " ")
    for sep in ("。", ".", "!", "?", ";"):
        if sep in s:
            s = s.split(sep)[0]
            break
    return s[:n]


# --------------------------------------------------------------------------- #
def _to_report_data(code: str, inp: dict, fs: dict) -> dict:
    macro = fs["macro"]; industry = fs["industry"]; fund = fs["fundamental"]
    tech = fs["technical"]; risk = fs["risk_review"]; verdict = fs["final_verdict"]
    sig = inp.get("strategy_signals") or {}

    price_last = _num((inp.get("price") or {}).get("last")) or _num(verdict.weighted_target_price)
    rating = _RATING_MAP.get(verdict.rating, "中立")
    gate = _ALERT_GATE.get(risk.alert_level, "CONDITIONAL PASS")
    if gate == "BLOCK" and rating in ("買進", "買進(分批)"):
        rating = "中立"                                   # SKILL 規則:BLOCK 不得為買進

    # 目標價:bear ≤ base ≤ bull(數字亂了就排序)
    bear, base, bull = _num(risk.bear_case_target), _num(verdict.weighted_target_price), _num(fund.fair_value_target)
    trio = sorted(x for x in (bear, base, bull) if x)
    if len(trio) == 3:
        bear, base, bull = trio
    elif base:
        bear = bear or round(base * 0.85, 2)
        bull = bull or round(base * 1.15, 2)

    macro_conf = int(_clip(round(100 - _num(macro.risk_score) * 8), 20, 90))
    fund_conf = int(_clip(round(55 + _num(fund.upside_potential) * 0.6), 20, 90))
    fund_stance = "bullish" if fund.upside_potential > 5 else "bearish" if fund.upside_potential < -5 else "neutral"

    sections = [
        {"id": "macro", "title": "總經與資金環境", "author": "總經策略師",
         "stance": macro.stance.lower(), "confidence": macro_conf,
         "body_md": (f"**立場:** {macro.stance} ｜ **總經風險評分:** {_num(macro.risk_score)}/10\n\n"
                     f"### 流動性與央行週期\n{macro.liquidity_cycle}\n\n"
                     f"### 主權 AI 與財政資本支出\n{macro.sovereign_capex_impact}")},
        {"id": "industry", "title": "產業結構與競爭", "author": "產業分析師",
         "stance": "bullish", "confidence": 60,
         "body_md": (f"**成長週期階段:** {industry.growth_sustainability}\n\n"
                     f"### 供應鏈與先進封裝\n{industry.supply_chain_health}\n\n"
                     f"### 雲端巨頭資本支出\n{industry.hyperscaler_capex_trend}\n\n"
                     f"### 護城河\n{industry.competitive_moat}")},
        {"id": "fundamental", "title": "財報拆解與估值", "author": "基本面分析師",
         "stance": fund_stance, "confidence": fund_conf,
         "body_md": (f"**合理價:** {_num(fund.fair_value_target)} ｜ **潛在上檔:** {_num(fund.upside_potential)}%\n\n"
                     f"### 營收動能與毛利\n{fund.revenue_quality}\n\n"
                     f"### 估值邏輯\n{fund.valuation_model}")},
        {"id": "technical", "title": "價格結構與籌碼", "author": "量化技術分析師",
         "stance": _stance_from_signals(sig), "confidence": 55,
         "body_md": (f"### 趨勢結構\n{tech.trend_structure}\n\n"
                     f"### 關鍵支撐 / 壓力\n{tech.key_support_resistance}\n\n"
                     f"### 量能與波動\n{tech.volatility_and_volume}\n\n"
                     f"### 進場策略\n{tech.entry_strategy}")},
    ]

    vulns = list(risk.structural_vulnerabilities or [])
    dev = {
        "kill_shots": [{"assumption": v, "probability": "中", "evidence": _first_sentence(risk.valuation_pushback, 80)}
                       for v in vulns[:3]],
        "premortem": vulns[:4] or ["估值假設打到保守值後的下行情境"],
        "red_flags": [{"item": "風控穿透質疑", "finding": str(risk.valuation_pushback)}],
        "bear_case_note": f"最差情境目標價 {bear}。{risk.valuation_pushback}",
        "verdict": gate,
    }

    highlights = [
        f"最終評級 {rating},加權目標價 {base}(現價 {price_last},上檔 {round((base / price_last - 1) * 100, 1) if price_last else 0}%)。",
        _first_sentence(fund.revenue_quality, 60) or "基本面:見內文。",
        f"反方 Gate:{gate}。最大風險:{(vulns[0] if vulns else _first_sentence(risk.valuation_pushback, 50))}",
    ]
    bull_thesis = [
        {"claim": _first_sentence(macro.liquidity_cycle, 50), "support": f"總經 / 立場 {macro.stance}", "status": "CONFIRMED"},
        {"claim": _first_sentence(industry.competitive_moat, 50), "support": "產業 / 護城河", "status": "CONFIRMED"},
        {"claim": _first_sentence(fund.valuation_model, 50), "support": f"基本面 / 上檔 {_num(fund.upside_potential)}%",
         "status": "CONFIRMED" if fund.upside_potential > 0 else "WEAK"},
    ]

    return {
        "ticker": inp.get("ticker", code),
        "company": inp.get("name", code),
        "period": inp.get("period", ""),
        "as_of_date": inp.get("as_of", datetime.date.today().isoformat()),
        "rating": rating,
        "price": {"last": price_last, "currency": (inp.get("price") or {}).get("currency", "TWD")},
        "target": {"bear": bear, "base": base, "bull": bull},
        "one_liner": _first_sentence(verdict.executive_summary, 40),
        "gate": {"verdict": gate, "summary": _first_sentence(risk.valuation_pushback, 120)},
        "highlights": highlights,
        "bull_thesis": bull_thesis,
        "sections": sections,
        "devils_advocate": dev,
        "monitor": [
            {"metric": "停損 / 部位控制", "up_trigger": "—", "down_trigger": verdict.stop_loss_boundary},
            {"metric": "基準目標價達成度", "up_trigger": f"站上 {bull} → 上修", "down_trigger": f"跌破 {bear} → 下修"},
        ],
        "sources": [],
        "analysts": ANALYSTS,
        "disclaimer": DISCLAIMER,
        "_verdict_probs": {"bull": _num(verdict.bull_prob), "base": _num(verdict.base_prob), "bear": _num(verdict.bear_prob)},
        "_engine": f"gemini:{os.environ.get('GEMINI_MODEL', 'gemini-flash-latest')}",
    }


# --------------------------------------------------------------------------- #
def _write_memos(wd: str, rd: dict, fs: dict):
    sec = {s["id"]: s for s in rd["sections"]}
    for sid, fn in (("macro", "macro.md"), ("industry", "industry.md"),
                    ("fundamental", "fundamental.md"), ("technical", "technical.md")):
        s = sec[sid]
        with open(os.path.join(wd, fn), "w", encoding="utf-8") as f:
            f.write(f"# {s['title']}（{s['author']}）\n\n"
                    f"stance: {s['stance']} ｜ confidence: {s['confidence']}/100\n\n{s['body_md']}\n")
    da = rd["devils_advocate"]
    with open(os.path.join(wd, "20-devils-advocate.md"), "w", encoding="utf-8") as f:
        f.write(f"# 反方風控官意見\n\n**Gate 裁決:{da['verdict']}**\n\n## 致命假設\n"
                + "".join(f"- {k['assumption']}(機率 {k['probability']}):{k['evidence']}\n" for k in da["kill_shots"])
                + "\n## Pre-mortem\n" + "".join(f"- {x}\n" for x in da["premortem"])
                + f"\n## 估值壓力測試\n{da['bear_case_note']}\n")
    v = rd.get("_verdict_probs", {})
    with open(os.path.join(wd, "30-final.md"), "w", encoding="utf-8") as f:
        f.write(f"# 最終決議 — {rd['company']}（{rd['ticker']}）\n\n"
                f"- 評級:{rd['rating']}\n- 目標價 bear/base/bull:{rd['target']['bear']} / {rd['target']['base']} / {rd['target']['bull']}\n"
                f"- 機率 牛/基準/熊:{v.get('bull')} / {v.get('base')} / {v.get('bear')}\n"
                f"- 反方 Gate:{rd['gate']['verdict']}\n\n## 決策要點\n{fs['final_verdict'].executive_summary}\n")


# --------------------------------------------------------------------------- #
def run_report(code: str, wd: str, *, focus: str = "") -> dict:
    """跑完整 Gemini Pod。wd 需已有 inputs.json(沒有就自己補一次)。回傳 report-data dict。"""
    code = code.strip().replace(".TW", "").replace(".TWO", "")
    ipath = os.path.join(wd, "inputs.json")
    if not os.path.isfile(ipath):
        rb.build_inputs_json_v1878(code, wd, mode="quick", user_focus=focus)
    inp = json.load(open(ipath, encoding="utf-8"))

    payload = {
        "ticker": inp.get("ticker", f"{code}.TW"),
        "name": inp.get("name", code),
        "market": inp.get("market", "TW"),
        "period": inp.get("period", ""),
        "current_price": _num((inp.get("price") or {}).get("last")),
        "raw_context": (focus or "") + "\n(質化脈絡以量化地面真相為準;無外部新聞來源)",
        "quant_data": inp,
    }
    fs = research_graph.invoke(payload)
    rd = _to_report_data(code, inp, fs)

    with open(os.path.join(wd, "report-data.json"), "w", encoding="utf-8") as f:
        json.dump(rd, f, ensure_ascii=False, indent=2, default=str)
    _write_memos(wd, rd, fs)
    with open(os.path.join(wd, "run.log"), "w", encoding="utf-8") as f:
        f.write(f"gemini_engine OK {datetime.datetime.now().isoformat()} "
                f"rating={rd['rating']} base={rd['target']['base']} gate={rd['gate']['verdict']}\n")
    return rd


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python gemini_engine.py <代號> [關注點]"); sys.exit(1)
    _code = sys.argv[1]
    _focus = sys.argv[2] if len(sys.argv) > 2 else ""
    _wd = rb.make_workdir(_code)
    print(f"工作目錄: {_wd}")
    _rd = run_report(_code, _wd, focus=_focus)
    print(json.dumps({k: _rd[k] for k in ("ticker", "rating", "target", "gate", "one_liner")},
                     ensure_ascii=False, indent=2))
    _bp = os.path.join(rb.REPO_ROOT, ".claude", "skills", "equity-research-team", "scripts", "build_pdf.py")
    import subprocess
    subprocess.run([sys.executable, _bp, os.path.join(_wd, "report-data.json")], cwd=rb.REPO_ROOT)
