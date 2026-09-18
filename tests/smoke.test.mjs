// tests/smoke.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("index.html declares the three required tab panels", () => {
  const html = readFileSync(new URL("../docs/index.html", import.meta.url), "utf8");
  assert.match(html, /id="tab-technical"/);
  assert.match(html, /id="tab-options"/);
  assert.match(html, /id="tab-backtest"/);
  assert.match(html, /js\/app\.js/);
});
