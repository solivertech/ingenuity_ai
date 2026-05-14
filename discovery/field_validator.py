"""
Field validation — fetches live page data and checks null rates for each
discovered field. Used by SchemaAgent to decide whether to re-prompt.
"""

import logging

from domains.base import DomainConfig

log = logging.getLogger(__name__)


def spot_check(adapter, config: DomainConfig) -> list[str]:
    """
    Fetch one page using the adapter and measure each required field's null rate.

    Returns a list of failing field descriptions (name + null %) for any required
    field with >50% null rate across up to 10 sample listings.
    Returns an empty list if the page cannot be fetched or no listings are found
    (no reason to penalise a config for an unreachable page).
    """
    from scraper.browser import Browser
    from scraper.extractor import extract_from_schema_org, extract_from_next_data

    try:
        with Browser() as browser:
            html = browser.get_page_content(adapter.build_url(page=1))
    except Exception as exc:
        log.warning("field_validator: browser error during spot-check: %s", exc)
        return []

    if not html:
        log.warning("field_validator: empty page during spot-check")
        return []

    raw_list = extract_from_schema_org(html) or extract_from_next_data(html)
    if not raw_list:
        log.info("field_validator: no structured listings found; skipping null-rate check")
        return []

    sample = raw_list[:10]
    failures: list[str] = []

    for field_schema in config.fields:
        if not field_schema.required:
            continue
        null_count = sum(
            1 for raw in sample
            if adapter.get_field(raw, field_schema) is None
        )
        null_rate = null_count / len(sample)
        if null_rate > 0.5:
            failures.append(f"{field_schema.name} ({int(null_rate * 100)}% null)")
            log.warning(
                "field_validator: required field '%s' has %.0f%% null rate",
                field_schema.name, null_rate * 100,
            )

    return failures
