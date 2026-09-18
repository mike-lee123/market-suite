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
