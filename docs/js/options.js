function erf(x) {
  // Abramowitz-Stegun 7.1.26 approximation, accurate to ~1.5e-7
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
  const a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const t = 1 / (1 + p * x);
  const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return sign * y;
}

export function normCdf(x) {
  return 0.5 * (1 + erf(x / Math.SQRT2));
}

function normPdf(x) {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
}

export function blackScholes(spot, strike, dteDays, riskFreeRate, iv, optionType) {
  const t = dteDays / 365;
  const d1 = (Math.log(spot / strike) + (riskFreeRate + 0.5 * iv * iv) * t) / (iv * Math.sqrt(t));
  const d2 = d1 - iv * Math.sqrt(t);
  const discount = Math.exp(-riskFreeRate * t);

  let price, delta;
  if (optionType === "call") {
    price = spot * normCdf(d1) - strike * discount * normCdf(d2);
    delta = normCdf(d1);
  } else {
    price = strike * discount * normCdf(-d2) - spot * normCdf(-d1);
    delta = normCdf(d1) - 1;
  }

  const gamma = normPdf(d1) / (spot * iv * Math.sqrt(t));
  const vegaPer1Pct = spot * normPdf(d1) * Math.sqrt(t) * 0.01;

  const thetaAnnualCall = -(spot * normPdf(d1) * iv) / (2 * Math.sqrt(t)) - riskFreeRate * strike * discount * normCdf(d2);
  const thetaAnnualPut = -(spot * normPdf(d1) * iv) / (2 * Math.sqrt(t)) + riskFreeRate * strike * discount * normCdf(-d2);
  const thetaPerDay = (optionType === "call" ? thetaAnnualCall : thetaAnnualPut) / 365;

  return { price, delta, gamma, thetaPerDay, vegaPer1Pct };
}

const POINT_VALUE = 50;

function priceRange(spot) {
  const span = spot * 0.1;
  const step = span / 100;
  if (!(step > 0)) return [];
  const prices = [];
  for (let p = spot - span; p <= spot + span; p += step) prices.push(Math.round(p));
  return prices;
}

function findBreakevens(prices, payoffs) {
  const breakevens = [];
  for (let i = 1; i < payoffs.length; i++) {
    if ((payoffs[i - 1] < 0 && payoffs[i] >= 0) || (payoffs[i - 1] > 0 && payoffs[i] <= 0)) {
      // Linear interpolation to find more precise breakeven
      const p1 = prices[i - 1];
      const p2 = prices[i];
      const y1 = payoffs[i - 1];
      const y2 = payoffs[i];
      const be = p1 - y1 * (p2 - p1) / (y2 - y1);
      breakevens.push(be);
    }
  }
  return breakevens;
}

export function calculateStrategyPayoff(strategyKey, spot, params) {
  const prices = priceRange(spot);
  let payoffs;
  let maxProfit;
  let maxLoss;
  let summary;

  const callPayoff = (price, k) => Math.max(price - k, 0);
  const putPayoff = (price, k) => Math.max(k - price, 0);

  if (strategyKey === "long_call") {
    payoffs = prices.map((p) => (callPayoff(p, params.k1) - params.prem1) * POINT_VALUE);
    maxProfit = "無限";
    maxLoss = params.prem1 * POINT_VALUE;
    summary = `買進履約價 ${params.k1} 的買權,付出權利金 ${params.prem1} 點`;
  } else if (strategyKey === "long_put") {
    payoffs = prices.map((p) => (putPayoff(p, params.k1) - params.prem1) * POINT_VALUE);
    maxProfit = (params.k1 - params.prem1) * POINT_VALUE;
    maxLoss = params.prem1 * POINT_VALUE;
    summary = `買進履約價 ${params.k1} 的賣權,付出權利金 ${params.prem1} 點`;
  } else if (strategyKey === "bull_call_spread") {
    payoffs = prices.map((p) =>
      (callPayoff(p, params.k1) - callPayoff(p, params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE
    );
    maxLoss = (params.prem1 - params.prem2) * POINT_VALUE;
    maxProfit = ((params.k2 - params.k1) - (params.prem1 - params.prem2)) * POINT_VALUE;
    summary = `買進 ${params.k1} 買權、賣出 ${params.k2} 買權`;
  } else if (strategyKey === "bear_put_spread") {
    payoffs = prices.map((p) =>
      (putPayoff(p, params.k1) - putPayoff(p, params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE
    );
    maxLoss = (params.prem1 - params.prem2) * POINT_VALUE;
    maxProfit = ((params.k1 - params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE;
    summary = `買進 ${params.k1} 賣權、賣出 ${params.k2} 賣權`;
  } else if (strategyKey === "bull_put_spread") {
    payoffs = prices.map((p) =>
      (params.prem1 - params.prem2 - putPayoff(p, params.k1) + putPayoff(p, params.k2)) * POINT_VALUE
    );
    maxProfit = (params.prem1 - params.prem2) * POINT_VALUE;
    maxLoss = ((params.k1 - params.k2) - (params.prem1 - params.prem2)) * POINT_VALUE;
    summary = `賣出 ${params.k1} 賣權、買進保護 ${params.k2} 賣權`;
  } else if (strategyKey === "iron_condor") {
    const netCredit = (params.prem_put_s - params.prem_put_b) + (params.prem_call_s - params.prem_call_b);
    payoffs = prices.map((p) => {
      const putLeg = -putPayoff(p, params.put_sell) + putPayoff(p, params.put_buy);
      const callLeg = -callPayoff(p, params.call_sell) + callPayoff(p, params.call_buy);
      return (netCredit + putLeg + callLeg) * POINT_VALUE;
    });
    maxProfit = netCredit * POINT_VALUE;
    const putWing = params.put_sell - params.put_buy;
    const callWing = params.call_buy - params.call_sell;
    maxLoss = (Math.max(putWing, callWing) - netCredit) * POINT_VALUE;
    summary = `賣出 ${params.put_sell}/${params.call_sell} 履約價、兩側買進保護 ${params.put_buy}/${params.call_buy}`;
  } else if (strategyKey === "long_straddle") {
    payoffs = prices.map((p) =>
      (callPayoff(p, params.k1) + putPayoff(p, params.k1) - params.prem1 - params.prem2) * POINT_VALUE
    );
    maxProfit = "無限";
    maxLoss = (params.prem1 + params.prem2) * POINT_VALUE;
    summary = `同時買進履約價 ${params.k1} 的買權與賣權`;
  } else {
    throw new Error(`未知策略: ${strategyKey}`);
  }

  return { prices, payoffs, maxProfit, maxLoss, breakevens: findBreakevens(prices, payoffs), summary };
}
