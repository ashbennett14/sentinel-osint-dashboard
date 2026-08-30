const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const script = fs.readFileSync(path.join(__dirname, "../../frontend/static/js/app.js"), "utf8");

function context(leaflet) {
  const mapElement = { innerHTML: "" };
  const sandbox = vm.createContext({
    location: { protocol: "https:", hostname: "sentinel-osint-dashboard.vercel.app" },
    window: { L: leaflet },
    L: leaflet,
    document: { addEventListener() {}, getElementById() { return mapElement; } },
  });
  vm.runInContext(script, sandbox);
  return { sandbox, mapElement };
}

test("map uses key-free tiles with attribution and keeps event overlay separate", () => {
  const attached = [];
  let tileUrl, tileOptions, centre, zoom;
  const map = { setView(c, z) { centre = c; zoom = z; return this; } };
  const leaflet = {
    map(id) { assert.equal(id, "map"); return map; },
    tileLayer(url, options) {
      tileUrl = url;
      tileOptions = options;
      return { addTo(target) { assert.equal(target, map); attached.push("tiles"); } };
    },
    layerGroup() {
      return { addTo(target) { assert.equal(target, map); attached.push("events"); return this; } };
    },
  };
  const { sandbox } = context(leaflet);
  vm.runInContext("initMap()", sandbox);
  assert.equal(tileUrl, "https://tile.openstreetmap.org/{z}/{x}/{y}.png");
  assert.match(tileOptions.attribution, /https:\/\/www.openstreetmap.org\/copyright/);
  assert.equal(tileOptions.className, "sentinel-basemap");
  assert.equal(tileOptions.referrerPolicy, "strict-origin-when-cross-origin");
  assert.equal(tileOptions.updateWhenIdle, true);
  assert.deepEqual(attached, ["tiles", "events"]);
  assert.deepEqual(Array.from(centre), [61.5, 24]);
  assert.equal(zoom, 4);
  assert.equal(vm.runInContext("sevColor(5)", sandbox), "#d22c29");
});

test("missing Leaflet still leaves a useful map-unavailable message", () => {
  const { sandbox, mapElement } = context(undefined);
  vm.runInContext("initMap()", sandbox);
  assert.match(mapElement.innerHTML, /Map unavailable/);
  assert.match(mapElement.innerHTML, /Reporting remains available/);
});
