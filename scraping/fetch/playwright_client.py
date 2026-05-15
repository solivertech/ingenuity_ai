"""
Tier 3 fetch client — Playwright with stealth patches and request interception.

Wraps the existing scraper.browser.Browser and applies:
  - navigator.webdriver masking
  - Canvas fingerprint noise
  - Resource type blocking (images, fonts, analytics)
"""

import asyncio
import logging

log = logging.getLogger(__name__)

_BLOCK_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}
_BLOCK_DOMAINS = {
    "google-analytics.com", "googletagmanager.com", "facebook.com",
    "twitter.com", "doubleclick.net", "hotjar.com", "segment.com", "mixpanel.com",
}

_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = {runtime: {}};
const _getCtx = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(type, ...args) {
    const ctx = _getCtx.call(this, type, ...args);
    if (type === '2d') {
        const _fill = ctx.fillText;
        ctx.fillText = function(...a) {
            a[0] = a[0] + String.fromCharCode(0);
            return _fill.apply(this, a);
        };
    }
    return ctx;
};
"""


class PlaywrightClient:
    """Tier 3: Playwright headless with stealth + resource interception."""

    def __init__(self, stealth: bool = True, intercept_resources: bool = True):
        self.stealth = stealth
        self.intercept_resources = intercept_resources

    async def fetch(self, url: str, proxy: str | None = None) -> tuple[int, str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, url, proxy)

    def _fetch_sync(self, url: str, proxy: str | None = None) -> tuple[int, str]:
        from scraper.browser import Browser
        browser = Browser(proxy=proxy)
        browser.start()
        try:
            if self.stealth:
                self._apply_stealth(browser)
            if self.intercept_resources:
                self._setup_interception(browser)
            html = browser.get_page_content(url) or ""
            if html and browser._page:
                html = self._postprocess_page(browser._page, html)
            return (200 if html else 0), html
        finally:
            browser.close()

    def _apply_stealth(self, browser) -> None:
        try:
            page = getattr(browser, "_page", None)
            if page:
                page.add_init_script(_STEALTH_SCRIPT)
        except Exception as exc:
            log.debug("Stealth patch skipped: %s", exc)

    def _setup_interception(self, browser) -> None:
        try:
            page = getattr(browser, "_page", None)
            if not page:
                return

            def _route(route):
                rt = route.request.resource_type
                url = route.request.url
                if rt in _BLOCK_RESOURCE_TYPES:
                    route.abort()
                elif any(d in url for d in _BLOCK_DOMAINS):
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", _route)
        except Exception as exc:
            log.debug("Request interception skipped: %s", exc)

    @staticmethod
    def _postprocess_page(page, original_html: str) -> str:
        """Dismiss consent popups, flatten shadow DOM, return updated HTML."""
        from scraping.parse.consent_remover import dismiss_consent_popup
        from scraping.parse.shadow_dom import flatten_shadow_dom
        try:
            dismiss_consent_popup(page)
            flatten_shadow_dom(page)
            return page.content() or original_html
        except Exception as exc:
            log.debug("Page post-processing skipped: %s", exc)
            return original_html
