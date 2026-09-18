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
