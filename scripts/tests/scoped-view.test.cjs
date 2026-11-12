const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

test("switching region clears the previous view and ignores late synopsis responses", async () => {
  const elements = new Map();
  const el = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent: "Old region data",
      classList: {add() {}, remove() {}, toggle() {}},
      replaceChildren() {}, removeAttribute() {}, close() {},
    });
    return elements.get(id);
  };
  const pending = [];
  const sandbox = vm.createContext({
    document: {getElementById: el, addEventListener() {}},
    location: {protocol:"https:", hostname:"example.test"},
    Option: function () {},
    console,
    resetReportingTimeline() {},
    reportingDate: Date.parse,
    fetch(url) { return new Promise(resolve => pending.push({url, resolve})); },
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../../frontend/static/js/app.js"), "utf8"), sandbox);
  const oldRequest = vm.runInContext("refreshSynopsis()", sandbox);
  const newRequest = vm.runInContext('state.ao = "AO_LEVANT"; resetScopedView(true); refreshSynopsis()', sandbox);
  assert.equal(el("synStrategic").textContent, "Loading synopsis…");
  assert.equal(el("kpiEvents").textContent, "—");
  assert.equal(el("feedList").textContent, "Loading reporting…");
  assert.match(pending[1].url, /ao=AO_LEVANT/);
  const response = strategic => ({ok:true, json:async () => ({
    strategic, window:"24h", generated_at:"2026-11-12T12:00:00Z",
  })});
  pending[1].resolve(response("Levant assessment"));
  await newRequest;
  pending[0].resolve(response("Old region assessment"));
  await oldRequest;
  assert.equal(el("synStrategic").textContent, "Levant assessment");
  assert.match(el("synopsisMeta").textContent, /Window: last 24 hours.*Published/);
});
