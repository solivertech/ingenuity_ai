"""
TieredFetcher — escalates through HTTP tiers automatically on block detection.

Tier priority (SCRAPING_ENGINE_PLAN.md §3):
  1  HTTPX        async HTTP/2, fastest
  2  curl_cffi    TLS fingerprint impersonation, bypasses JA3/JA4 detection
  3  Playwright   full JS rendering + stealth patches (Chromium)
  4  Camoufox     Firefox-based stealth — different TLS profile + canvas fingerprint

Tier-selection rules:
  - requires_js=True  → start at Playwright (skip 1 & 2)
  - browser_engine="camoufox" → start at Camoufox directly
  - Otherwise start at HTTPX and escalate on block

Proxy support:
  - Pass proxy= to fetch() / fetch_sync() to route through a proxy URL.
  - The proxy is forwarded to every tier client.
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from enum import Enum

from scraping.fetch.block_detector import BlockDetector

log = logging.getLogger(__name__)

_detector = BlockDetector()

_RETRY_BASE_DELAY_S = 2.0   # seconds; exponential: 2^attempt * jitter
_RETRY_MAX_ATTEMPTS = 3     # attempts per tier before escalating


class FetchTier(Enum):
    HTTPX      = 1
    CURL_CFFI  = 2
    PLAYWRIGHT = 3
    CAMOUFOX   = 4


@dataclass
class FetchResult:
    html: str
    tier_used: FetchTier
    status_code: int
    url: str
    error: str | None = None


class TieredFetcher:
    """
    Tries each fetch tier in order, escalating on block detection.
    Callers never need to know which tier succeeded.
    """

    def __init__(self, max_tier: FetchTier = FetchTier.PLAYWRIGHT):
        self.max_tier = max_tier

    async def fetch(
        self,
        url: str,
        domain_config=None,
        proxy: str | None = None,
    ) -> FetchResult:
        requires_js    = getattr(domain_config, "requires_js", False)
        browser_engine = getattr(domain_config, "browser_engine", "chromium")

        if browser_engine == "camoufox":
            start_value = FetchTier.CAMOUFOX.value
        elif requires_js:
            start_value = FetchTier.PLAYWRIGHT.value
        else:
            start_value = FetchTier.HTTPX.value

        for tier in FetchTier:
            if tier.value < start_value or tier.value > self.max_tier.value:
                continue
            result = await self._try_tier(tier, url, proxy)
            if result is not None:
                return result

        last_tier = max(
            (t for t in FetchTier if t.value <= self.max_tier.value),
            key=lambda t: t.value,
        )
        return FetchResult(
            html="", tier_used=last_tier,
            status_code=0, url=url, error="all tiers failed",
        )

    async def _try_tier(
        self,
        tier: FetchTier,
        url: str,
        proxy: str | None,
    ) -> "FetchResult | None":
        """Try one tier with exponential backoff. Returns None to escalate."""
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                status, html = await self._fetch_tier(tier, url, proxy)
            except Exception as exc:
                log.warning("Tier %s attempt %d error: %s", tier.name, attempt + 1, exc)
                if attempt + 1 < _RETRY_MAX_ATTEMPTS:
                    await self._backoff(attempt)
                    continue
                return None  # escalate

            reason = _detector.block_reason(status, html, url)
            if not reason:
                log.info("Fetched via %s: %s (%d bytes)", tier.name, url, len(html))
                return FetchResult(html=html, tier_used=tier, status_code=status, url=url)

            log.info(
                "Tier %s blocked (%s) attempt %d/%d — %s",
                tier.name, reason, attempt + 1, _RETRY_MAX_ATTEMPTS, url,
            )
            if status == 429 and attempt + 1 < _RETRY_MAX_ATTEMPTS:
                await self._backoff(attempt)
                continue
            return None  # escalate

        return None

    @staticmethod
    async def _backoff(attempt: int) -> None:
        delay = (_RETRY_BASE_DELAY_S ** (attempt + 1)) * random.uniform(0.8, 1.2)
        log.debug("Backoff %.1fs before retry", delay)
        await asyncio.sleep(delay)

    def fetch_sync(
        self,
        url: str,
        domain_config=None,
        proxy: str | None = None,
    ) -> FetchResult:
        """Synchronous wrapper for use in non-async contexts."""
        return asyncio.run(self.fetch(url, domain_config, proxy))

    async def _fetch_tier(
        self,
        tier: FetchTier,
        url: str,
        proxy: str | None,
    ) -> tuple[int, str]:
        if tier == FetchTier.HTTPX:
            from scraping.fetch.httpx_client import HTTPXClient
            return await HTTPXClient().fetch(url, proxy=proxy)
        if tier == FetchTier.CURL_CFFI:
            from scraping.fetch.curl_client import CurlClient
            return await CurlClient().fetch(url, proxy=proxy)
        if tier == FetchTier.PLAYWRIGHT:
            from scraping.fetch.playwright_client import PlaywrightClient
            return await PlaywrightClient(stealth=True, intercept_resources=True).fetch(
                url, proxy=proxy
            )
        if tier == FetchTier.CAMOUFOX:
            from scraping.fetch.camoufox_client import CamoufoxClient
            return await CamoufoxClient().fetch(url, proxy=proxy)
        raise ValueError(f"Unknown tier: {tier}")
