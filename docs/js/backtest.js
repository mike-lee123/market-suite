import { sma, rsi as calcRsi, macd as calcMacd, bollingerBands } from "./indicators.js";

export function simulateTrades(closes, dates, signals, initialCapital) {
  const trades = [];
  const equityCurve = new Array(closes.length);
  let cash = initialCapital;
  let position = 0; // shares-equivalent, expressed as a capital fraction of 1.0 when in a trade
  let entryPrice = null;
  let entryDate = null;
  let entryIndex = null;

  for (let i = 0; i < closes.length; i++) {
    const wantLong = signals[i] === 1;
    if (wantLong && position === 0) {
      position = 1;
      entryPrice = closes[i];
      entryDate = dates[i];
      entryIndex = i;
    } else if (!wantLong && position === 1) {
      const returnPct = ((closes[i] - entryPrice) / entryPrice) * 100;
      trades.push({
        entry_date: entryDate,
        entry_price: entryPrice,
        exit_date: dates[i],
        exit_price: closes[i],
        return_pct: returnPct,
        holding_days: i - entryIndex,
        is_win: closes[i] > entryPrice,
      });
      cash = cash * (1 + returnPct / 100);
      position = 0;
      entryPrice = null;
    }
    equityCurve[i] = position === 1 ? cash * (closes[i] / entryPrice) : cash;
  }

  if (position === 1) {
    const lastIdx = closes.length - 1;
    const returnPct = ((closes[lastIdx] - entryPrice) / entryPrice) * 100;
    trades.push({
      entry_date: entryDate,
      entry_price: entryPrice,
      exit_date: dates[lastIdx],
      exit_price: closes[lastIdx],
      return_pct: returnPct,
      holding_days: lastIdx - entryIndex,
      is_win: closes[lastIdx] > entryPrice,
    });
  }

  return { equityCurve, trades };
}

export function computeMetrics(closes, equityCurve, trades, initialCapital) {
  const finalEquity = equityCurve[equityCurve.length - 1];
  const totalReturnPct = ((finalEquity - initialCapital) / initialCapital) * 100;
  const buyHoldReturnPct = ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100;

  const years = closes.length / 252;
  const cagrPct = years > 0 ? (Math.pow(finalEquity / initialCapital, 1 / years) - 1) * 100 : 0;

  let peak = equityCurve[0];
  let maxDrawdownPct = 0;
  for (const value of equityCurve) {
    if (value > peak) peak = value;
    const drawdown = ((peak - value) / peak) * 100;
    if (drawdown > maxDrawdownPct) maxDrawdownPct = drawdown;
  }

  const dailyReturns = [];
  for (let i = 1; i < equityCurve.length; i++) {
    dailyReturns.push((equityCurve[i] - equityCurve[i - 1]) / equityCurve[i - 1]);
  }
  const meanReturn = dailyReturns.reduce((a, b) => a + b, 0) / (dailyReturns.length || 1);
  const variance = dailyReturns.reduce((a, b) => a + (b - meanReturn) ** 2, 0) / (dailyReturns.length || 1);
  const stdReturn = Math.sqrt(variance);
  const sharpeRatio = stdReturn > 0 ? (meanReturn / stdReturn) * Math.sqrt(252) : 0;

  const wins = trades.filter((t) => t.is_win);
  const losses = trades.filter((t) => !t.is_win);
  const winRatePct = trades.length > 0 ? (wins.length / trades.length) * 100 : 0;
  const grossProfit = wins.reduce((a, t) => a + Math.max(t.return_pct, 0), 0);
  const grossLoss = Math.abs(losses.reduce((a, t) => a + Math.min(t.return_pct, 0), 0));
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0);

  return {
    total_return_pct: totalReturnPct,
    buy_hold_return_pct: buyHoldReturnPct,
    cagr_pct: cagrPct,
    max_drawdown_pct: maxDrawdownPct,
    sharpe_ratio: sharpeRatio,
    win_rate_pct: winRatePct,
    total_trades: trades.length,
    profit_factor: profitFactor,
  };
}

function dualMaSignals(closes, { fast_period = 5, slow_period = 20 } = {}) {
  const fast = sma(closes, fast_period);
  const slow = sma(closes, slow_period);
  return closes.map((_, i) => (fast[i] !== null && slow[i] !== null && fast[i] > slow[i] ? 1 : 0));
}

function rsiSignals(closes, { rsi_period = 14, buy_threshold = 30, sell_threshold = 70 } = {}) {
  const values = calcRsi(closes, rsi_period);
  const signals = new Array(closes.length).fill(0);
  let holding = false;
  for (let i = 0; i < closes.length; i++) {
    if (!holding && values[i] !== null && values[i] < buy_threshold) holding = true;
    else if (holding && values[i] !== null && values[i] > sell_threshold) holding = false;
    signals[i] = holding ? 1 : 0;
  }
  return signals;
}

function macdSignals(closes) {
  const { dif, dea } = calcMacd(closes);
  return closes.map((_, i) => (dif[i] > dea[i] ? 1 : 0));
}

function bollingerSignals(closes) {
  const { lower, middle } = bollingerBands(closes, 20, 2);
  const signals = new Array(closes.length).fill(0);
  let holding = false;
  for (let i = 0; i < closes.length; i++) {
    if (lower[i] === null) { signals[i] = 0; continue; }
    if (!holding && closes[i] <= lower[i]) holding = true;
    else if (holding && closes[i] >= middle[i]) holding = false;
    signals[i] = holding ? 1 : 0;
  }
  return signals;
}

export function runBacktest(ohlc, strategyKey, params, initialCapital) {
  const { dates, close } = ohlc;
  let signals;
  if (strategyKey === "dual_ma") signals = dualMaSignals(close, params);
  else if (strategyKey === "rsi") signals = rsiSignals(close, params);
  else if (strategyKey === "macd") signals = macdSignals(close);
  else if (strategyKey === "bollinger") signals = bollingerSignals(close);
  else throw new Error(`未知回測策略: ${strategyKey}`);

  const { equityCurve, trades } = simulateTrades(close, dates, signals, initialCapital);
  const metrics = computeMetrics(close, equityCurve, trades, initialCapital);
  return { metrics, equityCurve, trades };
}
