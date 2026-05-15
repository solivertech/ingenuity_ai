"""
Session pool — tracks scraping sessions, block status, and proxy rotation.

Proxy assignment is round-robin: each call to get_proxy() returns the same
proxy until rotate_proxy() or mark_proxy_blocked() is called. Blocked proxies
are skipped; when all proxies are blocked the block list is cleared and the
cycle restarts.
"""

import logging

log = logging.getLogger(__name__)


class SessionPool:
    """
    Manages scraping sessions and proxy rotation.

    Usage with proxy list:
        pool = SessionPool(proxies=["http://p1:port", "http://p2:port"])
        proxy = pool.get_proxy()          # "http://p1:port"
        pool.mark_proxy_blocked(proxy)    # skip p1, advance to p2
        proxy = pool.get_proxy()          # "http://p2:port"
    """

    def __init__(self, proxies: list[str] | None = None):
        self._proxies: list[str] = list(proxies or [])
        self._idx: int = 0
        self._blocked_proxies: set[str] = set()
        # Legacy session-level block tracking (keeps backward compatibility)
        self._blocked_sessions: set[str] = set()

    # ── Proxy management ──────────────────────────────────────────────────────

    def get_proxy(self) -> str | None:
        """Return the current active proxy URL, or None if no proxies configured."""
        if not self._proxies:
            return None
        available = [p for p in self._proxies if p not in self._blocked_proxies]
        if not available:
            log.warning("All proxies blocked — resetting block list and retrying")
            self._blocked_proxies.clear()
            available = list(self._proxies)
        return available[self._idx % len(available)]

    def rotate_proxy(self) -> str | None:
        """Advance to the next proxy in the list. Returns the new proxy URL."""
        if not self._proxies:
            return None
        self._idx = (self._idx + 1) % len(self._proxies)
        return self.get_proxy()

    def mark_proxy_blocked(self, proxy_url: str) -> None:
        """Mark a specific proxy as blocked and rotate to the next one."""
        if proxy_url and proxy_url in self._proxies:
            self._blocked_proxies.add(proxy_url)
            log.warning("Proxy blocked: %s (%d/%d blocked)",
                        proxy_url, len(self._blocked_proxies), len(self._proxies))
            self.rotate_proxy()

    @property
    def proxy_count(self) -> int:
        return len(self._proxies)

    @property
    def blocked_proxy_count(self) -> int:
        return len(self._blocked_proxies)

    @property
    def has_proxies(self) -> bool:
        return bool(self._proxies)

    # ── Legacy session tracking (backward-compatible) ─────────────────────────

    def mark_blocked(self, session_id: str) -> None:
        """Mark a session as blocked. Also rotates the proxy if one is active."""
        self._blocked_sessions.add(session_id)
        log.warning("Session marked blocked: %s", session_id)
        current_proxy = self.get_proxy()
        if current_proxy:
            self.mark_proxy_blocked(current_proxy)

    def is_blocked(self, session_id: str) -> bool:
        return session_id in self._blocked_sessions

    def retire(self, session_id: str) -> None:
        self._blocked_sessions.discard(session_id)
        log.debug("Session retired: %s", session_id)
