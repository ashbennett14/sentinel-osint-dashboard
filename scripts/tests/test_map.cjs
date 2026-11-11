const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const script = fs.readFileSync(path.join(__dirname, "../../frontend/static/js/app.js"), "utf8");

function context(leaflet) {
  const mapElement = { innerHTML: "", addEventListener() {} };
  const sandbox = vm.createContext({
    location: { protocol: "https:", hostname: "sentinel-osint-dashboard.vercel.app" },
    window: { L: leaflet },
    L: leaflet,
    document: { addEventListener() {}, getElementById() { return mapElement; } },
  });
  vm.runInContext(script, sandbox);
  return { sandbox, mapElement };
}

test("map uses attributed terrain at regional zoom and falls back to streets", () => {
  const attached = [];
  const layers = [];
  const handlers = {};
  let centre, zoom;
  const map = {
    setView(c, z) { centre = c; zoom = z; return this; },
    getZoom() { return zoom; },
    on(event, handler) { handlers[event] = handler; },
    removeLayer(layer) { attached.push(`removed:${layer.options.className}`); },
  };
  const leaflet = {
    map(id) { assert.equal(id, "map"); return map; },
    tileLayer(url, options) {
      const layer = {
        url, options, events: {},
        on(event, handler) { this.events[event] = handler; },
        addTo(target) { assert.equal(target, map); attached.push(options.className); },
      };
      layers.push(layer);
      return layer;
    },
    divIcon(options) { return options; },
    marker(coords, options) { return { coords, options }; },
    layerGroup(markers) {
      return { options: {className: "labels"}, addTo(target) { assert.equal(target, map); attached.push(markers ? "labels" : "events"); return this; } };
    },
  };
  const { sandbox } = context(leaflet);
  vm.runInContext("initMap()", sandbox);
  const [streets, terrain] = layers;
  assert.equal(streets.url, "https://tile.openstreetmap.org/{z}/{x}/{y}.png");
  assert.match(streets.options.attribution, /https:\/\/www.openstreetmap.org\/copyright/);
  assert.match(terrain.url, /BlueMarble_ShadedRelief_Bathymetry.*\{z\}\/\{y\}\/\{x\}/);
  assert.match(terrain.options.attribution, /NASA Blue Marble/);
  assert.deepEqual(attached, ["sentinel-terrain", "labels", "events"]);
  assert.deepEqual(Array.from(centre), [62.5, 20]);
  assert.equal(zoom, 4);
  zoom = 8;
  handlers.zoomend();
  assert.deepEqual(attached.slice(-3), ["removed:sentinel-terrain", "removed:labels", "sentinel-basemap"]);
  zoom = 4;
  handlers.zoomend();
  assert.deepEqual(attached.slice(-2), ["sentinel-terrain", "labels"]);
  terrain.events.tileerror();
  assert.equal(attached.at(-1), "sentinel-basemap");
  assert.equal(vm.runInContext("sevColor(5)", sandbox), "#d22c29");
});

test("missing Leaflet still leaves a useful map-unavailable message", () => {
  const { sandbox, mapElement } = context(undefined);
  vm.runInContext("initMap()", sandbox);
  assert.match(mapElement.innerHTML, /Map unavailable/);
  assert.match(mapElement.innerHTML, /Reporting remains available/);
});
