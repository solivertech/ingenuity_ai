"""
Change detector — identifies field changes between the current run and a previous snapshot.

Compares items by their ID field and flags when watched fields change value.
"""

import logging

log = logging.getLogger(__name__)

_ID_FIELDS = ("vin", "id", "listing_id", "url", "listing_url")


class ChangeDetector:
    """Detects field-value changes between the current scrape and a previous one."""

    def __init__(self, id_field: str | None = None, tracked_fields: list[str] | None = None):
        self.id_field = id_field
        self.tracked_fields = tracked_fields or ["price"]

    def detect(self, current: list[dict], previous: list[dict]) -> list[dict]:
        """
        Return items from current whose tracked fields changed vs previous.
        Each returned item gets a 'changes' key: {field: (old_val, new_val)}.
        """
        prev_index = self._build_index(previous)
        if not prev_index:
            return []

        changed: list[dict] = []
        for item in current:
            item_id = self._get_id(item)
            if not item_id or item_id not in prev_index:
                continue
            prev_item = prev_index[item_id]
            item_changes = {
                f: (prev_item[f], item[f])
                for f in self.tracked_fields
                if item.get(f) is not None
                and prev_item.get(f) is not None
                and item[f] != prev_item[f]
            }
            if item_changes:
                copy = dict(item)
                copy["changes"] = item_changes
                changed.append(copy)
                log.debug("Change: %s → %s", item_id, item_changes)

        if changed:
            log.info("ChangeDetector: %d item(s) changed", len(changed))
        return changed

    def _build_index(self, items: list[dict]) -> dict[str, dict]:
        return {self._get_id(i): i for i in items if self._get_id(i)}

    def _get_id(self, item: dict) -> str | None:
        if self.id_field:
            val = item.get(self.id_field)
            return str(val) if val is not None else None
        for field in _ID_FIELDS:
            val = item.get(field)
            if val is not None:
                return str(val)
        return None
