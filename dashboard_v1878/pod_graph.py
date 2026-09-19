"""
pod_graph.py — LangGraph 6 人投研 Pod(Gemini 版),接 inputs.json 當地面真相

由 ai-research-pod/graph/investment_pod_graph.py 移植,主要差異:
  1. State 多一個 quant_data(= inputs.json dict);各節點 prompt 注入對應切片
  2. 金鑰讀取容錯 BOM;模型走 GEMINI_MODEL 環境變數(預設 gemini-flash-latest)
  3. 節點間延遲走 GEMINI_NODE_DELAY(預設 2s;免費層 RPM 緊就調大)
"""
from __future__ import annotations

import os
import time
from typing import Any, List, Literal, Union, TypedDict

from pydantic import BaseModel, Field, field_validator
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

_HERE = os.path.dirname(os.path.abspath(__file__))
_NODE_DELAY = float(os.environ.get("GEMINI_NODE_DELAY", "2"))
# flash-lite:最便宜、免費層額度也跟 flash 分開算。要更強改 GEMINI_MODEL=gemini-flash-latest
_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")


# --------------------------------------------------------------------------- #
#  金鑰
# --------------------------------------------------------------------------- #
def _load_key() -> str:
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if k:
        return k.strip()
    cands = [os.environ.get("GEMINI_ENV_FILE"),
             os.path.join(_HERE, ".env"),
             os.path.join(os.path.dirname(_HERE), ".env"),
             r"C:\Users\mikelee\Desktop\ai-research-pod\.env"]
    for envp in cands:
        if envp and os.path.isfile(envp):
            for line in open(envp, encoding="utf-8-sig"):   # utf-8-sig 吃掉 BOM
                line = line.strip()
                if line[:14] in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError("找不到 GEMINI_API_KEY:設環境變數,或在 market-suite/.env 放一行 GEMINI_API_KEY=...")


def get_llm(structured=None):
    llm = ChatGoogleGenerativeAI(model=_MODEL, temperature=0.2,
                                 google_api_key=_load_key(), request_timeout=120)
    return llm.with_structured_output(structured) if structured is not None else llm


# --------------------------------------------------------------------------- #
#  Pydantic 輸出結構(容錯:巢狀 dict/list 自動壓成字串)
# --------------------------------------------------------------------------- #
def _stringify(v: Any) -> str:
    if isinstance(v, dict):
        return "\n".join(f"- {k}: {val}" for k, val in v.items())
    if isinstance(v, list):
        return "\n".join(f"- {x}" for x in v)
    return str(v)


class MacroView(BaseModel):
    stance: Literal["Bullish", "Neutral", "Bearish"]
    liquidity_cycle: Union[str, dict, Any] = Field(description="央行利率政策與流動性週期判讀(純文字)")
    sovereign_capex_impact: Union[str, dict, Any] = Field(description="主權 AI 與跨國財政資本支出影響(純文字)")
    risk_score: float = Field(description="總經風險評分 0(安全)~10(危險)")

    @field_validator("liquidity_cycle", "sovereign_capex_impact", mode="before")
    @classmethod
    def _s(cls, v):
        return _stringify(v)


class IndustryView(BaseModel):
    supply_chain_health: Union[str, dict, Any] = Field(description="晶圓代工與先進封裝產能現況(純文字)")
    hyperscaler_capex_trend: Union[str, dict, Any] = Field(description="雲端巨頭資本支出動向(純文字)")
    competitive_moat: Union[str, dict, Any] = Field(description="軟硬體生態系護城河強度(純文字)")
    growth_sustainability: str = Field(description="產業成長週期所處階段")

    @field_validator("supply_chain_health", "hyperscaler_capex_trend", "competitive_moat", mode="before")
    @classmethod
    def _s(cls, v):
        return _stringify(v)


class FundamentalView(BaseModel):
    revenue_quality: Union[str, dict, Any] = Field(description="營收動能、毛利率趨勢拆解(純文字)")
    valuation_model: Union[str, dict, Any] = Field(description="估值邏輯與關鍵乘數(純文字)")
    fair_value_target: float = Field(description="基準情境合理估值目標價")
    upside_potential: float = Field(description="相對現價潛在漲幅 %")

    @field_validator("revenue_quality", "valuation_model", mode="before")
    @classmethod
    def _s(cls, v):
        return _stringify(v)


class TechnicalQuantView(BaseModel):
    trend_structure: Union[str, dict, Any] = Field(description="長線趨勢與均線架構(純文字)")
    key_support_resistance: Union[str, dict, Any] = Field(description="關鍵支撐區與壓力帶(純文字)")
    volatility_and_volume: Union[str, dict, Any] = Field(description="量能分佈與波動率(純文字)")
    entry_strategy: Union[str, dict, Any] = Field(description="量化建倉與進場策略(純文字)")

    @field_validator("trend_structure", "key_support_resistance", "volatility_and_volume", "entry_strategy", mode="before")
    @classmethod
    def _s(cls, v):
        return _stringify(v)


class RiskDefenseView(BaseModel):
    structural_vulnerabilities: List[str] = Field(description="至少 3 項足以引發估值崩跌的致命風險")
    valuation_pushback: Union[str, dict, Any] = Field(description="對目標價與樂觀假設的穿透式質疑(純文字)")
    bear_case_target: float = Field(description="最差情境極端下行目標價")
    alert_level: Literal["Low", "Medium", "High", "Critical"]

    @field_validator("valuation_pushback", mode="before")
    @classmethod
    def _s(cls, v):
        return _stringify(v)


class FinalResearchVerdict(BaseModel):
    rating: Literal["Strong Buy", "Overweight", "Neutral", "Underweight", "Strong Sell"]
    weighted_target_price: float = Field(description="機率加權綜合目標價")
    bull_prob: float = Field(description="樂觀情境機率 0~1")
    base_prob: float = Field(description="基準情境機率 0~1")
    bear_prob: float = Field(description="悲觀情境機率 0~1")
    stop_loss_boundary: str = Field(description="動態停損界線與部位控制")
    executive_summary: str = Field(description="投研總監仲裁決策要點")


class ResearchPodState(TypedDict):
    ticker: str
    name: str
    market: str
    period: str
    current_price: float
    raw_context: str
    quant_data: dict
    macro: MacroView
    industry: IndustryView
    fundamental: FundamentalView
    technical: TechnicalQuantView
    risk_review: RiskDefenseView
    final_verdict: FinalResearchVerdict


# --------------------------------------------------------------------------- #
#  inputs.json → 各角色 prompt 的量化簡報
# --------------------------------------------------------------------------- #
def _fmt(d: Any, indent: str = "") -> str:
    if isinstance(d, dict):
        return "\n".join(f"{indent}- {k}: {_fmt(v, indent + '  ')}" if isinstance(v, (dict, list))
                         else f"{indent}- {k}: {v}" for k, v in d.items())
    if isinstance(d, list):
        return "\n".join(f"{indent}- {_fmt(x, indent + '  ')}" for x in d)
    return str(d)


def _brief(q: dict, keys) -> str:
    parts = []
    for k in keys:
        if k in q and q[k] not in (None, {}, []):
            parts.append(f"[{k}]\n{_fmt(q[k])}")
    return "\n".join(parts) if parts else "(inputs.json 無此區塊)"


def _ground(state, keys) -> str:
    return ("\n\n【量化地面真相 — 以下數字為準,不得臆造或改寫;文字分析須與這些數字一致】\n"
            + _brief(state.get("quant_data") or {}, keys))


# --------------------------------------------------------------------------- #
#  節點
# --------------------------------------------------------------------------- #
def macro_node(state):
    print(" -> [1/6] 總經策略師…")
    llm = get_llm(MacroView)
    p = (f"評估標的 {state['name']}({state['ticker']},{state['market']} 市場)的總體經濟環境:\n"
         f"{state['raw_context']}" + _ground(state, ["macro_ribbon", "as_of"]))
    return {"macro": llm.invoke([
        ("system", "你是資深總經策略師,評估利率與景氣週期。各欄位以簡潔文字輸出,勿回傳巢狀字典。"),
        ("user", p)])}


def industry_node(state):
    time.sleep(_NODE_DELAY)
    print(" -> [2/6] 產業分析師…")
    llm = get_llm(IndustryView)
    p = (f"評估標的 {state['name']}({state['ticker']})在產業鏈的位置與競爭壁壘:\n"
         f"{state['raw_context']}" + _ground(state, ["fundamentals", "name"]))
    return {"industry": llm.invoke([
        ("system", "你是半導體產業分析師,專注先進封裝與護城河。各欄位以簡潔文字輸出,勿回傳巢狀字典。"),
        ("user", p)])}


def fundamental_node(state):
    time.sleep(_NODE_DELAY)
    print(" -> [3/6] 基本面分析師…")
    llm = get_llm(FundamentalView)
    p = (f"分析標的 {state['name']}({state['ticker']})財報與估值,現價 {state['current_price']}"
         f"({state['market']};台股幣別 TWD):\n{state['raw_context']}"
         + _ground(state, ["fundamentals", "price", "pe_bands", "dividends"]))
    return {"fundamental": llm.invoke([
        ("system", "你是科技基本面分析師,專精估值建模與目標價。fair_value_target 用地面真相的 pe×eps_ttm "
                   "或合理乘數推估,勿直接回推現價。文字欄位輸出純文字。"),
        ("user", p)])}


def technical_node(state):
    time.sleep(_NODE_DELAY)
    print(" -> [4/6] 量化技術分析師…")
    llm = get_llm(TechnicalQuantView)
    p = (f"分析標的 {state['name']}({state['ticker']})走勢型態與支撐壓力:\n{state['raw_context']}"
         + _ground(state, ["price", "ohlcv_summary", "indicators", "strategy_signals"]))
    return {"technical": llm.invoke([
        ("system", "你是量化技術分析師,以波段防守點位為核心。所有欄位必須為純文字字串,嚴禁字典或巢狀 JSON。"
                   "須引用地面真相裡的 strategy_signals(Wyckoff / MACD 強化 / 2560 / 布林)做交叉驗證。"),
        ("user", p)])}


def risk_controller_node(state):
    time.sleep(_NODE_DELAY)
    print(" -> [5/6] 反方風控官…")
    llm = get_llm(RiskDefenseView)
    combined = (f"【總經】{state['macro'].model_dump_json()}\n"
                f"【產業】{state['industry'].model_dump_json()}\n"
                f"【基本面】{state['fundamental'].model_dump_json()}\n"
                f"【技術面】{state['technical'].model_dump_json()}")
    p = (f"標的 {state['name']}({state['ticker']}),現價 {state['current_price']}。"
         f"嚴格反駁以下分析、鎖定致命結構風險、給最悲觀目標價:\n{combined}"
         + _ground(state, ["fundamentals", "strategy_signals"]))
    return {"risk_review": llm.invoke([
        ("system", "你是冷靜客觀的反方風控官,專戳市場盲目樂觀。文字欄位輸出純文字。"),
        ("user", p)])}


def research_director_node(state):
    time.sleep(_NODE_DELAY)
    print(" -> [6/6] 投研總監仲裁…")
    llm = get_llm(FinalResearchVerdict)
    dossier = (f"總經 {state['macro'].model_dump_json()}\n產業 {state['industry'].model_dump_json()}\n"
               f"基本面 {state['fundamental'].model_dump_json()}\n技術面 {state['technical'].model_dump_json()}\n"
               f"風控質詢 {state['risk_review'].model_dump_json()}")
    p = (f"標的 {state['name']}({state['ticker']}),現價 {state['current_price']}。"
         f"權衡所有觀點,分配牛/基準/熊機率(合計 1.0),計算加權目標價並給評級:\n{dossier}")
    return {"final_verdict": llm.invoke([
        ("system", "你是投研總監兼投委會主席,依風險報酬比做最終仲裁。"),
        ("user", p)])}


# --------------------------------------------------------------------------- #
_b = StateGraph(ResearchPodState)
for _n, _f in (("macro_analyst", macro_node), ("industry_analyst", industry_node),
               ("fundamental_analyst", fundamental_node), ("technical_analyst", technical_node),
               ("risk_controller", risk_controller_node), ("research_director", research_director_node)):
    _b.add_node(_n, _f)
_b.add_edge(START, "macro_analyst")
_b.add_edge("macro_analyst", "industry_analyst")
_b.add_edge("industry_analyst", "fundamental_analyst")
_b.add_edge("fundamental_analyst", "technical_analyst")
_b.add_edge("technical_analyst", "risk_controller")
_b.add_edge("risk_controller", "research_director")
_b.add_edge("research_director", END)

research_graph = _b.compile()
