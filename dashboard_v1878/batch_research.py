"""
batch_research.py — 對一組台股代號跑 6 人 AI 團隊研報,產出綜合排行榜(平行 + 兩段漏斗)

用法:
  python batch_research.py 2330 2454 2317 3661
  python batch_research.py --group "💡 矽光子CPO概念精銳" --top 20 --parallel 4
  python batch_research.py --group "..." --top 30 --funnel --report-top 8 --fast --parallel 5

模式:
  (預設)         每檔跑 quick(完整 6 人團隊)
  --funnel        兩段漏斗:先對全部跑超輕量 screen(一人分析師 · ~60–90s/檔),
                  排名後只對前 --report-top 名跑完整 quick(+PDF)

加速選項:
  --parallel K    同時跑 K 檔(預設 3,建議 3–5)
  --fast          screen / quick 分析改用 Haiku(更快、質化略淺)
  --no-pdf        quick 階段不出 PDF;結束後只對前 --pdf-top 名補
  --pdf-top N     搭配 --no-pdf / --funnel(預設 5)
  --report-top N  --funnel 第二段細看的檔數(預設 8)
  --per-timeout   單檔硬上限秒數(quick 900 / screen 300)
  --context-file  覆寫台股共用背景的文字檔

輸出(research/_batch/<YYYY-MM-DD-HHMM>/):
  leaderboard.csv / leaderboard.json    綜合排行榜(每檔跑完即落地)
  progress.log                          即時進度
每檔完整產出仍在 research/<code>.TW-<date>/。

時間感:15 檔 · 平行4 —— 純 quick ~15–20 分;--funnel --fast ~8–12 分。
"""
from __future__ import annotations

import os
import re
import sys
import csv
import json
import time
import argparse
import datetime
import subprocess
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait

import research_bridge_v1878 as rb

BATCH_DIR = os.path.join(rb.REPO_ROOT, "research", "_batch")
BUILD_PDF = os.path.join(rb.REPO_ROOT, ".claude", "skills", "equity-research-team", "scripts", "build_pdf.py")

TW_CONTEXT = (
    "利率處相對高原、市場對降息時點分歧;新台幣匯率為出口股毛利的關鍵擺動變數(走弱利多毛利率、"
    "回升為逆風)。AI 資料中心資本支出續強、可延續數年,惟高度集中於少數超大規模業者的 capex,"
    "存在循環性與 AI 生態系融資疑慮。半導體景氣位於擴張中段:先進製程 / 先進封裝(CoWoS)吃緊、"
    "傳統成熟製程需求分歧。地緣(台海、美國出口管制、產能外移要求)為結構性尾部風險。"
)
HAIKU = "claude-haiku-4-5-20251001"   # 明確 ID(別名在部分 CLI 版本會壞)


# --------------------------------------------------------------------------- #
def parse_codes(args) -> list[str]:
    codes: list[str] = list(args.codes)
    if args.file:
        for line in open(args.file, encoding="utf-8"):
            m = re.search(r"\d{4,6}", line)
            if m:
                codes.append(m.group(0))
    if args.group:
        try:
            from bw_core import STRATEGIC_GROUPS
            codes += list(STRATEGIC_GROUPS.get(args.group, []))
        except Exception as e:
            print("!! 讀不到 STRATEGIC_GROUPS:", e)
    seen, out = set(), []
    for c in codes:
        c = str(c).replace(".TW", "").replace(".TWO", "").strip()
        if c and c not in seen:
            seen.add(c); out.append(c)
    return out[: args.top] if args.top else out


def _name_of(code: str) -> str:
    try:
        from bw_core import ZHTW_MAP
        return ZHTW_MAP.get(code) or f"個股{code}"
    except Exception:
        return f"個股{code}"


# --------------------------------------------------------------------------- #
_RATING = {
    "買進": 2.0, "買進(分批)": 1.6, "偏多": 1.4, "中立偏多": 1.3,
    "中立": 1.0, "持有": 1.0, "中立 / 持有": 1.0, "中立/持有": 1.0,
    "偏空": 0.4, "賣出": 0.0,
}
_GATE = {"PASS": 1.0, "CONDITIONAL PASS": 0.4, "BLOCK": -1.0}


def _rating_score(r: str) -> float:
    r = (r or "").strip()
    # 長 key 先比:否則 "買進" 會先命中 "買進(分批)"(誤給 2.0 而非 1.6),
    # "偏多" 會先命中 "中立偏多"(誤給 1.4 而非 1.3)
    for k in sorted(_RATING, key=len, reverse=True):
        if k in r:
            return _RATING[k]
    return 1.0


def score(rating, gate, base, price, sig, confidence=None) -> dict:
    price = price or 0
    base = base or 0
    upside = ((base - price) / price) if price else 0.0
    rs = _rating_score(rating)
    gs = _GATE.get(str(gate or "").upper(), 0.0)
    tech = 0.0
    if (sig.get("macd_enhanced") or {}).get("valid"):
        tech += 0.5
    if (sig.get("s2560") or {}).get("is_buy"):
        tech += 0.3
    if (sig.get("dual_bollinger") or {}).get("is_buy"):
        tech += 0.3
    if any(w in sig.get("wyckoff_box", "") for w in ("強勢", "重啟", "攻勢", "起漲")):
        tech += 0.2
    if (sig.get("rsi_divergence") or {}).get("bearish"):
        tech -= 0.5
    rr = (sig.get("macd_enhanced") or {}).get("rr")
    if isinstance(rr, (int, float)) and rr >= 2.5:
        tech += 0.2
    up_clip = max(-0.4, min(0.6, upside))
    comp = rs + gs * 0.5 + up_clip * 2 + tech
    if confidence is not None:
        try:
            comp += (float(confidence) - 50) / 100.0
        except (TypeError, ValueError):
            pass
    return {"composite": round(comp, 2), "upside_pct": round(upside * 100, 1),
            "tech_score": round(tech, 2)}


# --------------------------------------------------------------------------- #
def prep(code: str, focus: str, plog) -> tuple | None:
    name = _name_of(code)
    wd = rb.make_workdir(code)
    try:
        rb.build_inputs_json_v1878(code, wd, mode="quick", user_focus=focus)
    except Exception as e:
        plog(f"[{code} {name}] inputs.json 失敗:{e}")
        return None
    sig = {}
    try:
        sig = json.load(open(os.path.join(wd, "inputs.json"), encoding="utf-8")).get("strategy_signals", {})
    except Exception:
        pass
    return wd, name, (sig or {})


def harvest(code, name, wd, sig, mode, plog) -> dict:
    if mode == "screen":
        s = None
        p = os.path.join(wd, "screen.json")
        if os.path.isfile(p):
            try:
                s = json.load(open(p, encoding="utf-8"))
            except Exception:
                pass
        if not s:
            plog(f"[{code} {name}] ✗ screen 未產出")
            return {"code": code, "name": name, "stage": "screen", "error": "no_screen", "workdir": wd}
        sc = score(s.get("rating"), None, s.get("target_base"),
                   None, sig, s.get("confidence"))
        row = {"code": code, "name": name, "stage": "screen",
               "rating": s.get("rating", "—"), "gate": "—",
               "target_base": s.get("target_base"),
               "confidence": s.get("confidence"),
               "bull": s.get("bull", ""), "bear": s.get("bear", ""),
               "one_liner": (s.get("bull", "") or "")[:40],
               "wyckoff": sig.get("wyckoff_box", ""),
               "macd_rr": (sig.get("macd_enhanced") or {}).get("rr"),
               "tdcc_pct": sig.get("tdcc_top1000_pct"),
               "pdf": "", "workdir": wd, **sc}
        # screen 沒有現價,upside 以 inputs.json 補
        try:
            px = json.load(open(os.path.join(wd, "inputs.json"), encoding="utf-8")).get("price", {}).get("last")
            row.update(score(s.get("rating"), None, s.get("target_base"), px, sig, s.get("confidence")))
            row["price"] = px
        except Exception:
            pass
        plog(f"[{code} {name}] · screen {row['rating']} / 目標 {row['target_base']} / 綜合 {row['composite']}")
        return row

    st = rb.poll_report(wd)
    d = st.get("data") or {}
    if not d:
        plog(f"[{code} {name}] ✗ 未產出 report-data.json")
        return {"code": code, "name": name, "stage": "quick", "error": "no_report", "workdir": wd}
    sc = score(d.get("rating"), (d.get("gate") or {}).get("verdict"),
               (d.get("target") or {}).get("base"), (d.get("price") or {}).get("last"), sig)
    row = {
        "code": code, "name": name, "stage": "quick",
        "rating": d.get("rating", "—"),
        "gate": (d.get("gate") or {}).get("verdict", "—"),
        "price": (d.get("price") or {}).get("last"),
        "target_bear": (d.get("target") or {}).get("bear"),
        "target_base": (d.get("target") or {}).get("base"),
        "target_bull": (d.get("target") or {}).get("bull"),
        **sc,
        "wyckoff": sig.get("wyckoff_box", ""),
        "macd_rr": (sig.get("macd_enhanced") or {}).get("rr"),
        "tdcc_pct": sig.get("tdcc_top1000_pct"),
        "one_liner": d.get("one_liner", ""),
        "pdf": os.path.join(wd, "report.pdf") if st.get("pdf") else "",
        "workdir": wd,
    }
    plog(f"[{code} {name}] ✓ {row['rating']} / Gate {row['gate']} / base {row['target_base']} / 綜合 {sc['composite']}")
    return row


def _dump(outdir: str, rows: list[dict]):
    ranked = sorted(rows, key=lambda r: r.get("composite", -99), reverse=True)
    json.dump({"generated": datetime.datetime.now().isoformat(), "rows": ranked},
              open(os.path.join(outdir, "leaderboard.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=str)
    if ranked:
        cols = ["code", "name", "stage", "rating", "gate", "composite", "upside_pct",
                "target_bear", "target_base", "target_bull", "price", "confidence",
                "tech_score", "macd_rr", "tdcc_pct", "bull", "bear", "one_liner", "pdf"]
        with open(os.path.join(outdir, "leaderboard.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in ranked:
                w.writerow(r)
        write_xlsx(os.path.join(outdir, "leaderboard.xlsx"), ranked)


_XLSX_COLS = [
    ("排名", None), ("類型", "stage"), ("代號", "code"), ("名稱", "name"),
    ("綜合分", "composite"), ("評級", "rating"), ("反方Gate", "gate"),
    ("上檔%", "upside_pct"), ("現價", "price"),
    ("熊目標", "target_bear"), ("基準目標", "target_base"), ("牛目標", "target_bull"),
    ("信心", "confidence"), ("技術分", "tech_score"), ("MACD盈虧比", "macd_rr"),
    ("大戶持股%", "tdcc_pct"), ("Wyckoff", "wyckoff"),
    ("一句話 / 最強多方", "one_liner"), ("最大風險", "bear"),
    ("PDF 路徑", "pdf"), ("工作目錄", "workdir"), ("錯誤", "error"),
]


def write_xlsx(path: str, ranked: list[dict]):
    """把排行榜寫成有格式的 .xlsx(標題列凍結、autofilter、欄寬)。引擎缺就跳過。"""
    try:
        import pandas as pd
    except Exception:
        return
    recs = []
    for i, r in enumerate(ranked, 1):
        row = {}
        for label, key in _XLSX_COLS:
            if key is None:
                row[label] = i
            elif key == "stage":
                row[label] = ("🔬細看" if r.get("stage") == "quick"
                              else "🔎快篩" if r.get("stage") == "screen"
                              else r.get("stage", ""))
            else:
                row[label] = r.get(key, "")
        recs.append(row)
    df = pd.DataFrame(recs, columns=[c for c, _ in _XLSX_COLS])
    engine = "xlsxwriter"
    try:
        import xlsxwriter  # noqa
    except Exception:
        engine = "openpyxl"
    try:
        with pd.ExcelWriter(path, engine=engine) as xw:
            df.to_excel(xw, index=False, sheet_name="排行榜")
            ws = xw.sheets["排行榜"]
            if engine == "xlsxwriter":
                ws.freeze_panes(1, 0)
                ws.autofilter(0, 0, len(df), len(df.columns) - 1)
                widths = {"排名": 5, "類型": 8, "代號": 7, "名稱": 12, "綜合分": 7,
                          "評級": 12, "反方Gate": 16, "上檔%": 7, "現價": 9,
                          "一句話 / 最強多方": 46, "最大風險": 46,
                          "PDF 路徑": 52, "工作目錄": 48}
                for ci, (label, _) in enumerate(_XLSX_COLS):
                    ws.set_column(ci, ci, widths.get(label, 11))
    except Exception as e:
        print("!! 寫 xlsx 失敗:", e)


# --------------------------------------------------------------------------- #
def run_pool(codes, mode, *, model, tw_ctx, skip_pdf, par, per_timeout,
             focus, outdir, rows, plog, label):
    """對 codes 跑 mode。prep(抓價 / 引擎 / 基本面)以執行緒池預跑,主迴圈只管
    啟動 claude(最多 par 併發)、輪詢、落地 —— prep 的網路等待不再卡住排程。
    結果 append 進 rows(共用清單)並逐檔落地。回傳本段 rows。"""
    prep_workers = int(os.environ.get("RESEARCH_PREP_WORKERS", str(max(2, min(4, par)))))
    plog(f"───── {label}:{len(codes)} 檔 · claude 平行 {par} · prep 平行 {prep_workers} · "
         f"{'Haiku' if model else 'Sonnet'} · {mode}{' · 不出PDF' if skip_pdf else ''} ─────")

    seg: list[dict] = []
    ready: list[tuple] = []          # 已備妥、等待啟動 claude 的 (code, wd, name, sig)
    running: dict[str, dict] = {}

    def _fail(code, name, err):
        r = {"code": code, "name": name, "stage": mode, "error": err}
        seg.append(r); rows.append(r); _dump(outdir, rows)

    ex = ThreadPoolExecutor(max_workers=prep_workers)
    try:
        futs = {ex.submit(prep, c, focus, plog): c for c in codes}   # 全部 prep 一次投出,池子限併發

        while futs or ready or running:
            # 1) 收割完成的 prep
            done = [f for f in futs if f.done()]
            if not done and not ready and not running and futs:
                wait(list(futs), timeout=15, return_when=FIRST_COMPLETED)
                done = [f for f in futs if f.done()]
            for f in done:
                c = futs.pop(f)
                try:
                    p = f.result()
                except Exception as e:
                    plog(f"[{c}] prep 例外:{e}"); _fail(c, _name_of(c), f"prep:{e}"); continue
                if p is None:
                    _fail(c, _name_of(c), "inputs"); continue
                ready.append((c, *p))           # p = (wd, name, sig)

            # 2) 啟動 claude,最多 par 併發
            while ready and len(running) < par:
                code, wd, name, sig = ready.pop(0)
                try:
                    proc = rb.run_research(wd, code, name, mode, model=model,
                                           tw_context=tw_ctx, skip_pdf=skip_pdf)
                except RuntimeError as e:
                    plog(f"[{code}] 無法啟動 claude:{e}"); _fail(code, name, f"claude:{e}"); continue
                running[code] = {"proc": proc, "wd": wd, "name": name, "sig": sig, "t0": time.time()}
                plog(f"[{code} {name}] ▶ 啟動(執行中 {len(running)}/{par},待啟 {len(ready)},prep中 {len(futs)})")

            # 3) 輪詢 running
            for code in list(running):
                j = running[code]
                over = time.time() - j["t0"] > per_timeout
                if j["proc"].poll() is not None or over:
                    if over:
                        j["proc"].terminate()
                        plog(f"[{code} {j['name']}] 逾時 {per_timeout}s,終止")
                    r = harvest(code, j["name"], j["wd"], j["sig"], mode, plog)
                    seg.append(r); rows.append(r); running.pop(code); _dump(outdir, rows)

            if running or (futs and not ready):
                time.sleep(3)
    finally:
        try:
            ex.shutdown(wait=False, cancel_futures=True)   # Py3.9+
        except TypeError:
            ex.shutdown(wait=False)
    return seg


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--group"); ap.add_argument("--file")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--focus", default="")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--no-pdf", dest="no_pdf", action="store_true")
    ap.add_argument("--pdf-top", type=int, default=5)
    ap.add_argument("--funnel", action="store_true", help="兩段漏斗:screen 全部 → 前 N 名跑 quick")
    ap.add_argument("--report-top", dest="report_top", type=int, default=8)
    ap.add_argument("--per-timeout", type=int, default=0)
    ap.add_argument("--context-file")
    args = ap.parse_args()

    # 主控台預設 cp950 時,進度行裡的 ▶ / ───── 等字元會讓 print 丟 UnicodeEncodeError 炸掉整批
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    codes = parse_codes(args)
    if not codes:
        print("沒有可跑的代號。用法見檔頭 docstring。"); sys.exit(1)
    if len(codes) > 30:
        print(f"!! {len(codes)} 檔超過 30,截斷。"); codes = codes[:30]

    tw_ctx = TW_CONTEXT
    if args.context_file and os.path.isfile(args.context_file):
        tw_ctx = open(args.context_file, encoding="utf-8").read().strip()
    fast_model = HAIKU if args.fast else None
    par = max(1, min(6, args.parallel))

    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M")
    outdir = os.path.join(BATCH_DIR, stamp)
    os.makedirs(outdir, exist_ok=True)
    logf = open(os.path.join(outdir, "progress.log"), "w", encoding="utf-8", errors="replace")

    def plog(msg):
        line = f"{datetime.datetime.now():%H:%M:%S}  {msg}"
        try:
            print(line, flush=True)
        except UnicodeEncodeError:
            enc = (sys.stdout.encoding or "ascii")
            print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)
        logf.write(line + "\n"); logf.flush()

    rows: list[dict] = []

    if args.funnel:
        plog(f"批次(兩段漏斗)開始:{len(codes)} 檔 → {outdir}")
        plog("代號:" + " ".join(codes))
        # 第一段:screen 全部
        seg1 = run_pool(codes, "screen", model=fast_model, tw_ctx=tw_ctx, skip_pdf=True,
                        par=par, per_timeout=args.per_timeout or 300, focus=args.focus,
                        outdir=outdir, rows=rows, plog=plog, label="第一段 · 快篩")
        ok1 = [r for r in seg1 if not r.get("error")]
        ranked1 = sorted(ok1, key=lambda r: r.get("composite", -99), reverse=True)
        keep = [r["code"] for r in ranked1[: args.report_top]]
        plog(f"快篩前 {len(keep)} 名進第二段:" +
             " ".join(f"{r['code']}({r['rating']}/{r['composite']})" for r in ranked1[: args.report_top]))
        # rows 裡 screen 版先移除將被 quick 取代的,避免重複列
        rows[:] = [r for r in rows if r["code"] not in keep]
        # 第二段:quick 前 N 名
        seg2 = run_pool(keep, "quick", model=None, tw_ctx=tw_ctx, skip_pdf=args.no_pdf,
                        par=par, per_timeout=args.per_timeout or 900, focus=args.focus,
                        outdir=outdir, rows=rows, plog=plog, label="第二段 · 細看")
        # 第二段失敗的 → 還原它的第一段 screen 結果(至少排行榜有它)
        failed2 = {r["code"] for r in seg2 if r.get("error")}
        s1_by_code = {r["code"]: r for r in seg1}
        for c in failed2:
            if c in s1_by_code and not s1_by_code[c].get("error"):
                fb = dict(s1_by_code[c]); fb["stage"] = "screen(第二段失敗回退)"
                rows[:] = [r for r in rows if r["code"] != c] + [fb]
                plog(f"[{c}] 第二段失敗 → 回退第一段 screen 結果")
        _dump(outdir, rows)
    else:
        plog(f"批次開始:{len(codes)} 檔 · 平行 {par} · {'Haiku' if fast_model else 'Sonnet'} "
             f"· {'不出PDF' if args.no_pdf else '每檔出PDF'} → {outdir}")
        plog("代號:" + " ".join(codes))
        run_pool(codes, "quick", model=fast_model, tw_ctx=tw_ctx, skip_pdf=args.no_pdf,
                 par=par, per_timeout=args.per_timeout or 900, focus=args.focus,
                 outdir=outdir, rows=rows, plog=plog, label="quick 全部")

    ok = [r for r in rows if not r.get("error")]
    plog(f"批次完成。成功 {len(ok)} / {len(rows)}")

    # 補 PDF:--no-pdf 的 quick 段,或 --funnel 第二段
    need_pdf = [r for r in ok if r.get("stage") == "quick" and not r.get("pdf")]
    if (args.no_pdf or args.funnel) and need_pdf:
        top = sorted(need_pdf, key=lambda r: r.get("composite", -99), reverse=True)[: args.pdf_top]
        plog(f"補產 {len(top)} 份 PDF …")
        for r in top:
            rd = os.path.join(r["workdir"], "report-data.json")
            if os.path.isfile(rd):
                try:
                    # 內層 to_pdf 最壞 2×BUILD_PDF_TIMEOUT(預設 60);外層留餘裕
                    subprocess.run([sys.executable, BUILD_PDF, rd], cwd=rb.REPO_ROOT,
                                   capture_output=True, timeout=180)
                    pdf = os.path.join(r["workdir"], "report.pdf")
                    if os.path.isfile(pdf):
                        r["pdf"] = pdf; plog(f"  [{r['code']} {r['name']}] PDF ✓")
                except Exception as e:
                    plog(f"  [{r['code']}] PDF 失敗:{e}")
        _dump(outdir, rows)

    plog(f"排行榜:{os.path.join(outdir, 'leaderboard.csv')}")


if __name__ == "__main__":
    main()
