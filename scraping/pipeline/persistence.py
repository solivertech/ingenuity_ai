"""Thin wrapper around the existing storage layer for generic domain items."""

import logging

log = logging.getLogger(__name__)


def save_items(
    items: list[dict],
    run_id: str,
    profile_id: str,
    domain_id: str,
    domain_config=None,
) -> None:
    """Persist enriched items to SQLite via history_db."""
    try:
        from storage import history_db
        history_db.save_listings(
            items, run_id, profile_id,
            domain_id=domain_id,
            domain_config=domain_config,
        )
        log.info(
            "Saved %d items (profile=%s, domain=%s)", len(items), profile_id, domain_id
        )
    except Exception as exc:
        log.error("Failed to save items to DB: %s", exc)
