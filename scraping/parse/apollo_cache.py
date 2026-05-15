"""Generic Apollo/GraphQL cache extraction — domain-agnostic."""

import json
import logging
import re

log = logging.getLogger(__name__)


def extract_apollo_cache(
    html: str, typename_filter: list[str] | None = None
) -> list[dict]:
    """
    Extract items from Apollo/GraphQL window variable.
    If typename_filter is given, only return objects with matching __typename.
    """
    match = re.search(
        r'window\.__(?:APOLLO_STATE__|apollo\w*)\s*=\s*(\{.*?\});\s*(?:window|</script)',
        html,
        re.DOTALL,
    )
    if not match:
        match = re.search(
            r'"__APOLLO_STATE__"\s*:\s*(\{.*?\})\s*[,}]', html, re.DOTALL
        )
    if not match:
        log.debug("Apollo cache not found")
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        log.debug("Failed to parse Apollo cache: %s", exc)
        return []

    results = [
        val for val in data.values()
        if isinstance(val, dict)
        and (typename_filter is None or val.get("__typename") in typename_filter)
    ]
    log.debug("Apollo cache: %d item(s) (filter=%s)", len(results), typename_filter)
    return results
