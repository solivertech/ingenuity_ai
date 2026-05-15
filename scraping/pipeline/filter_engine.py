"""
Generic filter engine — evaluates DomainConfig.filter_rules against scraped items.

Supported operators: ==, !=, <, <=, >, >=, contains, not_contains
"""

import logging
from collections import defaultdict
from typing import Any

log = logging.getLogger(__name__)

_OPS: dict[str, Any] = {
    "==":           lambda a, b: a == b,
    "!=":           lambda a, b: a != b,
    "<":            lambda a, b: float(a) < float(b),
    "<=":           lambda a, b: float(a) <= float(b),
    ">":            lambda a, b: float(a) > float(b),
    ">=":           lambda a, b: float(a) >= float(b),
    "contains":     lambda a, b: str(b).lower() in str(a).lower(),
    "not_contains": lambda a, b: str(b).lower() not in str(a).lower(),
}


def _attr(obj, name: str, default=None):
    if hasattr(obj, name):
        return getattr(obj, name, default)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


class FilterEngine:
    """Evaluates filter rules from DomainConfig and optional profile overrides."""

    def __init__(self, domain_config=None):
        self.domain_rules = list(getattr(domain_config, "filter_rules", []) or [])

    def apply(self, items: list[dict], profile_rules: list[dict] | None = None) -> list[dict]:
        """Return items that pass all filter rules."""
        all_rules = self.domain_rules + (profile_rules or [])
        if not all_rules:
            return items

        removed: dict[str, int] = defaultdict(int)
        kept: list[dict] = []

        for item in items:
            passed = True
            for rule in all_rules:
                field = _attr(rule, "field")
                operator = _attr(rule, "operator")
                value = _attr(rule, "value")
                if field is None or operator is None:
                    continue
                item_val = item.get(field)
                if item_val is None:
                    continue
                op_fn = _OPS.get(operator)
                if op_fn is None:
                    log.warning("Unknown filter operator: %s", operator)
                    continue
                try:
                    if not op_fn(item_val, value):
                        removed[f"{field} {operator} {value}"] += 1
                        passed = False
                        break
                except (TypeError, ValueError):
                    pass
            if passed:
                kept.append(item)

        if removed:
            reasons = ", ".join(f"{k}={v}" for k, v in removed.items())
            log.info(
                "FilterEngine: removed %d items (%s) — %d remain",
                sum(removed.values()), reasons, len(kept),
            )
        return kept
