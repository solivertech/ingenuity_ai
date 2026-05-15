"""Tier 1 fetch client — async HTTPX with HTTP/2 and connection pooling."""

import logging

log = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class HTTPXClient:
    """Tier 1: async HTTP/2 client. Fastest for sites that don't block Python."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch(
        self,
        url: str,
        headers: dict | None = None,
        proxy: str | None = None,
    ) -> tuple[int, str]:
        """Return (status_code, html). Raises on network error."""
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx not installed — run: pip install 'httpx[http2]'")

        h = {**_DEFAULT_HEADERS, **(headers or {})}
        async with httpx.AsyncClient(
            http2=True, timeout=self.timeout, follow_redirects=True,
            **({"proxy": proxy} if proxy else {}),
        ) as client:
            response = await client.get(url, headers=h)
            log.debug("HTTPX %s → %d (%d bytes)%s",
                      url, response.status_code, len(response.text),
                      f" via {proxy}" if proxy else "")
            return response.status_code, response.text
