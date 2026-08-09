# SENTINEL — Open-Source Intelligence Fusion Dashboard

A locally hosted OSINT aggregation and analysis dashboard focused on four AOs (Areas of Observation):

- **AO HIGH NORTH** — High North, Finland, and the Baltic states. Focus: hybrid/grey-zone activity, infrastructure, border security and military posture.
- **AO UKRAINE & EASTERN EUROPE** — Ukraine and eastern/central Europe. Focus: the war in Ukraine, regional security and direct spillover.
- **AO BALKANS** — The Western Balkans, Greece and Bulgaria. Focus: stability, military posture, border security, NATO/EU missions and malign influence.
- **AO LEVANT** — The Broader Middle East, with emphasis on Lebanon and Jordan. Focus: militia/state-proxy activity, cross-border strikes, political-security instability.

It crawls open sources (RSS, public Telegram channel previews, X/Twitter where an API key is configured), geotags and classifies events into SIGACT-style records, plots them on a map, and uses Claude (your own Anthropic API key) to generate:

- Rolling 24h / 48h / 7-day written synopses (strategic / operational / tactical layers)
- A full daily analyst brief with short/medium/long-term outlook, written in military-intelligence house style
- A free local 5–10 minute morning audio briefing with one chapter per AO, transcript and 30-day archive

**This is an OSINT civilian analytical tool built entirely from public, open sources.** It does not access classified systems and "SIGACT" here means "significant activity" reports derived from open reporting, not a military C2 feed. Treat its output as a *drafting aid*, not a verified intelligence product — every generated brief carries source links so a human analyst can check the underlying reporting.

## Architecture

```
osint-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app + REST API
│   │   ├── config.py          Settings (.env driven)
│   │   ├── database.py        SQLAlchemy engine/session
│   │   ├── models.py          Source, Article, SigAct, Brief tables
│   │   ├── schemas.py         Pydantic response models
│   │   ├── sources.py         Curated source catalogue for all four AOs
│   │   ├── scheduler.py       APScheduler jobs (ingest, classify, brief)
│   │   ├── ingest/
│   │   │   ├── rss_ingest.py       RSS/Atom feed puller (feedparser)
│   │   │   ├── telegram_ingest.py  Public t.me/s/<channel> scraper
│   │   │   ├── twitter_ingest.py   X API v2 (optional, needs bearer token)
│   │   │   └── geotag.py           Keyword gazetteer -> AO + lat/lon + category
│   │   └── analysis/
│   │       ├── claude_client.py    Thin wrapper around the Anthropic SDK
│   │       ├── synopsis.py         24h/48h/7d strategic-op-tactical synopsis
│   │       └── brief.py            Full daily analyst brief generator
│   ├── requirements.txt
│   ├── .env.example
│   └── run.py
└── frontend/
    ├── index.html
    ├── static/css/dashboard.css
    └── static/js/app.js
```

## Public cloud deployment

SENTINEL supports a public, read-only deployment using Vercel, Supabase and
GitHub Actions while retaining the existing SQLite/macOS mode for local use.
The browser uses same-origin `/api` requests online; all source mutations and
manual trigger endpoints return HTTP 403 in hosted mode. Scheduled work runs
only in GitHub Actions, never inside a Vercel serverless process.

Required GitHub Actions secrets:

- `DATABASE_URL` — Supabase transaction-pooler Postgres URL
- `DIRECT_DATABASE_URL` — direct Postgres URL used by the weekly `pg_dump`
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Required Vercel production environment variables:

- `DATABASE_URL`
- `HOSTED_MODE=true`
- `HOSTED_READ_ONLY=true`
- `SCHEDULER_ENABLED=false`
- `SUPABASE_URL`
- `SUPABASE_AUDIO_BUCKET=audio-briefs`
- `ALLOWED_ORIGINS=https://<production-project>.vercel.app`

Do not add the Supabase service-role key to the browser or source tree. Vercel
only needs the public project URL to redirect audio playback to the public
bucket; the service-role key is restricted to GitHub Actions.

Before the first deployment, create a public Storage bucket named
`audio-briefs`, then migrate the local database from the project root:

```bash
DATABASE_URL='postgresql://...' \
SUPABASE_URL='https://PROJECT.supabase.co' \
SUPABASE_SERVICE_ROLE_KEY='...' \
python3 scripts/migrate_sqlite_to_postgres.py
```

The migration refuses a non-empty target, makes a timestamped local backup,
preserves IDs and timestamps, uploads existing audio, resets Postgres sequences
and verifies row-count parity. The workflows under `.github/workflows/` provide
30-minute six-shard collection, four-hour synopsis generation, DST-safe morning
brief/audio generation, retention, manual dispatch and weekly recovery exports.

## Updating to a new version

As of this version, **you no longer need to delete `sentinel.db`** between updates. The backend auto-migrates the database schema on startup — it checks for any new columns/tables the code expects and adds them in place (additive only: no renames or drops), so your crawled history and settings survive updates.

To apply an update:

```bash
cd ~/Downloads
unzip -o sentinel-osint-dashboard.zip -d .    # -o overwrites in place, keeps your .env/db/venv/logs
cd osint-dashboard
./scripts/update.sh
```

`update.sh` refreshes any new Python dependencies and restarts the background services (or tells you to just restart `python run.py` if you're not running it as a service). You'll see lines like `Migration: added column articles.some_new_field` in `logs/backend.log` on the first startup after an update that changed the schema — that's expected and confirms it worked.

## v2 changes — read this if upgrading from a copy before background-service support

What's new:

- **Reliability tiers per source** (`official` / `established_media` / `regional_specialist` / `unverified`) — fed into every synopsis/brief prompt so the model hedges language appropriately instead of treating all sources as equal.
- **Deduplication** — near-identical reporting of the same event (same AO + category, similar title, within a 36h window) collapses into one SIGACT with a "reported by N sources" note, instead of N separate map markers.
- **Trend detection** — a rolling 14-day frequency count per category feeds into the daily brief so it can flag recurring patterns (e.g. "3rd suspected jamming incident this period") instead of treating each event in isolation.
- **Fact-check pass** — after generating the daily brief, a second LLM call reviews it against the raw source list and flags any unsupported claims. Shown in its own box under the brief.
- **Search & filter** on the SIGACT log (free-text + category dropdown).
- **30-day window** added alongside 24h/48h/7d.
- **Source management panel** in the dashboard — enable/disable or delete sources, or add new ones, without touching `sources.py`. Backed by `/api/sources` CRUD endpoints.
- **Brief history** — a dropdown to view any previously generated brief, not just the latest (`/api/briefs`).
- **Download/print the brief** — as Markdown, or via the browser's print dialog (styled for clean output, save-as-PDF works from there).
- **Desktop notifications** — a toggle in the header; once enabled (and browser permission granted), you get a native OS notification whenever a new severity 4-5 SIGACT appears in the currently selected AO/window.
- **Optional email alerts** — set `ALERT_SMTP_HOST` + `ALERT_EMAIL_TO` (and related `ALERT_*` vars) in `.env` to get an email for every new severity ≥4 event, sent once per event. Disabled by default; no config needed if you don't want it.
- **Error visibility** — if synopsis or brief generation starts failing (bad API key, rate limit, etc.), a red banner appears at the top of the dashboard rather than the panel silently going stale.
- **Expanded starter sources & gazetteer** — more RSS feeds and Telegram channels across both AOs, plus more granular locations (specific bases, named operations, more towns) in `ingest/geotag.py`.

## Branding

All logo assets live in `frontend/static/img/`, generated from the provided logo sheet:
- `sentinel-logo-horizontal.png` — dashboard header
- `sentinel-icon.png` — source square icon (used to generate the sizes below)
- `sentinel-wordmark.png` — shown on printed/exported briefs
- `favicon-16.png` / `favicon-32.png` / `apple-touch-icon.png` / `icon-192.png` / `icon-512.png` — browser tab, bookmarks, and "add to home screen" icons, referenced via `frontend/manifest.json`

The dashboard's accent colors (`--teal`, `--red` in `dashboard.css`) are sampled directly from the logo artwork rather than picked independently, so the UI and the branding match. If you swap in updated artwork, re-run a quick color sample against the new file and update those two CSS variables (and the matching hardcoded hex values in `sevColor()` in `app.js`, used for map markers) to stay consistent.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY, optionally TWITTER_BEARER_TOKEN
python run.py
```

For the higher-quality local British audio voice on Apple Silicon, install the
separate Python 3.12 speech runtime once from the project root:

```bash
./scripts/install_tts.sh
```

If that runtime is unavailable, morning audio automatically falls back to the
built-in British macOS voice. No paid speech API is required.

The API serves on `http://localhost:8000`. Open `frontend/index.html` directly in a browser (or `python -m http.server 8080` from `frontend/`) — it talks to the API at `localhost:8000` by default (edit `API_BASE` at the top of `static/js/app.js` if you change the port).

On first run, the scheduler immediately does an ingest pass, then repeats every `INGEST_INTERVAL_MINUTES` (default 15). Classification/geotagging runs right after each ingest. Synopsis and full brief generation call Claude and are cached — they regenerate on a timer (default: synopses every 30 min, full brief once an hour) rather than on every page load, to control API cost.

## Running it in the background (no Terminal needed after setup)

Once the setup above works (venv created, dependencies installed, `.env` configured), install SENTINEL as a macOS background service so it starts automatically at login and keeps running without a Terminal window open:

```bash
cd osint-dashboard
./scripts/install_background_service.sh
```

This registers two `launchd` agents (the standard macOS way to run background services) that:
- start the backend and frontend automatically whenever you log in
- restart them automatically if either one crashes
- write logs to `logs/backend.log` / `logs/frontend.log` in the project folder instead of a terminal window

After running it once, just open `http://localhost:8080` in your browser any time — no need to run `python run.py` again, even after a reboot.

**To stop it** (e.g. before making code changes, or if you want it fully off):
```bash
./scripts/uninstall_background_service.sh
```

**To apply code/config changes** while it's running as a service: run `./scripts/uninstall_background_service.sh` then `./scripts/install_background_service.sh` again — this picks up any edits to `.env` or the code.

**Note:** this only runs while you're logged into your Mac (normal for a personal laptop) — it does not run when the machine is fully shut down, and closing the lid will pause it (sleep) but it resumes when you wake the machine.

## What's real vs. what you need to configure

- **RSS ingestion**: fully functional — `feedparser` pulls every feed in `sources.py`. Feed URLs drift over time; treat the starter list as a seed and prune/replace dead ones (the ingest log in `/api/health` will show per-source error counts).
- **Telegram**: scrapes the public HTML preview (`https://t.me/s/<channel>`) of channels you list in `sources.py` — no API keys or login needed, but only works for channels that are public and have previews enabled, and is best-effort (no images/polls, and Telegram may rate-limit scraping at volume).
- **X/Twitter**: stubbed to use X API v2 recent-search; requires your own `TWITTER_BEARER_TOKEN` (paid tier as of 2024+). Without a token, it's skipped silently and logged as disabled.
- **Geotagging/classification**: a keyword gazetteer + rule-based classifier, not a trained NER model. It's deliberately transparent and editable (`ingest/geotag.py`) rather than a black box — expect to tune the keyword lists for your priority intelligence requirements (PIRs).
- **Synopsis & brief generation**: real calls to the Claude API using `anthropic` SDK and your key. Prompts are in `analysis/synopsis.py` and `analysis/brief.py` — edit the analyst persona/format there to taste.

## Extending

- Add feeds/channels: edit `SOURCES` in `backend/app/sources.py`.
- Add a new AO or retune region boundaries: edit `AO_DEFINITIONS` in `ingest/geotag.py`.
- Swap the map basemap or SIGACT icon set: `frontend/static/js/app.js` (`initMap`).
