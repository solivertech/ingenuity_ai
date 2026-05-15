"""
Session pool — tracks scraping sessions, block status, and proxy assignment.

Proxy rotation support is stubbed. Full implementation in a future phase.
"""

import logging

log = logging.getLogger(__name__)


class SessionPool:
    """Manages scraping sessions across runs. Stub for proxy support."""

    def __init__(self):
        self._blocked: set[str] = set()

    def mark_blocked(self, session_id: str) -> None:
        self._blocked.add(session_id)
        log.warning("Session marked blocked: %s", session_id)

    def is_blocked(self, session_id: str) -> bool:
        return session_id in self._blocked

    def retire(self, session_id: str) -> None:
        self._blocked.discard(session_id)
        log.debug("Session retired: %s", session_id)
