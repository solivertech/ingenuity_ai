"""
DOM drift detector — monitors per-field extraction success rates.

When a field's success rate drops below DRIFT_THRESHOLD across the last
LOOKBACK_RUNS runs, it is flagged as drifted and partial re-discovery
is triggered for that field.
"""

import logging
from collections import defaultdict

log = logging.getLogger(__name__)

DRIFT_THRESHOLD = 0.30
LOOKBACK_RUNS = 10


class DriftDetector:
    """
    Tracks per-domain, per-field extraction success rates.
    Call record_run() after each scrape, then check() for drifted fields.
    """

    def __init__(self):
        # domain_id → field_name → list[bool] (True = extracted successfully)
        self._history: dict[str, dict[str, list[bool]]] = defaultdict(
            lambda: defaultdict(list)
        )

    def record_run(
        self, domain_id: str, items: list[dict], field_names: list[str]
    ) -> None:
        """Record which fields were successfully extracted in this run."""
        if not items:
            return
        for field_name in field_names:
            success = sum(
                1 for item in items if item.get(field_name) is not None
            ) / len(items)
            history = self._history[domain_id][field_name]
            history.append(success >= 0.5)
            if len(history) > LOOKBACK_RUNS:
                history.pop(0)

    def check(self, domain_id: str) -> list[str]:
        """Return field names with failure rate above DRIFT_THRESHOLD."""
        drifted: list[str] = []
        for field_name, history in self._history.get(domain_id, {}).items():
            if len(history) < 3:
                continue
            failure_rate = history.count(False) / len(history)
            if failure_rate > DRIFT_THRESHOLD:
                log.warning(
                    "Drift: domain=%s field=%s failure_rate=%.0f%%",
                    domain_id, field_name, failure_rate * 100,
                )
                drifted.append(field_name)
        return drifted

    def should_rediscover(self, domain_id: str) -> tuple[bool, list[str]]:
        """Returns (should_rediscover, drifted_fields)."""
        drifted = self.check(domain_id)
        return bool(drifted), drifted
