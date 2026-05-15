"""
Tier 4 fetch client — Camoufox Firefox-based stealth browser.

Camoufox uses Firefox under the hood with anti-detection patches applied at
compile time (not via JS injection), which produces a different TLS fingerprint
and canvas fingerprint than Chromium. Use when Playwright (Tier 3) is blocked.

Installation:
    pip install camoufox
    python -m camoufox fetch      # downloads the patched Firefox binary once

Set browser_engine: "camoufox" in a domain config to start directly at this tier.
"""

import asyncio
import logging

log = logging.getLogger(__name__)

_BLOCK_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}
_BLOCK_DOMAINS = {
    "google-analytics.com", "googletagmanager.com", "facebook.com",
    "twitter.com", "doubleclick.net", "hotjar.com", "segment.com", "mixpanel.com",
}


class CamoufoxClient:
    """Tier 4: Firefox stealth via Camoufox."""

    def __init__(
        self,
        headless: bool = True,
        intercept_resources: bool = True,
        timeout: int = 30000,
    ):
        self.headless = headless
        self.intercept_resources = intercept_resources
        self.timeout = timeout

    async def fetch(self, url: str, proxy: str | None = None) -> tuple[int, str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, url, proxy)

    def _fetch_sync(self, url: str, proxy: str | None = None) -> tuple[int, str]:
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            raise RuntimeError(
                "camoufox not installed — run:\n"
                "  pip install camoufox\n"
                "  python -m camoufox fetch"
            )

        launch_kwargs: dict = {"headless": self.headless}
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}

        try:
            with Camoufox(**launch_kwargs) as browser:
                page = browser.new_page()
                if self.intercept_resources:
                    self._setup_interception(page)
                page.goto(url, timeout=self.timeout)
                self._postprocess(page)
                html = page.content() or ""
                log.info(
                    "Camoufox fetched %s (%d bytes)%s",
                    url, len(html), f" via {proxy}" if proxy else "",
                )
                return (200 if html else 0), html
        except Exception as exc:
            log.warning("Camoufox fetch failed for %s: %s", url, exc)
            raise

    @staticmethod
    def _setup_interception(page) -> None:
        def _route(route):
            rt = route.request.resource_type
            url = route.request.url
            if rt in _BLOCK_RESOURCE_TYPES:
                route.abort()
            elif any(d in url for d in _BLOCK_DOMAINS):
                route.abort()
            else:
                route.continue_()
        try:
            page.route("**/*", _route)
        except Exception as exc:
            log.debug("Camoufox request interception skipped: %s", exc)

    @staticmethod
    def _postprocess(page) -> None:
        """Dismiss consent popups and flatten shadow DOM."""
        from scraping.parse.consent_remover import dismiss_consent_popup
        from scraping.parse.shadow_dom import flatten_shadow_dom
        try:
            dismiss_consent_popup(page)
            flatten_shadow_dom(page)
        except Exception as exc:
            log.debug("Camoufox post-processing skipped: %s", exc)
