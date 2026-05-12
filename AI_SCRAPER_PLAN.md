# Universal AI Scraper — Implementation Plan

This document is the complete blueprint for transforming the current Autospy codebase into a
general-purpose, AI-driven web scraping platform. It includes a full file map of the current
project, the domain adapter interface design, the AI field-detection flow, and a phased
implementation plan with specific file-level changes.

---

## Table of Contents

1. [Feasibility Assessment](#1-feasibility-assessment)
2. [Current Project File Map](#2-current-project-file-map)
3. [Target Architecture](#3-target-architecture)
4. [Domain Adapter Interface](#4-domain-adapter-interface)
5. [AI Field Detection Flow](#5-ai-field-detection-flow)
6. [Implementation Plan — Phased](#6-implementation-plan--phased)
7. [File-Level Change Map](#7-file-level-change-map)
8. [New Files to Create](#8-new-files-to-create)
9. [Config & Profile Schema Changes](#9-config--profile-schema-changes)
10. [Frontend Changes](#10-frontend-changes)

---

## 1. Feasibility Assessment

**Short answer: Yes, high feasibility. Estimated effort: 3–4 weeks.**

### What carries over unchanged (~70% of the codebase)

| System | Status |
|---|---|
| Multi-LLM fallback chain (NVIDIA → Cerebras → Anthropic → Ollama) | Fully domain-agnostic. Zero changes needed. |
| Job scheduling & real-time log streaming (SSE) | Zero changes needed. |
| FastAPI dashboard backend (routers, auth, portal) | Minor changes only (new router for domain management). |
| React frontend (run, schedule, history, settings views) | Minor additions only (domain wizard view). |
| SQLite storage schema | Minor generalization of column names. |
| Email/notification system | Template parameterization only. |
| Multi-profile architecture | Extend to support non-automotive domains. |
| Playwright browser lifecycle | Zero changes needed. |

### What must change (~30% of the codebase)

| Component | Problem | Solution |
|---|---|---|
| `scraper/extractor.py` → `normalize_vehicle()` | Hardcoded car schema | Replace with config-driven field mapper |
| `scraper/urls.py` | Carvana base64 URL format | Move behind `DomainAdapter.build_url()` |
| `analysis/rules.py` | Scoring weights tuned for cars | Make weights config-driven per domain |
| `profiles.py` | Car-specific fields (`fuel_type`, `drivetrain`) | Generalize `SearchProfile` |
| `notifications/email_alert.py` | Template references Carvana language | Jinja2 templates per domain |
| `utils/vin_decode.py` | Automotive-only | Optional module, not called by core |

### Net assessment

The infrastructure (LLM orchestration, scheduling, dashboard, storage) is the hard part and
it is already built. The work is extraction of car-specific logic into a swappable adapter
layer plus one new capability: the AI-driven schema discovery step that replaces hardcoded
field definitions.

---

## 2. Current Project File Map

Use this map when editing or adding files. Every source file is listed with its role and
key symbols.

```
car_search/
│
├── main.py                         # Orchestrator: scrape → filter → enrich → LLM → save → email
│   ├── run_profile()               # One full cycle for a single SearchProfile
│   ├── run_all_profiles()          # Loops profiles, handles per-make isolation
│   └── CLI entry point (argparse)
│
├── config.py                       # Central settings loader
│   ├── Reads dashboard_settings.json (UI-editable)
│   └── Reads .env (secrets: API keys, OAuth tokens)
│
├── profiles.py                     # Multi-profile YAML loader
│   ├── SearchProfile (dataclass)   # Fields: vehicles, filters, email_to, LLM behavior
│   └── load_profiles()             # Reads profiles.yaml
│
├── carvana_tracker.py              # Legacy standalone script (no profiles/dashboard)
│
├── profiles.yaml                   # User-defined search profiles (not Python)
├── dashboard_settings.json         # UI-editable settings persisted here
├── .env / .env.example             # Secrets only
│
├── scraper/
│   ├── browser.py                  # Playwright browser lifecycle
│   │   ├── BrowserSession          # Context manager; single shared browser per run
│   │   └── get_page_content()      # Returns raw HTML string; never raises
│   │
│   ├── extractor.py                # Multi-strategy data extraction  ← PRIMARY CHANGE TARGET
│   │   ├── extract_from_schema_org()   # Strategy 1: ld+json @type=Vehicle
│   │   ├── extract_from_next_data()    # Strategy 2: __NEXT_DATA__ JSON
│   │   ├── extract_from_apollo_cache() # Strategy 3: Apollo/GraphQL window var
│   │   ├── extract_from_dom()          # Strategy 4: BeautifulSoup CSS selectors
│   │   ├── normalize_vehicle()         # Maps raw dict → standard schema  ← REPLACE
│   │   └── extract_listings()          # Orchestrates all strategies + backfill
│   │
│   └── urls.py                     # Carvana URL builder (base64 filter encoding)  ← MOVE TO ADAPTER
│       └── build_search_url()
│
├── analysis/
│   ├── llm.py                      # LLM orchestrator  ← NO CHANGE NEEDED
│   │   ├── LLMResult (dataclass)
│   │   ├── LLMAnalyzer.analyze()
│   │   ├── LLMAnalyzer.build_prompt()          ← PARAMETERIZE domain context
│   │   └── LLMAnalyzer.build_synthesis_prompt()
│   │
│   ├── rules.py                    # Filtering + value scoring  ← PARAMETERIZE WEIGHTS
│   │   ├── apply_filters()         # Remove listings by price/mileage/year/trim
│   │   ├── enrich_listings()       # Compute value_score for all listings
│   │   ├── enrich_listing()        # Compute value_score for one listing
│   │   └── _value_score()          # Weighted formula (35/25/20/10/10)  ← MAKE CONFIG-DRIVEN
│   │
│   ├── anthropic_client.py         # Anthropic SDK wrapper (no changes needed)
│   ├── cerebras_client.py          # Cerebras API wrapper (no changes needed)
│   ├── nvidia_client.py            # NVIDIA NIM wrapper (no changes needed)
│   ├── ollama_client.py            # Ollama wrapper (no changes needed)
│   └── validator.py                # Input validation helpers
│
├── storage/
│   ├── history_db.py               # SQLite schema + CRUD  ← MINOR COLUMN GENERALIZATION
│   │   ├── init_db()
│   │   ├── save_listings()
│   │   ├── get_run_history()
│   │   └── get_price_history()
│   │
│   └── csv_writer.py               # Timestamped CSV output  ← DYNAMIC COLUMNS
│       └── write_csv()
│
├── notifications/
│   └── email_alert.py              # Gmail OAuth2 email  ← JINJA2 TEMPLATE SWAP
│       ├── build_email_html()
│       ├── should_send_email()
│       └── send_email()
│
├── utils/
│   ├── payment_calc.py             # Monthly payment math (automotive)  ← OPTIONAL MODULE
│   ├── vin_decode.py               # VIN normalization (automotive-only)  ← OPTIONAL MODULE
│   └── trends.py                   # Price history chart generation
│
├── dashboard/
│   ├── backend/
│   │   ├── app.py                  # FastAPI factory + CORS
│   │   ├── app_scheduler.py        # In-process async scheduler
│   │   ├── job_manager.py          # Job lifecycle, subprocess, SSE log streaming
│   │   ├── settings_store.py       # Reads/writes dashboard_settings.json
│   │   ├── setup_checks.py         # Validates LLM connectivity
│   │   ├── auth_deps.py            # JWT auth middleware
│   │   ├── auth_utils.py           # Token helpers
│   │   ├── doc_generator.py        # Vehicle reference doc generation
│   │   └── routers/
│   │       ├── runs.py             # POST /runs, GET /runs/stream, cancel
│   │       ├── schedule.py         # GET/PUT /schedule
│   │       ├── profiles.py         # GET /profiles (YAML loader)
│   │       ├── history.py          # GET /history, /stats, /price-trends
│   │       ├── settings.py         # GET/PUT /settings
│   │       ├── docs.py             # GET /docs (vehicle reference markdown)
│   │       ├── setup.py            # GET /setup/status
│   │       ├── system.py           # GET /system/logs, /system/info
│   │       ├── auth.py             # POST /auth/login
│   │       └── portal.py          # Portal routes (external access)
│   │
│   └── frontend/src/
│       ├── App.tsx                 # Router, status polling, nav bar
│       ├── views/
│       │   ├── RunView.tsx         # Manual run trigger + live log stream
│       │   ├── ScheduleView.tsx    # Scheduler config
│       │   ├── ProfilesView.tsx    # Profile display
│       │   ├── HistoryView.tsx     # Run history + price trends
│       │   ├── DocsView.tsx        # Reference doc viewer
│       │   ├── SettingsView.tsx    # Settings editor
│       │   └── SystemView.tsx      # System logs
│       └── components/
│           ├── ConsoleDrawer.tsx   # Persistent log drawer
│           ├── StatusBar.tsx       # Scheduler/job status strip
│           └── [other UI components]
│
└── tests/
    ├── test_urls.py
    ├── test_rules.py
    ├── test_payment_calc.py
    ├── test_llm_fallback.py
    └── test_email_highlighting.py
```

---

## 3. Target Architecture

The generalized system adds three new layers without removing anything:

```
car_search/  (renamed: universal_scraper/ or keep as-is)
│
├── domains/                        # NEW — domain adapter layer
│   ├── base.py                     # Abstract DomainAdapter interface
│   ├── registry.py                 # Registry of available adapters
│   ├── automotive/                 # Current Carvana logic moved here
│   │   ├── __init__.py
│   │   ├── adapter.py              # CarvanaAdapter(DomainAdapter)
│   │   ├── url_builder.py          # Moved from scraper/urls.py
│   │   └── normalizer.py           # Moved from extractor.normalize_vehicle()
│   └── generic/                    # AI-discovered domains live here
│       ├── __init__.py
│       └── adapter.py              # GenericAdapter(DomainAdapter)
│
├── discovery/                      # NEW — AI schema discovery
│   ├── schema_agent.py             # LLM-powered field detection
│   ├── field_validator.py          # Spot-check discovered mappings against live data
│   └── domain_config.py            # Dataclass for a saved domain definition
│
├── scraper/
│   ├── browser.py                  # Unchanged
│   └── extractor.py                # Refactored: strategies stay, normalize() becomes generic
│
├── [all other dirs unchanged]
```

**Data flow for a generic domain:**

```
User request: "Scrape Zillow for 3-bed homes in Austin under $500k.
               I want price, sqft, beds, baths, address, days on market."
        │
        ▼
[Discovery Agent]  ←── fetches sample page HTML via Playwright
        │               sends to LLM with user's field request
        │               LLM returns: FieldSchema (see Section 5)
        ▼
[Domain Config saved]   domain = "zillow_homes_austin"
        │               field_map = {"price": "$.listingPrice", "sqft": "$.livingArea", ...}
        │               alert_triggers = [{"field": "price", "operator": "<", "value": 500000}]
        │               scoring_weights = {"price": 40, "sqft": 30, "days_on_market": 30}
        ▼
[Scraper]               GenericAdapter.build_url(page=N) → URL
                        browser.get_page_content(url)
                        GenericExtractor.extract(html, field_map) → list[dict]
        ▼
[Rules Engine]          apply_generic_filters(listings, alert_triggers)
                        enrich_generic(listings, scoring_weights)
        ▼
[LLM Analyzer]          build_generic_prompt(listings, user_context) → analysis
        ▼
[Storage / Email]       Unchanged
```

---

## 4. Domain Adapter Interface

This is the abstraction that replaces every car-specific hardcoded piece.
Create this as `domains/base.py`.

```python
# domains/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FieldSchema:
    """Describes one field to extract from a listing."""
    name: str                        # canonical name used in storage/email/LLM
    display_name: str                # human-readable label for email/UI
    json_paths: list[str]            # ordered fallback paths (JSONPath or dot-notation)
    css_selectors: list[str]         # DOM fallback selectors
    data_type: str                   # "float" | "int" | "str" | "bool"
    unit: str = ""                   # "$", "sqft", "mi", "" etc.
    required: bool = False           # if True, listing is invalid without this field
    is_primary_sort: bool = False    # if True, used as default sort key


@dataclass
class DomainConfig:
    """Complete description of a scrapeable domain. Persisted as JSON."""
    domain_id: str                   # e.g. "zillow_homes_austin"
    display_name: str                # e.g. "Zillow — Austin Homes"
    base_url: str                    # e.g. "https://www.zillow.com/austin-tx/"
    pagination_style: str            # "query_param" | "path_segment" | "none"
    pagination_param: str            # e.g. "page" or "p"
    max_pages: int = 10
    fields: list[FieldSchema] = field(default_factory=list)
    filter_rules: list[dict] = field(default_factory=list)
    # e.g. [{"field": "price", "operator": "<=", "value": 500000}]
    scoring_weights: dict[str, float] = field(default_factory=dict)
    # e.g. {"price": 35, "sqft": 25, "days_on_market": 20, "beds": 20}
    system_prompt_context: str = ""  # injected into LLM system prompt
    alert_on_new: bool = True
    alert_on_drop_pct: float = 5.0   # alert when primary_sort field drops by this %
    created_at: str = ""
    user_request: str = ""           # original natural language request, for reference


class DomainAdapter(ABC):
    """
    Base class for all domain-specific scraping adapters.
    Each adapter encapsulates URL construction and raw→normalized field mapping.
    """

    @property
    @abstractmethod
    def domain_config(self) -> DomainConfig:
        """Return the DomainConfig for this adapter."""

    @abstractmethod
    def build_url(self, page: int = 1, **filters) -> str:
        """
        Build the URL for a given page of results, applying any site-specific
        filter encoding (query params, path segments, base64 blobs, etc.).
        """

    @abstractmethod
    def normalize(self, raw: dict, strategy: str) -> dict | None:
        """
        Convert a raw extracted dict into the standard listing schema.
        Keys must match the field names in domain_config.fields.
        Return None if the listing is invalid (missing required fields).
        """

    def get_field(self, raw: dict, schema: FieldSchema):
        """
        Default field extraction: try json_paths in order.
        Subclasses can override for site-specific quirks.
        """
        for path in schema.json_paths:
            val = _json_path_get(raw, path)
            if val is not None:
                return _coerce(val, schema.data_type)
        return None


# ── Utility functions ──────────────────────────────────────────────────────────

def _json_path_get(obj: dict, path: str):
    """
    Simple dot-notation path getter.
    Supports: "offers.price", "$.listing.listPrice", "mileageFromOdometer"
    """
    path = path.lstrip("$.")
    parts = path.split(".")
    cur = obj
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def _coerce(val, data_type: str):
    try:
        if data_type == "float":
            return float(str(val).replace(",", "").replace("$", "").strip())
        if data_type == "int":
            return int(str(val).replace(",", "").strip())
        if data_type == "bool":
            return bool(val)
        return str(val).strip()
    except (ValueError, TypeError):
        return None
```

### Automotive adapter (wrapping existing logic)

```python
# domains/automotive/adapter.py
from domains.base import DomainAdapter, DomainConfig, FieldSchema
from scraper.extractor import normalize_vehicle   # existing function, unchanged
from scraper.urls import build_search_url         # existing function, unchanged


AUTOMOTIVE_CONFIG = DomainConfig(
    domain_id="carvana_suvs",
    display_name="Carvana — SUVs",
    base_url="https://www.carvana.com/cars",
    pagination_style="query_param",
    pagination_param="page",
    max_pages=15,
    fields=[
        FieldSchema("price",    "Price",    ["offers.price", "price", "listPrice"],        [], "float", "$",    required=True, is_primary_sort=True),
        FieldSchema("mileage",  "Mileage",  ["mileageFromOdometer", "mileage", "miles"],   [], "int",   "mi"),
        FieldSchema("year",     "Year",     ["modelDate", "year", "modelYear"],            [], "int"),
        FieldSchema("trim",     "Trim",     ["trim", "trimLevel"],                         [], "str"),
        FieldSchema("vin",      "VIN",      ["vehicleIdentificationNumber", "vin"],        [], "str"),
        FieldSchema("drivetrain","Drivetrain",["driveWheelConfiguration", "driveType"],    [], "str"),
    ],
    scoring_weights={"price": 35, "mileage": 25, "age": 20, "shipping": 10, "hybrid": 10},
    system_prompt_context="You are an automotive analyst helping a buyer find the best used vehicle deal on Carvana.",
    alert_on_new=True,
    alert_on_drop_pct=5.0,
)


class CarvanaAdapter(DomainAdapter):

    @property
    def domain_config(self) -> DomainConfig:
        return AUTOMOTIVE_CONFIG

    def build_url(self, page: int = 1, **filters) -> str:
        return build_search_url(**filters, page=page)

    def normalize(self, raw: dict, strategy: str) -> dict | None:
        make  = raw.get("make") or filters.get("make", "")
        model = raw.get("model") or filters.get("model", "")
        return normalize_vehicle(raw, make, model, strategy)
```

### Generic adapter (AI-discovered domains)

```python
# domains/generic/adapter.py
from domains.base import DomainAdapter, DomainConfig
from datetime import datetime, timezone


class GenericAdapter(DomainAdapter):
    """
    Fully config-driven adapter for any domain defined by a DomainConfig.
    No hardcoded field logic — all extraction driven by FieldSchema.json_paths.
    """

    def __init__(self, config: DomainConfig):
        self._config = config

    @property
    def domain_config(self) -> DomainConfig:
        return self._config

    def build_url(self, page: int = 1, **filters) -> str:
        base = self._config.base_url.rstrip("/")
        if self._config.pagination_style == "query_param":
            sep = "&" if "?" in base else "?"
            return f"{base}{sep}{self._config.pagination_param}={page}"
        if self._config.pagination_style == "path_segment":
            return f"{base}/{page}"
        return base

    def normalize(self, raw: dict, strategy: str) -> dict | None:
        result = {"extraction_strategy": strategy, "scraped_at": datetime.now(timezone.utc).isoformat()}
        missing_required = False
        for schema in self._config.fields:
            val = self.get_field(raw, schema)
            if val is None and schema.required:
                missing_required = True
                break
            result[schema.name] = val
        if missing_required:
            return None
        return result
```

---

## 5. AI Field Detection Flow

This is the new capability: the user describes what they want, and an LLM agent
figures out how to extract it from a site they've never seen before.

### Step-by-step flow

```
1. User inputs:
   - Target URL (or site name)
   - Natural language request:
     "I want to track Zillow listings in Austin TX under $500k.
      Pull: price, square footage, bedrooms, bathrooms, address,
      days on market, and listing URL."

2. Discovery Agent fetches a sample page:
   - Uses Playwright (existing browser.py) to load the URL
   - Extracts: raw HTML, all ld+json blocks, __NEXT_DATA__, any window.* vars
   - Truncates HTML to ~15k chars for LLM context (keeps JSON blocks in full)

3. Discovery Agent sends to LLM (SchemaAgent):
   SYSTEM:
     You are a web data extraction expert. Your job is to analyze raw page
     data from a website and produce a precise extraction schema that maps
     the user's requested fields to the actual data structures on the page.

     You have three sources to work with:
       1. Structured JSON (ld+json, __NEXT_DATA__, Apollo cache) — prefer these
       2. HTML DOM — use CSS selectors as fallback
       3. Infer from visible text if structured data is absent

     Output ONLY valid JSON. No explanation. No markdown fences.

   USER:
     Target URL: https://www.zillow.com/austin-tx/
     User request: "price, square footage, bedrooms, bathrooms, address,
                    days on market, listing URL"

     === STRUCTURED JSON FOUND ON PAGE ===
     [ld+json blocks, __NEXT_DATA__ excerpt, window vars — truncated to 12k chars]

     === HTML SAMPLE (first 3000 chars of body) ===
     [rendered HTML excerpt]

     Produce a JSON object matching this schema:
     {
       "fields": [
         {
           "name": "price",
           "display_name": "Price",
           "json_paths": ["$.price", "$.hdpData.homeInfo.price"],
           "css_selectors": ["[data-test='property-card-price']"],
           "data_type": "float",
           "unit": "$",
           "required": true,
           "is_primary_sort": true
         },
         ...
       ],
       "pagination_style": "query_param",
       "pagination_param": "page",
       "system_prompt_context": "You are a real estate analyst...",
       "scoring_weights": {"price": 35, "sqft": 25, "days_on_market": 20, "beds": 10, "baths": 10}
     }

4. LLM returns FieldSchema JSON. Discovery Agent:
   - Parses and validates the JSON
   - Constructs a DomainConfig object
   - Saves it to domains/saved/<domain_id>.json

5. Field validation (spot-check):
   - Fetches 2–3 more pages using the new config
   - Runs GenericAdapter.normalize() on 5 sample listings
   - For each field: checks non-null rate, type correctness, value plausibility
   - If any required field has >50% null rate: re-prompts LLM with the failures
     and asks for corrected json_paths (up to 2 retry attempts)

6. User sees a preview in the dashboard:
   - "Found 24 listings. Sample: {price: $389,000, sqft: 1,842, beds: 3, ...}"
   - User confirms or edits field mappings in a simple UI form
   - Saved as a named "domain" they can reuse

7. From this point, the domain runs exactly like Carvana does today:
   - Scheduled scraping, LLM analysis, email alerts, history, trend charts
```

### SchemaAgent implementation sketch

```python
# discovery/schema_agent.py
import json
import logging
from dataclasses import asdict

from domains.base import DomainConfig, FieldSchema
from analysis.llm import LLMAnalyzer, LLMResult
from scraper.browser import BrowserSession

log = logging.getLogger(__name__)

DISCOVERY_SYSTEM_PROMPT = """You are a web data extraction expert. Analyze the raw page data
provided and produce a JSON extraction schema that maps the user's requested fields to
the actual data structures present. Always prefer structured JSON paths (ld+json,
__NEXT_DATA__, Apollo/GraphQL window objects) over DOM selectors. Use DOM selectors
only as fallback. Output ONLY valid JSON — no explanation, no markdown code fences."""

DISCOVERY_SCHEMA_TEMPLATE = """{
  "fields": [
    {
      "name": "<snake_case_field_name>",
      "display_name": "<Human Readable Name>",
      "json_paths": ["<primary.path>", "<fallback.path>"],
      "css_selectors": ["[data-testid='...']", ".class-name"],
      "data_type": "float|int|str|bool",
      "unit": "$|sqft|mi|",
      "required": true|false,
      "is_primary_sort": true|false
    }
  ],
  "pagination_style": "query_param|path_segment|none",
  "pagination_param": "page",
  "system_prompt_context": "You are a <domain> analyst...",
  "scoring_weights": {"<field_name>": <0-100>, ...}
}"""


class SchemaAgent:
    def __init__(self, llm: LLMAnalyzer):
        self.llm = llm

    def discover(
        self,
        url: str,
        user_request: str,
        domain_id: str,
        display_name: str,
    ) -> DomainConfig | None:
        """
        Fetch the target URL and ask the LLM to produce a DomainConfig.
        Returns None if discovery fails after retries.
        """
        with BrowserSession() as browser:
            html = browser.get_page_content(url)

        if not html:
            log.error("SchemaAgent: failed to fetch %s", url)
            return None

        page_context = _extract_page_context(html)
        prompt = _build_discovery_prompt(url, user_request, page_context)

        result: LLMResult = self.llm.analyze([], _prompt_override=prompt)
        if not result.analysis:
            log.error("SchemaAgent: LLM returned no output")
            return None

        config = _parse_llm_response(result.analysis, url, domain_id, display_name, user_request)
        if config is None:
            log.error("SchemaAgent: could not parse LLM JSON response")
            return None

        log.info("SchemaAgent: discovered %d fields for %s", len(config.fields), domain_id)
        return config

    def validate_and_refine(
        self,
        config: DomainConfig,
        max_retries: int = 2,
    ) -> DomainConfig:
        """
        Spot-check the config against live data. Re-prompts on failure.
        Returns the (possibly refined) config.
        """
        from domains.generic.adapter import GenericAdapter
        adapter = GenericAdapter(config)

        for attempt in range(max_retries + 1):
            failures = _spot_check(adapter, config)
            if not failures:
                log.info("SchemaAgent: validation passed on attempt %d", attempt + 1)
                return config
            if attempt == max_retries:
                log.warning("SchemaAgent: validation failed after %d retries; returning best effort", max_retries)
                return config
            log.info("SchemaAgent: refining schema, attempt %d — failures: %s", attempt + 1, failures)
            config = self._refine(config, failures)

        return config

    def _refine(self, config: DomainConfig, failures: list[str]) -> DomainConfig:
        """Ask the LLM to fix fields that had high null rates."""
        failure_str = "\n".join(f"- {f}" for f in failures)
        refine_prompt = (
            f"The following fields had >50% null extraction rate on live data:\n{failure_str}\n\n"
            f"Current field definitions:\n{json.dumps([asdict(f) for f in config.fields], indent=2)}\n\n"
            f"Provide a corrected JSON 'fields' array only. Fix the json_paths and/or "
            f"css_selectors for the failing fields. Output ONLY the corrected JSON array."
        )
        result = self.llm.analyze([], _prompt_override=refine_prompt)
        if not result.analysis:
            return config
        try:
            fields_data = json.loads(result.analysis)
            if isinstance(fields_data, list):
                config.fields = [FieldSchema(**f) for f in fields_data]
        except (json.JSONDecodeError, TypeError):
            pass
        return config


def _extract_page_context(html: str) -> str:
    """Pull structured JSON and a short HTML sample from raw page HTML."""
    import re
    parts = []

    # ld+json blocks
    blocks = re.findall(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    if blocks:
        parts.append("=== ld+json blocks ===\n" + "\n---\n".join(blocks[:5]))

    # __NEXT_DATA__
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        parts.append("=== __NEXT_DATA__ (first 6000 chars) ===\n" + m.group(1)[:6000])

    # window.* vars
    window_vars = re.findall(r'window\.__\w+\s*=\s*(\{.*?\});', html, re.DOTALL)
    if window_vars:
        parts.append("=== window vars (first 3000 chars each) ===\n" +
                     "\n---\n".join(v[:3000] for v in window_vars[:3]))

    # Short HTML body sample
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(separator=" ", strip=True)[:3000]
    parts.append("=== Page text sample ===\n" + body_text)

    return "\n\n".join(parts)[:15000]


def _build_discovery_prompt(url: str, user_request: str, page_context: str) -> str:
    return (
        f"[SYSTEM]\n{DISCOVERY_SYSTEM_PROMPT}\n\n"
        f"[TARGET URL]\n{url}\n\n"
        f"[USER REQUEST]\n{user_request}\n\n"
        f"[PAGE DATA]\n{page_context}\n\n"
        f"[OUTPUT SCHEMA]\nProduce JSON matching this structure:\n{DISCOVERY_SCHEMA_TEMPLATE}"
    )


def _parse_llm_response(
    text: str, url: str, domain_id: str, display_name: str, user_request: str
) -> DomainConfig | None:
    import re
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        fields = [FieldSchema(**f) for f in data.get("fields", [])]
        return DomainConfig(
            domain_id=domain_id,
            display_name=display_name,
            base_url=url,
            pagination_style=data.get("pagination_style", "query_param"),
            pagination_param=data.get("pagination_param", "page"),
            fields=fields,
            scoring_weights=data.get("scoring_weights", {}),
            system_prompt_context=data.get("system_prompt_context", ""),
            user_request=user_request,
        )
    except (TypeError, KeyError):
        return None


def _spot_check(adapter, config: DomainConfig) -> list[str]:
    """
    Fetch one page and check field null rates. Returns list of failing field names.
    """
    from scraper.browser import BrowserSession
    from scraper.extractor import extract_from_schema_org, extract_from_next_data

    with BrowserSession() as browser:
        html = browser.get_page_content(adapter.build_url(page=1))

    if not html:
        return []

    raw_list = extract_from_schema_org(html) or extract_from_next_data(html)
    if not raw_list:
        return []

    sample = raw_list[:10]
    failures = []
    for field_schema in config.fields:
        null_count = sum(
            1 for raw in sample
            if adapter.get_field(raw, field_schema) is None
        )
        null_rate = null_count / len(sample)
        if null_rate > 0.5 and field_schema.required:
            failures.append(f"{field_schema.name} ({int(null_rate*100)}% null)")

    return failures
```

---

## 6. Implementation Plan — Phased

### Phase 1: Extract and isolate car-specific logic (Week 1)
*Goal: nothing breaks; Carvana still works; car logic is now behind the adapter interface.*

> **Commits:** Create git commits throughout this phase at logical checkpoints (e.g. after the `domains/` scaffold, after each adapter, after rules/email changes). Do not batch all changes into one commit at the end.

- [x] **1.1** Create `domains/` package structure (`base.py`, `registry.py`, `automotive/`, `generic/`)
- [x] **1.2** Move `scraper/urls.py::build_search_url` → `domains/automotive/url_builder.py`
- [x] **1.3** Move `scraper/extractor.py::normalize_vehicle` → `domains/automotive/normalizer.py`
- [x] **1.4** Create `domains/automotive/adapter.py` implementing `CarvanaAdapter(DomainAdapter)`
- [x] **1.5** Update `scraper/extractor.py::extract_listings` to call `adapter.normalize()` instead of `normalize_vehicle()` directly; pass adapter in as parameter
- [x] **1.6** Update `main.py` to load the appropriate adapter per profile
- [x] **1.7** Make `analysis/rules.py::_value_score` use `scoring_weights` dict from `DomainConfig` instead of hardcoded constants
- [x] **1.8** Make `notifications/email_alert.py::build_email_html` accept a `domain_config` parameter; use `display_name` and `fields` for column headers; replace Carvana-specific language with domain name
- [x] **1.9** Run all existing tests to confirm nothing broke

> **Verification:** Review the checklist above and mark each item `[x]` as confirmed complete. Do not mark an item done unless the code change is in place and tests pass.

> **Docs:** Update `CLAUDE.md` (architecture section) and `README.md` to reflect the new `domains/` package, the adapter pattern, and any changed import paths or dev instructions introduced in this phase.

### Phase 2: Generic extractor and storage generalization (Week 1–2)
*Goal: a GenericAdapter can successfully scrape a second site end-to-end.*

> **Commits:** Commit after `GenericAdapter` is created, after storage is generalized, and after manual validation passes. Do not batch all changes into one commit at the end.

- [ ] **2.1** Create `domains/generic/adapter.py` (`GenericAdapter`) as sketched in Section 4
- [ ] **2.2** Create `discovery/domain_config.py` with save/load to `domains/saved/<id>.json`
- [ ] **2.3** Generalize `storage/history_db.py`: store listings as JSON blobs (flexible columns) alongside indexed fields (`domain_id`, `listing_id`, `primary_sort_value`, `run_id`)
- [ ] **2.4** Generalize `storage/csv_writer.py`: derive column list from `domain_config.fields`
- [ ] **2.5** Test manually: point `GenericAdapter` at a second real site, verify extraction

> **Verification:** Review the checklist above and mark each item `[x]` as confirmed complete. Do not mark an item done unless the code change is in place and verified working.

> **Docs:** Update `CLAUDE.md` (architecture section) and `README.md` to reflect the generalized storage schema, `GenericAdapter`, and `discovery/domain_config.py`.

### Phase 3: AI schema discovery (Week 2)
*Goal: user can enter a URL + plain-language request and get a working domain config.*

> **Commits:** Commit after `SchemaAgent` and `field_validator` are created, after each API route is added, and after the LLM wiring is complete. Do not batch all changes into one commit at the end.

- [ ] **3.1** Create `discovery/schema_agent.py` as sketched in Section 5
- [ ] **3.2** Create `discovery/field_validator.py` (spot-check logic extracted from `schema_agent.py`)
- [ ] **3.3** Add `POST /domains/discover` route to FastAPI backend (`dashboard/backend/routers/domains.py`)
  - Body: `{url, user_request, domain_id, display_name}`
  - Response: streaming SSE log + final `DomainConfig` JSON
- [ ] **3.4** Add `GET /domains` route: list all saved domain configs from `domains/saved/`
- [ ] **3.5** Add `DELETE /domains/{domain_id}` route
- [ ] **3.6** Wire `LLMAnalyzer` into `SchemaAgent` (reuse existing fallback chain)

> **Verification:** Review the checklist above and mark each item `[x]` as confirmed complete. Test each API route manually (or with curl) before marking 3.3–3.5 done.

> **Docs:** Update `CLAUDE.md` (architecture section and key files table) and `README.md` to document the `discovery/` package, `SchemaAgent` flow, and the new `/domains/*` API endpoints.

### Phase 4: LLM prompt generalization (Week 2–3)
*Goal: LLM analysis prompt works for any domain, not just cars.*

> **Commits:** Commit after each of `build_prompt()`, `build_synthesis_prompt()`, and `__init__` is refactored. Do not batch all changes into one commit at the end.

- [ ] **4.1** Refactor `analysis/llm.py::build_prompt()`:
  - Accept `domain_config: DomainConfig` parameter
  - Replace car-specific system context with `domain_config.system_prompt_context`
  - Build listing table from `domain_config.fields` (dynamic columns)
  - Replace hybrid/financing notes with domain-specific context from profile
- [ ] **4.2** Refactor `analysis/llm.py::build_synthesis_prompt()` same way
- [ ] **4.3** Update `LLMAnalyzer.__init__` to accept and store `domain_config`

> **Verification:** Review the checklist above and mark each item `[x]` as confirmed complete. Run an end-to-end Carvana scrape to confirm the automotive prompt is unchanged in behavior.

> **Docs:** Update `CLAUDE.md` (LLM fallback chain section) and `README.md` to note that `LLMAnalyzer` is now domain-config-driven and describe the `system_prompt_context` field.

### Phase 5: Dashboard UI — Domain Wizard (Week 3)
*Goal: user can onboard a new domain without touching any Python.*

> **Commits:** Commit after `DomainWizardView.tsx` is functional, after nav/routing changes, and after `ProfilesView` and `HistoryView` modifications. Do not batch all changes into one commit at the end.

- [ ] **5.1** Create `DomainWizardView.tsx`:
  - Step 1: Enter URL + paste or type user request
  - Step 2: Live log stream while SchemaAgent runs
  - Step 3: Preview table of sample listings (5 rows)
  - Step 4: Edit field names/types in a simple table editor
  - Step 5: Name + save the domain
- [ ] **5.2** Add "Domains" entry to the nav bar in `App.tsx`
- [ ] **5.3** Add domain selector to `ProfilesView.tsx` / profile YAML schema
- [ ] **5.4** Add domain column to `HistoryView.tsx` run list

> **Verification:** Review the checklist above and mark each item `[x]` as confirmed complete. Manually walk through all 5 wizard steps in the browser before marking 5.1 done.

> **Docs:** Update `CLAUDE.md` (frontend section) and `README.md` to document the Domain Wizard flow and the new `/domains` route.

### Phase 6: Profile schema generalization (Week 3–4)
*Goal: `profiles.yaml` supports non-automotive domains.*

> **Commits:** Commit after the `SearchProfile` dataclass changes, after `profiles.yaml` is updated with the new example, and after the router change. Do not batch all changes into one commit at the end.

- [ ] **6.1** Add `domain_id` field to `SearchProfile` dataclass in `profiles.py`
- [ ] **6.2** Add `filter_rules` list (replaces `max_price`, `max_mileage`, `min_year` for generic domains)
- [ ] **6.3** Keep backward compatibility: if `domain_id` is absent, assume `carvana_suvs`
- [ ] **6.4** Update `profiles.yaml` example with a second domain entry
- [ ] **6.5** Update `dashboard/backend/routers/profiles.py` to expose `domain_id`

> **Verification:** Review the checklist above and mark each item `[x]` as confirmed complete. Load an existing `profiles.yaml` without `domain_id` to confirm backward compatibility before marking 6.3 done.

> **Docs:** Update `CLAUDE.md` (profile system section) and `README.md` to document the new `domain_id` and `filter_rules` fields and show the updated `profiles.yaml` structure.

### Phase 7: Polish and testing (Week 4)

> **Commits:** Commit after each new test file is added, after the robots.txt check is in place, and after settings changes. Do not batch all changes into one commit at the end.

- [ ] **7.1** Add `tests/test_schema_agent.py` with mocked LLM and known HTML fixtures
- [ ] **7.2** Add `tests/test_generic_adapter.py`
- [ ] **7.3** Add `tests/test_generic_rules.py`
- [ ] **7.4** Update `README.md` with new domain setup instructions
- [ ] **7.5** Add rate-limit / robots.txt check to `SchemaAgent.discover()` (warn, don't block)
- [ ] **7.6** Add `SCRAPING_DELAY_MS` config setting to `dashboard_settings.json` (default: 1500ms between pages)

> **Verification:** Review the checklist above and mark each item `[x]` as confirmed complete. Run the full test suite (`python -m pytest tests/ -v`) and confirm all tests pass before marking this phase done.

> **Docs:** Update `CLAUDE.md` (commands section and architecture) and `README.md` to document the new test files, the `SCRAPING_DELAY_MS` setting, and the robots.txt behavior.

---

## 7. File-Level Change Map

For each existing file, what changes and what stays the same.

| File | Change Type | What Changes |
|---|---|---|
| `main.py` | Modify | Load adapter from domain registry; pass adapter into `run_profile()` |
| `config.py` | Minor | Add `DOMAINS_DIR` path setting |
| `profiles.py` | Modify | Add `domain_id`, `filter_rules` to `SearchProfile`; backward-compat defaults |
| `scraper/extractor.py` | Refactor | `extract_listings()` accepts adapter param; `normalize_vehicle()` moved out |
| `scraper/urls.py` | Move | Content moves to `domains/automotive/url_builder.py`; file becomes a shim |
| `analysis/llm.py` | Modify | `build_prompt()` / `build_synthesis_prompt()` accept `domain_config` |
| `analysis/rules.py` | Modify | `_value_score()` uses `scoring_weights` dict instead of literals |
| `storage/history_db.py` | Modify | Add `domain_id` column to `runs` and `listings`; listings support JSON blob |
| `storage/csv_writer.py` | Modify | Dynamic column derivation from `domain_config.fields` |
| `notifications/email_alert.py` | Modify | Accept `domain_config`; Jinja2 templates; replace hardcoded Carvana strings |
| `dashboard/backend/app.py` | Minor | Register new `domains` router |
| `dashboard/backend/routers/profiles.py` | Modify | Expose `domain_id` in profile API response |
| `dashboard/frontend/src/App.tsx` | Minor | Add Domains nav entry and route |
| `utils/vin_decode.py` | No change | Still used by `CarvanaAdapter`; not called by generic path |
| `utils/payment_calc.py` | No change | Still used by `CarvanaAdapter`; not called by generic path |
| All `analysis/*_client.py` | No change | LLM clients are already fully domain-agnostic |
| `dashboard/backend/job_manager.py` | No change | Job lifecycle is domain-agnostic |
| `dashboard/backend/app_scheduler.py` | No change | Scheduler is domain-agnostic |

---

## 8. New Files to Create

```
domains/
├── __init__.py
├── base.py                         # DomainAdapter, DomainConfig, FieldSchema (Section 4)
├── registry.py                     # load_adapter(domain_id) → DomainAdapter
├── automotive/
│   ├── __init__.py
│   ├── adapter.py                  # CarvanaAdapter(DomainAdapter)
│   ├── url_builder.py              # Moved from scraper/urls.py
│   └── normalizer.py               # Moved from extractor.normalize_vehicle()
├── generic/
│   ├── __init__.py
│   └── adapter.py                  # GenericAdapter(DomainAdapter) — config-driven
└── saved/
    └── .gitkeep                    # Domain configs saved here as <domain_id>.json

discovery/
├── __init__.py
├── schema_agent.py                 # LLM-powered schema discovery (Section 5)
├── field_validator.py              # Spot-check extracted fields against live data
└── domain_config.py                # save_config() / load_config() / list_configs()

dashboard/backend/routers/
└── domains.py                      # POST /domains/discover, GET /domains, DELETE /domains/{id}

dashboard/frontend/src/views/
└── DomainWizardView.tsx            # 5-step domain onboarding UI

tests/
├── test_schema_agent.py
├── test_generic_adapter.py
└── test_generic_rules.py
```

---

## 9. Config & Profile Schema Changes

### `dashboard_settings.json` additions

```json
{
  "domains_dir": "domains/saved",
  "scraping_delay_ms": 1500,
  "discovery_max_retries": 2,
  "discovery_html_truncate_chars": 15000
}
```

### `profiles.yaml` new fields

```yaml
profiles:
  - profile_id: carvana_suvs
    label: "SUVs on Carvana"
    domain_id: carvana_suvs          # NEW — links to domains/saved/carvana_suvs.json
    vehicles:
      - make: Toyota
        model: RAV4
    # ... rest unchanged

  - profile_id: zillow_austin        # NEW — example generic domain
    label: "Austin Homes on Zillow"
    domain_id: zillow_homes_austin   # must match a file in domains/saved/
    filter_rules:                    # NEW — replaces max_price/max_mileage for generic domains
      - field: price
        operator: "<="
        value: 500000
      - field: beds
        operator: ">="
        value: 3
    email_to:
      - user@example.com
```

### `SearchProfile` dataclass additions

```python
# profiles.py
@dataclass
class SearchProfile:
    # ... existing fields unchanged ...
    domain_id: str = "carvana_suvs"            # NEW
    filter_rules: list[dict] = field(default_factory=list)  # NEW (generic domains)
```

---

## 10. Frontend Changes

### New views

**`DomainWizardView.tsx`** — 5-step wizard:
1. URL input + user request textarea
2. Live SSE log stream while SchemaAgent runs (reuse `ConsoleDrawer` component)
3. Sample data preview table (5 rows × discovered fields)
4. Field editor: name, display_name, data_type, unit, required (editable grid)
5. Save with domain_id + display_name input

### Modified views

**`ProfilesView.tsx`**: Add domain badge showing which domain each profile targets.

**`HistoryView.tsx`**: Add domain column to runs table.

**`SettingsView.tsx`**: Add `scraping_delay_ms` and `discovery_max_retries` fields.

**`App.tsx`**: Add `/domains` route and nav entry.

### Reusable components (no change needed)

- `ConsoleDrawer.tsx` — SSE log streaming already works for discovery jobs
- `StatusBar.tsx` — unchanged
- All auth/portal components — unchanged

---

## Key Design Decisions

**Why keep `normalize_vehicle()` as-is and wrap it?**
It's battle-tested with 4 fallback paths and handles Carvana's quirky Schema.org embedding.
Moving it to `CarvanaAdapter.normalize()` preserves all that without rewriting anything.

**Why LLM for field discovery instead of a static rule-based approach?**
Site structures vary wildly — ld+json, GraphQL, React SSR, plain HTML. An LLM can read
the actual page structure and produce the right paths without requiring a human to reverse-
engineer each site. The validation step catches hallucinations.

**Why not use JSONPath libraries (jsonpath-ng, jmespath)?**
Simple dot-notation covers 90% of cases and has zero dependencies. The `_json_path_get()`
utility can be extended to support bracket notation (`[0]`, `['key']`) if needed later.

**Why Jinja2 for email templates?**
The current `build_email_html()` is 300+ lines of f-string concatenation. Jinja2 lets
domain-specific templates live in `notifications/templates/<domain_id>.html` without
touching Python, making it easy to customize per domain.

**Why save domain configs as JSON files instead of in the database?**
Domain configs are code-like artifacts that benefit from being version-controlled and
human-readable. The database is for time-series data (listings, runs, prices).
The `domains/saved/` directory can be committed to git.
