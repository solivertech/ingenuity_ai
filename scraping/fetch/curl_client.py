"""
Tier 2 fetch client — curl_cffi TLS fingerprint impersonation.

Bypasses JA3/JA4 TLS fingerprint detection by mimicking Chrome's exact
TLS extension list, cipher order, and ALPN negotiation.
"""

import asyncio
import logging

log = logging.getLogger(__name__)

_DEFAULT_PROFILE = "chrome124"


class CurlClient:
    """Tier 2: TLS fingerprint impersonation via curl_cffi."""

    def __init__(self, impersonate: str = _DEFAULT_PROFILE, timeout: float = 30.0):
        self.impersonate = impersonate
        self.timeout = timeout

    async def fetch(
        self,
        url: str,
        headers: dict | None = None,
        proxy: str | None = None,
    ) -> tuple[int, str]:
        """Return (status_code, html). Raises on network error or missing dependency."""
        try:
            import curl_cffi.requests as curl_requests
        except ImportError:
            raise RuntimeError("curl_cffi not installed — run: pip install curl_cffi")

        loop = asyncio.get_event_loop()
        _proxy = proxy

        def _sync_fetch() -> tuple[int, str]:
            kwargs: dict = {"headers": headers or {}, "timeout": self.timeout}
            if _proxy:
                kwargs["proxies"] = {"https": _proxy, "http": _proxy}
            session = curl_requests.Session(impersonate=self.impersonate)
            resp = session.get(url, **kwargs)
            return resp.status_code, resp.text

        status, html = await loop.run_in_executor(None, _sync_fetch)
        log.debug("curl_cffi[%s] %s → %d (%d bytes)%s",
                  self.impersonate, url, status, len(html),
                  f" via {proxy}" if proxy else "")
        return status, html
