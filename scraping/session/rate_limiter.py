"""
Per-domain rate limiter with ±20% jitter.

Adds random timing variation to avoid detectable request patterns.
"""

import asyncio
import logging
import random
import time

log = logging.getLogger(__name__)


class RateLimiter:
    """Per-domain rate limiting with jitter. Supports both async and sync usage."""

    def __init__(self, base_delay_ms: int = 1500):
        self.base_delay_ms = base_delay_ms
        self._last_request: dict[str, float] = {}

    async def wait(self, domain: str) -> None:
        """Async wait before next request to this domain."""
        delay_s = self._compute_delay(domain)
        if delay_s > 0:
            log.debug("RateLimiter: %.0fms for %s", delay_s * 1000, domain)
            await asyncio.sleep(delay_s)
        self._last_request[domain] = time.monotonic()

    def wait_sync(self, domain: str) -> None:
        """Synchronous wait before next request to this domain."""
        delay_s = self._compute_delay(domain)
        if delay_s > 0:
            log.debug("RateLimiter: %.0fms for %s", delay_s * 1000, domain)
            time.sleep(delay_s)
        self._last_request[domain] = time.monotonic()

    def _compute_delay(self, domain: str) -> float:
        elapsed_ms = (time.monotonic() - self._last_request.get(domain, 0)) * 1000
        jitter = random.uniform(0.8, 1.2)
        target_ms = self.base_delay_ms * jitter
        remaining_ms = target_ms - elapsed_ms
        return max(0.0, remaining_ms / 1000)
