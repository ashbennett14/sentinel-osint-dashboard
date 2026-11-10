const IS_LOCAL = location.protocol === "file:" || ["localhost", "127.0.0.1"].includes(location.hostname);
const API_BASE = location.protocol === "file:"
  ? "http://localhost:8000"
  : (IS_LOCAL ? `${location.protocol}//${location.hostname}:8000` : "");
let READ_ONLY = !IS_LOCAL;

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
  AO_HIGH_NORTH: [61.5, 24.0],
  AO_EUROPE: [48.8, 21.5],
  AO_BALKANS: [43.8, 21.0],
  AO_LEVANT: [32.5, 36.0],
};
const AO_ZOOM = { AO_HIGH_NORTH: 4, AO_EUROPE: 4, AO_BALKANS: 5, AO_LEVANT: 6 };
const AO_META = {
  AO_HIGH_NORTH: {
    title: "High North Watch",
    description: "High North, Finland and the Baltic states · Hybrid, infrastructure and regional security activity",
    briefTitle: "AO High North daily analyst brief",
    slug: "high-north",
  },
  AO_EUROPE: {
    title: "Ukraine & Eastern Europe",
    description: "Ukraine and eastern / central Europe · Conflict, regional security and spillover activity",
    briefTitle: "AO Ukraine & Eastern Europe daily analyst brief",
    slug: "eastern-europe",
  },
  AO_BALKANS: {
    title: "The Balkans",
    description: "Western Balkans, Greece and Bulgaria · Stability, security posture and regional influence",
    briefTitle: "AO Balkans daily analyst brief",
    slug: "balkans",
  },
  AO_LEVANT: {
    title: "Levant Watch",
    description: "Lebanon, Jordan and the broader Middle East · State, proxy and cross-border activity",
    briefTitle: "AO Levant daily analyst brief",
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
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    className: "sentinel-basemap",
    referrerPolicy: "strict-origin-when-cross-origin",
    updateWhenIdle: true,
    keepBuffer: 1,
    maxZoom: 18,
  }).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
}

function sevColor(sev) {
  if (sev >= 5) return "#d22c29";
  if (sev === 4) return "#d9a441";
  if (sev === 3) return "#5aa5bf";
  if (sev === 2) return "#c98a4f";
  return "#7c8890";
}

function plotSigActs(sigacts) {
  if (!markersLayer || !map) return;
  markersLayer.clearLayers();
  markersById.clear();
  const plotted = [];
  sigacts.forEach((s) => {
    if (s.lat == null || s.lon == null) return;
    const marker = L.circleMarker([s.lat, s.lon], {
      radius: 5 + s.severity,
      color: sevColor(s.severity),
      fillColor: sevColor(s.severity),
      fillOpacity: 0.6,
      weight: 1.5,
    });
    let popup =
      `<strong>${escapeHtml(s.title)}</strong><br>` +
      `<span style="font-family:monospace;font-size:11px">${s.category} · sev ${s.severity} · ${s.country || ""} · ${s.reliability || ""}</span><br>` +
      `<a href="${safeUrl(s.url)}" target="_blank" rel="noopener">source ↗</a><br>${evidenceButton(s.id)}`;
    if (s.cluster_size > 1) {
      popup += `<div class="cluster-sources">Also reported by ${s.cluster_size - 1} other source(s): ${escapeHtml((s.also_reported_by || []).join(", "))}</div>`;
    }
    marker.bindPopup(popup);
    marker.on("click", () => selectEvent(s.id, true));
    marker.addTo(markersLayer);
    markersById.set(s.id, marker);
    plotted.push(marker.getLatLng());
  });
  if (plotted.length) {
    map.fitBounds(L.latLngBounds(plotted), { padding: [28, 28], maxZoom: 7 });
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
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
  return (value || "unclassified").replaceAll("_", " ");
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
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
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
    plotSigActs(data);
    renderFeed(data);
    updateOverview(data);
    maybeNotify(data);
  } catch (e) {
    if (request !== sigactRequest) return;
    console.warn("sigacts fetch failed", e);
    document.getElementById("feedList").innerHTML =
      `<div class="feed-item"><span class="feed-meta">Backend unreachable at ${API_BASE} — is it running?</span></div>`;
  }
}

async function refreshSynopsis() {
  const strategicEl = document.getElementById("synStrategic");
  const operationalEl = document.getElementById("synOperational");
  const tacticalEl = document.getElementById("synTactical");
  const metaEl = document.getElementById("synopsisMeta");
  try {
    const data = await fetchJson(`/api/synopsis?ao=${state.ao}&window=${state.window}`);
    strategicEl.textContent = data.strategic || "—";
    operationalEl.textContent = data.operational || "—";
    tacticalEl.textContent = data.tactical || "—";
    showFreshness(metaEl, data.generated_at, 8);
  } catch (e) {
    strategicEl.textContent = "No synopsis generated yet for this AO/window.";
    operationalEl.textContent = "—";
    tacticalEl.textContent = "—";
    metaEl.textContent = "Update unavailable";
    metaEl.classList.add("is-stale");
  }
}

let currentBriefContent = "";
let currentAudioEpisode = null;

function withoutClassification(content) {
  return (content || "")
    .replace(/^\*\*Classification:\*\*[^\n]*(?:\n|$)/gim, "")
    .replace(/^Classification:[^\n]*(?:\n|$)/gim, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

async function refreshBrief(briefId) {
  const el = document.getElementById("briefContent");
  const metaEl = document.getElementById("briefMeta");
  const factBox = document.getElementById("factCheckBox");
  const factText = document.getElementById("factCheckText");
  try {
    const path = briefId && briefId !== "latest"
      ? `/api/briefs/${briefId}`
      : `/api/brief/latest?ao=${state.ao}`;
    const data = await fetchJson(path);
    currentBriefContent = withoutClassification(data.content);
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
    if (data.fact_check_notes) {
      factText.textContent = data.fact_check_notes;
      factBox.classList.remove("hidden");
    } else {
      factBox.classList.add("hidden");
    }
  } catch (e) {
    el.textContent = "No analyst brief generated yet — the first generation cycle runs shortly after startup.";
    document.getElementById("briefNav").innerHTML = "";
    metaEl.textContent = "Update unavailable";
    factBox.classList.add("hidden");
  }
}

async function refreshBriefHistory() {
  const select = document.getElementById("briefHistory");
  try {
    const briefs = await fetchJson(`/api/briefs?ao=${state.ao}&limit=30`);
    const currentValue = select.value;
    select.innerHTML = `<option value="latest">Latest</option>` + briefs.map(
      (b) => `<option value="${b.id}">${utcDate(b.generated_at).toLocaleString()}</option>`
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

function utcDate(value) {
  return new Date(value + (value && value.endsWith("Z") ? "" : "Z"));
}

async function refreshAudioBrief(episodeId) {
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
    const previousId = currentAudioEpisode && currentAudioEpisode.id;
    const previousAudioUrl = currentAudioEpisode && currentAudioEpisode.audio_url;
    currentAudioEpisode = data;
    title.textContent = data.title;
    meta.textContent = `${formatAudioTime(data.duration_seconds)} · Four regional chapters`;
    meta.classList.toggle("is-stale", Date.now() - utcDate(data.generated_at).getTime() > 30 * 3600000);
    period.textContent = `${utcDate(data.period_start).toLocaleString()} to ${utcDate(data.period_end).toLocaleString()}`;
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
    currentAudioEpisode = null;
    title.textContent = "Awaiting first episode";
    meta.textContent = "Daily four-AO update · ready by 07:00";
    period.textContent = "Generate the first episode now, or leave SENTINEL running for the morning schedule.";
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
  const remember = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  const recall = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  playButton.addEventListener("click", () => {
    if (!player.src) return;
    if (player.paused) player.play().catch(() => {}); else player.pause();
  });
  player.addEventListener("play", () => { playButton.textContent = "Pause briefing"; });
  player.addEventListener("pause", () => { playButton.textContent = "Play briefing"; });
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
    systemState.textContent = ingest && ingest.last_success_at
      ? `Collected ${timeAgo(ingest.last_success_at)}`
      : "Collection pending";
    document.querySelector(".dot-live").classList.toggle("is-stale", !ingest?.last_success_at || Date.now() - utcDate(ingest.last_success_at).getTime() > 2 * 3600000);
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
    banner.textContent = `⚠ Backend unreachable at ${API_BASE}`;
    banner.classList.remove("hidden");
  }
}

function renderFeed(sigacts) {
  const list = document.getElementById("feedList");
  document.getElementById("feedCount").textContent = `${sigacts.length} events`;
  if (!sigacts.length) {
    list.innerHTML = `<div class="feed-item"><span class="feed-meta">No qualifying SIGACTs in this window.</span></div>`;
    return;
  }
  list.innerHTML = sigacts.map((s) => {
    const summary = (s.summary || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
    return `
      <article data-event-id="${s.id}" class="feed-item ${s.severity >= 4 ? "feed-item-critical" : ""}">
        <div class="feed-item-topline">
          <span class="severity-pill severity-${s.severity}">SEV ${s.severity}</span>
          <span class="category-pill">${escapeHtml(formatCategory(s.category))}</span>
          <time>${timeAgo(s.published_at)}</time>
        </div>
        <a class="feed-title" href="${safeUrl(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.title)}</a>
        ${summary ? `<p class="feed-summary">${escapeHtml(summary.slice(0, 180))}${summary.length > 180 ? "…" : ""}</p>` : ""}
        <div class="feed-footer">
          <span>${escapeHtml(s.source_name || "Unknown source")}</span>
          <span>${escapeHtml(s.country || "Location unconfirmed")}</span>
          ${s.cluster_size > 1 ? `<span>+${s.cluster_size - 1} related article${s.cluster_size > 2 ? "s" : ""}</span>` : ""}
          ${evidenceButton(s.id)}
          ${s.lat != null && s.lon != null ? `<button class="locate-btn" data-id="${s.id}">Locate</button>` : ""}
        </div>
      </article>`;
  }).join("");

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
  const diffMs = Date.now() - new Date(isoStr + (isoStr.endsWith("Z") ? "" : "Z")).getTime();
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
async function refreshSources() {
  const list = document.getElementById("sourcesList");
  try {
    const sources = await fetchJson(`/api/sources`);
    const enabled = sources.filter((s) => s.enabled);
    const healthy = enabled.filter((s) => !s.last_error).length;
    const relevant = enabled.filter((s) => s.ao === state.ao || s.ao === "GLOBAL");
    const relevantHealthy = relevant.filter((s) => !s.last_error).length;
    document.getElementById("sourceSummary").textContent =
      `${healthy}/${enabled.length} enabled sources healthy`;
    document.getElementById("kpiSources").textContent = `${relevantHealthy}/${relevant.length}`;
    list.innerHTML = relevant.map((s) => `
      <div class="source-row">
        <span class="src-name">${escapeHtml(s.name)}</span>
        <span class="src-meta">${s.kind}</span>
        <span class="src-meta">${s.ao}</span>
        <span class="src-meta">${s.reliability}</span>
        <span class="src-meta ${s.error_count > 3 ? "src-error" : ""}">${s.last_error ? "err: " + escapeHtml(s.last_error).slice(0, 40) : (s.last_fetched_at ? "ok · " + timeAgo(s.last_fetched_at) : "not fetched yet")}</span>
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
function wireBriefControls() {
  document.getElementById("downloadBriefBtn").addEventListener("click", () => {
    const blob = new Blob([currentBriefContent || ""], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sentinel-${AO_META[state.ao].slug}-brief-${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  });
  document.getElementById("printBriefBtn").addEventListener("click", () => window.print());
  document.getElementById("briefHistory").addEventListener("change", (e) => refreshBrief(e.target.value));
}

// ---------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------
function refreshAll() {
  if (!document.getElementById("evidenceDrawer").open) {
    refreshChanges();
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
      document.querySelectorAll(".ao-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".ao-tab").forEach((b) => b.removeAttribute("aria-current"));
      btn.setAttribute("aria-current", "page");
      btn.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      state.ao = btn.dataset.ao;
      document.getElementById("evidenceDrawer").close();
      markersLayer?.clearLayers();
      markersById.clear();
      document.getElementById("feedList").textContent = "Loading reporting…";
      refreshChanges(true);
      document.getElementById("briefTitle").textContent = AO_META[state.ao].briefTitle;
      document.getElementById("briefHistory").value = "latest";
      if (map) map.setView(AO_CENTER[state.ao], AO_ZOOM[state.ao]);
      updateAoHeader();
      refreshSigActs();
      refreshSynopsis();
      refreshBrief("latest");
      refreshBriefHistory();
    });
  });

  document.querySelectorAll(".window-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".window-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.window = btn.dataset.window;
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
  });

  let searchTimeout;
  document.getElementById("feedSearch").addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      state.search = e.target.value.trim();
      refreshSigActs();
    }, 300);
  });
  document.getElementById("feedCategoryFilter").addEventListener("change", (e) => {
    state.category = e.target.value;
    refreshSigActs();
  });

  wireNotifyButton();
  wireSourcesForm();
  wireBriefControls();
  wireAudioControls();
  wireEvidence();
}

const ukTime = new Intl.DateTimeFormat("en-GB", {
  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  timeZone: "Europe/London", timeZoneName: "short",
});
const formatUkTime = (value) => ukTime.format(new Date(value));
const evidenceButton = (id) => `<button type="button" class="btn-ghost evidence-trigger" data-evidence-id="${Number(id)}">View evidence</button>`;
let changesRequest = 0;
let evidenceRequest = 0;
let evidenceTrigger = null;

async function refreshChanges(reset = false) {
  const ao = state.ao;
  const request = ++changesRequest;
  const list = document.getElementById("changesList");
  const periods = document.getElementById("changesPeriods");
  const status = document.getElementById("changesStatus");
  const freshness = document.getElementById("changesFreshness");
  if (reset) {
    list.replaceChildren();
    delete list.dataset.rendered;
    periods.textContent = freshness.textContent = "";
    status.textContent = "Checking recent reporting…";
  }
  try {
    const data = await fetchJson(`/api/changes?ao=${encodeURIComponent(ao)}`);
    if (request !== changesRequest || ao !== state.ao) return;
    const range = (period) => `${formatUkTime(period.start)} to ${formatUkTime(period.end)}`;
    periods.textContent = `Latest: ${range(data.current_period)} · Previous: ${range(data.previous_period)}`;
    freshness.textContent = data.last_collected_at ? `Collected ${formatUkTime(data.last_collected_at)}` : "Collection time unavailable";
    freshness.classList.toggle("is-stale", data.collection_state !== "current");
    const message = data.collection_state === "current"
      ? (data.items.length ? "Based on retained reporting. Follow-up coverage does not itself confirm a change." : "No qualifying reporting in the latest 24 hours.")
      : (data.collection_state === "stale" ? "Collection is delayed. Recent reporting may be incomplete." : "Collection status is unavailable. This window may be incomplete.");
    if (status.textContent !== message) status.textContent = message;
    const focusedId = list.contains(document.activeElement) ? document.activeElement.dataset.evidenceId : null;
    const markup = data.items.map(item => {
      const label = item.kind === "new" ? "New to SENTINEL" : "Follow-up coverage";
      const extra = item.added_publishers.length ? ` · Added publisher: ${item.added_publishers.join(", ")}` : "";
      return `<li><div><span class="change-kind">${label}</span><h3 class="change-headline">${escapeHtml(item.title)}</h3><span class="meta">${escapeHtml(formatUkTime(item.published_at) + extra)}</span></div>${evidenceButton(item.article_id)}</li>`;
    }).join("");
    if (markup !== list.dataset.rendered) {
      list.innerHTML = markup;
      list.dataset.rendered = markup;
      if (focusedId) (list.querySelector(`[data-evidence-id="${Number(focusedId)}"]`) || document.getElementById("changesTitle")).focus();
    }
  } catch (_) {
    if (request !== changesRequest || ao !== state.ao) return;
    list.replaceChildren();
    delete list.dataset.rendered;
    periods.textContent = freshness.textContent = "";
    status.textContent = "The reporting comparison is unavailable. Try again shortly.";
  }
}

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
    title.textContent = data.title;
    status.textContent = "Related reporting, newest first. Repeated claims may come from the same underlying account.";
    timeline.innerHTML = data.articles.map(article => {
      const excerpt = article.excerpt.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
      const url = safeUrl(article.url);
      return `<li><div class="meta">${escapeHtml(article.publisher || "Publisher not listed")} · ${escapeHtml(formatUkTime(article.published_at))}</div><h4>${escapeHtml(article.title)}</h4>${excerpt ? `<p>${escapeHtml(excerpt)}</p>` : ""}${url !== "#" ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open original article ↗</a>` : ""}</li>`;
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
    const target = evidenceTrigger?.isConnected ? evidenceTrigger : document.getElementById("changesTitle");
    target.focus();
    evidenceTrigger = null;
  });
}

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("periodControls").append(document.getElementById("windowToggle"));
  const labels = ["High North", "Ukraine & Eastern Europe", "Balkans", "Levant"];
  document.querySelectorAll(".ao-tab-label").forEach((label, index) => { label.textContent = labels[index]; });
  document.querySelectorAll(".window-btn").forEach((button) => {
    button.textContent = {"24h":"24 hours", "48h":"48 hours", "7d":"7 days", "30d":"30 days"}[button.dataset.window];
  });
  document.getElementById("resetMapBtn").addEventListener("click", () => map?.setView(AO_CENTER[state.ao], AO_ZOOM[state.ao]));
  document.getElementById("expandMapBtn").addEventListener("click", (event) => {
    const expanded = document.querySelector(".map-panel").classList.toggle("map-expanded");
    event.currentTarget.textContent = expanded ? "Close expanded map" : "Expand map";
    event.currentTarget.setAttribute("aria-pressed", String(expanded));
    map?.invalidateSize();
  });
  document.getElementById("readingModeBtn").addEventListener("click", (event) => {
    const reading = document.body.classList.toggle("reading-mode");
    event.currentTarget.textContent = reading ? "Exit reading view" : "Reading view";
    event.currentTarget.setAttribute("aria-pressed", String(reading));
    document.getElementById("briefPanel").scrollIntoView({behavior:"smooth"});
  });
  if (READ_ONLY) {
    ["collectBtn", "analysisBtn", "addSourceBtn", "addSourceForm", "generateAudioBtn"].forEach((id) => {
      document.getElementById(id)?.classList.add("hidden");
    });
  }
  initMap();
  wireControls();
  document.querySelector(".ao-tab.active")?.setAttribute("aria-current", "page");
  updateAoHeader();
  refreshAll();
  setInterval(refreshAll, 60000); // poll every minute
});

function showFreshness(element, value, hours) {
  const stale = !value || Date.now() - utcDate(value).getTime() > hours * 3600000;
  element.textContent = `${stale ? "Previous update" : "Updated"} ${timeAgo(value)}`;
  element.title = value ? utcDate(value).toLocaleString() : "No update available";
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
