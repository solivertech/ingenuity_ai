# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Autospy** is an AI-driven vehicle search tracker built around Carvana. It scrapes listings, applies rule-based filtering and value scoring, runs LLM analysis across a multi-provider fallback chain, stores results in SQLite, and sends Gmail alerts. It is currently being extended into a general-purpose web scraping platform (see `AI_SCRAPER_PLAN.md`).

The codebase has two independently runnable surfaces:
- **CLI scraper** (`main.py`) — runs profiles, invokes the full pipeline
- **Dashboard** — FastAPI backend + React/Vite frontend (desktop) + optional web portal

## Development commands

### Python backend

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run the scraper once (CLI)
python main.py --once

# Validate config and test LLM backends
python main.py --check-setup

# Run tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_rules.py -v

# Start the dashboard backend (dev, hot reload)
uvicorn dashboard.backend.app:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
# Desktop dashboard (http://localhost:5173)
cd dashboard/frontend
npm run dev
npm run build        # tsc -b && vite build
npm run lint         # eslint

# Web portal (http://localhost:5174)
cd dashboard/webapp
npm run dev
npm run build
```

### Development startup (full stack)

Three terminals:
1. `uvicorn dashboard.backend.app:app --reload --host 127.0.0.1 --port 8000`
2. `cd dashboard/frontend && npm run dev`
3. (optional) `cd dashboard/webapp && npm run dev`

## Architecture

### Domain adapter layer

`domains/base.py` defines three dataclasses and one abstract base class:
- `FieldSchema` — one extractable field (json_paths, css_selectors, data_type, unit)
- `DomainConfig` — complete site definition (fields, filter_rules, scoring_weights, system_prompt_context)
- `DomainAdapter` — abstract interface: `build_url()`, `normalize()`, `domain_config` property
- `domains/registry.py::load_adapter(domain_id)` — returns a `DomainAdapter` instance by ID

`domains/automotive/` contains the Carvana implementation:
- `url_builder.py` — base64-encoded Carvana filter URL builder (moved from `scraper/urls.py`)
- `normalizer.py` — `normalize_vehicle()` (moved from `scraper/extractor.py`)
- `adapter.py` — `CarvanaAdapter` wrapping the above, plus `AUTOMOTIVE_CONFIG`

`scraper/urls.py` is now a shim that re-exports from `domains/automotive/url_builder.py`.

### Scraper pipeline (CLI flow)

`main.py::run_once()` → `_run_profile()` per profile:
1. `domains/registry.py::load_adapter(domain_id)` — loads the appropriate adapter (defaults to `carvana_suvs`)
2. `adapter.build_url()` — builds the page URL with site-specific encoding
3. `scraper/browser.py::Browser` — Playwright session; `get_page_content()` returns raw HTML
4. `scraper/extractor.py::extract_listings(html, make, model, adapter)` — four strategies in priority order: Schema.org ld+json → `__NEXT_DATA__` → Apollo/GraphQL window vars → BeautifulSoup DOM; calls `adapter.normalize()` on each raw dict
5. `analysis/validator.py` — removes brand-bleed (wrong make in results)
6. `analysis/rules.py` — `apply_filters()` drops listings outside profile bounds; `enrich_listings()` computes `value_score` via `_value_score(scoring_weights=adapter.domain_config.scoring_weights)`
7. `analysis/llm.py::LLMAnalyzer.analyze()` — LLM fallback chain (see below)
8. `storage/history_db.py` — SQLite CRUD; `storage/csv_writer.py` — timestamped CSV
9. `notifications/email_alert.py` — Gmail OAuth2 HTML email; accepts optional `domain_config` param

### LLM fallback chain

`LLMAnalyzer.analyze()` tries providers in order and returns the first that succeeds. Never raises.

Priority: **NVIDIA NIM → Cerebras → Anthropic → Network Ollama → none**

Each provider is gated by its `*_ENABLED` flag and API key in config. Returns `LLMResult` with `backend_used`, `model_used`, `tokens_used`, `latency_ms`, `error`, `cache_hit` (Anthropic only), `top_pick_vins`.

Anthropic client (`analysis/anthropic_client.py`) uses prompt caching.

### Config system

`config.py` loads settings from two sources:
- `dashboard_settings.json` — UI-editable settings (via `dashboard/backend/settings_store.py`)
- `.env` — secrets only (API keys, Gmail OAuth tokens)

Copy `.env.example` to `.env` to start. All `config.*` constants are module-level attributes.

### Dashboard backend

`dashboard/backend/app.py::create_app()` — FastAPI factory.

- **LocalOnlyMiddleware** blocks external callers from unauthenticated desktop routes
- Desktop routes (no JWT, localhost-only): `profiles`, `runs`, `history`, `schedule`, `setup`, `settings`, `docs`, `system`
- Portal routes (JWT-gated): `auth`, `portal`
- `app_scheduler.py` — in-process async scheduler that fires `main.py` jobs on a cron
- `job_manager.py` — subprocess job lifecycle + SSE log streaming to frontend
- `settings_store.py` — reads/writes `dashboard_settings.json`

CORS allows: `localhost:5173`, `localhost:5174`, `localhost:8000`, `tauri.localhost`, `tauri://localhost`.

### Profile system

`profiles.py::SearchProfile` — dataclass loaded from `profiles.yaml`. Key fields: `profile_id`, `label`, `vehicles` (list of `(make, model)` tuples), `max_price`, `max_mileage`, `min_year`, `max_year`, `email_to`, `fuel_type_filters`, `model_preference`, `excluded_trim_keywords`, `show_financing`.

`load_profiles(path)` validates and raises on malformed config. Backward-compatible: missing optional fields default safely.

### Frontend

React + TypeScript + Vite. Main views in `dashboard/frontend/src/views/`:
- `RunView.tsx` — manual run trigger + live SSE log stream
- `ScheduleView.tsx` — cron/interval config
- `HistoryView.tsx` — run history, price trends
- `ProfilesView.tsx` — profile display
- `SettingsView.tsx` — settings editor
- `SystemView.tsx` — system logs

Shared components: `ConsoleDrawer.tsx` (persistent SSE log drawer), `StatusBar.tsx` (scheduler/job status).

Web portal (`dashboard/webapp/`) is a separate Vite app with its own JWT-gated routes.

## Key files for common tasks

| Task | File |
|---|---|
| Add/change scrape extraction strategies | `scraper/extractor.py` |
| Change Carvana URL construction | `domains/automotive/url_builder.py` |
| Change Carvana field normalization | `domains/automotive/normalizer.py` |
| Add a new domain adapter | `domains/` — new subdir + register in `domains/registry.py` |
| Change domain config / scoring weights | `domains/automotive/adapter.py::AUTOMOTIVE_CONFIG` |
| Change filtering or value scoring | `analysis/rules.py` |
| Change LLM prompt or provider logic | `analysis/llm.py` |
| Change profile schema | `profiles.py` |
| Change settings available in UI | `dashboard/backend/settings_store.py` + `config.py` |
| Add a backend API route | `dashboard/backend/routers/` |
| Add a frontend view | `dashboard/frontend/src/views/` |
| Change email template | `notifications/email_alert.py` |
| Change DB schema | `storage/history_db.py` |

## Planned generalization

`AI_SCRAPER_PLAN.md` contains the full phased plan for converting this into a domain-agnostic scraper. It introduces:
- `domains/` — `DomainAdapter` / `DomainConfig` / `FieldSchema` abstractions
- `discovery/` — `SchemaAgent` for LLM-driven field detection from raw page HTML
- `DomainWizardView.tsx` — 5-step UI for onboarding new domains

When working on generalization tasks, treat the plan as the authoritative design doc.
