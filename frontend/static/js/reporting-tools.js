// Browser-only reporting tools. No accounts, notifications or model calls.
const reportingHours = { "24h": 24, "48h": 48, "7d": 168, "30d": 720 };
let reportingSnapshot = [];
let reportingEnd = 0;
let followingRequest = 0;
const followingKey = "sentinel-following-v1";
let following = readFollowing();

function readFollowing() {
  try {
    const data = JSON.parse(localStorage.getItem(followingKey));
    return Array.isArray(data) ? data.filter(item => item && typeof item.key === "string" && /^[a-z0-9-]{1,80}$/.test(item.key) && typeof item.label === "string" && Object.hasOwn(AO_META, item.ao) && (item.kind === "topic" || (item.kind === "story" && Number.isSafeInteger(item.id) && item.id > 0))).slice(0, 24).map(item => ({...item, seen: Array.isArray(item.seen) ? item.seen.filter(Number.isSafeInteger).slice(0, 500) : []})) : [];
  } catch (_) { return []; }
}

function saveFollowing() {
  try { localStorage.setItem(followingKey, JSON.stringify(following)); } catch (_) {
    document.getElementById("followingStatus").textContent = "Browser storage is unavailable. Follows will only last for this visit.";
  }
  document.getElementById("followingCount").textContent = `${following.length} saved`;
}

function readView() {
  const p = new URLSearchParams(location.search);
  const category = document.getElementById("feedCategoryFilter");
  state.ao = Object.hasOwn(AO_META, p.get("ao")) ? p.get("ao") : "AO_HIGH_NORTH";
  state.window = Object.hasOwn(reportingHours, p.get("window")) ? p.get("window") : "24h";
  state.category = [...category.options].some(o => o.value === p.get("category")) ? p.get("category") : "";
  state.search = (p.get("q") || "").trim().slice(0, 160);
  category.value = state.category;
  document.getElementById("feedSearch").value = state.search;
  document.querySelectorAll(".ao-tab").forEach(btn => {
    const active = btn.dataset.ao === state.ao;
    btn.classList.toggle("active", active);
    if (active) btn.setAttribute("aria-current", "page"); else btn.removeAttribute("aria-current");
  });
  document.querySelectorAll(".window-btn").forEach(btn => {
    const active = btn.dataset.window === state.window;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  });
  document.getElementById("briefTitle").textContent = AO_META[state.ao].briefTitle;
}

function viewUrl() {
  const url = new URL(location.href);
  url.search = new URLSearchParams({ao: state.ao, window: state.window});
  if (state.search) url.searchParams.set("q", state.search);
  if (state.category) url.searchParams.set("category", state.category);
  return url;
}

function writeView(replace = false) {
  const url = viewUrl();
  if (url.href !== location.href) history[replace ? "replaceState" : "pushState"](null, "", url);
}

function reportingDate(value) {
  if (!value) return NaN;
  return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`);
}

function resetReportingTimeline() {
  reportingSnapshot = [];
  reportingEnd = 0;
  const slider = document.getElementById("timelinePosition");
  slider.value = "1000";
  slider.disabled = true;
  document.getElementById("timelineLabel").textContent = "Latest reporting";
  document.getElementById("followingItems").replaceChildren();
  followingRequest++;
}

function timelineIsLive() {
  return document.getElementById("timelinePosition").value === "1000";
}

function receiveReporting(items) {
  reportingSnapshot = items;
  reportingEnd = Date.now();
  document.getElementById("timelinePosition").disabled = !items.length;
  paintReporting();
  refreshFollowing();
}

function paintReporting(fit = true) {
  const slider = document.getElementById("timelinePosition");
  const end = reportingEnd || Date.now();
  const start = end - reportingHours[state.window] * 3600000;
  const cutoff = start + (end - start) * Number(slider.value) / Number(slider.max);
  const live = timelineIsLive();
  const label = live ? "Latest reporting" : `Published by ${formatUkTime(new Date(cutoff).toISOString())}`;
  document.getElementById("timelineLabel").textContent = label;
  slider.setAttribute("aria-valuetext", label);
  const data = live ? reportingSnapshot : reportingSnapshot.filter(item => reportingDate(item.published_at) <= cutoff);
  plotSigActs(data, fit);
  renderFeed(data);
  updateOverview(data);
}

function savedStory(id, ao = state.ao) {
  return following.find(item => item.kind === "story" && item.id === id && item.ao === ao);
}

function followButton(id) {
  const saved = !!savedStory(id);
  return `<button type="button" class="btn-ghost follow-trigger" aria-pressed="${saved}" data-follow-id="${Number(id)}">${saved ? "Saved" : "Save story"}</button>`;
}

function addFollow(item) {
  const status = document.getElementById("followingStatus");
  if (following.length >= 24 || (item.kind === "story" && following.filter(item => item.kind === "story").length >= 12)) {
    status.textContent = "Watchlist is full. Remove a saved item before adding another.";
    document.getElementById("following").open = true;
    return false;
  }
  following.push(item);
  status.textContent = "Saved to Following.";
  return true;
}

function syncFollowButtons() {
  document.querySelectorAll("[data-follow-id]").forEach(button => {
    const saved = !!savedStory(Number(button.dataset.followId));
    button.textContent = saved ? "Saved" : "Save story";
    button.setAttribute("aria-pressed", String(saved));
  });
}

function markStoryRead(data, ao) {
  const saved = savedStory(data.article_id, ao);
  if (!saved) return;
  saved.seen = [...new Set([saved.id, ...data.articles.map(a => a.id), ...(saved.seen || [])])].slice(0, 100);
  saveFollowing();
  refreshFollowing();
}

async function refreshFollowing() {
  const details = document.getElementById("following");
  if (!details.open) return;
  const request = ++followingRequest;
  const ao = state.ao;
  const entries = following.filter(item => item.ao === ao);
  const list = document.getElementById("followingItems");
  const results = await Promise.all(entries.map(async item => {
    if (item.kind === "topic") {
      const matches = reportingSnapshot.filter(a => `${a.country || ""} ${a.title} ${a.summary || ""}`.toLowerCase().includes(item.label.toLowerCase()));
      const unread = matches.filter(a => !(item.seen || []).includes(a.id)).length;
      return { item, note: `${matches.length} in this view · ${unread} unread`, matches: matches.slice(0, 5), ids: matches.map(a => a.id) };
    }
    try {
      const data = await fetchJson(`/api/events/${item.id}/evidence?ao=${encodeURIComponent(ao)}`);
      const unseen = data.articles.filter(a => !(item.seen || [item.id]).includes(a.id)).length;
      return { item, note: unseen ? `${unseen} unread related article${unseen === 1 ? "" : "s"}` : "No unread related articles" };
    } catch (_) { return { item, note: "Evidence unavailable or outside retention" }; }
  }));
  if (request !== followingRequest || ao !== state.ao || !details.open) return;
  const markup = results.map(({item, note, matches, ids}) => `<div class="following-row">
    <strong>${escapeHtml(item.label)}</strong><span class="meta">${escapeHtml(note)}</span>
    <div>${item.kind === "story" ? evidenceButton(item.id) : `<button type="button" class="btn-ghost" data-read-follow="${escapeHtml(item.key)}">Mark current matches read</button>`}
    <button type="button" class="btn-ghost" data-remove-follow="${escapeHtml(item.key)}">Remove</button></div>
    ${matches?.length ? `<ul>${matches.map(a => `<li><a href="${safeUrl(a.url)}" target="_blank" rel="noopener">${escapeHtml(a.title)}</a></li>`).join("")}</ul>` : ""}
  </div>`).join("");
  const next = markup || '<p class="meta">Nothing saved for this AO yet.</p>';
  if (next !== list.innerHTML) list.innerHTML = next;
  for (const button of list.querySelectorAll("[data-read-follow]")) {
    button.onclick = () => {
      const result = results.find(r => r.item.key === button.dataset.readFollow);
      if (!result) return;
      result.item.seen = [...new Set([...result.ids, ...(result.item.seen || [])])].slice(0, 500);
      saveFollowing();
      refreshFollowing();
    };
  }
}

function wireReportingTools() {
  document.getElementById("shareView").addEventListener("click", async () => {
    state.search = document.getElementById("feedSearch").value.trim().slice(0, 160);
    writeView(true);
    const status = document.getElementById("shareStatus");
    try { await navigator.clipboard.writeText(viewUrl().href); status.textContent = "View link copied"; }
    catch (_) { status.textContent = "Copy the view link from your address bar."; }
  });
  window.addEventListener("popstate", () => {
    const previousAo = state.ao;
    const previousWindow = state.window;
    readView();
    if (previousAo !== state.ao || previousWindow !== state.window) {
      resetScopedView(previousAo !== state.ao);
    } else {
      resetReportingTimeline();
    }
    updateAoHeader();
    refreshAll();
  });
  let frame;
  document.getElementById("timelinePosition").addEventListener("input", () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => paintReporting(false));
  });
  document.getElementById("timelineLive").addEventListener("click", () => {
    document.getElementById("timelinePosition").value = "1000";
    paintReporting(false);
    refreshSigActs();
  });
  const details = document.getElementById("following");
  details.addEventListener("toggle", () => refreshFollowing());
  document.getElementById("followTopicForm").addEventListener("submit", event => {
    event.preventDefault();
    const input = document.getElementById("followTopic");
    const label = input.value.trim().slice(0, 80);
    if (!label) return;
    if (following.some(item => item.ao === state.ao && item.kind === "topic" && item.label.toLowerCase() === label.toLowerCase())) {
      document.getElementById("followingStatus").textContent = "You already follow that topic in this AO.";
      return;
    }
    if (addFollow({key: crypto.randomUUID(), kind: "topic", ao: state.ao, label, seen: []})) {
      input.value = "";
      saveFollowing();
      refreshFollowing();
    }
  });
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-follow-id], [data-remove-follow]");
    if (!button) return;
    if (button.hasAttribute("data-follow-id")) {
      const id = Number(button.dataset.followId);
      const saved = savedStory(id);
      if (saved) following = following.filter(item => item !== saved);
      else {
        const article = reportingSnapshot.find(item => item.id === id);
        if (article) addFollow({key: crypto.randomUUID(), kind: "story", id, ao: state.ao, label: article.title, seen: [id]});
      }
    } else following = following.filter(item => item.key !== button.dataset.removeFollow);
    saveFollowing();
    syncFollowButtons();
    refreshFollowing();
  });
  saveFollowing();
}

const coverageCountries = {
  AO_HIGH_NORTH: ["Norway", "Sweden", "Finland", "Estonia", "Latvia", "Lithuania", "Iceland", "Denmark"],
  AO_EUROPE: ["Ukraine", "Russia", "Belarus", "Moldova", "Poland", "Romania", "Hungary", "Slovakia", "Czechia"],
  AO_BALKANS: ["Albania", "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Greece", "Kosovo", "Montenegro", "North Macedonia", "Serbia", "Slovenia"],
  AO_LEVANT: ["Israel", "Gaza", "West Bank", "Lebanon", "Syria", "Jordan", "Iraq"],
};

function renderCoverage(el, data, sources) {
  if (!data) {
    el.textContent = "Seven-day coverage is temporarily unavailable.";
    return;
  }
  const publishers = Object.keys(data.by_source).length;
  const articles = Object.values(data.by_country).reduce((total, count) => total + count, 0);
  const names = [...new Set([...(coverageCountries[data.ao] || []), ...Object.keys(data.by_country)])].sort();
  const countries = names.map(name => {
    const count = Number(data.by_country[name]) || 0;
    return `<li class="${count ? "" : "coverage-zero"}">${escapeHtml(name)} <strong>${count}</strong></li>`;
  }).join("");
  const top = sources.filter(s => data.by_source[s.id]).sort((a, b) => data.by_source[b.id] - data.by_source[a.id]).slice(0, 5);
  el.innerHTML = `<strong>Coverage over the last 7 days</strong>
    <p>${articles} dashboard articles from ${publishers} contributing feeds · ${escapeHtml(formatUkTime(data.start))} to ${escapeHtml(formatUkTime(data.end))}</p>
    <ul aria-label="Articles by country">${countries}</ul>
    <p>Counts show articles, not distinct events or independent confirmation. Zero means no qualifying article was located there; it does not mean nothing happened.</p>
    ${top.length ? `<p><strong>Most active feeds:</strong> ${top.map(s => `${escapeHtml(s.name)} (${data.by_source[s.id]})`).join(" · ")}</p>` : ""}`;
}
