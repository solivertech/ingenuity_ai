"""
CSS/XPath DOM extraction using selectolax (fast C parser).
Falls back to BeautifulSoup when selectolax is unavailable.
"""

import logging

log = logging.getLogger(__name__)


class DOMSelector:
    """Extracts field values from HTML using CSS selectors."""

    def extract_field(self, html: str, selectors: list[str]) -> str | None:
        """Try each CSS selector in order; return first non-empty text match."""
        try:
            from selectolax.parser import HTMLParser
            tree = HTMLParser(html)
            for sel in selectors:
                try:
                    node = tree.css_first(sel)
                    if node:
                        text = node.text(strip=True)
                        if text:
                            return text
                except Exception:
                    continue
        except ImportError:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for sel in selectors:
                try:
                    el = soup.select_one(sel)
                    if el:
                        text = el.get_text(strip=True)
                        if text:
                            return text
                except Exception:
                    continue
        return None

    def extract_all(self, html: str, selector: str) -> list[str]:
        """Return text of all elements matching selector."""
        results: list[str] = []
        try:
            from selectolax.parser import HTMLParser
            for node in HTMLParser(html).css(selector):
                text = node.text(strip=True)
                if text:
                    results.append(text)
        except ImportError:
            from bs4 import BeautifulSoup
            for el in BeautifulSoup(html, "html.parser").select(selector):
                text = el.get_text(strip=True)
                if text:
                    results.append(text)
        return results

    def extract_items(self, html: str, domain_config) -> list[dict]:
        """
        Extract a list of items using domain config css_selectors.
        Per-field values are collected then zipped into item dicts.
        """
        if not domain_config or not domain_config.fields:
            return []

        field_values: dict[str, list[str]] = {}
        for f in domain_config.fields:
            selectors = getattr(f, "css_selectors", []) or []
            if not selectors:
                continue
            for sel in selectors:
                found = self.extract_all(html, sel)
                if found:
                    field_values[f.name] = found
                    break

        if not field_values:
            return []

        max_count = max(len(v) for v in field_values.values())
        if max_count == 0:
            return []

        items = []
        for i in range(max_count):
            item = {fname: (vals[i] if i < len(vals) else None)
                    for fname, vals in field_values.items()}
            items.append(item)

        log.debug("DOMSelector: extracted %d items", len(items))
        return items
