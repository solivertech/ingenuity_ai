"""Generic Schema.org ld+json extraction — domain-agnostic."""

import json
import logging
import re

log = logging.getLogger(__name__)


def extract_schema_org(html: str, types: list[str] | None = None) -> list[dict]:
    """
    Extract all ld+json blocks from HTML.
    If types is given, only return blocks whose @type is in types.
    Handles both single objects and arrays.
    """
    raw_blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    results: list[dict] = []
    for raw in raw_blocks:
        try:
            data = json.loads(raw)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if types is None or item.get("@type") in types:
                    results.append(item)
        except (json.JSONDecodeError, AttributeError):
            continue
    log.debug("Schema.org: %d block(s) (type filter=%s)", len(results), types)
    return results
