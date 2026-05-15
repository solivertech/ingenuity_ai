"""
HTML → clean Markdown conversion.

Strips noise (nav, footer, ads, cookie banners, scripts) and converts
the main content to Markdown. Reduces LLM token usage by 60-80%.
"""

import logging
import re

log = logging.getLogger(__name__)

_STRIP_TAGS = [
    "script", "style", "noscript", "iframe", "nav",
    "footer", "header", "aside", "form",
]

_NOISE_ATTR_RE = re.compile(
    r"cookie|banner|popup|modal|consent|gdpr|newsletter|"
    r"subscribe|advertisement|\bad-\b|sidebar|overlay",
    re.IGNORECASE,
)


class HTMLCleaner:
    """Converts raw HTML to clean Markdown for LLM consumption."""

    def clean(self, html: str) -> str:
        """Strip noise elements and return clean Markdown."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        for tag in _STRIP_TAGS:
            for el in soup.find_all(tag):
                el.decompose()

        for el in soup.find_all(True):
            attrs = getattr(el, "attrs", None)
            if not attrs:
                continue
            classes = " ".join(attrs.get("class") or [])
            el_id = attrs.get("id") or ""
            if _NOISE_ATTR_RE.search(classes) or _NOISE_ATTR_RE.search(el_id):
                el.decompose()

        return self.to_markdown(str(soup))

    def to_markdown(self, html: str) -> str:
        """Convert HTML to Markdown. Uses markdownify if installed."""
        try:
            import markdownify
            md = markdownify.markdownify(html, heading_style="ATX", strip=["a"])
            md = re.sub(r"\n{3,}", "\n\n", md)
            return md.strip()
        except ImportError:
            return self._plain_text(html)

    def _plain_text(self, html: str) -> str:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text).strip()
