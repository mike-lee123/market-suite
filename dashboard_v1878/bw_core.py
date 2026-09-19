# ============================================================================
# bw_core.py — 從 dashboard.py 抽出的純計算層(零 streamlit 相依)
#   內容 = dashboard.py 前 527 行,已移除 import streamlit / @st.cache_* / 兩段 st.* UI 呼叫。
#   由 research_bridge_v1878.py 匯入;改演算法請同步改 dashboard.py。
# ============================================================================

# ==============================================================================
# 檔案名稱: bw_ultimate_dashboard_v18.78_dashboard_FullMaster.py
# 說明: 併武 V18.78 dashboard FullMaster - 僅放寬多週期共振短線艙預設門檻，其餘 16 艙 100% 原封不動
# ==============================================================================

import io
import os
import re
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import time
import sys
from io import StringIO
import math
from typing import Dict, Any

# 動態匯入 Shioaji
try:
    import shioaji as sj
    SHIOAJI_AVAILABLE = True
except ImportError:
    SHIOAJI_AVAILABLE = False

import yfinance as yf

# 共用連線:keep-alive 省掉每檔重新 TLS 握手,是平行抓價時的主要加速點
_YQ_SESSION = requests.Session()
_YQ_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

# ==============================================================================
# 🛡️ 併武台股量化交易系統 V18.78 - 全市場自動化警示與戰術旗艦版
# ==============================================================================



class MATradingManager:
    def __init__(self, total_capital: float = 1000000.0, risk_tolerance_pct: float = 1.0):
        self.total_capital = total_capital
        self.risk_tolerance_pct = risk_tolerance_pct

    def calculate_trade_risk(self, symbol: str, entry_price: float, stop_loss: float, t1: float, t2: float, t3: float, use_pyramid: bool, ma13_val: float) -> Dict[str, Any]:
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0: risk_per_share = 0.01
        risk_capital = self.total_capital * (self.risk_tolerance_pct / 100.0)
        shares = int(risk_capital / risk_per_share)
        investment = shares * entry_price
        return {
            "shares": shares,
            "order_desc": f"{shares} 股 (約 {shares//1000} 張)",
            "actual_investment": investment
        }

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
    loss = ((-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean())
    rs = gain / (loss + 1e-8)
    return 100 - (100 / (1 + rs))

def detect_rsi_divergence_active(df, window=15):
    if len(df) < window * 2: return False, False
    closes = df["Close"].values
    rsi = df["RSI_14"].values
    recent_window_slice = closes[-3:]
    recent_low_idx = len(closes) - 3 + np.argmin(recent_window_slice)
    prev_closes_slice = closes[-(window * 2) : -3]
    if len(prev_closes_slice) < 5: return False, False
    prev_low_idx = len(closes) - (window * 2) + np.argmin(prev_closes_slice)
    is_bullish_div = (closes[recent_low_idx] <= closes[prev_low_idx] * 1.03) and (rsi[recent_low_idx] > rsi[prev_low_idx]) and (rsi[recent_low_idx] <= 55)
    
    recent_high_idx = len(closes) - 3 + np.argmax(closes[-3:])
    prev_high_idx = len(closes) - (window * 2) + np.argmax(closes[-(window * 2) : -3])
    is_bearish_div = (closes[recent_high_idx] >= closes[prev_high_idx] * 0.97) and (rsi[recent_high_idx] < rsi[prev_high_idx]) and (rsi[recent_high_idx] >= 45)
    return is_bullish_div, is_bearish_div

def calculate_cyc(df, n=20):
    pv = df['Close'] * df['Volume']
    return pv.rolling(window=n).sum() / (df['Volume'].rolling(window=n).sum() + 1e-8)

def calculate_roc_indicator(df, n=12):
    return (df['Close'] - df['Close'].shift(n)) / (df['Close'].shift(n) + 1e-8) * 100

def calculate_kd(df, n=9):
    low_min = df['Low'].rolling(window=n).min()
    high_max = df['High'].rolling(window=n).max()
    denom = (high_max - low_min).replace(0, np.nan)
    rsv = ((df['Close'] - low_min) / denom * 100).fillna(50)
    k, d = [], []
    last_k, last_d = 50.0, 50.0
    for val in rsv:
        current_k = (2/3) * last_k + (1/3) * val
        current_d = (2/3) * last_d + (1/3) * current_k
        k.append(current_k)
        d.append(current_d)
        last_k, last_d = current_k, current_d
    return pd.Series(k, index=df.index), pd.Series(d, index=df.index)

def calculate_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist

def calculate_macd_enhanced(df: pd.DataFrame, fast=6, slow=13, signal=9) -> pd.DataFrame:
    df = df.copy()
    ema_fast = df['Close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=slow, adjust=False).mean()
    df['MACD_DIF'] = ema_fast - ema_slow
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=signal, adjust=False).mean()
    df['MACD_Hist'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2
    return df

def calculate_atr(df: pd.DataFrame, period=14) -> pd.Series:
    df = df.copy()
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()

def evaluate_box_tactics_rsi14(close, ma13, ma55, rsi, squeeze, vol_ratio, p1, p2, prescore, is_bull_div, is_bear_div, tdcc, active_chips, mfi, cyc20):
    if is_bull_div: return "🟢 RSI積極型底背離機會", "多方背離，可於支撐區逢低試單"
    if rsi >= 75: return "🌟 強勢蓄力(>=80分)", "動能強勁，沿 MA13 續抱"
    if mfi >= 65 and cyc20 <= close: return "🚀 洗盤結束重啟攻勢機會", "籌碼安定，留意量縮回踩轉強點"
    return "⚖️ 中性整理", "區間對待，嚴守防線"

def evaluate_escape_resonance_sop(close, roc, roc_ma, macd_line, macd_hist, prev_hist, cyc5, prev_cyc5, cyc13, cyc34):
    if macd_hist < 0 and prev_hist > 0: return "💀 終極逃頂警報", "動能反轉向下，優先獲利入袋"
    if close < cyc5: return "🚨 高檔轉弱破位", "跌破短線成本線，嚴格執行減碼"
    return "🛡️ 正常運行", "多頭結構保持良好"

def multi_timeframe_strategy_scanner(df_15m: pd.DataFrame, df_60m: pd.DataFrame, ticker_code="") -> tuple:
    if df_15m.empty or df_60m.empty: return "資料不足", False, "⚖️ B級"
    df_15m = df_15m.copy()
    df_60m = df_60m.copy()
    df_60m['MA_60H'] = df_60m['Close'].rolling(window=60, min_periods=1).mean()
    df_15m['MA_60'] = df_15m['Close'].rolling(window=60, min_periods=1).mean()
    
    last_15 = df_15m.iloc[-1]
    last_60 = df_60m.iloc[-1]
    c_price = float(last_15['Close'])
    
    is_15m_bull = c_price >= float(last_15.get('MA_60', c_price))
    is_60m_bull = float(last_60['Close']) >= float(last_60.get('MA_60H', last_60['Close']))
    
    tdcc_pct = DEFAULT_TDCC_1000.get(ticker_code, 60.0)
    vol_today = float(last_15.get('Volume', 0))
    vol_ma5 = float(df_15m['Volume'].rolling(5, min_periods=1).mean().iloc[-1]) if len(df_15m) >= 5 else vol_today
    vol_ratio = vol_today / (vol_ma5 + 1e-8)
    
    if not is_15m_bull and not is_60m_bull:
        return "🚨 警戒區【雙週期空頭排列】嚴禁做多", False, "🚨 警戒區"
    elif is_15m_bull and is_60m_bull and tdcc_pct >= 55.0 and vol_ratio >= 1.1:
        return "🌟 S級【頂級強勢共振】雙週期多頭+大戶鎖碼+量價齊揚", True, "🌟 S級"
    elif is_15m_bull and is_60m_bull:
        return "🔥 A級【黃金多頭排列】雙週期多頭", True, "🔥 A級"
    else:
        return "⚠️ B級【多空拉鋸整理】結構尚待確認", False, "⚠️ B級"

def calculate_fibonacci_levels(df: pd.DataFrame, lookback=60):
    if len(df) < lookback: lookback = len(df)
    sub_df = df.iloc[-lookback:]
    swing_high = float(sub_df['High'].max())
    swing_low = float(sub_df['Low'].min())
    price_range = swing_high - swing_low
    return {
        "High": swing_high, "Low": swing_low,
        "Fib_0382": swing_high - (price_range * 0.382),
        "Fib_0500": swing_high - (price_range * 0.500),
        "Fib_0618": swing_high - (price_range * 0.618),
        "Fib_0786": swing_high - (price_range * 0.786)
    }

def evaluate_fibonacci_strategy(df: pd.DataFrame, lookback=60) -> dict:
    if len(df) < lookback + 10: return {"status": "資料不足", "is_valid": False}
    df = df.copy()
    fib = calculate_fibonacci_levels(df, lookback=lookback)
    df['RSI_14'] = calculate_rsi(df['Close'], period=14)
    _, _, hist = calculate_macd(df, fast=12, slow=26, signal=9)
    df['MACD_Hist'] = hist
    last, prev = df.iloc[-1], df.iloc[-2]
    c_close, c_low, rsi_val = float(last['Close']), float(last['Low']), float(last['RSI_14'])
    in_fib_zone = (c_low <= fib["Fib_0382"]) and (c_close >= fib["Fib_0618"])
    rsi_condition = (rsi_val <= 42.0) or (rsi_val > float(prev['RSI_14']))
    macd_turning = (last['MACD_Hist'] > prev['MACD_Hist'])
    is_bullish_candle = (last['Close'] > last['Open']) and ((last['Close'] - last['Open']) > (last['High'] - last['Low']) * 0.5)
    is_valid = in_fib_zone and rsi_condition and macd_turning and is_bullish_candle
    return {
        "is_valid": is_valid, "fib_levels": fib, "current_price": c_close, "rsi_val": round(rsi_val, 1),
        "評語": "🟢 【Fibonacci 黃金共振買點】支撐區止穩且指標動能轉強！" if is_valid else "⚖️ 尚未完全符合 Fibonacci 共振進場條件"
    }

def plot_fibonacci_interactive_chart(df: pd.DataFrame, symbol_name: str, lookback=60) -> go.Figure:
    df = df.copy()
    fib = calculate_fibonacci_levels(df, lookback=lookback)
    df['RSI_14'] = calculate_rsi(df['Close'], period=14)
    _, _, hist = calculate_macd(df, fast=12, slow=26, signal=9)
    df['MACD_Hist'] = hist
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.55, 0.25, 0.20], vertical_spacing=0.03, subplot_titles=(f"[{symbol_name}] Fibonacci 關鍵回撤支撐與 K 線戰術圖", "RSI (14) 動能與超賣區", "MACD 動能柱狀體"))
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#00FF66', decreasing_line_color='#FF3333'), row=1, col=1)
    fig.add_hline(y=fib["High"], line_dash="dash", line_color="gray", annotation_text=f"波段高點: {fib['High']:.2f}", row=1, col=1)
    fig.add_hline(y=fib["Fib_0382"], line_dash="dot", line_color="blue", annotation_text=f"Fib 0.382: {fib['Fib_0382']:.2f}", row=1, col=1)
    fig.add_hline(y=fib["Fib_0500"], line_dash="solid", line_color="orange", annotation_text=f"Fib 0.500: {fib['Fib_0500']:.2f}", row=1, col=1)
    fig.add_hline(y=fib["Fib_0618"], line_dash="solid", line_color="red", annotation_text=f"Fib 0.618 (黃金支撐): {fib['Fib_0618']:.2f}", row=1, col=1)
    fig.add_hline(y=fib["Low"], line_dash="dash", line_color="gray", annotation_text=f"起漲低點: {fib['Low']:.2f}", row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name='RSI (14)', line=dict(color='cyan', width=1.5)), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name='MACD Hist', marker_color=['#00FF66' if val >= 0 else '#FF3333' for val in df['MACD_Hist']]), row=3, col=1)
    fig.update_layout(template="plotly_dark", height=850, xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified")
    return fig

def evaluate_macd_enhanced_strategy(df_daily: pd.DataFrame, df_operational: pd.DataFrame, min_risk_reward_ratio=2.0) -> dict:
    if len(df_daily) < 30 or len(df_operational) < 30: return {"status": "資料不足", "is_valid_trade": False}
    df_daily = df_daily.copy()
    df_daily['EMA_20'] = df_daily['Close'].ewm(span=20, adjust=False).mean()
    daily_ema_slope = df_daily['EMA_20'].iloc[-1] - df_daily['EMA_20'].iloc[-3]
    is_daily_uptrend = daily_ema_slope > 0 
    df_op = calculate_macd_enhanced(df_operational, fast=6, slow=13, signal=9)
    df_op['ATR'] = calculate_atr(df_op, period=14)
    last_row, prev_row = df_op.iloc[-1], df_op.iloc[-2]
    entry_price, atr_val, k_low = float(last_row['Close']), float(last_row['ATR']), float(last_row['Low'])
    is_macd_turning_up = (prev_row['MACD_DIF'] <= prev_row['MACD_DEA']) and (last_row['MACD_DIF'] > last_row['MACD_DEA'])
    stop_loss_price = k_low - atr_val
    risk_per_share = entry_price - stop_loss_price
    recent_high = float(df_op['High'].rolling(20).max().iloc[-1])
    take_profit_price = max(recent_high, entry_price + (risk_per_share * 2.5))
    reward_per_share = take_profit_price - entry_price
    risk_reward_ratio = reward_per_share / (risk_per_share if risk_per_share > 0 else 1e-8)
    is_valid_setup = is_daily_uptrend and is_macd_turning_up and (risk_reward_ratio >= min_risk_reward_ratio)
    return {
        "大週期趨勢多頭": is_daily_uptrend, "MACD強化版進場訊號": is_macd_turning_up, "建議進場價": round(entry_price, 2),
        "ATR動態止損價": round(stop_loss_price, 2), "預期停利價": round(take_profit_price, 2), "實測盈虧比": round(risk_reward_ratio, 2),
        "is_valid_trade": is_valid_setup, "評語": "🟢 符合交易系統開單條件！" if is_valid_setup else "⚖️ 條件未完全吻合或盈虧比不足，建議放棄交易。"
    }

def plot_macd_enhanced_interactive_chart(df: pd.DataFrame, symbol_name: str) -> go.Figure:
    df = df.copy()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['Vol_MA5'] = df['Volume'].rolling(5).mean()
    df = calculate_macd_enhanced(df, fast=6, slow=13, signal=9)
    k_v, d_v = calculate_kd(df, n=9)
    df['K'], df['D'], df['J'] = k_v, d_v, 3 * k_v - 2 * d_v
    df['Signal_Long'], df['Signal_Short'] = False, False
    for i in range(2, len(df)):
        curr_hist, prev_hist = df['MACD_Hist'].iloc[i], df['MACD_Hist'].iloc[i-1]
        c_close, ema_val = df['Close'].iloc[i], df['EMA_20'].iloc[i]
        if (prev_hist <= 0 and curr_hist > 0) and (c_close >= ema_val * 0.99): df.loc[df.index[i], 'Signal_Long'] = True
        elif (prev_hist >= 0 and curr_hist < 0) and (c_close <= ema_val * 1.01): df.loc[df.index[i], 'Signal_Short'] = True
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.45, 0.20, 0.20, 0.15], vertical_spacing=0.03, subplot_titles=(f"[{symbol_name}] K線與 EMA20 趨勢線", "MACD 強化版 (6, 13, 9)", "KDJ 隨機指標", "成交量與 5日均量線"))
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price', increasing_line_color='#00FF66', decreasing_line_color='#FF3333'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], name='EMA 20', line=dict(color='yellow', width=2)), row=1, col=1)
    long_df, short_df = df[df['Signal_Long']], df[df['Signal_Short']]
    if not long_df.empty: fig.add_trace(go.Scatter(x=long_df.index, y=long_df['Low'] * 0.99, mode='markers', name='🔵 做多信號', marker=dict(symbol='triangle-up', size=13, color='#00E5FF')), row=1, col=1)
    if not short_df.empty: fig.add_trace(go.Scatter(x=short_df.index, y=short_df['High'] * 1.01, mode='markers', name='🟡 做空信號', marker=dict(symbol='triangle-down', size=13, color='#FFD700')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_DIF'], name='DIF', line=dict(color='#00FFFF', width=1.2)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_DEA'], name='DEA', line=dict(color='#FF9900', width=1.2)), row=2, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name='Hist', marker_color=['#00FF66' if v >= 0 else '#FF3333' for v in df['MACD_Hist']]), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['K'], name='K', line=dict(color='yellow', width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['D'], name='D', line=dict(color='cyan', width=1)), row=3, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=['#00FF66' if c >= o else '#FF3333' for c, o in zip(df['Close'], df['Open'])]), row=4, col=1)
    fig.update_layout(template="plotly_dark", height=950, xaxis_rangeslider_visible=False, margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified")
    return fig

def estimate_active_chips(df, threshold=0.08, window=30):
    active_ratio = []
    for i in range(len(df)):
        if i < window: active_ratio.append(50.0); continue
        cc = df['Close'].iloc[i]
        w_df = df.iloc[i - window + 1 : i + 1]
        ratio = (w_df.loc[(w_df['Close'] >= cc*(1-threshold)) & (w_df['Close'] <= cc*(1+threshold)), 'Volume'].sum() / w_df['Volume'].sum() * 100) if w_df['Volume'].sum() > 0 else 50.0
        active_ratio.append(ratio)
    return pd.Series(active_ratio, index=df.index)

def scan_2560_strategy(df):
    if len(df) < 85: return "數據不足", False, 0, 0
    c = float(df['Close'].iloc[-1])
    ma25 = float(df['Close'].rolling(25).mean().iloc[-1])
    return ("🔥 2560扣抵完美共振，站穩25均線", True, ma25 * 0.97, c * 1.08) if c >= ma25 else ("⚖️ 尚未符合2560共振條件", False, c*0.95, c*1.05)

def scan_dual_bollinger_strategy(df):
    if len(df) < 70: return "數據不足", False, 0
    c = float(df['Close'].iloc[-1])
    return ("🔥 雙重布林通道突破下軌反彈", True, c * 0.96) if c > 0 else ("⚖️ 觀望中", False, c*0.95)

def detect_gap_and_support_signals(df):
    if len(df) < 5: return "資料不足", False, 0, 10.0
    c = float(df['Close'].iloc[-1])
    return "🛡️ 近期無重大缺口風險，支撐穩固", False, c * 0.95, 5.0

def detect_60min_divergences(df):
    df['Top_Divergence_Warning'] = False
    df['Secondary_Bottom_Divergence'] = False
    if len(df) >= 30:
        closes = df['Close'].values
        macd_hist = df['MACD_Hist'].values
        if closes[-1] > closes[-15] and macd_hist[-1] < macd_hist[-15]:
            df.loc[df.index[-1], 'Top_Divergence_Warning'] = True
        if closes[-1] < closes[-15] and macd_hist[-1] > macd_hist[-15]:
            df.loc[df.index[-1], 'Secondary_Bottom_Divergence'] = True
    return df

def fetch_from_yahoo_chart_api(symbol, range_str="2y") -> pd.DataFrame:
  clean_sym = symbol.strip().replace(".TW", "").replace(".TWO", "")
  suffixes = [".TWO", ".TW", ""] if clean_sym in OTC_LIST or symbol.endswith(".TWO") else [".TW", ".TWO", ""]
  for suff in suffixes:
      target_ticker = f"{clean_sym}{suff}"
      try:
          url = f"https://query1.finance.yahoo.com/v8/finance/chart/{target_ticker}"
          params = {"range": range_str, "interval": "1d", "includeAdjustedClose": "true"}
          res = _YQ_SESSION.get(url, params=params, timeout=(4, 8))
          if res.status_code == 429:
              # 被限流:讀 Retry-After 精準退避,別盲等,也別當成 404 換下一個後綴
              try:
                  wait_s = min(float(res.headers.get("Retry-After", 3)), 10.0)
              except (TypeError, ValueError):
                  wait_s = 3.0
              time.sleep(wait_s)
              res = _YQ_SESSION.get(url, params=params, timeout=(4, 8))
          if res.status_code == 200:
              json_data = res.json()
              result = json_data.get("chart", {}).get("result", [None])[0]
              if result:
                  timestamps = result.get("timestamp", [])
                  quote = result.get("indicators", {}).get("quote", [{}])[0]
                  closes = quote.get("close", [])
                  if closes and len(closes) > 10:
                      df = pd.DataFrame({
                          "Open": quote.get("open", []), "High": quote.get("high", []),
                          "Low": quote.get("low", []), "Close": closes, "Volume": quote.get("volume", [])
                      }, index=pd.to_datetime([datetime.fromtimestamp(ts).date() for ts in timestamps])).dropna(subset=["Close"])
                      if not df.empty and len(df) >= 30: return df
      except: continue
  return pd.DataFrame()

def get_global_shioaji_client(api_key: str, secret_key: str):
    if not SHIOAJI_AVAILABLE or not api_key or not secret_key: return None
    try:
        api = sj.Shioaji(simulation=True)
        api.login(api_key=api_key.strip(), secret_key=secret_key.strip())
        try: api.fetch_contracts()
        except: pass
        return api
    except: return None

def fetch_multitimeframe_data(ticker_symbol: str, interval_min: int = 60, api_client=None) -> pd.DataFrame:
    clean_code = ticker_symbol.replace(".TW", "").replace(".TWO", "").strip()
    if api_client is not None:
        try:
            contract = api_client.Contracts.Stocks.get(clean_code)
            if contract:
                today_str = datetime.today().strftime('%Y-%m-%d')
                kbars = api_client.kbars(contract, start=today_str, end=today_str)
                df_sj = pd.DataFrame({**kbars})
                if not df_sj.empty:
                    df_sj['ts'] = pd.to_datetime(df_sj['ts'])
                    df_sj.set_index('ts', inplace=True)
                    rule = '15min' if interval_min == 15 else '1h'
                    df_res = df_sj.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna(subset=['Close'])
                    if not df_res.empty: return df_res
        except: pass
    try:
        clean_sym = ticker_symbol.strip().replace(".TW", "").replace(".TWO", "")
        target_t = f"{clean_sym}.TWO" if clean_sym in OTC_LIST else f"{clean_sym}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{target_t}"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {"range": "60d", "interval": "1m", "includeAdjustedClose": "true"}
        res = requests.get(url, headers=headers, params=params, timeout=4)
        if res.status_code == 200:
            json_data = res.json()
            result = json_data.get("chart", {}).get("result", [None])[0]
            if result:
                timestamps = result.get("timestamp", [])
                quote = result.get("indicators", {}).get("quote", [{}])[0]
                df_1m = pd.DataFrame({
                    "Open": quote.get("open", []), "High": quote.get("high", []),
                    "Low": quote.get("low", []), "Close": quote.get("close", []), "Volume": quote.get("volume", [])
                }, index=pd.to_datetime([datetime.fromtimestamp(ts) for ts in timestamps])).dropna(subset=["Close"])
                if not df_1m.empty:
                    rule = '15min' if interval_min == 15 else '1h'
                    return df_1m.resample(rule).agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna(subset=['Close'])
    except: pass
    return pd.DataFrame()

def fetch_yahoo_intraday_data(symbol: str) -> pd.DataFrame:
    try:
        clean_sym = symbol.strip().replace(".TW", "").replace(".TWO", "")
        target_t = f"{clean_sym}.TWO" if clean_sym in OTC_LIST else f"{clean_sym}.TW"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{target_t}"
        headers = {"User-Agent": "Mozilla/5.0"}
        params = {"range": "1d", "interval": "1m", "includeAdjustedClose": "true"}
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code != 200: return pd.DataFrame()
        json_data = res.json()
        result = json_data.get("chart", {}).get("result", [None])[0]
        if not result: return pd.DataFrame()
        timestamps = result.get("timestamp", [])
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        df = pd.DataFrame({
            "Open": quote.get("open", []), "High": quote.get("high", []),
            "Low": quote.get("low", []), "Close": quote.get("close", []), "Volume": quote.get("volume", [])
        }, index=pd.to_datetime([datetime.fromtimestamp(ts) for ts in timestamps])).dropna(subset=["Close"])
        return df
    except: return pd.DataFrame()

def fetch_global_us_dashboard_data():
  symbols = {"SOX": "^SOX", "TSM": "TSM", "DJI": "^DJI", "KOSPI": "^KS11", "USDTWD": "TWD=X"}
  results = {}
  for key, symbol in symbols.items():
    df = fetch_from_yahoo_chart_api(symbol, range_str="10d")
    if not df.empty and len(df) >= 2:
      cp, pp = float(df["Close"].iloc[-1]), float(df["Close"].iloc[-2])
      results[key] = {"price": cp, "change": ((cp - pp) / pp) * 100}
    else:
      fallback_vals = {"SOX": 5150.0, "TSM": 185.0, "DJI": 41200.0, "KOSPI": 2580.0, "USDTWD": 31.85}
      results[key] = {"price": fallback_vals.get(key, 100.0), "change": 0.75}
  return results

class AdvancedWyckoffQuantEngine:
  def process(self, df: pd.DataFrame, prescore: float = 85.0) -> pd.DataFrame:
    data = df.copy()
    if data.empty or len(data) < 20: return data
    data["MA20"] = data["Close"].rolling(20, min_periods=1).mean()
    data["STD20"] = data["Close"].rolling(20, min_periods=1).std(ddof=0).fillna(0)
    data["Upper"] = data["MA20"] + 2 * data["STD20"]
    data["Lower"] = data["MA20"] - 2 * data["STD20"]
    data["RSI_14"] = calculate_rsi(data["Close"], period=14)
    data["MFI"] = estimate_active_chips(data, threshold=0.1, window=14)
    data["CYC20"] = calculate_cyc(data, 20)
    data["MA_13"] = data["Close"].rolling(window=13).mean()
    data["Vol_20MA"] = data["Volume"].rolling(window=20, min_periods=1).mean()
    data["Vol_Surge_Ratio"] = np.where(data["Vol_20MA"] > 0, data["Volume"] / data["Vol_20MA"], 1.0)
    data["ROC_12"] = calculate_roc_indicator(data, 12)
    data["ROC_MA6"] = data["ROC_12"].rolling(6).mean()
    tp_vol = ((data["High"] + data["Low"] + data["Close"]) / 3.0) * data["Volume"]
    data["CYC5"] = tp_vol.rolling(5).sum() / (data["Volume"].rolling(5).sum() + 1e-8)
    data["CYC13"] = tp_vol.rolling(13).sum() / (data["Volume"].rolling(13).sum() + 1e-8)
    data["CYC34"] = tp_vol.rolling(34).sum() / (data["Volume"].rolling(34).sum() + 1e-8)
    k_v, d_v = calculate_kd(data)
    data["k"], data["d"] = k_v, d_v
    dif_v, dea_v, hist_v = calculate_macd(data)
    data["MACD_Line"], data["MACD_Signal"], data["MACD_Hist"] = dif_v, dea_v, hist_v
    return data

ZHTW_MAP = {
    "7734": "印能科技", "5880": "合庫金", "2027": "大成鋼", "2412": "中華電", "2206": "三陽工業", "2395": "研華", "2211": "長榮鋼", "4938": "和碩",
    "2615": "萬海", "2408": "南亞科", "2912": "統一超", "2880": "華南金", "2892": "第一金", "2618": "長榮航", "2886": "兆豐金", "2207": "和泰車",
    "2317": "鴻海", "2610": "華航", "1402": "遠東新", "1476": "儒鴻", "4904": "遠傳", "2884": "玉山金", "2603": "長榮", "3045": "台灣大",
    "2881": "富邦金", "2887": "台新金", "2882": "國泰金", "3702": "大聯大", "3005": "神基", "2451": "創見", "3189": "景碩", "2885": "元大金",
    "1303": "南亞", "8046": "南電", "1216": "統一", "3711": "日月光投控", "2330": "台積電", "2891": "中信金", "2385": "群光", "1102": "亞泥",
    "2645": "長榮航太", "6901": "鑽石生技", "3231": "緯創", "1101": "台泥", "2006": "東鋼", "6669": "緯穎", "2059": "川湖", "2324": "仁寶",
    "2377": "微英", "6505": "台塑化", "2357": "華碩", "2634": "漢翔", "1590": "亞德客-KY", "3034": "聯詠", "2609": "陽明", "5871": "中租-KY",
    "1301": "台塑", "3605": "宏致", "2883": "凱基金", "2303": "聯電", "1605": "華新", "2327": "國巨", "2308": "台達電", "4958": "臻鼎-KY",
    "4764": "雙鍵", "2344": "華邦電", "2105": "正新", "2301": "光寶科", "1504": "東元", "3037": "欣興", "1319": "東陽", "8069": "元太",
    "2368": "金像電", "2492": "華新科", "3044": "健鼎", "1802": "台玻", "6412": "群電", "3416": "融程電", "2379": "瑞昱", "6937": "天虹",
    "2360": "致茂", "3653": "健策", "4770": "上品", "1326": "台化", "6213": "聯茂", "3017": "奇鋐", "6409": "旭隼", "2415": "錩新",
    "2630": "亞航", "4572": "駐龍", "6139": "亞翔", "2481": "強茂", "2454": "聯發科", "2382": "廣達", "7769": "鴻勁", "7768": "頌勝",
    "5234": "達星", "2313": "華通", "2467": "志聖", "3023": "信邦", "2383": "台光電", "2478": "大毅", "4919": "新唐", "3583": "辛耘",
    "2345": "智邦", "2449": "京元電子", "1795": "美時", "6285": "啟碁", "8210": "勤誠", "6449": "鈺邦", "6239": "力成", "5269": "祥碩",
    "3090": "日電貿", "1717": "長興", "2474": "可成", "2428": "興勤", "2483": "百容", "3015": "全網", "6451": "訊芯-KY", "3008": "大立光",
    "3665": "貿聯-KY", "0055": "元大MSCI金融", "00713": "元大台灣高息低波", "00939": "統一台灣高息動能", "00918": "大華優利高填息", "00919": "群益台灣精選高股息",
    "2002": "中鋼", "3081": "聯亞", "3163": "波若威", "1560": "中砂", "3035": "智原", "5403": "中菲", "2354": "鴻準", "6197": "佳必琪",
    "2458": "義隆", "8033": "雷虎", "00878": "國泰永續高股息", "0056": "元大高股息", "00921": "兆豐龍頭等權重", "00701": "國泰臺灣低波動",
    "00934": "中信成長高股息", "00915": "凱基台灣優選高股息", "00940": "元大臺灣價值高股息", "3363": "上詮", "7719": "碳基", "3450": "聯鈞",
    "8112": "至上", "4908": "前鼎", "6163": "華電網", "6442": "光盛", "3013": "晟銘電", "4749": "新應材", "6223": "旺矽", "3587": "閎康",
    "3131": "弘塑", "3661": "世芯-KY", "6176": "瑞儀", "2417": "圓剛", "3406": "玉晶光", "1582": "信錦", "3533": "嘉澤", "3019": "亞光",
    "2421": "建準", "1513": "中興電", "2404": "漢唐", "2312": "金寶", "6257": "矽格", "4909": "新復興", "6515": "穎崴", "4949": "有成精密",
    "2402": "毅嘉", "2390": "云辰", "8042": "金山電", "5222": "全訊", "4956": "光鋐", "6271": "同欣電", "6146": "耕興", "3014": "聯陽",
    "6143": "振曜", "2472": "立隆電", "3026": "禾伸堂", "3227": "原相", "6224": "聚鼎", "00733": "富邦臺灣中小", "0050": "元大台灣50",
    "006208": "富邦台50", "00403A": "特選大聯軍科技ETF", "0052": "富邦科技", "00927": "群益半導體收益", "9105": "泰金寶-DR", "2457": "飛宏",
    "3138": "耀登", "2328": "廣宇", "2409": "友達", "6618": "永虹先進", "6781": "AES-KY", "3211": "順達", "4931": "新盛力", "5309": "系統電",
    "3323": "加百裕", "6282": "康舒", "2392": "正崴", "3003": "健和興", "3491": "昇達科", "2355": "敬鵬", "2314": "台揚", "2419": "仲琦",
    "3380": "明泰", "6274": "台燿", "2367": "燿華", "6672": "騰輝-KY", "3105": "穩懋", "3042": "晶技", "8289": "泰藝", "3221": "台嘉碩",
    "2455": "全新", "4971": "IET-KY", "4991": "環宇-KY", "8086": "宏捷科", "3443": "創意", "3228": "金麗科", "5347": "世界先進", "3265": "台星科",
    "6510": "精測", "6683": "雍智科技", "6830": "汎銓", "6706": "惠特", "6715": "嘉基", "2486": "一詮", "8261": "富鼎", "6187": "萬潤",
    "6640": "均華", "8111": "立碁", "6588": "東典光電", "7717": "萊德光電-KY", "4979": "華星光", "3234": "光環", "6530": "創威", "8048": "德勝",
    "5371": "中光電", "7402": "邑錡", "3704": "合勤控", "4968": "立積", "4541": "晟田", "4536": "拓凱", "5475": "德宏"
}
OTC_LIST = ["5403", "3081", "3131", "3227", "7734", "5475"]

DEFAULT_TDCC_1000 = {t: 70.0 for t in ZHTW_MAP.keys()}
DEFAULT_TDCC_1000.update({
    "2330": 88.5, "2317": 68.2, "2454": 62.4, "2382": 65.1, "3231": 58.7, "2615": 83.5, "5880": 70.2, "2451": 66.9,
    "8033": 72.5, "2634": 75.0, "5371": 71.0, "3081": 78.4, "3131": 82.0, "3661": 79.5, "3017": 76.2, "6781": 81.0, "5475": 65.0
})

def load_latest_tdcc_data():
    tdcc_map = DEFAULT_TDCC_1000.copy()
    csv_path = os.path.join(os.getcwd(), "latest_tdcc.csv")
    if os.path.exists(csv_path):
        try:
            df_t = pd.read_csv(csv_path)
            for _, row in df_t.iterrows():
                code_s = str(row.get("證券代號", "")).strip()
                pct_s = row.get("大戶持股比率", None)
                if code_s and pct_s is not None: tdcc_map[code_s] = float(pct_s)
        except: pass
    return tdcc_map

DEFAULT_TDCC_1000 = load_latest_tdcc_data()

STRATEGIC_GROUPS = {
    "⚠️ 【大聯軍 - 完整 200+ 檔全軍總動員掃描】": list(ZHTW_MAP.keys()),
    "半導體與 AI 權值核心": ["2330", "2317", "2454", "2382", "3231", "3035", "3661", "2303"],
    "金融保險護盤艦隊": ["2881", "2882", "2891", "2886", "2884", "5880", "2880", "2892"],
    "傳產航運與高股息精銳": ["2603", "2615", "2618", "1402", "1301", "1303", "2002", "0050", "0056", "00878"],
    "⚡ BBU電池備援與AI電源概念精銳": ["6781", "3211", "4931", "5309", "3323", "6282", "2308", "2301", "2392", "3003"],
    "🛰️ Starlink星鏈與低軌衛星概念精銳": ["3491", "2313", "6285", "2355", "2314", "2419", "3380", "2383", "6274", "6213", "2367", "6672", "3105", "5222", "3138", "3042", "8289", "3221", "6271", "6282", "6412", "6442"],
    "🛸 無人機與軍工航天精銳": ['8033', '2634', '5371', '2645', '2630', '7719', '3019', '7402', '3005', '3416', '3704', '5222', '4968', '4541', '5309', '3323', '4536'],
    "💡 矽光子CPO概念精銳": ['3081', '3105', '2455', '4971', '4991', '8086', '3661', '3443', '2454', '3035', '3228', '2330', '2303', '5347', '3711', '6239', '3450', '6257', '3265', '6451', '6223', '6515', '6510', '6683', '6830', '2360', '6706', '2345', '3380', '2317', '2382', '3231', '2308', '3665', '6715', '2392', '6197', '2486', '8261', '2421', '3131', '3583', '6187', '2467', '6640', '3037', '3189', '8046', '2368', '3163', '6442', '3363', '8111', '6588', '7717', '4979', '4908', '3234', '6530', '8048'],
}

def get_defense_line_label(close, ma13):
  return "🚨【最高警戒 - 實質跌破 🛡️ MA13熔斷防線】強制停損避險！" if close < ma13 else "🛡️ MA13熔斷防線 (安全運行中)"

