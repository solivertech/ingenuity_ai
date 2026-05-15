"""
Block signal detection — identifies when a site has blocked the scraper.

Checks status codes, response body content, URL patterns, and response size.
"""

import re

BLOCK_STATUS_CODES = {403, 429, 503, 401, 407}

_BLOCK_BODY_RE = re.compile(
    r"captcha|challenge|access.denied|bot.detection|verify.you.are.human|"
    r"too.many.requests|blocked|forbidden|cloudflare|ddos.protection|"
    r"unusual.traffic|automated.access",
    re.IGNORECASE,
)

_BLOCK_URL_RE = re.compile(
    r"/login\b|/auth\b|/captcha|/challenge|/block\b|/banned",
    re.IGNORECASE,
)

MIN_CONTENT_BYTES = 1000


class BlockDetector:
    """Detects block/bot-challenge responses from any combination of signals."""

    def is_blocked(self, status_code: int, html: str, url: str) -> bool:
        return self.block_reason(status_code, html, url) is not None

    def block_reason(self, status_code: int, html: str, url: str) -> str | None:
        if status_code in BLOCK_STATUS_CODES:
            return f"HTTP {status_code}"
        if _BLOCK_URL_RE.search(url):
            return f"block URL: {url}"
        if len(html) < MIN_CONTENT_BYTES:
            return f"response too short ({len(html)} bytes)"
        m = _BLOCK_BODY_RE.search(html[:5000])
        if m:
            return f"block keyword in body: {m.group()}"
        return None
