"""
Tests for discovery/schema_agent.py — module-level helpers and SchemaAgent
with all I/O (Browser, LLMAnalyzer, requests) mocked.
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from discovery.schema_agent import (
    SchemaAgent,
    _extract_page_context,
    _build_discovery_prompt,
    _parse_llm_response,
    _check_robots_txt,
)
from domains.base import DomainConfig, FieldSchema


# ── Fixtures ──────────────────────────────────────────────────────────────────

_MINIMAL_LLM_JSON = json.dumps({
    "fields": [
        {
            "name": "price",
            "display_name": "Price",
            "json_paths": ["offers.price"],
            "css_selectors": [".price"],
            "data_type": "float",
            "unit": "$",
            "required": True,
            "is_primary_sort": True,
        }
    ],
    "pagination_style": "query_param",
    "pagination_param": "page",
    "system_prompt_context": "You are a pricing analyst.",
    "scoring_weights": {"price": 50},
})

_HTML_WITH_LD_JSON = """
<html><head>
<script type="application/ld+json">{"@type":"Product","offers":{"price":1000}}</script>
</head><body>Hello world from the page</body></html>
"""

_HTML_WITH_NEXT_DATA = """
<html><body>
<script id="__NEXT_DATA__" type="application/json">{"props":{"listings":[{"price":500}]}}</script>
</body></html>
"""

_HTML_WITH_WINDOW_VAR = """
<html><body>
<script>window.__APOLLO_STATE__ = {"Listing:1":{"price":999}};</script>
</body></html>
"""


# ── _extract_page_context ────────────────────────────────────────────────────

def test_extract_context_includes_ld_json():
    ctx = _extract_page_context(_HTML_WITH_LD_JSON)
    assert "ld+json" in ctx
    assert "Product" in ctx


def test_extract_context_includes_next_data():
    ctx = _extract_page_context(_HTML_WITH_NEXT_DATA)
    assert "__NEXT_DATA__" in ctx
    assert "listings" in ctx


def test_extract_context_includes_window_var():
    ctx = _extract_page_context(_HTML_WITH_WINDOW_VAR)
    assert "window vars" in ctx
    # The regex captures the JSON value, not the variable name
    assert "Listing:1" in ctx


def test_extract_context_always_includes_page_text():
    ctx = _extract_page_context("<html><body>Some visible text</body></html>")
    assert "Page text sample" in ctx
    assert "Some visible text" in ctx


def test_extract_context_truncated_to_15000():
    big_html = "<html><body>" + "x" * 20000 + "</body></html>"
    ctx = _extract_page_context(big_html)
    assert len(ctx) <= 15000


# ── _build_discovery_prompt ───────────────────────────────────────────────────

def test_build_prompt_contains_url():
    p = _build_discovery_prompt("https://example.com/listings", "find prices", "ctx")
    assert "https://example.com/listings" in p


def test_build_prompt_contains_user_request():
    p = _build_discovery_prompt("https://x.com", "I need price and mileage", "ctx")
    assert "I need price and mileage" in p


def test_build_prompt_contains_page_context():
    p = _build_discovery_prompt("https://x.com", "req", "UNIQUE_CONTEXT_MARKER")
    assert "UNIQUE_CONTEXT_MARKER" in p


def test_build_prompt_contains_schema_template():
    p = _build_discovery_prompt("https://x.com", "req", "ctx")
    assert "json_paths" in p


# ── _parse_llm_response ───────────────────────────────────────────────────────

def test_parse_valid_json_returns_domain_config():
    cfg = _parse_llm_response(_MINIMAL_LLM_JSON, "https://x.com", "my_domain", "My Domain", "find prices")
    assert isinstance(cfg, DomainConfig)
    assert cfg.domain_id == "my_domain"
    assert cfg.display_name == "My Domain"
    assert len(cfg.fields) == 1
    assert cfg.fields[0].name == "price"


def test_parse_strips_markdown_fences():
    fenced = f"```json\n{_MINIMAL_LLM_JSON}\n```"
    cfg = _parse_llm_response(fenced, "https://x.com", "d", "D", "req")
    assert cfg is not None
    assert cfg.fields[0].name == "price"


def test_parse_bad_json_returns_none():
    cfg = _parse_llm_response("this is not json", "https://x.com", "d", "D", "req")
    assert cfg is None


def test_parse_missing_fields_key_returns_empty_fields():
    data = json.dumps({"pagination_style": "none", "pagination_param": "p", "scoring_weights": {}})
    cfg = _parse_llm_response(data, "https://x.com", "d", "D", "req")
    assert cfg is not None
    assert cfg.fields == []


def test_parse_sets_base_url():
    cfg = _parse_llm_response(_MINIMAL_LLM_JSON, "https://shop.example.com/items", "d", "D", "req")
    assert cfg.base_url == "https://shop.example.com/items"


def test_parse_sets_user_request():
    cfg = _parse_llm_response(_MINIMAL_LLM_JSON, "https://x.com", "d", "D", "track prices please")
    assert cfg.user_request == "track prices please"


# ── SchemaAgent.discover() ────────────────────────────────────────────────────

def _make_agent(analysis_text=_MINIMAL_LLM_JSON):
    llm = MagicMock()
    result = MagicMock()
    result.analysis = analysis_text
    llm.analyze.return_value = result
    return SchemaAgent(llm)


def test_discover_returns_domain_config_on_success():
    agent = _make_agent()
    with patch("discovery.schema_agent._check_robots_txt"), \
         patch("scraper.browser.Browser") as MockBrowser:
        MockBrowser.return_value.__enter__.return_value.get_page_content.return_value = _HTML_WITH_LD_JSON
        cfg = agent.discover("https://x.com", "find prices", "x_domain", "X Domain")
    assert isinstance(cfg, DomainConfig)
    assert cfg.domain_id == "x_domain"


def test_discover_returns_none_on_empty_html():
    agent = _make_agent()
    with patch("discovery.schema_agent._check_robots_txt"), \
         patch("scraper.browser.Browser") as MockBrowser:
        MockBrowser.return_value.__enter__.return_value.get_page_content.return_value = ""
        cfg = agent.discover("https://x.com", "req", "d", "D")
    assert cfg is None


def test_discover_returns_none_when_llm_no_analysis():
    llm = MagicMock()
    result = MagicMock()
    result.analysis = None
    llm.analyze.return_value = result
    agent = SchemaAgent(llm)
    with patch("discovery.schema_agent._check_robots_txt"), \
         patch("scraper.browser.Browser") as MockBrowser:
        MockBrowser.return_value.__enter__.return_value.get_page_content.return_value = _HTML_WITH_LD_JSON
        cfg = agent.discover("https://x.com", "req", "d", "D")
    assert cfg is None


def test_discover_returns_none_when_llm_unparseable():
    agent = _make_agent(analysis_text="not json at all")
    with patch("discovery.schema_agent._check_robots_txt"), \
         patch("scraper.browser.Browser") as MockBrowser:
        MockBrowser.return_value.__enter__.return_value.get_page_content.return_value = _HTML_WITH_LD_JSON
        cfg = agent.discover("https://x.com", "req", "d", "D")
    assert cfg is None


def test_discover_calls_robots_check():
    agent = _make_agent()
    with patch("discovery.schema_agent._check_robots_txt") as mock_robots, \
         patch("scraper.browser.Browser") as MockBrowser:
        MockBrowser.return_value.__enter__.return_value.get_page_content.return_value = _HTML_WITH_LD_JSON
        agent.discover("https://example.com/items", "req", "d", "D")
    mock_robots.assert_called_once_with("https://example.com/items")


# ── SchemaAgent._refine() ─────────────────────────────────────────────────────

def _make_config():
    return _parse_llm_response(_MINIMAL_LLM_JSON, "https://x.com", "d", "D", "req")


def test_refine_updates_fields_from_valid_response():
    updated_fields = [
        {
            "name": "price",
            "display_name": "Price",
            "json_paths": ["product.price"],
            "css_selectors": [],
            "data_type": "float",
            "unit": "$",
            "required": True,
            "is_primary_sort": True,
        }
    ]
    llm = MagicMock()
    result = MagicMock()
    result.analysis = json.dumps(updated_fields)
    llm.analyze.return_value = result
    agent = SchemaAgent(llm)
    cfg = _make_config()
    refined = agent._refine(cfg, ["price (80% null)"])
    assert refined.fields[0].json_paths == ["product.price"]


def test_refine_returns_original_config_on_bad_response():
    llm = MagicMock()
    result = MagicMock()
    result.analysis = "not valid json"
    llm.analyze.return_value = result
    agent = SchemaAgent(llm)
    cfg = _make_config()
    original_paths = cfg.fields[0].json_paths[:]
    refined = agent._refine(cfg, ["price (80% null)"])
    assert refined.fields[0].json_paths == original_paths


# ── _check_robots_txt ────────────────────────────────────────────────────────

def test_check_robots_warns_when_disallowed(caplog):
    import logging
    robots_txt = "User-agent: *\nDisallow: /"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = robots_txt
    with patch("requests.get", return_value=mock_resp), \
         caplog.at_level(logging.WARNING, logger="discovery.schema_agent"):
        _check_robots_txt("https://example.com/listings")
    assert any("disallows" in r.message for r in caplog.records)


def test_check_robots_silent_when_permitted(caplog):
    import logging
    robots_txt = "User-agent: *\nDisallow: /admin"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = robots_txt
    with patch("requests.get", return_value=mock_resp), \
         caplog.at_level(logging.WARNING, logger="discovery.schema_agent"):
        _check_robots_txt("https://example.com/listings")
    assert not any("disallows" in r.message for r in caplog.records)


def test_check_robots_silently_handles_network_error():
    with patch("requests.get", side_effect=ConnectionError("no network")):
        _check_robots_txt("https://unreachable.example.com/items")  # must not raise


def test_check_robots_silently_handles_404():
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch("requests.get", return_value=mock_resp):
        _check_robots_txt("https://example.com/items")  # must not raise
