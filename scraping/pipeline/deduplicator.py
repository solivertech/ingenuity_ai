"""
Item deduplication — removes duplicate items within a scrape run.

Uses configurable ID fields from DomainConfig, falling back to hashing
the full item dict when no ID field is present.
"""

import hashlib
import json
import logging

log = logging.getLogger(__name__)

_COMMON_ID_FIELDS = ("vin", "id", "listing_id", "url", "listing_url")


class Deduplicator:
    """Deduplicates scraped items. Preserves first-seen order."""

    def __init__(self, id_fields: list[str] | None = None):
        self.id_fields = id_fields

    def deduplicate(self, items: list[dict], domain_config=None) -> list[dict]:
        id_fields = self.id_fields or self._detect_id_fields(domain_config)
        seen: set[str] = set()
        result: list[dict] = []
        dupes = 0

        for item in items:
            key = self._item_key(item, id_fields)
            if key in seen:
                dupes += 1
            else:
                seen.add(key)
                result.append(item)

        if dupes:
            log.info("Deduplicator: removed %d duplicates — %d unique remain", dupes, len(result))
        return result

    def _detect_id_fields(self, domain_config) -> list[str]:
        if domain_config and domain_config.fields:
            names = {f.name for f in domain_config.fields}
            for candidate in _COMMON_ID_FIELDS:
                if candidate in names:
                    return [candidate]
        return list(_COMMON_ID_FIELDS)

    def _item_key(self, item: dict, id_fields: list[str]) -> str:
        for field in id_fields:
            val = item.get(field)
            if val is not None:
                return str(val)
        serialized = json.dumps(item, sort_keys=True, default=str)
        return hashlib.md5(serialized.encode()).hexdigest()
