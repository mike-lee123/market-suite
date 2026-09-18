import { test } from "node:test";
import assert from "node:assert/strict";
import { sma, ema, bollingerBands, rsi, kd, macd, bias, diagnoseTrend, diagnoseKD, diagnoseRSI, diagnoseMACD } from "../../docs/js/indicators.js";

test("sma returns null before period is reached, then the rolling mean", () => {
  const result = sma([1, 2, 3, 4, 5], 3);
  assert.equal(result[0], null);
  assert.equal(result[1], null);
  assert.equal(result[2], 2);   // mean(1,2,3)
  assert.equal(result[3], 3);   // mean(2,3,4)
  assert.equal(result[4], 4);   // mean(3,4,5)
});

test("ema seeds with the first value and decays by the standard alpha", () => {
  const result = ema([10, 12, 14], 3); // alpha = 2/(3+1) = 0.5
  assert.equal(result[0], 10);
  assert.equal(result[1], 11);          // 0.5*12 + 0.5*10
  assert.equal(result[2], 12.5);        // 0.5*14 + 0.5*11
});

test("bollingerBands middle band matches sma and bands widen with volatility", () => {
  const values = [10, 10, 10, 10, 20, 10, 10, 10, 10, 10,
                   10, 10, 10, 10, 10, 10, 10, 10, 10, 10];
  const { upper, middle, lower } = bollingerBands(values, 20, 2);
  assert.equal(middle[19], sma(values, 20)[19]);
  assert.ok(upper[19] > middle[19]);
  assert.ok(lower[19] < middle[19]);
  assert.equal(upper[18], null); // fewer than `period` points yet
});

test("rsi is 100 when there are no losses in the window", () => {
  const result = rsi([10, 11, 12, 13, 14, 15, 16], 6);
  assert.equal(result[6], 100);
});

test("rsi is 0 when there are no gains in the window", () => {
  const result = rsi([16, 15, 14, 13, 12, 11, 10], 6);
  assert.equal(result[6], 0);
});

test("kd starts smoothing from 50 and moves toward the RSV", () => {
  const highs = [10, 10, 10, 10, 10, 10, 10, 10, 10, 20];
  const lows  = [ 5,  5,  5,  5,  5,  5,  5,  5,  5,  5];
  const closes= [ 8,  8,  8,  8,  8,  8,  8,  8,  8, 20]; // RSV jumps to 100 on the last bar
  const { k, d } = kd(highs, lows, closes, 9);
  assert.equal(k.length, 10);
  assert.equal(d.length, 10);
  assert.ok(k[9] > k[8]); // K should rise toward the new high RSV
  assert.ok(k[9] < 100);  // but smoothing keeps it below the raw RSV
});

test("macd hist is twice the gap between DIF and DEA", () => {
  const closes = Array.from({ length: 40 }, (_, i) => 100 + i);
  const { dif, dea, hist } = macd(closes, 12, 26, 9);
  const lastIdx = closes.length - 1;
  assert.ok(Math.abs(hist[lastIdx] - 2 * (dif[lastIdx] - dea[lastIdx])) < 1e-9);
});

test("bias is zero when price equals its moving average", () => {
  const flat = new Array(25).fill(100);
  const result = bias(flat, 20);
  assert.equal(result[24], 0);
});

test("diagnoseTrend recognizes bullish and bearish alignment", () => {
  assert.equal(diagnoseTrend(30, 20, 10), "多頭排列 (MA5 > MA20 > MA60)");
  assert.equal(diagnoseTrend(10, 20, 30), "空頭排列 (MA5 < MA20 < MA60)");
  assert.equal(diagnoseTrend(20, 20, 20), "均線糾結/震盪整理");
});

test("diagnoseKD flags golden and death crosses before falling back to zone labels", () => {
  assert.equal(diagnoseKD(55, 50, 48, 50), "黃金交叉 (K向上突破D)");
  assert.equal(diagnoseKD(45, 50, 52, 50), "死亡交叉 (K向下跌破D)");
  assert.equal(diagnoseKD(85, 60, 84, 60), "超買區 (>80)");
  assert.equal(diagnoseKD(15, 40, 16, 40), "超賣區 (<20)");
});

test("diagnoseRSI and diagnoseMACD label zones", () => {
  assert.equal(diagnoseRSI(80), "超買警戒區 (>75)");
  assert.equal(diagnoseRSI(10), "超賣反彈區 (<25)");
  assert.equal(diagnoseRSI(50), "正常波動區");
  assert.equal(diagnoseMACD(1.5), "柱狀圖轉正 (紅柱擴大)");
  assert.equal(diagnoseMACD(-1.5), "柱狀圖為負 (綠柱擴大)");
});
