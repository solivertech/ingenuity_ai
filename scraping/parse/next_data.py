"""Generic __NEXT_DATA__ extraction — domain-agnostic."""

import json
import logging
import re

log = logging.getLogger(__name__)


def extract_next_data(html: str) -> dict | None:
    """Return the full __NEXT_DATA__ JSON object, or None if not found."""
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        log.debug("__NEXT_DATA__ not found")
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        log.debug("Failed to parse __NEXT_DATA__: %s", exc)
        return None
