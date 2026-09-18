import { test } from "node:test";
import assert from "node:assert/strict";
import { normCdf, blackScholes } from "../../docs/js/options.js";

test("normCdf matches known standard-normal values", () => {
  assert.ok(Math.abs(normCdf(0) - 0.5) < 1e-6);
  assert.ok(Math.abs(normCdf(1.96) - 0.975) < 1e-3);
});

test("blackScholes call price matches the textbook Hull example (~4.76)", () => {
  const result = blackScholes(42, 40, 182.5, 0.10, 0.20, "call");
  assert.ok(Math.abs(result.price - 4.76) < 0.05);
  assert.ok(result.delta > 0.6 && result.delta < 0.8);
});

test("blackScholes put price matches the textbook Hull example (~0.81)", () => {
  const result = blackScholes(42, 40, 182.5, 0.10, 0.20, "put");
  assert.ok(Math.abs(result.price - 0.81) < 0.05);
  assert.ok(result.delta < -0.1 && result.delta > -0.4);
});

test("call and put share the same gamma and vega (put-call parity)", () => {
  const call = blackScholes(100, 100, 30, 0.02, 0.25, "call");
  const put = blackScholes(100, 100, 30, 0.02, 0.25, "put");
  assert.ok(Math.abs(call.gamma - put.gamma) < 1e-9);
  assert.ok(Math.abs(call.vegaPer1Pct - put.vegaPer1Pct) < 1e-9);
});

import { calculateStrategyPayoff } from "../../docs/js/options.js";

test("long_call: capped loss at the premium, unlimited upside", () => {
  const r = calculateStrategyPayoff("long_call", 17000, { k1: 17000, prem1: 50 });
  assert.equal(r.maxLoss, 50 * 50); // premium * point value
  assert.equal(r.maxProfit, "無限");
  assert.ok(r.breakevens.some((b) => Math.abs(b - 17050) < 1));
});

test("long_put: capped loss at the premium, capped-but-large downside profit", () => {
  const r = calculateStrategyPayoff("long_put", 17000, { k1: 17000, prem1: 50 });
  assert.equal(r.maxLoss, 50 * 50);
  assert.ok(r.breakevens.some((b) => Math.abs(b - 16950) < 1));
});

test("bull_call_spread: max profit and max loss are both capped", () => {
  const r = calculateStrategyPayoff("bull_call_spread", 17000, { k1: 17000, k2: 17200, prem1: 80, prem2: 30 });
  assert.equal(r.maxLoss, (80 - 30) * 50);
  assert.equal(r.maxProfit, ((17200 - 17000) - (80 - 30)) * 50);
});

test("iron_condor: max profit is the net credit, both wings cap the loss", () => {
  const r = calculateStrategyPayoff("iron_condor", 17000, {
    put_sell: 16800, put_buy: 16600, call_sell: 17200, call_buy: 17400,
    prem_put_s: 40, prem_put_b: 15, prem_call_s: 40, prem_call_b: 15,
  });
  const netCredit = (40 - 15) + (40 - 15);
  assert.equal(r.maxProfit, netCredit * 50);
});

test("long_straddle: loses both premiums at the strike, profits either direction", () => {
  const r = calculateStrategyPayoff("long_straddle", 17000, { k1: 17000, prem1: 45, prem2: 45 });
  assert.equal(r.maxLoss, (45 + 45) * 50);
  assert.equal(r.maxProfit, "無限");
  const atStrikeIdx = r.prices.findIndex((p) => p === 17000);
  assert.ok(Math.abs(r.payoffs[atStrikeIdx] - (-(45 + 45) * 50)) < 1);
});
