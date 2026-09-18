export function sma(values, period) {
  const out = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    if (i >= period - 1) out[i] = sum / period;
  }
  return out;
}

export function ema(values, period) {
  const alpha = 2 / (period + 1);
  const out = new Array(values.length);
  out[0] = values[0];
  for (let i = 1; i < values.length; i++) {
    out[i] = alpha * values[i] + (1 - alpha) * out[i - 1];
  }
  return out;
}

export function bollingerBands(values, period = 20, numStd = 2) {
  const middle = sma(values, period);
  const upper = new Array(values.length).fill(null);
  const lower = new Array(values.length).fill(null);
  for (let i = period - 1; i < values.length; i++) {
    const window = values.slice(i - period + 1, i + 1);
    const mean = middle[i];
    const variance = window.reduce((acc, v) => acc + (v - mean) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    upper[i] = mean + numStd * std;
    lower[i] = mean - numStd * std;
  }
  return { upper, middle, lower };
}

export function rsi(closes, period = 6) {
  const out = new Array(closes.length).fill(null);
  const gains = new Array(closes.length).fill(0);
  const losses = new Array(closes.length).fill(0);
  for (let i = 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    gains[i] = delta > 0 ? delta : 0;
    losses[i] = delta < 0 ? -delta : 0;
  }
  for (let i = 0; i < closes.length; i++) {
    const start = Math.max(0, i - period + 1);
    const windowGains = gains.slice(start, i + 1);
    const windowLosses = losses.slice(start, i + 1);
    const avgGain = windowGains.reduce((a, b) => a + b, 0) / windowGains.length;
    const avgLoss = windowLosses.reduce((a, b) => a + b, 0) / windowLosses.length;
    if (avgLoss === 0) {
      out[i] = avgGain === 0 ? 50 : 100;
    } else {
      const rs = avgGain / avgLoss;
      out[i] = 100 - 100 / (1 + rs);
    }
  }
  return out;
}

export function kd(highs, lows, closes, period = 9) {
  const k = new Array(closes.length);
  const d = new Array(closes.length);
  let lastK = 50;
  let lastD = 50;
  for (let i = 0; i < closes.length; i++) {
    const start = Math.max(0, i - period + 1);
    const highMax = Math.max(...highs.slice(start, i + 1));
    const lowMin = Math.min(...lows.slice(start, i + 1));
    const denom = highMax - lowMin;
    const rsv = denom === 0 ? 50 : ((closes[i] - lowMin) / denom) * 100;
    const currentK = (2 / 3) * lastK + (1 / 3) * rsv;
    const currentD = (2 / 3) * lastD + (1 / 3) * currentK;
    k[i] = currentK;
    d[i] = currentD;
    lastK = currentK;
    lastD = currentD;
  }
  return { k, d };
}

export function macd(closes, fast = 12, slow = 26, signalPeriod = 9) {
  const emaFast = ema(closes, fast);
  const emaSlow = ema(closes, slow);
  const dif = closes.map((_, i) => emaFast[i] - emaSlow[i]);
  const dea = ema(dif, signalPeriod);
  const hist = dif.map((v, i) => (v - dea[i]) * 2);
  return { dif, dea, hist };
}

export function bias(closes, period = 20) {
  const ma = sma(closes, period);
  return closes.map((c, i) => (ma[i] === null ? null : ((c - ma[i]) / ma[i]) * 100));
}

export function diagnoseTrend(ma5, ma20, ma60) {
  if (ma5 > ma20 && ma20 > ma60) return "多頭排列 (MA5 > MA20 > MA60)";
  if (ma5 < ma20 && ma20 < ma60) return "空頭排列 (MA5 < MA20 < MA60)";
  return "均線糾結/震盪整理";
}

export function diagnoseKD(k, d, prevK, prevD) {
  if (k > d && prevK <= prevD) return "黃金交叉 (K向上突破D)";
  if (k < d && prevK >= prevD) return "死亡交叉 (K向下跌破D)";
  if (k > 80) return "超買區 (>80)";
  if (k < 20) return "超賣區 (<20)";
  return "中性區域";
}

export function diagnoseRSI(rsiValue) {
  if (rsiValue > 75) return "超買警戒區 (>75)";
  if (rsiValue < 25) return "超賣反彈區 (<25)";
  return "正常波動區";
}

export function diagnoseMACD(hist) {
  return hist > 0 ? "柱狀圖轉正 (紅柱擴大)" : "柱狀圖為負 (綠柱擴大)";
}
