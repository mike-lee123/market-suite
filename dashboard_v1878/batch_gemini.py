"""
batch_gemini.py — 對一組台股代號跑 Gemini Pod 研報,產出綜合排行榜(Claude 版 batch_research.py 的省錢替身)

用法:
  python batch_gemini.py 2330 2454 2317 3661
  python batch_gemini.py --group "💡 矽光子CPO概念精銳" --top 20 --parallel 3
  python batch_gemini.py 2330 --no-pdf

與 batch_research.py 差異:
  - 不派 claude 子行程,改在 process 內呼叫 pod_graph(Gemini)
  - 沒有 screen / funnel 兩段漏斗(Gemini 本來就快又便宜,一律完整跑)
輸出:research/_batch/<時間>/leaderboard.{csv,json,xlsx} + progress.log;每檔產出在 research/<code>.TW-<date>/

節流:GEMINI_NODE_DELAY(節點間秒數,預設 2)、--parallel(同時幾檔,預設 3);免費層 RPM 緊就把 parallel 調 1~2、delay 調大。
"""
from __future__ import annotations

import os
import sys
import time
import argparse
import datetime
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault("RESEARCH_WORKDIR_SUFFIX", "-gemini")   # 與 Claude 版分開落地

import research_bridge_v1878 as rb
from batch_research import parse_codes, _name_of, score, _dump, prep, harvest, BUILD_PDF
import pod_graph
import gemini_engine

BATCH_DIR = os.path.join(rb.REPO_ROOT, "research", "_batch")


def _one(code: str, focus: str, skip_pdf: bool, per_timeout: int, plog) -> dict:
    name = _name_of(code)
    t0 = time.time()
    p = prep(code, focus, plog)
    if p is None:
        return {"code": code, "name": name, "stage": "quick", "error": "inputs"}
    wd, name, sig = p
    try:
        gemini_engine.run_report(code, wd, focus=focus)
    except Exception as e:
        plog(f"[{code} {name}] ✗ Gemini 失敗:{type(e).__name__} {str(e)[:160]}")
        return {"code": code, "name": name, "stage": "quick", "error": f"gemini:{type(e).__name__}", "workdir": wd}
    if not skip_pdf:
        rdp = os.path.join(wd, "report-data.json")
        try:
            subprocess.run([sys.executable, BUILD_PDF, rdp], cwd=rb.REPO_ROOT,
                           capture_output=True, timeout=max(60, per_timeout))
        except Exception as e:
            plog(f"[{code} {name}] PDF 失敗:{e}")
    row = harvest(code, name, wd, sig, "quick", plog)
    plog(f"[{code} {name}] ✓ {row.get('rating')} / Gate {row.get('gate')} / base {row.get('target_base')} "
         f"/ 綜合 {row.get('composite')} ({time.time() - t0:.0f}s)")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--group"); ap.add_argument("--file")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--focus", default="")
    ap.add_argument("--parallel", type=int, default=3)
    ap.add_argument("--no-pdf", dest="no_pdf", action="store_true")
    ap.add_argument("--per-timeout", type=int, default=180)
    args = ap.parse_args()

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
            enc = sys.stdout.encoding or "ascii"
            print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)
        logf.write(line + "\n"); logf.flush()

    plog(f"Gemini 批次:{len(codes)} 檔 · 平行 {par} · 模型 {pod_graph._MODEL} "
         f"· 節點延遲 {os.environ.get('GEMINI_NODE_DELAY', '2')}s → {outdir}")
    plog("代號:" + " ".join(codes))

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=par) as ex:
        futs = {ex.submit(_one, c, args.focus, args.no_pdf, args.per_timeout, plog): c for c in codes}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"code": c, "name": _name_of(c), "stage": "quick", "error": f"crash:{type(e).__name__}"}
                plog(f"[{c}] 例外:{e}")
            rows.append(r); _dump(outdir, rows)

    ok = [r for r in rows if not r.get("error")]
    plog(f"批次完成。成功 {len(ok)} / {len(rows)}")

    if args.no_pdf and ok:
        top = sorted(ok, key=lambda r: r.get("composite", -99), reverse=True)[:5]
        plog(f"補產 {len(top)} 份 PDF …")
        for r in top:
            rdp = os.path.join(r["workdir"], "report-data.json")
            if os.path.isfile(rdp):
                try:
                    subprocess.run([sys.executable, BUILD_PDF, rdp], cwd=rb.REPO_ROOT,
                                   capture_output=True, timeout=180)
                    if os.path.isfile(os.path.join(r["workdir"], "report.pdf")):
                        r["pdf"] = os.path.join(r["workdir"], "report.pdf"); plog(f"  [{r['code']}] PDF ✓")
                except Exception as e:
                    plog(f"  [{r['code']}] PDF 失敗:{e}")
        _dump(outdir, rows)

    plog(f"排行榜:{os.path.join(outdir, 'leaderboard.csv')}")


if __name__ == "__main__":
    main()
