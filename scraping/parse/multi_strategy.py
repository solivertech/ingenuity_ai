"""
MultiStrategyParser — tries extraction strategies in priority order.

Strategy order (SCRAPING_ENGINE_PLAN.md §3):
  1. Schema.org ld+json
  2. __NEXT_DATA__ JSON (via domain config json_paths)
  3. Apollo/GraphQL cache
  4. DOM CSS selectors (via selectolax + domain config css_selectors)
  5. LLM extraction from Markdown (most expensive, last resort)

For domains whose ld+json uses jsonpath array expressions (e.g. $.items[*].name),
the schema_org strategy expands the array into individual item dicts keyed by
field name so that GenericAdapter.normalize() can resolve them by direct lookup.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class ParseResult:
    items: list[dict] = field(default_factory=list)
    strategy_used: str = "none"
    confidence: float = 0.0
    fields_found: list[str] = field(default_factory=list)


class MultiStrategyParser:
    """
    Orchestrates all extraction strategies.
    Returns the first result that passes the confidence threshold.
    """

    CONFIDENCE_THRESHOLD = 0.3

    def parse(self, html: str, domain_config) -> ParseResult:
        for name, fn in self._strategies():
            try:
                raw_items = fn(html, domain_config)
                if not raw_items:
                    log.debug("Strategy %s: no items", name)
                    continue
                valid, confidence, fields = self._evaluate(raw_items, domain_config)
                if valid and confidence >= self.CONFIDENCE_THRESHOLD:
                    log.info(
                        "Strategy %s: %d items (confidence=%.2f, fields=%s)",
                        name, len(valid), confidence, fields,
                    )
                    return ParseResult(
                        items=valid,
                        strategy_used=name,
                        confidence=confidence,
                        fields_found=fields,
                    )
                log.debug(
                    "Strategy %s: %d raw but confidence=%.2f < %.2f",
                    name, len(raw_items), confidence, self.CONFIDENCE_THRESHOLD,
                )
            except Exception as exc:
                log.warning("Strategy %s error: %s", name, exc)

        log.warning("All parse strategies failed for this page")
        return ParseResult()

    # ── Strategy implementations ──────────────────────────────────────────────

    def _strategies(self):
        return [
            ("schema_org",    self._schema_org),
            ("next_data",     self._next_data),
            ("apollo_cache",  self._apollo_cache),
            ("dom_selector",  self._dom_selector),
            ("llm_extractor", self._llm_extractor),
        ]

    def _schema_org(self, html: str, domain_config) -> list[dict]:
        from scraping.parse.schema_org import extract_schema_org
        blocks = extract_schema_org(html)
        if not blocks or not domain_config:
            return blocks

        # Check if any field path uses jsonpath array syntax
        needs_expansion = any(
            "[" in p
            for f in (domain_config.fields or [])
            for p in getattr(f, "json_paths", [])
        )
        if needs_expansion:
            return self._expand_jsonpath_blocks(blocks, domain_config)
        return blocks

    def _expand_jsonpath_blocks(self, blocks: list[dict], domain_config) -> list[dict]:
        """
        Evaluate jsonpath expressions (containing [*]) against root blocks,
        zip extracted arrays into individual item dicts keyed by field name.
        """
        try:
            from jsonpath_ng import parse as jp_parse
        except ImportError:
            log.warning("jsonpath_ng not installed — cannot expand array paths")
            return blocks

        all_items: list[dict] = []
        for block in blocks:
            field_lists: dict[str, list] = {}
            for f in domain_config.fields:
                for path in getattr(f, "json_paths", []):
                    try:
                        matches = [m.value for m in jp_parse(path).find(block)]
                        if matches:
                            field_lists[f.name] = matches
                            break
                    except Exception:
                        continue

            if not field_lists:
                continue

            max_len = max(len(v) for v in field_lists.values())
            for i in range(max_len):
                item = {
                    fname: (vals[i] if i < len(vals) else None)
                    for fname, vals in field_lists.items()
                }
                all_items.append(item)

        return all_items

    def _next_data(self, html: str, domain_config) -> list[dict]:
        from scraping.parse.next_data import extract_next_data
        data = extract_next_data(html)
        if not data or not domain_config or not domain_config.fields:
            return []

        # Try to find list-valued paths in __NEXT_DATA__
        try:
            from jsonpath_ng import parse as jp_parse
        except ImportError:
            return []

        for f in domain_config.fields:
            for path in getattr(f, "json_paths", []):
                try:
                    matches = [m.value for m in jp_parse(path).find(data)]
                    if matches and isinstance(matches[0], list):
                        # Found a list of items — expand and return
                        field_lists: dict[str, list] = {}
                        for fs in domain_config.fields:
                            for p in getattr(fs, "json_paths", []):
                                try:
                                    ms = [m.value for m in jp_parse(p).find(data)]
                                    if ms:
                                        field_lists[fs.name] = ms if isinstance(ms[0], list) else ms
                                        break
                                except Exception:
                                    continue

                        # Flatten: if any value is itself a list, use it as the item array
                        flat: dict[str, list] = {}
                        item_count = 0
                        for fname, vals in field_lists.items():
                            if isinstance(vals, list) and vals and isinstance(vals[0], list):
                                flat[fname] = vals[0]
                                item_count = max(item_count, len(vals[0]))
                            else:
                                flat[fname] = vals
                                item_count = max(item_count, len(vals))

                        items = []
                        for i in range(item_count):
                            item = {
                                fn: (fv[i] if i < len(fv) else None)
                                for fn, fv in flat.items()
                            }
                            items.append(item)
                        return items
                except Exception:
                    continue
        return []

    def _apollo_cache(self, html: str, domain_config) -> list[dict]:
        from scraping.parse.apollo_cache import extract_apollo_cache
        return extract_apollo_cache(html)

    def _dom_selector(self, html: str, domain_config) -> list[dict]:
        from scraping.parse.dom_selector import DOMSelector
        return DOMSelector().extract_items(html, domain_config)

    def _llm_extractor(self, html: str, domain_config) -> list[dict]:
        from scraping.parse.llm_extractor import LLMExtractor
        return LLMExtractor().extract(html, domain_config)

    # ── Result evaluation ─────────────────────────────────────────────────────

    def _evaluate(
        self, items: list[dict], domain_config
    ) -> tuple[list[dict], float, list[str]]:
        """Score results against the domain config's required fields."""
        if not items:
            return [], 0.0, []

        if not domain_config or not domain_config.fields:
            return items, 1.0, []

        required = [f for f in domain_config.fields if f.required]
        all_field_schemas = domain_config.fields

        valid: list[dict] = []
        fields_found: set[str] = set()

        for item in items:
            # A required field is present if found by name OR by any of its json_paths
            req_satisfied = all(
                _field_present(item, f) for f in required
            )
            if req_satisfied or not required:
                valid.append(item)
                for f in all_field_schemas:
                    if _field_present(item, f):
                        fields_found.add(f.name)

        if not valid:
            return [], 0.0, []

        confidence = len(fields_found) / max(1, len(all_field_schemas))
        return valid, confidence, sorted(fields_found)


def _field_present(item: dict, field_schema) -> bool:
    """Check if a field is present in an item, checking both name and json_paths."""
    if item.get(field_schema.name) is not None:
        return True
    for path in getattr(field_schema, "json_paths", []):
        if _json_path_get(item, path) is not None:
            return True
    return False


def _json_path_get(obj: dict, path: str):
    """Simple dot-notation path getter (mirrors domains.base._json_path_get)."""
    path = path.lstrip("$.")
    parts = path.split(".")
    cur = obj
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur
