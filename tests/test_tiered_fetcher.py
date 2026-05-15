"""Tests for scraping.fetch.tiered_fetcher.TieredFetcher."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from scraping.fetch.tiered_fetcher import FetchResult, FetchTier, TieredFetcher

_GOOD_HTML = "x" * 2000  # above MIN_CONTENT_BYTES (1000)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _cfg(requires_js=False, scraping_delay_ms=None):
    class _Cfg:
        pass
    c = _Cfg()
    c.requires_js = requires_js
    c.scraping_delay_ms = scraping_delay_ms
    return c


# ── Successful fetch via first available tier ─────────────────────────────────

def test_httpx_succeeds_returns_result():
    fetcher = TieredFetcher()
    with patch.object(fetcher, "_fetch_tier", new=AsyncMock(return_value=(200, _GOOD_HTML))):
        result = _run(fetcher.fetch("http://example.com"))
    assert result.tier_used == FetchTier.HTTPX
    assert result.html == _GOOD_HTML
    assert result.status_code == 200
    assert result.error is None


def test_fetch_result_contains_url():
    fetcher = TieredFetcher()
    url = "http://example.com/listing"
    with patch.object(fetcher, "_fetch_tier", new=AsyncMock(return_value=(200, _GOOD_HTML))):
        result = _run(fetcher.fetch(url))
    assert result.url == url


# ── requires_js skips to Playwright ──────────────────────────────────────────

def test_requires_js_starts_at_playwright():
    fetcher = TieredFetcher()
    calls = []

    async def mock_fetch_tier(tier, url, proxy=None):
        calls.append(tier)
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        _run(fetcher.fetch("http://example.com", domain_config=_cfg(requires_js=True)))

    assert calls == [FetchTier.PLAYWRIGHT]


def test_no_domain_config_starts_at_httpx():
    fetcher = TieredFetcher()
    calls = []

    async def mock_fetch_tier(tier, url, proxy=None):
        calls.append(tier)
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        _run(fetcher.fetch("http://example.com"))

    assert calls[0] == FetchTier.HTTPX


# ── Tier escalation on block ──────────────────────────────────────────────────

def test_blocked_tier_escalates_to_next():
    fetcher = TieredFetcher()
    call_order = []

    async def mock_fetch_tier(tier, url, proxy=None):
        call_order.append(tier)
        if tier == FetchTier.HTTPX:
            return (403, "forbidden")  # block signal
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        result = _run(fetcher.fetch("http://example.com"))

    assert FetchTier.HTTPX in call_order
    assert FetchTier.CURL_CFFI in call_order
    assert result.tier_used == FetchTier.CURL_CFFI


def test_all_tiers_blocked_returns_error_result():
    fetcher = TieredFetcher()

    async def mock_fetch_tier(tier, url, proxy=None):
        return (403, "blocked")

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        with patch("scraping.fetch.tiered_fetcher.TieredFetcher._backoff", new=AsyncMock()):
            result = _run(fetcher.fetch("http://example.com"))

    assert result.error == "all tiers failed"
    assert result.html == ""


def test_short_response_treated_as_block():
    fetcher = TieredFetcher()
    call_order = []

    async def mock_fetch_tier(tier, url, proxy=None):
        call_order.append(tier)
        if tier == FetchTier.HTTPX:
            return (200, "tiny")  # below MIN_CONTENT_BYTES
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        result = _run(fetcher.fetch("http://example.com"))

    assert len(call_order) >= 2
    assert result.tier_used != FetchTier.HTTPX


# ── Retry on 429 within tier ──────────────────────────────────────────────────

def test_429_retries_within_same_tier():
    fetcher = TieredFetcher()
    call_count = {"n": 0}

    async def mock_fetch_tier(tier, url, proxy=None):
        if tier == FetchTier.HTTPX:
            call_count["n"] += 1
            if call_count["n"] < 3:
                return (429, "rate limited")
            return (200, _GOOD_HTML)
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        with patch("scraping.fetch.tiered_fetcher.TieredFetcher._backoff", new=AsyncMock()):
            result = _run(fetcher.fetch("http://example.com"))

    assert result.tier_used == FetchTier.HTTPX
    assert call_count["n"] == 3


def test_non_429_block_does_not_retry_within_tier():
    fetcher = TieredFetcher()
    httpx_calls = {"n": 0}

    async def mock_fetch_tier(tier, url, proxy=None):
        if tier == FetchTier.HTTPX:
            httpx_calls["n"] += 1
            return (403, "forbidden")
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        _run(fetcher.fetch("http://example.com"))

    assert httpx_calls["n"] == 1  # no retry, escalated immediately


# ── Exception handling ────────────────────────────────────────────────────────

def test_exception_in_tier_retries_then_escalates():
    fetcher = TieredFetcher()
    call_order = []

    async def mock_fetch_tier(tier, url, proxy=None):
        call_order.append(tier)
        if tier == FetchTier.HTTPX:
            raise ConnectionError("network error")
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        with patch("scraping.fetch.tiered_fetcher.TieredFetcher._backoff", new=AsyncMock()):
            result = _run(fetcher.fetch("http://example.com"))

    # HTTPX attempted _RETRY_MAX_ATTEMPTS times before escalating
    assert call_order.count(FetchTier.HTTPX) == 3
    assert result.tier_used == FetchTier.CURL_CFFI


# ── max_tier cap ──────────────────────────────────────────────────────────────

def test_max_tier_httpx_never_tries_higher_tiers():
    fetcher = TieredFetcher(max_tier=FetchTier.HTTPX)
    call_order = []

    async def mock_fetch_tier(tier, url, proxy=None):
        call_order.append(tier)
        return (403, "blocked")

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        with patch("scraping.fetch.tiered_fetcher.TieredFetcher._backoff", new=AsyncMock()):
            result = _run(fetcher.fetch("http://example.com"))

    assert all(t == FetchTier.HTTPX for t in call_order)
    assert result.error == "all tiers failed"


# ── fetch_sync wrapper ────────────────────────────────────────────────────────

def test_fetch_sync_returns_same_result_as_async():
    fetcher = TieredFetcher()
    with patch.object(fetcher, "_fetch_tier", new=AsyncMock(return_value=(200, _GOOD_HTML))):
        result = fetcher.fetch_sync("http://example.com")
    assert isinstance(result, FetchResult)
    assert result.html == _GOOD_HTML


# ── Camoufox Tier 4 ───────────────────────────────────────────────────────────

def test_camoufox_tier_exists():
    assert FetchTier.CAMOUFOX.value == 4


def test_browser_engine_camoufox_starts_at_camoufox():
    fetcher = TieredFetcher(max_tier=FetchTier.CAMOUFOX)
    calls = []

    async def mock_fetch_tier(tier, url, proxy=None):
        calls.append(tier)
        return (200, _GOOD_HTML)

    cfg = _cfg()
    cfg.browser_engine = "camoufox"
    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        _run(fetcher.fetch("http://example.com", domain_config=cfg))

    assert calls == [FetchTier.CAMOUFOX]


def test_default_max_tier_excludes_camoufox():
    fetcher = TieredFetcher()  # default max_tier=PLAYWRIGHT
    calls = []

    async def mock_fetch_tier(tier, url, proxy=None):
        calls.append(tier)
        return (403, "blocked")

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        with patch("scraping.fetch.tiered_fetcher.TieredFetcher._backoff", new=AsyncMock()):
            _run(fetcher.fetch("http://example.com"))

    assert FetchTier.CAMOUFOX not in calls


def test_playwright_blocked_escalates_to_camoufox_when_allowed():
    fetcher = TieredFetcher(max_tier=FetchTier.CAMOUFOX)
    call_order = []

    async def mock_fetch_tier(tier, url, proxy=None):
        call_order.append(tier)
        # Block all tiers except Camoufox
        if tier != FetchTier.CAMOUFOX:
            return (403, "blocked")
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        result = _run(fetcher.fetch("http://example.com"))

    assert FetchTier.CAMOUFOX in call_order
    assert result.tier_used == FetchTier.CAMOUFOX


# ── Proxy threading ───────────────────────────────────────────────────────────

def test_proxy_is_passed_to_fetch_tier():
    fetcher = TieredFetcher()
    received_proxies = []

    async def mock_fetch_tier(tier, url, proxy=None):
        received_proxies.append(proxy)
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        _run(fetcher.fetch("http://example.com", proxy="http://proxy:8080"))

    assert received_proxies[0] == "http://proxy:8080"


def test_no_proxy_passes_none_to_fetch_tier():
    fetcher = TieredFetcher()
    received_proxies = []

    async def mock_fetch_tier(tier, url, proxy=None):
        received_proxies.append(proxy)
        return (200, _GOOD_HTML)

    with patch.object(fetcher, "_fetch_tier", side_effect=mock_fetch_tier):
        _run(fetcher.fetch("http://example.com"))

    assert received_proxies[0] is None
