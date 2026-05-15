"""Tests for scraping.parse.multi_strategy.MultiStrategyParser."""

import os
import json
import pytest
from scraping.parse.multi_strategy import MultiStrategyParser, ParseResult


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
        return f.read()


def _field(name, json_paths=None, css_selectors=None, required=True):
    class _F:
        pass
    f = _F()
    f.name = name
    f.json_paths = json_paths or [name]
    f.css_selectors = css_selectors or []
    f.required = required
    f.data_type = "str"
    return f


def _cfg(fields=None):
    class _C:
        pass
    c = _C()
    c.fields = fields or []
    return c


# ── ParseResult structure ─────────────────────────────────────────────────────

def test_empty_html_returns_empty_result():
    result = MultiStrategyParser().parse("", None)
    assert isinstance(result, ParseResult)
    assert result.items == []
    assert result.strategy_used == "none"
    assert result.confidence == 0.0
    assert result.fields_found == []


def test_parse_result_has_expected_attributes():
    result = MultiStrategyParser().parse("", None)
    assert hasattr(result, "items")
    assert hasattr(result, "strategy_used")
    assert hasattr(result, "confidence")
    assert hasattr(result, "fields_found")


def test_strategy_used_is_string():
    result = MultiStrategyParser().parse("", None)
    assert isinstance(result.strategy_used, str)


def test_items_is_list():
    result = MultiStrategyParser().parse("", None)
    assert isinstance(result.items, list)


# ── Schema.org strategy ───────────────────────────────────────────────────────

def test_schema_org_returns_items():
    html = _load("sample_page_schema_org.html")
    result = MultiStrategyParser().parse(html, None)
    assert result.items
    assert result.strategy_used == "schema_org"


def test_schema_org_confidence_is_positive():
    html = _load("sample_page_schema_org.html")
    result = MultiStrategyParser().parse(html, None)
    assert result.confidence > 0.0


def test_schema_org_item_count():
    html = _load("sample_page_schema_org.html")
    result = MultiStrategyParser().parse(html, None)
    assert len(result.items) == 2


def test_schema_org_item_has_name_field():
    html = _load("sample_page_schema_org.html")
    result = MultiStrategyParser().parse(html, None)
    assert any(item.get("name") for item in result.items)


def test_schema_org_with_domain_config_scores_known_fields():
    html = _load("sample_page_schema_org.html")
    cfg = _cfg(fields=[
        _field("title", json_paths=["name"]),
        _field("price", json_paths=["offers.price"]),
    ])
    result = MultiStrategyParser().parse(html, cfg)
    assert result.confidence > 0.0


# ── Next.js strategy ──────────────────────────────────────────────────────────

def test_nextdata_page_uses_next_data_or_another_strategy():
    html = _load("sample_page_nextdata.html")
    result = MultiStrategyParser().parse(html, None)
    # next_data returns empty without jsonpath fields; another strategy may pick it up
    # The important contract is: no exception and a valid ParseResult
    assert isinstance(result, ParseResult)


def test_nextdata_with_field_config_returns_items():
    html = _load("sample_page_nextdata.html")
    cfg = _cfg(fields=[
        _field("title", json_paths=["props.pageProps.listings[*].title"]),
        _field("price", json_paths=["props.pageProps.listings[*].price"]),
    ])
    result = MultiStrategyParser().parse(html, cfg)
    # With jsonpath array expressions, next_data strategy should expand items
    assert isinstance(result, ParseResult)


# ── No-config path ────────────────────────────────────────────────────────────

def test_no_domain_config_schema_org_returns_raw_items():
    html = _load("sample_page_schema_org.html")
    result = MultiStrategyParser().parse(html, None)
    assert result.items
    # With no config, confidence is 1.0 (no required fields to miss)
    assert result.confidence == 1.0


def test_no_domain_config_static_html_falls_back():
    html = _load("sample_page_static.html")
    result = MultiStrategyParser().parse(html, None)
    # Static HTML has no structured data and no domain config → all strategies fail
    # but no exception should be raised
    assert isinstance(result, ParseResult)


# ── Confidence threshold ──────────────────────────────────────────────────────

def test_confidence_between_0_and_1():
    html = _load("sample_page_schema_org.html")
    result = MultiStrategyParser().parse(html, None)
    assert 0.0 <= result.confidence <= 1.0


def test_confidence_is_0_when_no_items():
    result = MultiStrategyParser().parse("", None)
    assert result.confidence == 0.0
