import { test } from "node:test";
import assert from "node:assert/strict";
import { sma, ema, bollingerBands } from "../../docs/js/indicators.js";

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
