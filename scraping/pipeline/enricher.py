"""
Generic item enricher — computes value_score from domain config scoring_weights.

Score is 0–100. Fields listed in scoring_weights contribute proportionally.
Fields whose names contain price/cost/mileage/fee are treated as lower-is-better.
"""

import logging
from collections import defaultdict

log = logging.getLogger(__name__)

_LOWER_IS_BETTER_KEYWORDS = {"price", "cost", "fee", "mileage", "monthly", "distance"}


class GenericEnricher:
    """Computes value_score for items based on domain config scoring_weights."""

    def __init__(self, domain_config=None):
        self.weights: dict[str, float] = {}
        if domain_config:
            self.weights = dict(domain_config.scoring_weights or {})

    def enrich(self, items: list[dict]) -> list[dict]:
        """Add value_score to each item in-place. Returns the same list."""
        if not items:
            return items

        if not self.weights:
            for item in items:
                item.setdefault("value_score", 0.0)
            return items

        group_avgs = self._group_averages(items)
        for item in items:
            item["value_score"] = self._score(item, group_avgs)
        return items

    def _score(self, item: dict, group_avgs: dict) -> float:
        total_weight = sum(self.weights.values()) or 1.0
        score = 0.0

        for field_name, weight in self.weights.items():
            val = item.get(field_name)
            if val is None:
                score += weight / 2.0
                continue
            avg = group_avgs.get(field_name)
            try:
                fval = float(val)
                if avg and avg > 0:
                    pct_diff = max(-0.5, min(0.5, (fval - avg) / avg))
                    lower_better = any(kw in field_name.lower() for kw in _LOWER_IS_BETTER_KEYWORDS)
                    component = ((0.5 - pct_diff) if lower_better else (0.5 + pct_diff)) * weight
                else:
                    component = weight / 2.0
            except (TypeError, ValueError):
                component = weight / 2.0
            score += component

        return round(min(100.0, max(0.0, (score / total_weight) * 100)), 2)

    def _group_averages(self, items: list[dict]) -> dict[str, float]:
        sums: dict[str, list[float]] = defaultdict(list)
        for item in items:
            for field_name in self.weights:
                val = item.get(field_name)
                if val is not None:
                    try:
                        sums[field_name].append(float(val))
                    except (TypeError, ValueError):
                        pass
        return {k: sum(v) / len(v) for k, v in sums.items() if v}
