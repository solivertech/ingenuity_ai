"""
Normalizer — validates and coerces raw item dicts against a DomainConfig schema.

Step 1 of the pipeline: drops items missing required fields and coerces
each declared field to its declared data_type.
"""

import logging
from typing import Any

log = logging.getLogger(__name__)


def _coerce(value: Any, data_type: str) -> Any:
    """Coerce value to data_type. Returns None on failure."""
    if value is None:
        return None
    try:
        if data_type in ("float", "number"):
            if isinstance(value, str):
                value = value.replace(",", "").replace("$", "").strip()
            return float(value)
        if data_type in ("int", "integer"):
            if isinstance(value, str):
                value = value.replace(",", "").strip()
            return int(float(value))
        if data_type == "bool":
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "1")
            return bool(value)
        # str and unknown types
        return value if isinstance(value, str) else str(value)
    except (ValueError, TypeError):
        return None


class DomainItemNormalizer:
    """
    Validates and coerces raw item dicts against DomainConfig.fields.

    Items with None values for required fields are dropped. Extra keys
    not declared in the schema are preserved unchanged (e.g. internal
    fields like extraction_strategy).
    """

    def __init__(self, domain_config=None):
        self.domain_config = domain_config

    def normalize(self, item: dict) -> dict | None:
        if self.domain_config is None or not getattr(self.domain_config, "fields", None):
            return item

        result = dict(item)

        for field in self.domain_config.fields:
            raw = item.get(field.name)
            coerced = _coerce(raw, field.data_type)
            if coerced is None and field.required:
                log.debug(
                    "Dropping item: missing required field '%s' (raw=%r)",
                    field.name, raw,
                )
                return None
            result[field.name] = coerced

        return result

    def normalize_many(self, items: list[dict]) -> list[dict]:
        out = []
        dropped = 0
        for item in items:
            normalized = self.normalize(item)
            if normalized is not None:
                out.append(normalized)
            else:
                dropped += 1
        if dropped:
            log.info(
                "Normalizer: dropped %d/%d items (missing required fields)",
                dropped, len(items),
            )
        return out
