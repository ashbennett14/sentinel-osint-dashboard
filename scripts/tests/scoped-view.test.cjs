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

test("an incomplete replay begins at the oldest loaded report and labels its limits", () => {
  const elements = new Map();
  const el = id => {
    if (!elements.has(id)) elements.set(id, {value: "0", max: "1000", setAttribute() {}});
    return elements.get(id);
  };
  let plotted = [];
  const sandbox = vm.createContext({
    document: {getElementById: el},
    state: {window: "30d", search: "warning", category: ""},
    localStorage: {getItem: () => null},
    formatUkTime: value => value,
    plotSigActs: items => { plotted = items; },
    renderFeed() {},
    updateOverview() {},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../../frontend/static/js/reporting-tools.js"), "utf8"), sandbox);
  vm.runInContext(`
    reportingSnapshot = [
      {id: 2, published_at: "2026-11-12T15:00:00Z"},
      {id: 1, published_at: "2026-11-12T14:00:00Z"},
    ];
    reportingMeta = {start:"2026-10-13T16:00:00Z", as_of:"2026-11-12T16:00:00Z", total:501, next_offset:2};
    paintReporting();
  `, sandbox);
  assert.equal(plotted.length, 1);
  assert.equal(plotted[0].id, 1);
  assert.match(el("timelineLabel").textContent, /2026-11-12T14:00/);
  assert.match(el("replayScope").textContent, /2 of 501/);
  assert.match(el("feedCount").textContent, /Replay: 1 of 2/);
});
