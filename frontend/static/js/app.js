const IS_FILE = location.protocol === "file:";
const IS_LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
const API_BASE = IS_LOCAL ? `${location.protocol}//${location.hostname}:8000` : "";
let READ_ONLY = true;
if (IS_FILE) location.replace("https://sentinel-osint-dashboard.vercel.app/");

const state = {
  ao: "AO_HIGH_NORTH",
  window: "24h",
  search: "",
  category: "",
  notifyEnabled: false,
  knownHighSevIds: new Set(),
  busy: false,
};

// ---------------------------------------------------------------------
// Map
// ---------------------------------------------------------------------
let map, markersLayer;
const markersById = new Map();

const AO_CENTER = {
  AO_HIGH_NORTH: [62.5, 20.0],
  AO_EUROPE: [48.8, 21.5],
  AO_BALKANS: [43.8, 21.0],
  AO_LEVANT: [32.5, 36.0],
};
const AO_ZOOM = { AO_HIGH_NORTH: 4, AO_EUROPE: 4, AO_BALKANS: 5, AO_LEVANT: 6 };
const TERRAIN_LABELS = [
  [63, 10, "Norway"], [63, 17, "Sweden"], [64, 27, "Finland"], [59, 25, "Estonia"],
  [57, 25, "Latvia"], [55.4, 24.2, "Lithuania"], [65, 0, "Norwegian Sea"],
  [56.2, 18.5, "Baltic Sea"], [48.9, 31.5, "Ukraine"], [52.2, 19.3, "Poland"],
  [53.5, 28, "Belarus"], [47.1, 28.2, "Moldova"], [45.8, 25, "Romania"],
  [44, 20.5, "Serbia"], [44.2, 17.4, "Bosnia & Herz."], [41.2, 21.8, "North Macedonia"],
  [42.6, 25.2, "Bulgaria"], [39.6, 22.3, "Greece"], [41.2, 19.9, "Albania"],
  [34.1, 36, "Lebanon"], [35, 38.7, "Syria"], [31.3, 35, "Israel"],
  [31.4, 37, "Jordan"], [33.5, 43, "Iraq"],
];
const AO_META = {
  AO_HIGH_NORTH: {
    title: "High North, Finland & the Baltics",
    description: "Arctic, Nordic and Baltic security · Infrastructure, military posture and regional activity",
    briefTitle: "AO High North Daily Analyst Brief",
    slug: "high-north",
  },
  AO_EUROPE: {
    title: "Ukraine & Eastern Europe",
    description: "Ukraine and eastern / central Europe · Conflict, regional security and spillover activity",
    briefTitle: "AO Ukraine & Eastern Europe Daily Analyst Brief",
    slug: "eastern-europe",
  },
  AO_BALKANS: {
    title: "The Balkans",
    description: "Western Balkans, Greece and Bulgaria · Stability, security posture and regional influence",
    briefTitle: "AO Balkans Daily Analyst Brief",
    slug: "balkans",
  },
  AO_LEVANT: {
    title: "The Levant",
    description: "Lebanon, Jordan and the broader Middle East · State, proxy and cross-border activity",
    briefTitle: "AO Levant Daily Analyst Brief",
    slug: "levant",
  },
};

const WINDOW_LABELS = { "24h": "last 24 hours", "48h": "last 48 hours", "7d": "last 7 days", "30d": "last 30 days" };

function initMap() {
  if (!window.L) {
    const mapEl = document.getElementById("map");
    mapEl.innerHTML = `<div class="map-unavailable"><strong>Map unavailable</strong><span>Reporting remains available in the event list.</span></div>`;
    return;
  }
  map = L.map("map", { zoomControl: true }).setView(AO_CENTER[state.ao], AO_ZOOM[state.ao]);
  // Direct, key-free tiles; let the browser honour the provider's cache headers.
  const streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    className: "sentinel-basemap",
    referrerPolicy: "strict-origin-when-cross-origin",
    updateWhenIdle: true,
    keepBuffer: 1,
    maxZoom: 18,
  });
  const terrain = L.tileLayer("https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg", {
    attribution: 'Terrain: <a href="https://science.nasa.gov/resource/blue-marble/">NASA Blue Marble</a> (static imagery)',
    className: "sentinel-terrain",
    updateWhenIdle: true,
    keepBuffer: 1,
    maxNativeZoom: 8,
  });
  let basemap;
  const terrainButton = document.getElementById("mapLabelsBtn");
  const terrainLabels = L.layerGroup(TERRAIN_LABELS.map(([lat, lng, name]) => L.marker([lat, lng], {
    interactive: false, keyboard: false, pane: "shadowPane",
    icon: L.divIcon({ className: "terrain-label", html: name, iconSize: [0, 0] }),
  })));
  const setBasemap = (next) => {
    if (next === basemap) return;
    if (basemap) map.removeLayer(basemap);
    if (basemap === terrain) map.removeLayer(terrainLabels);
    basemap = next;
    terrainButton.setAttribute("aria-pressed", String(next === terrain));
    if (next === terrain) terrainLabels.addTo(map);
    next.addTo(map);
  };
  terrainButton.addEventListener("click", () => setBasemap(basemap === terrain ? streets : terrain));
  terrain.on("tileerror", () => {
    if (basemap === terrain) setBasemap(streets);
  });
  setBasemap(streets);
  markersLayer = L.layerGroup().addTo(map);
  if (window.ResizeObserver) {
    const mapResize = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    mapResize.observe(map.getContainer());
  }
}

const MAP_EVENT_GLYPHS = {
  airspace_incursion: '<path d="M12 3v18m-4-1 4-3 4 3M4 14l8-5 8 5"/>',
  electronic_warfare: '<path d="M12 13v8M8 21h8M8 6a6 6 0 0 0 0 8m8-8a6 6 0 0 1 0 8"/><circle cx="12" cy="10" r="2"/>',
  cyber_attack: '<rect x="4" y="5" width="16" height="13" rx="2"/><path d="m8 9 3 2.5L8 14m5 0h3M9 21h6"/>',
  sabotage: '<path d="M7 4v4m-3 0h8v2a4 4 0 0 1-4 4H6l-2 3m13 3v-4m-5 0h8v-2a4 4 0 0 0-4-4h-1"/>',
  kinetic_strike: '<path d="m13 3-8 11h6l-1 7 9-11h-6z"/>',
  bombing: '<path d="m12 3 2.2 5 5.3-2-2 5.3L22 14l-5.4 1.3L16 21l-4-3.5L8 21l-.6-5.7L2 14l4.5-2.7-2-5.3 5.3 2z"/>',
  civil_unrest: '<path d="M3 19v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2m2-6a4 4 0 0 1 4 4v2"/><circle cx="9" cy="8" r="3"/><path d="M16 5a3 3 0 0 1 0 6"/>',
  security_operation: '<path d="M12 3 5 6v5c0 4 2.5 7.5 7 10 4.5-2.5 7-6 7-10V6l-7-3Z"/><path d="m9 12 2 2 4-4"/>',
  exercise: '<path d="M5 21V4m0 1h13l-3 4 3 4H5"/>',
  espionage: '<path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/>',
};
const MAP_DEFAULT_GLYPH = '<path d="M6 4h9l3 3v13H6zM9 10h6m-6 4h6"/>';

function eventMapIcon(event) {
  const severity = Math.min(5, Math.max(1, Math.round(Number(event.severity) || 1)));
  const glyph = Object.hasOwn(MAP_EVENT_GLYPHS, event.category) ? MAP_EVENT_GLYPHS[event.category] : MAP_DEFAULT_GLYPH;
  return L.divIcon({
    className: `event-map-icon event-map-severity-${severity}`,
    html: `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${glyph}</svg>`,
    iconSize: [24, 24], iconAnchor: [12, 12], popupAnchor: [0, -13],
  });
}

function plotSigActs(sigacts, fit = true) {
  if (!markersLayer || !map) return;
  markersLayer.clearLayers();
  markersById.clear();
  const plotted = [];
  sigacts.forEach((s) => {
    if (s.lat == null || s.lon == null) return;
    const marker = L.marker([s.lat, s.lon], {
      icon: eventMapIcon(s),
      title: sourceText(s, "title"),
      zIndexOffset: Math.max(0, Number(s.severity) || 0) * 250,
    });
    let popup =
      `<strong>${escapeHtml(sourceText(s, "title"))}</strong><br>` +
      `<span>${escapeHtml(formatCategory(s.category))} · ${SEVERITY_LABELS[s.severity] || "Unrated"} · ${escapeHtml(s.country || "Approximate location")}</span><br>` +
      `<a href="${safeUrl(s.url)}" target="_blank" rel="noopener">source ↗</a><br>${evidenceButton(s.id)}`;
    if (s.cluster_size > 1) {
      popup += `<div class="cluster-sources">${s.cluster_size - 1} related article(s) · may repeat the same account</div>`;
    }
    marker.bindPopup(popup);
    marker.on("click", () => selectEvent(s.id, true));
    marker.addTo(markersLayer);
    markersById.set(s.id, marker);
    // An outlying Greenland/Atlantic report should not pull the Nordic
    // overview off the region. Its marker and Locate action remain available.
    if (state.ao !== "AO_HIGH_NORTH" || (s.lon >= -6 && s.lon <= 45 && s.lat >= 53 && s.lat <= 75)) {
      plotted.push(marker.getLatLng());
    }
  });
  if (fit && plotted.length) {
    map.fitBounds(L.latLngBounds(plotted), { padding: [28, 28], maxZoom: 7 });
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

function plainReporting(value) {
  const decoder = document.createElement("textarea");
  let text = String(value || "");
  for (let i = 0; i < 2; i++) {
    decoder.innerHTML = text.replace(/<[^>]*>/g, " ");
    text = decoder.value;
  }
  return text.replace(/\s+/g, " ").trim();
}

const browserTranslations = new Map();
const sourceText = (s, field) => browserTranslations.get(s.id)?.[field] || plainReporting(s[field + "_en"] || s[field]);
const browserCanTranslate = () => typeof window.Translator?.create === "function" &&
  typeof window.LanguageDetector?.create === "function";
const SEVERITY_LABELS = {1:"Low", 2:"Low", 3:"Medium", 4:"High", 5:"Critical"};

async function translateReport(s, button) {
  const status = button.closest("article").querySelector(".translation-status");
  button.disabled = true;
  status.textContent = "Preparing browser translation…";
  let detector, translator;
  try {
    const title = plainReporting(s.title);
    const summary = plainReporting(s.summary).slice(0, 800);
    detector = await window.LanguageDetector.create();
    const [language] = await detector.detect(`${title}\n${summary}`);
    if (!language || ["en", "und"].includes(language.detectedLanguage)) {
      status.textContent = "The browser could not identify a translation to offer.";
      return;
    }
    translator = await window.Translator.create({sourceLanguage:language.detectedLanguage, targetLanguage:"en"});
    const translated = {title:await translator.translate(title), summary:summary ? await translator.translate(summary) : ""};
    if (browserTranslations.size >= 200) browserTranslations.delete(browserTranslations.keys().next().value);
    browserTranslations.set(s.id, translated);
    if (button.isConnected) {
      const item = button.closest("article");
      item.querySelector(".feed-title").textContent = translated.title;
      const excerpt = item.querySelector(".feed-summary");
      if (excerpt) excerpt.textContent = translated.summary.slice(0, 180) + (translated.summary.length > 180 ? "…" : "");
      status.textContent = "Machine translated · original in Evidence";
      button.hidden = true;
    }
  } catch (_) {
    status.textContent = "Translation unavailable in this browser. The original is in Evidence.";
  } finally {
    detector?.destroy?.();
    translator?.destroy?.();
    button.disabled = false;
  }
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch (_) {
    return "#";
  }
}

function formatCategory(value) {
  return (value || "other reporting").replaceAll("_", " ");
}

function updateAoHeader() {
  const meta = AO_META[state.ao];
  document.getElementById("aoTitle").textContent = meta.title;
  document.getElementById("aoDescription").textContent = meta.description;
  document.getElementById("kpiWindow").textContent = WINDOW_LABELS[state.window];
}

function updateOverview(sigacts) {
  document.getElementById("kpiEvents").textContent = sigacts.length.toLocaleString();
  document.getElementById("kpiCritical").textContent = sigacts.filter((s) => s.severity >= 4).length.toLocaleString();
  document.getElementById("kpiMapped").textContent = sigacts.filter((s) => s.lat != null && s.lon != null).length.toLocaleString();
  document.getElementById("kpiWindow").textContent = WINDOW_LABELS[state.window];
}

// ---------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------
async function fetchJson(path, options) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) throw Object.assign(new Error(`${path} -> ${res.status}`), { status: res.status });
  if (res.status === 204) return null;
  return res.json();
}

function setButtonBusy(button, busy, busyLabel) {
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = busyLabel;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
  }
}

async function triggerJob(path, button, busyLabel, successLabel) {
  setButtonBusy(button, true, busyLabel);
  try {
    await fetchJson(path, { method: "POST" });
    button.textContent = successLabel;
    window.setTimeout(() => refreshAll(), 2500);
  } catch (e) {
    button.textContent = "Could not start";
  } finally {
    window.setTimeout(() => setButtonBusy(button, false), 1800);
  }
}

let sigactRequest = 0;
async function refreshSigActs() {
  const request = ++sigactRequest;
  try {
    const params = new URLSearchParams({ ao: state.ao, window: state.window });
    if (state.search) params.set("q", state.search);
    if (state.category) params.set("category", state.category);
    const data = await fetchJson(`/api/sigacts?${params.toString()}`);
    if (request !== sigactRequest) return;
    receiveReporting(data);
    maybeNotify(data);
  } catch (e) {
    if (request !== sigactRequest) return;
    console.warn("sigacts fetch failed", e);
    document.getElementById("feedCount").textContent = "Unavailable";
    document.getElementById("feedList").textContent = "Latest reporting could not load. The dashboard will retry automatically.";
  }
}

function resetScopedView(regionChanged) {
  resetReportingTimeline();
  plotSigActs([], false);
  document.getElementById("feedList").textContent = "Loading reporting…";
  document.getElementById("feedCount").textContent = "Loading…";
  for (const id of ["kpiEvents", "kpiCritical", "kpiMapped"]) document.getElementById(id).textContent = "—";
  document.getElementById("synStrategic").textContent = "Loading synopsis…";
  document.getElementById("synOperational").textContent = "—";
  document.getElementById("synTactical").textContent = "—";
  const synopsisMeta = document.getElementById("synopsisMeta");
  synopsisMeta.textContent = WINDOW_LABELS[state.window];
  synopsisMeta.removeAttribute("title");
  synopsisMeta.classList.remove("is-stale");
  if (!regionChanged) return;
  document.getElementById("evidenceDrawer").close();
  document.getElementById("briefHistory").replaceChildren(new Option("Latest", "latest"));
  document.getElementById("kpiSources").textContent = "—";
  document.getElementById("sourcesList").replaceChildren();
  document.getElementById("sourceCoverage").textContent = "Loading regional feed coverage…";
  map?.setView(AO_CENTER[state.ao], AO_ZOOM[state.ao], {animate:false});
}

let synopsisRequest = 0;
async function refreshSynopsis() {
  const request = ++synopsisRequest;
  const strategicEl = document.getElementById("synStrategic");
  const operationalEl = document.getElementById("synOperational");
  const tacticalEl = document.getElementById("synTactical");
  const metaEl = document.getElementById("synopsisMeta");
  try {
    const data = await fetchJson(`/api/synopsis?ao=${state.ao}&window=${state.window}`);
    if (request !== synopsisRequest) return;
    strategicEl.textContent = data.strategic || "—";
    operationalEl.textContent = data.operational || "—";
    tacticalEl.textContent = data.tactical || "—";
    showFreshness(metaEl, data.generated_at, 8);
    metaEl.textContent = `Window: ${WINDOW_LABELS[data.window] || WINDOW_LABELS[state.window]} · ${metaEl.textContent}`;
  } catch (e) {
    if (request !== synopsisRequest) return;
    strategicEl.textContent = e.status === 404 ? "No synopsis has been published for this region and window." : "The synopsis could not load. The dashboard will retry automatically.";
    operationalEl.textContent = "—";
    tacticalEl.textContent = "—";
    metaEl.textContent = "Update unavailable";
    metaEl.classList.add("is-stale");
  }
}

let briefRequest = 0;
let briefHistoryRequest = 0;
let briefPdfSelection = "";
let currentAudioEpisode = null;

function withoutClassification(content) {
  return (content || "")
    .replace(/^\*\*Classification:\*\*[^\n]*(?:\n|$)/gim, "")
    .replace(/^Classification:[^\n]*(?:\n|$)/gim, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

async function refreshBrief(briefId) {
  const request = ++briefRequest;
  const el = document.getElementById("briefContent");
  const metaEl = document.getElementById("briefMeta");
  const factBox = document.getElementById("factCheckBox");
  const factText = document.getElementById("factCheckText");
  const path = briefId && briefId !== "latest"
    ? `/api/briefs/${briefId}`
    : `/api/brief/latest?ao=${state.ao}`;
  if (path !== briefPdfSelection) {
    updateBriefPdfLinks(null);
    el.textContent = "Loading regional brief…";
    metaEl.textContent = "";
    metaEl.removeAttribute("title");
    metaEl.classList.remove("is-stale");
    document.getElementById("briefNav").replaceChildren();
    factBox.classList.add("hidden");
    factBox.open = false;
  }
  briefPdfSelection = path;
  try {
    const data = await fetchJson(path);
    if (request !== briefRequest) return;
    const currentBriefContent = withoutClassification(data.content);
    const rendered = marked.parse(currentBriefContent);
    el.innerHTML = window.DOMPurify
      ? DOMPurify.sanitize(rendered, { USE_PROFILES: { html: true } })
      : escapeHtml(currentBriefContent);
    el.querySelector("h1")?.remove();
    const headings = [...el.querySelectorAll("h2")];
    document.getElementById("briefNav").innerHTML = headings.map((heading, index) => {
      heading.id = `brief-section-${index}`;
      return `<a href="#${heading.id}">${escapeHtml(heading.textContent.replace(/^\d+[.)]\s*/, ""))}</a>`;
    }).join("");
    showFreshness(metaEl, data.generated_at, 30);
    updateBriefPdfLinks(data.id);
    if (data.fact_check_notes) {
      factText.textContent = data.fact_check_notes;
      factBox.classList.remove("hidden");
    } else {
      factBox.classList.add("hidden");
    }
  } catch (e) {
    if (request !== briefRequest) return;
    updateBriefPdfLinks(null);
    el.textContent = e.status === 404 ? "No regional brief has been published for this selection." : "The regional brief could not load. The dashboard will retry automatically.";
    document.getElementById("briefNav").innerHTML = "";
    metaEl.textContent = "Update unavailable";
    metaEl.classList.add("is-stale");
    factBox.classList.add("hidden");
  }
}

async function refreshBriefHistory() {
  const request = ++briefHistoryRequest;
  const select = document.getElementById("briefHistory");
  try {
    const briefs = await fetchJson(`/api/briefs?ao=${state.ao}&limit=30`);
    if (request !== briefHistoryRequest) return;
    const currentValue = select.value;
    select.innerHTML = `<option value="latest">Latest</option>` + briefs.map(
      (b) => `<option value="${b.id}">${formatUkTime(b.generated_at)}</option>`
    ).join("");
    select.value = currentValue || "latest";
  } catch (e) {
    console.warn("brief history fetch failed", e);
  }
}

function formatAudioTime(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  const mins = Math.floor(value / 60);
  return `${mins}:${String(value % 60).padStart(2, "0")}`;
}

const ukDay = new Intl.DateTimeFormat("en-CA", {timeZone:"Europe/London", year:"numeric", month:"2-digit", day:"2-digit"});
let audioRequest = 0;

async function refreshAudioBrief(episodeId) {
  const request = ++audioRequest;
  const title = document.getElementById("audioEpisodeTitle");
  const meta = document.getElementById("audioBriefMeta");
  const period = document.getElementById("audioPeriod");
  const player = document.getElementById("audioPlayer");
  const chapters = document.getElementById("audioChapters");
  const transcript = document.getElementById("audioTranscript");
  const download = document.getElementById("downloadAudioBtn");
  try {
    const path = episodeId && episodeId !== "latest"
      ? `/api/audio-briefs/${episodeId}`
      : "/api/audio-brief/latest";
    const data = await fetchJson(path);
    if (request !== audioRequest) return;
    const previousId = currentAudioEpisode && currentAudioEpisode.id;
    const previousAudioUrl = currentAudioEpisode && currentAudioEpisode.audio_url;
    currentAudioEpisode = data;
    title.textContent = data.title;
    const latest = !episodeId || episodeId === "latest";
    const previousEdition = latest && ukDay.format(new Date()) > data.episode_date;
    const prefix = previousEdition ? "Today’s episode not yet available · Latest: " : "";
    meta.textContent = `${prefix}${data.episode_date} edition · ${formatAudioTime(data.duration_seconds)} · Published ${formatUkTime(data.generated_at)}`;
    meta.classList.toggle("is-stale", previousEdition);
    period.textContent = `Reporting period: ${formatUkTime(data.period_start)} to ${formatUkTime(data.period_end)} · All four regions`;
    transcript.textContent = data.transcript || "No transcript is available.";
    download.disabled = !data.audio_url;
    if (data.audio_url && (previousId !== data.id || previousAudioUrl !== data.audio_url || !player.src)) {
      player.src = `${API_BASE}${data.audio_url}`;
      player.load();
    }
    const aoChapters = (data.chapters || []).filter((chapter) =>
      ["high-north", "eastern-europe", "balkans", "levant"].includes(chapter.key)
    );
    chapters.innerHTML = aoChapters.map((chapter) => `
      <button class="chapter-btn" data-start="${Number(chapter.start_seconds) || 0}">
        <span class="chapter-time">${formatAudioTime(chapter.start_seconds)}</span>${escapeHtml(chapter.title)}
      </button>
    `).join("");
    chapters.querySelectorAll(".chapter-btn").forEach((button) => {
      button.addEventListener("click", () => {
        player.currentTime = Number(button.dataset.start) || 0;
        player.play().catch(() => {});
      });
    });
    updateAudioChapter();
  } catch (e) {
    if (request !== audioRequest) return;
    currentAudioEpisode = null;
    title.textContent = "Episode unavailable";
    meta.textContent = e.status === 404 ? "No episode published for this selection" : "Could not check the episode. The dashboard will retry.";
    meta.classList.add("is-stale");
    period.textContent = READ_ONLY ? "No episode is available right now. New episodes are published automatically." : "Generate the first episode now, or leave SENTINEL running for the morning schedule.";
    transcript.textContent = "No transcript is available yet.";
    chapters.innerHTML = "";
    download.disabled = true;
    player.removeAttribute("src");
    player.load();
  }
}

async function refreshAudioHistory() {
  const select = document.getElementById("audioBriefHistory");
  try {
    const episodes = await fetchJson("/api/audio-briefs?limit=30");
    const currentValue = select.value;
    select.innerHTML = `<option value="latest">Latest episode</option>` + episodes.map(
      (episode) => `<option value="${episode.id}">${escapeHtml(episode.episode_date)} · ${formatAudioTime(episode.duration_seconds)}</option>`
    ).join("");
    select.value = [...select.options].some((option) => option.value === currentValue)
      ? currentValue
      : "latest";
  } catch (e) {
    console.warn("audio briefing history fetch failed", e);
  }
}

function wireAudioControls() {
  const player = document.getElementById("audioPlayer");
  const playButton = document.getElementById("audioPlayBtn");
  const seek = document.getElementById("audioSeek");
  const mute = document.getElementById("audioMute");
  const elapsed = document.getElementById("audioElapsed");
  const duration = document.getElementById("audioDuration");
  const syncTransport = () => {
    const total = Number.isFinite(player.duration) ? player.duration : 0;
    seek.max = String(total || 1);
    seek.value = String(player.currentTime);
    seek.disabled = !total || !!player.error;
    seek.setAttribute("aria-valuetext", `${formatAudioTime(player.currentTime)} of ${formatAudioTime(total)}`);
    elapsed.textContent = formatAudioTime(player.currentTime);
    duration.textContent = formatAudioTime(total);
    playButton.disabled = !player.currentSrc || !!player.error;
    playButton.setAttribute("aria-label", player.paused ? "Play briefing" : "Pause briefing");
    playButton.firstElementChild.textContent = player.paused ? "▶" : "Ⅱ";
    mute.setAttribute("aria-pressed", String(player.muted));
  };
  ["loadstart", "durationchange", "emptied", "error", "play", "pause", "ended", "timeupdate", "volumechange"].forEach(event => player.addEventListener(event, syncTransport));
  seek.addEventListener("input", () => {
    if (Number.isFinite(player.duration)) player.currentTime = Number(seek.value);
  });
  mute.addEventListener("click", () => { player.muted = !player.muted; });
  player.classList.add("hidden");
  document.getElementById("audioTransport").classList.remove("hidden");
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  const recall = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  playButton.addEventListener("click", () => {
    if (!player.src) return;
    if (player.paused) player.play().catch(() => {}); else player.pause();
  });
  player.addEventListener("loadedmetadata", () => {
    const saved = Number(recall(`sentinel-audio-${currentAudioEpisode?.id}`));
    if (saved > 0 && saved < player.duration - 5) player.currentTime = saved;
    player.playbackRate = Number(document.getElementById("audioSpeed").value);
  });
  player.addEventListener("timeupdate", () => {
    updateAudioChapter();
    if (currentAudioEpisode) remember(`sentinel-audio-${currentAudioEpisode.id}`, String(player.currentTime));
  });
  document.getElementById("audioSpeed").value = recall("sentinel-speed") || "1";
  document.getElementById("audioSpeed").addEventListener("change", (event) => {
    player.playbackRate = Number(event.target.value);
    remember("sentinel-speed", event.target.value);
  });
  const history = document.getElementById("audioBriefHistory");
  const generate = document.getElementById("generateAudioBtn");
  const download = document.getElementById("downloadAudioBtn");
  history.addEventListener("change", () => refreshAudioBrief(history.value));
  download.addEventListener("click", () => {
    if (!currentAudioEpisode || !currentAudioEpisode.audio_url) return;
    const anchor = document.createElement("a");
    anchor.href = `${API_BASE}${currentAudioEpisode.audio_url}?download=true`;
    anchor.download = `sentinel-morning-${currentAudioEpisode.episode_date}.m4a`;
    anchor.click();
  });
  if (READ_ONLY) return;
  generate.addEventListener("click", async () => {
    setButtonBusy(generate, true, "Generating…");
    try {
      await fetchJson("/api/trigger/audio-brief", { method: "POST" });
      generate.textContent = "Generation started";
      window.setTimeout(() => {
        refreshAudioBrief("latest");
        refreshAudioHistory();
      }, 30000);
    } catch (e) {
      generate.textContent = "Could not start";
    } finally {
      window.setTimeout(() => setButtonBusy(generate, false), 2500);
    }
  });
}

async function refreshHealth() {
  const banner = document.getElementById("statusBanner");
  const systemState = document.getElementById("systemState");
  try {
    const data = await fetchJson(`/api/health`);
    document.getElementById("healthDetails").innerHTML = (data.components || []).map((component) =>
      `<div><strong>${escapeHtml({ingest:"Collection",synopsis:"Synopsis",brief:"Daily brief",audio:"Audio briefing"}[component.component] || component.component)}</strong><span>${component.last_success_at ? escapeHtml(timeAgo(component.last_success_at)) : "Awaiting update"}${component.last_error ? " · delayed" : ""}</span></div>`
    ).join("");
    const ingest = (data.components || []).find((c) => c.component === "ingest");
    const fresh = document.getElementById("reportingFreshness");
    const collected = reportingDate(ingest?.last_success_at);
    const delayed = !Number.isFinite(collected) || !!ingest?.last_error || Date.now() - collected > 2 * 3600000;
    fresh.textContent = Number.isFinite(collected)
      ? `${delayed ? "Collection delayed · " : ""}Last successful collection (all regions): ${formatUkTime(ingest.last_success_at)}${delayed ? " · Recent reporting may be incomplete." : ""}`
      : "Collection time unavailable · Recent reporting may be incomplete.";
    fresh.classList.toggle("is-stale", delayed);
    systemState.textContent = ingest && ingest.last_success_at
      ? `Collected ${timeAgo(ingest.last_success_at)}`
      : "Collection pending";
    document.querySelector(".dot-live").classList.toggle("is-stale", delayed);
    const problems = (data.components || []).filter((c) => c.last_error);
    if (problems.length) {
      banner.textContent = problems.map(
        (c) => `${({ingest:"Collection",synopsis:"Synopsis",brief:"Daily brief",audio:"Audio briefing"}[c.component] || c.component)} update delayed. The last available product is shown.`
      ).join("   |   ");
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  } catch (e) {
    systemState.textContent = "Offline";
    document.getElementById("reportingFreshness").textContent = "Collection status unavailable · Recent reporting may be incomplete.";
    document.getElementById("reportingFreshness").classList.add("is-stale");
    banner.textContent = "Dashboard updates are temporarily unavailable. Retrying automatically.";
    banner.classList.remove("hidden");
  }
}

function renderFeed(sigacts) {
  const list = document.getElementById("feedList");
  const expanded = new Set([...list.querySelectorAll('.feed-details-toggle[aria-expanded="true"]')].map(toggle => toggle.closest("[data-event-id]").dataset.eventId));
  document.getElementById("feedCount").textContent = `${sigacts.length} event${sigacts.length === 1 ? "" : "s"}${timelineIsLive() ? "" : " · replay"}`;
  if (!sigacts.length) {
    list.innerHTML = `<div class="feed-item"><span class="feed-meta">${timelineIsLive() ? "No qualifying events for the selected AO, period and filters." : "No loaded reports were published by this point in the replay."}</span></div>`;
    return;
  }
  list.innerHTML = sigacts.map((s) => {
    const title = sourceText(s, "title");
    const excerpt = sourceText(s, "summary");
    const summary = excerpt.startsWith(title) ? "" : excerpt;
    const related = Math.max(0, (s.cluster_size || 1) - 1);
    const open = expanded.has(String(s.id));
    return `
      <article data-event-id="${s.id}" class="feed-item ${s.severity >= 4 ? "feed-item-critical" : ""}">
        <svg class="feed-document" aria-hidden="true" width="20" height="22" viewBox="0 0 20 22" fill="none" stroke="currentColor"><path d="M4 1.5h8l5 5v13a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-17a1 1 0 0 1 1-1Z"/><path d="M12 2v5h5M6 10h8M6 13h8M6 16h6"/></svg>
        <a class="feed-title" dir="auto" href="${safeUrl(s.url)}" target="_blank" rel="noopener">${escapeHtml(title)}</a>
        ${summary ? `<p class="feed-summary">${escapeHtml(summary.slice(0, 180))}${summary.length > 180 ? "…" : ""}</p>` : ""}
        <time class="feed-time" title="${formatUkTime(s.published_at)}">${timeAgo(s.published_at)}</time>
        <button class="btn-ghost evidence-trigger feed-evidence" type="button" data-evidence-id="${Number(s.id)}" aria-label="Evidence for ${escapeHtml(title).replaceAll('"', '&quot;')}">Evidence</button>
        <div class="feed-actions">
          <button class="feed-details-toggle" type="button" aria-expanded="${open}" aria-controls="feed-details-${s.id}">Details</button>
          ${related ? `<span class="meta">${related} related article${related === 1 ? "" : "s"}</span>` : ""}
          ${s.original_language && browserCanTranslate() && !browserTranslations.has(s.id) ? `<button class="btn-ghost translate-report" data-id="${Number(s.id)}" type="button">Translate to English</button>` : ""}
          ${s.original_language ? `<span class="meta translation-status" role="status">${browserTranslations.has(s.id) ? "Machine translated · original in Evidence" : "Original language"}</span>` : ""}
        </div>
        <div class="feed-footer" id="feed-details-${s.id}"${open ? "" : " hidden"}>
          <span class="severity-pill severity-${s.severity}">${SEVERITY_LABELS[s.severity] || "Unrated"}</span>
          <span class="category-pill">${escapeHtml(formatCategory(s.category))}</span>
          <span>${escapeHtml(s.source_name || "Unknown source")}</span>
          <span>${escapeHtml(s.country || "Location unconfirmed")}</span>
          ${followButton(s.id)}
          ${s.lat != null && s.lon != null ? `<button class="locate-btn" data-id="${s.id}">Locate</button>` : ""}
        </div>
      </article>`;
  }).join("");

  list.querySelectorAll(".feed-details-toggle").forEach(button => {
    button.addEventListener("click", () => {
      const open = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!open));
      document.getElementById(button.getAttribute("aria-controls")).hidden = open;
    });
  });
  const byId = new Map(sigacts.map(article => [article.id, article]));
  list.querySelectorAll(".translate-report").forEach(button => {
    button.addEventListener("click", () => translateReport(byId.get(Number(button.dataset.id)), button));
  });

  list.querySelectorAll(".locate-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const marker = markersById.get(Number(button.dataset.id));
      if (!marker || !map) return;
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 7), { animate: true });
      marker.openPopup();
      selectEvent(Number(button.dataset.id));
      document.getElementById("map").scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

function timeAgo(isoStr) {
  if (!isoStr) return "";
  const diffMs = Math.max(0, Date.now() - reportingDate(isoStr));
  if (!Number.isFinite(diffMs)) return "";
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

// ---------------------------------------------------------------------
// Desktop notifications for new high-severity SIGACTs
// ---------------------------------------------------------------------
function maybeNotify(sigacts) {
  if (!state.notifyEnabled || !("Notification" in window) || Notification.permission !== "granted") return;
  sigacts.forEach((s) => {
    if (s.severity >= 4 && !state.knownHighSevIds.has(s.id)) {
      state.knownHighSevIds.add(s.id);
      new Notification(`SENTINEL: Sev ${s.severity} ${s.category}`, {
        body: s.title,
        tag: `sigact-${s.id}`,
      });
    }
  });
}

function wireNotifyButton() {
  const btn = document.getElementById("notifyBtn");
  btn.addEventListener("click", async () => {
    if (!("Notification" in window)) {
      alert("This browser doesn't support desktop notifications.");
      return;
    }
    if (Notification.permission !== "granted") {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") return;
    }
    state.notifyEnabled = !state.notifyEnabled;
    btn.textContent = state.notifyEnabled ? "🔔 Alerts: On" : "🔔 Alerts: Off";
  });
}

// ---------------------------------------------------------------------
// Sources panel (CRUD)
// ---------------------------------------------------------------------
let sourcesRequest = 0;
async function refreshSources() {
  const request = ++sourcesRequest;
  const list = document.getElementById("sourcesList");
  const ao = state.ao;
  const coverageEl = document.getElementById("sourceCoverage");
  const expanded = !document.getElementById("sourcesPanel").classList.contains("collapsed");
  try {
    const [sources, coverage] = await Promise.all([
      fetchJson(`/api/sources`),
      expanded ? fetchJson(`/api/source-coverage?ao=${encodeURIComponent(ao)}`).catch(() => null) : null,
    ]);
    if (request !== sourcesRequest || ao !== state.ao) return;
    const enabled = sources.filter((s) => s.enabled);
    const healthy = enabled.filter((s) => s.last_fetched_at && !s.last_error).length;
    const relevant = enabled.filter((s) => s.ao === ao || s.ao === "GLOBAL" || coverage?.by_source[s.id]);
    const relevantHealthy = relevant.filter((s) => s.last_fetched_at && !s.last_error).length;
    document.getElementById("sourceSummary").textContent =
      `All regions: ${healthy}/${enabled.length} feeds fetched without errors`;
    document.getElementById("kpiSources").textContent = `${relevantHealthy}/${relevant.length}`;
    if (expanded) renderCoverage(coverageEl, coverage, relevant);
    list.innerHTML = relevant.map((s) => `
      <div class="source-row">
        <span class="src-name">${escapeHtml(s.name)}</span>
        <span class="src-meta">${s.kind}</span>
        <span class="src-meta">${s.ao}</span>
        <span class="src-meta">${s.reliability}</span>
        <span class="src-meta ${s.last_error ? "src-error" : ""}">${s.last_error ? "Fetch failing" : (s.last_fetched_at ? "Fetched " + timeAgo(s.last_fetched_at) : "Not fetched yet")}${coverage ? ` · ${coverage.by_source[s.id] || 0} recent articles` : ""}</span>
        ${READ_ONLY ? "" : `<button class="src-toggle ${s.enabled ? "on" : "off"}" data-id="${s.id}" data-enabled="${s.enabled}">${s.enabled ? "Enabled" : "Disabled"}</button>
        <button class="src-delete" data-id="${s.id}">Delete</button>`}
      </div>
    `).join("");

    list.querySelectorAll(".src-toggle").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const newEnabled = btn.dataset.enabled !== "true";
        await fetchJson(`/api/sources/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: newEnabled }),
        });
        refreshSources();
      });
    });
    list.querySelectorAll(".src-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm("Delete this source?")) return;
        await fetchJson(`/api/sources/${btn.dataset.id}`, { method: "DELETE" });
        refreshSources();
      });
    });
  } catch (e) {
    if (ao !== state.ao) return;
    coverageEl.textContent = "Source coverage is unavailable.";
    list.innerHTML = `<div class="feed-item"><span class="feed-meta">Could not load sources.</span></div>`;
  }
}

function wireSourcesForm() {
  if (READ_ONLY) return;
  const formToggle = document.getElementById("addSourceBtn");
  const form = document.getElementById("addSourceForm");
  formToggle.addEventListener("click", () => {
    setSourcesCollapsed(false);
    form.classList.toggle("hidden");
  });

  document.getElementById("saveSourceBtn").addEventListener("click", async () => {
    const payload = {
      name: document.getElementById("srcName").value.trim(),
      kind: document.getElementById("srcKind").value,
      url_or_handle: document.getElementById("srcUrl").value.trim(),
      ao: document.getElementById("srcAo").value,
      reliability: document.getElementById("srcReliability").value,
    };
    if (!payload.name || !payload.url_or_handle) {
      alert("Name and URL/handle are required.");
      return;
    }
    try {
      await fetchJson(`/api/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      form.classList.add("hidden");
      document.getElementById("srcName").value = "";
      document.getElementById("srcUrl").value = "";
      refreshSources();
    } catch (e) {
      alert("Could not add source — it may already exist.");
    }
  });
}

function setSourcesCollapsed(collapsed) {
  const panel = document.getElementById("sourcesPanel");
  const button = document.getElementById("sourcesToggleBtn");
  panel.classList.toggle("collapsed", collapsed);
  button.textContent = collapsed ? "Show sources" : "Hide sources";
  button.setAttribute("aria-expanded", String(!collapsed));
}

// ---------------------------------------------------------------------
// Brief download / print
// ---------------------------------------------------------------------
function updateBriefPdfLinks(id) {
  for (const [button, query] of [["downloadBriefBtn", "?download=true"], ["printBriefBtn", ""]]) {
    const link = document.getElementById(button);
    if (Number.isSafeInteger(id) && id > 0) {
      link.href = `${API_BASE}/api/briefs/${id}/pdf${query}`;
      link.removeAttribute("aria-disabled");
    } else {
      link.removeAttribute("href");
      link.setAttribute("aria-disabled", "true");
    }
  }
}

function wireBriefControls() {
  document.getElementById("briefHistory").addEventListener("change", (e) => refreshBrief(e.target.value));
}

// ---------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------
function refreshAll() {
  if (!document.getElementById("evidenceDrawer").open && timelineIsLive()) {
    refreshSigActs();
  }
  refreshSynopsis();
  refreshBrief(document.getElementById("briefHistory").value);
  refreshBriefHistory();
  refreshHealth();
  refreshSources();
  refreshAudioBrief(document.getElementById("audioBriefHistory").value);
  refreshAudioHistory();
}

function wireControls() {
  document.querySelectorAll(".ao-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (state.ao === btn.dataset.ao) return;
      document.querySelectorAll(".ao-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".ao-tab").forEach((b) => b.removeAttribute("aria-current"));
      btn.setAttribute("aria-current", "page");
      btn.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      state.ao = btn.dataset.ao;
      writeView();
      resetScopedView(true);
      document.getElementById("briefTitle").textContent = AO_META[state.ao].briefTitle;
      updateAoHeader();
      refreshSigActs();
      refreshSynopsis();
      refreshBrief("latest");
      refreshBriefHistory();
      refreshSources();
    });
  });

  document.querySelectorAll(".window-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (state.window === btn.dataset.window) return;
      document.querySelectorAll(".window-btn").forEach((b) => { b.classList.remove("active"); b.setAttribute("aria-pressed", "false"); });
      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");
      state.window = btn.dataset.window;
      writeView();
      resetScopedView(false);
      updateAoHeader();
      refreshSigActs();
      refreshSynopsis();
    });
  });

  const collectBtn = document.getElementById("collectBtn");
  if (!READ_ONLY) collectBtn.addEventListener("click", () =>
      triggerJob("/api/trigger/ingest", collectBtn, "Collecting…", "Collection started")
    );
  const analysisBtn = document.getElementById("analysisBtn");
  if (!READ_ONLY) analysisBtn.addEventListener("click", async () => {
    setButtonBusy(analysisBtn, true, "Generating…");
    try {
      await Promise.all([
        fetchJson("/api/trigger/synopsis", { method: "POST" }),
        fetchJson("/api/trigger/brief", { method: "POST" }),
      ]);
      analysisBtn.textContent = "Analysis started";
      window.setTimeout(() => refreshAll(), 5000);
    } catch (e) {
      analysisBtn.textContent = "Could not start";
    } finally {
      window.setTimeout(() => setButtonBusy(analysisBtn, false), 1800);
    }
  });
  document.getElementById("sourcesToggleBtn").addEventListener("click", () => {
    setSourcesCollapsed(!document.getElementById("sourcesPanel").classList.contains("collapsed"));
    if (!document.getElementById("sourcesPanel").classList.contains("collapsed")) refreshSources();
  });

  let searchTimeout;
  document.getElementById("feedSearch").addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      state.search = e.target.value.trim().slice(0, 160);
      writeView(true);
      resetReportingTimeline();
      refreshSigActs();
    }, 300);
  });
  document.getElementById("feedCategoryFilter").addEventListener("change", (e) => {
    state.category = e.target.value;
    writeView();
    resetReportingTimeline();
    refreshSigActs();
  });

  if (!READ_ONLY) wireNotifyButton();
  wireSourcesForm();
  wireBriefControls();
  wireAudioControls();
  wireEvidence();
  wireReportingTools();
}

const ukTime = new Intl.DateTimeFormat("en-GB", {
  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  timeZone: "Europe/London", timeZoneName: "short",
});
const formatUkTime = (value) => {
  const date = reportingDate(value);
  return Number.isFinite(date) ? ukTime.format(date) : "Date unavailable";
};
const evidenceButton = (id) => `<button type="button" class="btn-ghost evidence-trigger" data-evidence-id="${Number(id)}">View evidence</button>`;
let evidenceRequest = 0;
let evidenceTrigger = null;

async function openEvidence(trigger) {
  const ao = state.ao;
  const id = Number(trigger.dataset.evidenceId);
  if (!Number.isSafeInteger(id) || id < 1) return;
  const request = ++evidenceRequest;
  const drawer = document.getElementById("evidenceDrawer");
  const title = document.getElementById("evidenceEvent");
  const status = document.getElementById("evidenceStatus");
  const timeline = document.getElementById("evidenceTimeline");
  const older = document.getElementById("evidenceOlder");
  evidenceTrigger = trigger;
  title.textContent = AO_META[ao].title;
  status.textContent = "Loading evidence…";
  older.textContent = "";
  timeline.replaceChildren();
  drawer.showModal();
  drawer.querySelector(".evidence-body").scrollTop = 0;
  try {
    const data = await fetchJson(`/api/events/${id}/evidence?ao=${encodeURIComponent(ao)}`);
    if (!drawer.open || request !== evidenceRequest || ao !== state.ao) return;
    title.textContent = plainReporting(data.title);
    markStoryRead(data, ao);
    status.textContent = "Related reporting, newest first. Repeated claims may come from the same underlying account.";
    timeline.innerHTML = data.articles.map(article => {
      const excerpt = plainReporting(article.excerpt);
      const url = safeUrl(article.url);
      return `<li><div class="meta">${escapeHtml(article.publisher || "Publisher not listed")} · ${escapeHtml(formatUkTime(article.published_at))}</div><h4 dir="auto">${escapeHtml(plainReporting(article.title))}</h4>${excerpt ? `<p dir="auto">${escapeHtml(excerpt)}</p>` : ""}${url !== "#" ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open original article ↗</a>` : ""}</li>`;
    }).join("");
    if (data.older_count) older.textContent = `${data.older_count} older related article(s) not shown.`;
  } catch (_) {
    if (!drawer.open || request !== evidenceRequest || ao !== state.ao) return;
    status.textContent = "Evidence is unavailable. The event may have expired or moved out of this AO.";
  }
}

function wireEvidence() {
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-evidence-id]");
    if (trigger && !document.getElementById("evidenceDrawer").open) openEvidence(trigger);
  });
  document.getElementById("evidenceDrawer").addEventListener("close", () => {
    evidenceRequest++;
    const target = evidenceTrigger?.isConnected ? evidenceTrigger : document.getElementById("reportingTitle");
    target.focus();
    evidenceTrigger = null;
  });
}

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  if (IS_FILE) return;
  if (IS_LOCAL) {
    try {
      const runtime = await fetchJson("/api/runtime-config", { signal: AbortSignal.timeout(3000) });
      READ_ONLY = runtime.read_only !== false;
    } catch (_) {
      // Fail closed if local admin capability cannot be confirmed.
    }
  }
  document.getElementById("resetMapBtn").addEventListener("click", () => map?.setView(AO_CENTER[state.ao], AO_ZOOM[state.ao]));
  const mapPanel = document.querySelector(".map-panel");
  const expandMapButton = document.getElementById("expandMapBtn");
  const setMapExpanded = (expanded) => {
    mapPanel.classList.toggle("map-expanded", expanded);
    const label = expanded ? "Close expanded map" : "Expand map";
    expandMapButton.setAttribute("aria-label", label);
    expandMapButton.title = label;
    expandMapButton.setAttribute("aria-pressed", String(expanded));
    map?.invalidateSize();
  };
  expandMapButton.addEventListener("click", () => setMapExpanded(!mapPanel.classList.contains("map-expanded")));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && mapPanel.classList.contains("map-expanded") && !document.getElementById("evidenceDrawer").open) {
      setMapExpanded(false);
      expandMapButton.focus();
    }
  });
  document.getElementById("readingModeBtn").addEventListener("click", (event) => {
    const reading = document.body.classList.toggle("reading-mode");
    event.currentTarget.textContent = reading ? "Exit reading view" : "Reading view";
    event.currentTarget.setAttribute("aria-pressed", String(reading));
    document.getElementById("briefPanel").scrollIntoView({behavior:"smooth"});
  });
  const manualControls = ["collectBtn", "analysisBtn", "notifyBtn"];
  if (READ_ONLY) {
    [...manualControls, "addSourceBtn", "addSourceForm", "generateAudioBtn"].forEach((id) => {
      document.getElementById(id)?.classList.add("hidden");
    });
  } else {
    [...manualControls, "addSourceBtn", "generateAudioBtn"].forEach((id) => document.getElementById(id)?.classList.remove("hidden"));
  }
  readView();
  document.getElementById("mapIconKey").innerHTML = Object.entries({...MAP_EVENT_GLYPHS, other:MAP_DEFAULT_GLYPH})
    .map(([category, glyph]) => `<li><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7">${glyph}</svg>${formatCategory(category)}</li>`).join("");
  initMap();
  wireControls();
  document.querySelector(".ao-tab.active")?.setAttribute("aria-current", "page");
  updateAoHeader();
  refreshAll();
  setInterval(refreshAll, 60000); // poll every minute
});

function showFreshness(element, value, hours) {
  const stamp = reportingDate(value);
  const stale = !Number.isFinite(stamp) || Date.now() - stamp > hours * 3600000;
  element.textContent = Number.isFinite(stamp) ? `${stale ? "Earlier edition · Published" : "Published"} ${formatUkTime(value)}` : "Publication time unavailable";
  element.title = Number.isFinite(stamp) ? timeAgo(value) : "No update available";
  element.classList.toggle("is-stale", stale);
}

function selectEvent(id, scroll = false) {
  document.querySelectorAll("[data-event-id]").forEach((item) => {
    const selected = Number(item.dataset.eventId) === Number(id);
    item.classList.toggle("selected-event", selected);
    if (selected && scroll) item.scrollIntoView({behavior:"smooth", block:"nearest"});
  });
}

function updateAudioChapter() {
  const seconds = document.getElementById("audioPlayer").currentTime;
  const chapter = [...(currentAudioEpisode?.chapters || [])].reverse().find((item) => seconds >= item.start_seconds);
  document.querySelectorAll(".chapter-btn").forEach((button) => {
    const active = chapter && Number(button.dataset.start) === chapter.start_seconds;
    button.classList.toggle("active", !!active);
    if (active) button.setAttribute("aria-current", "true"); else button.removeAttribute("aria-current");
  });
}
