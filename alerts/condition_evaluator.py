"""
Alert condition evaluator — checks DomainConfig alert_conditions against item data.

Condition types:
  threshold    — field op value (e.g. price <= 400000)
  appearance   — new item appeared (handled by change_detector)
  change       — field changed since last run (handled by change_detector)
"""

import logging
from typing import Any

log = logging.getLogger(__name__)

_OPS: dict[str, Any] = {
    "<=": lambda a, b: float(a) <= float(b),
    "<":  lambda a, b: float(a) < float(b),
    ">=": lambda a, b: float(a) >= float(b),
    ">":  lambda a, b: float(a) > float(b),
    "==": lambda a, b: str(a) == str(b),
    "!=": lambda a, b: str(a) != str(b),
}


def _attr(obj, name: str, default=None):
    if hasattr(obj, name):
        return getattr(obj, name, default)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


class ConditionEvaluator:
    """Evaluates alert conditions from DomainConfig against scraped items."""

    def __init__(self, domain_config=None):
        self.conditions = list(getattr(domain_config, "alert_conditions", []) or [])

    def evaluate(self, items: list[dict]) -> list[dict]:
        """Return items that trigger any condition. Adds 'alert_reason' key."""
        if not self.conditions:
            return []

        triggered: list[dict] = []
        for item in items:
            for cond in self.conditions:
                reason = self._check(item, cond)
                if reason:
                    copy = dict(item)
                    copy["alert_reason"] = reason
                    triggered.append(copy)
                    break

        if triggered:
            log.info("ConditionEvaluator: %d item(s) triggered alerts", len(triggered))
        return triggered

    def _check(self, item: dict, condition) -> str | None:
        cond_type = _attr(condition, "type", "threshold")
        if cond_type != "threshold":
            return None

        field = _attr(condition, "field")
        op = _attr(condition, "operator")
        value = _attr(condition, "value")
        if not all([field, op, value is not None]):
            return None

        item_val = item.get(field)
        if item_val is None:
            return None

        op_fn = _OPS.get(op)
        if op_fn is None:
            return None

        try:
            if op_fn(item_val, value):
                return f"{field} {op} {value}"
        except (TypeError, ValueError):
            pass
        return None
