"""Tests for scraping.parse.html_cleaner.HTMLCleaner."""

import os
import pytest
from scraping.parse.html_cleaner import HTMLCleaner


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _clean(html: str) -> str:
    return HTMLCleaner().clean(html)


# ── Tag stripping ─────────────────────────────────────────────────────────────

def test_strips_script_tags():
    result = _clean("<html><body><script>alert('x')</script><p>content</p></body></html>")
    assert "alert" not in result
    assert "content" in result


def test_strips_style_tags():
    result = _clean("<html><body><style>.foo{color:red}</style><p>content</p></body></html>")
    assert ".foo" not in result
    assert "content" in result


def test_strips_nav_tags():
    result = _clean("<html><body><nav>Menu items</nav><main>Main content</main></body></html>")
    assert "Menu items" not in result
    assert "Main content" in result


def test_strips_footer_tags():
    result = _clean("<html><body><footer>Footer text</footer><p>Real content</p></body></html>")
    assert "Footer text" not in result
    assert "Real content" in result


def test_strips_header_tags():
    result = _clean("<html><body><header>Header text</header><p>Real content</p></body></html>")
    assert "Header text" not in result
    assert "Real content" in result


def test_strips_aside_tags():
    result = _clean("<html><body><aside>Sidebar</aside><p>content</p></body></html>")
    assert "Sidebar" not in result


def test_strips_form_tags():
    result = _clean("<html><body><form><input/></form><p>content</p></body></html>")
    assert "content" in result


def test_strips_noscript_tags():
    result = _clean("<html><body><noscript>JS off</noscript><p>content</p></body></html>")
    assert "JS off" not in result


# ── Noise attribute stripping ─────────────────────────────────────────────────

def test_strips_cookie_class():
    result = _clean('<html><body><div class="cookie-banner">Accept cookies</div><p>content</p></body></html>')
    assert "Accept cookies" not in result
    assert "content" in result


def test_strips_popup_class():
    result = _clean('<html><body><div class="popup-modal">Subscribe</div><p>content</p></body></html>')
    assert "Subscribe" not in result


def test_strips_consent_id():
    result = _clean('<html><body><div id="consent-overlay">GDPR</div><p>content</p></body></html>')
    assert "GDPR" not in result


def test_strips_advertisement_class():
    result = _clean('<html><body><div class="advertisement">Buy now</div><p>content</p></body></html>')
    assert "Buy now" not in result


def test_preserves_content_without_noise_attrs():
    result = _clean('<html><body><div class="product-listing"><p>Widget $25</p></div></body></html>')
    assert "Widget" in result
    assert "25" in result


# ── Return type ───────────────────────────────────────────────────────────────

def test_clean_returns_string():
    result = HTMLCleaner().clean("<html><body><p>hello</p></body></html>")
    assert isinstance(result, str)


def test_clean_empty_html_returns_string():
    result = HTMLCleaner().clean("")
    assert isinstance(result, str)


def test_to_markdown_returns_non_empty_string():
    result = HTMLCleaner().to_markdown("<p>hello world</p>")
    assert isinstance(result, str)
    assert "hello" in result


def test_to_markdown_preserves_headings():
    result = HTMLCleaner().to_markdown("<h1>Title</h1><p>body</p>")
    assert "Title" in result


# ── Fixture-based ─────────────────────────────────────────────────────────────

def test_static_fixture_strips_noise():
    with open(os.path.join(FIXTURES, "sample_page_static.html"), encoding="utf-8") as f:
        html = f.read()
    result = _clean(html)
    assert "Navigation menu" not in result
    assert "Footer content" not in result
    assert "tracker" not in result        # script content stripped


def test_static_fixture_preserves_listings():
    with open(os.path.join(FIXTURES, "sample_page_static.html"), encoding="utf-8") as f:
        html = f.read()
    result = _clean(html)
    assert "Red Widget" in result
    assert "Blue Widget" in result


def test_schema_org_fixture_strips_nav():
    with open(os.path.join(FIXTURES, "sample_page_schema_org.html"), encoding="utf-8") as f:
        html = f.read()
    result = _clean(html)
    assert "Site navigation" not in result
    assert "Products for Sale" in result
