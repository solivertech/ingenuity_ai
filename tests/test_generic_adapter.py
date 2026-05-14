"""
Tests for domains/base.py utilities and domains/generic/adapter.py.

No network or browser required — all inputs are constructed in-process.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domains.base import DomainConfig, FieldSchema, _json_path_get, _coerce
from domains.generic.adapter import GenericAdapter


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _field(name="price", json_paths=None, data_type="float", required=True, is_primary_sort=False):
    return FieldSchema(
        name=name,
        display_name=name.title(),
        json_paths=json_paths or [name],
        css_selectors=[],
        data_type=data_type,
        unit="",
        required=required,
        is_primary_sort=is_primary_sort,
    )


def _config(fields=None, pagination_style="query_param", pagination_param="page", base_url="https://example.com/items"):
    return DomainConfig(
        domain_id="test_domain",
        display_name="Test Domain",
        base_url=base_url,
        pagination_style=pagination_style,
        pagination_param=pagination_param,
        fields=fields or [_field()],
    )


# ── _json_path_get ────────────────────────────────────────────────────────────

def test_json_path_simple_key():
    assert _json_path_get({"price": 100}, "price") == 100


def test_json_path_dot_notation():
    assert _json_path_get({"offers": {"price": 99}}, "offers.price") == 99


def test_json_path_strips_dollar_dot_prefix():
    assert _json_path_get({"a": {"b": 5}}, "$.a.b") == 5


def test_json_path_missing_key_returns_none():
    assert _json_path_get({"x": 1}, "y") is None


def test_json_path_missing_nested_key_returns_none():
    assert _json_path_get({"a": {"b": 1}}, "a.c") is None


def test_json_path_intermediate_not_dict_returns_none():
    assert _json_path_get({"a": "not_a_dict"}, "a.b") is None


def test_json_path_empty_path_returns_none():
    # The implementation splits "" into [""], which is a missing key lookup → None
    assert _json_path_get({"a": 1}, "") is None


# ── _coerce ───────────────────────────────────────────────────────────────────

def test_coerce_float_plain():
    assert _coerce("12.5", "float") == 12.5


def test_coerce_float_with_dollar():
    assert _coerce("$1,200.00", "float") == 1200.0


def test_coerce_float_with_commas():
    assert _coerce("1,234,567", "float") == 1234567.0


def test_coerce_int_plain():
    assert _coerce("42", "int") == 42


def test_coerce_int_with_commas():
    assert _coerce("80,000", "int") == 80000


def test_coerce_str_strips_whitespace():
    assert _coerce("  hello  ", "str") == "hello"


def test_coerce_bool_truthy():
    assert _coerce(1, "bool") is True


def test_coerce_bool_falsy():
    assert _coerce(0, "bool") is False


def test_coerce_bad_float_returns_none():
    assert _coerce("not_a_number", "float") is None


def test_coerce_bad_int_returns_none():
    assert _coerce("abc", "int") is None


def test_coerce_none_float_returns_none():
    assert _coerce(None, "float") is None


# ── GenericAdapter.build_url ──────────────────────────────────────────────────

def test_build_url_query_param_page_1():
    adapter = GenericAdapter(_config(base_url="https://example.com/items"))
    assert adapter.build_url(page=1) == "https://example.com/items?page=1"


def test_build_url_query_param_page_3():
    adapter = GenericAdapter(_config(base_url="https://example.com/items"))
    assert adapter.build_url(page=3) == "https://example.com/items?page=3"


def test_build_url_query_param_appends_to_existing_qs():
    cfg = _config(base_url="https://example.com/items?sort=price")
    adapter = GenericAdapter(cfg)
    url = adapter.build_url(page=2)
    assert url == "https://example.com/items?sort=price&page=2"


def test_build_url_path_segment():
    cfg = _config(base_url="https://example.com/listings", pagination_style="path_segment")
    adapter = GenericAdapter(cfg)
    assert adapter.build_url(page=5) == "https://example.com/listings/5"


def test_build_url_none_pagination_returns_base():
    cfg = _config(base_url="https://example.com/all", pagination_style="none")
    adapter = GenericAdapter(cfg)
    assert adapter.build_url(page=1) == "https://example.com/all"


# ── GenericAdapter.normalize ──────────────────────────────────────────────────

def test_normalize_returns_dict_when_required_field_present():
    fields = [_field("price", json_paths=["price"], required=True)]
    adapter = GenericAdapter(_config(fields=fields))
    result = adapter.normalize({"price": 500.0}, strategy="test")
    assert result is not None
    assert result["price"] == 500.0


def test_normalize_returns_none_when_required_field_missing():
    fields = [_field("price", json_paths=["price"], required=True)]
    adapter = GenericAdapter(_config(fields=fields))
    result = adapter.normalize({"other_key": "x"}, strategy="test")
    assert result is None


def test_normalize_includes_optional_field_as_none_when_absent():
    fields = [
        _field("price", json_paths=["price"], required=True),
        _field("mileage", json_paths=["mileage"], required=False),
    ]
    adapter = GenericAdapter(_config(fields=fields))
    result = adapter.normalize({"price": 100.0}, strategy="test")
    assert result is not None
    assert result["mileage"] is None


def test_normalize_sets_extraction_strategy():
    fields = [_field("price", json_paths=["price"], required=True)]
    adapter = GenericAdapter(_config(fields=fields))
    result = adapter.normalize({"price": 1.0}, strategy="ld_json")
    assert result["extraction_strategy"] == "ld_json"


def test_normalize_sets_scraped_at():
    fields = [_field("price", json_paths=["price"], required=True)]
    adapter = GenericAdapter(_config(fields=fields))
    result = adapter.normalize({"price": 1.0}, strategy="test")
    assert "scraped_at" in result


def test_normalize_multiple_fields():
    fields = [
        _field("price",   json_paths=["price"],   data_type="float", required=True),
        _field("title",   json_paths=["title"],   data_type="str",   required=False),
    ]
    adapter = GenericAdapter(_config(fields=fields))
    result = adapter.normalize({"price": 9.99, "title": "Widget"}, strategy="test")
    assert result["price"] == 9.99
    assert result["title"] == "Widget"


# ── GenericAdapter.get_field (path fallback) ──────────────────────────────────

def test_get_field_uses_first_matching_path():
    f = _field("price", json_paths=["product.price", "offers.price"])
    adapter = GenericAdapter(_config(fields=[f]))
    val = adapter.get_field({"product": {"price": 42.0}}, f)
    assert val == 42.0


def test_get_field_falls_back_to_second_path():
    f = _field("price", json_paths=["product.price", "offers.price"])
    adapter = GenericAdapter(_config(fields=[f]))
    val = adapter.get_field({"offers": {"price": 99.0}}, f)
    assert val == 99.0


def test_get_field_returns_none_when_all_paths_miss():
    f = _field("price", json_paths=["a.b", "c.d"])
    adapter = GenericAdapter(_config(fields=[f]))
    val = adapter.get_field({"x": 1}, f)
    assert val is None


def test_get_field_coerces_int_type():
    f = _field("year", json_paths=["year"], data_type="int")
    adapter = GenericAdapter(_config(fields=[f]))
    val = adapter.get_field({"year": "2023"}, f)
    assert val == 2023


def test_get_field_coerces_bool_type():
    f = _field("certified", json_paths=["certified"], data_type="bool")
    adapter = GenericAdapter(_config(fields=[f]))
    val = adapter.get_field({"certified": 1}, f)
    assert val is True
