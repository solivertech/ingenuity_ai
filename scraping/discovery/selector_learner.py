"""
Adaptive selector learner — learns and updates CSS selectors over time.

Stub implementation. Full implementation (Scrapling-style adaptive selectors)
planned for a future phase.
"""

import logging

log = logging.getLogger(__name__)


class SelectorLearner:
    """Generates and updates CSS selectors for domain fields. Stub."""

    def generate(self, element_html: str) -> list[str]:
        log.debug("SelectorLearner.generate() — stub")
        return []

    def update(self, domain_id: str, field_name: str, selectors: list[str]) -> None:
        log.debug("SelectorLearner.update(%s, %s) — stub", domain_id, field_name)
