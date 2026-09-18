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
