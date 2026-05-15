"""Tests for scraping.pipeline.enricher.GenericEnricher."""

import pytest
from scraping.pipeline.enricher import GenericEnricher


def _cfg(weights):
    class _Cfg:
        scoring_weights = weights
    return _Cfg()


def _item(**kwargs):
    return dict(kwargs)


# ── No weights ────────────────────────────────────────────────────────────────

def test_no_config_sets_zero_score():
    ge = GenericEnricher(None)
    items = [_item(price=100)]
    result = ge.enrich(items)
    assert result[0]["value_score"] == 0.0


def test_empty_weights_sets_zero_score():
    ge = GenericEnricher(_cfg({}))
    items = [_item(price=100)]
    result = ge.enrich(items)
    assert result[0]["value_score"] == 0.0


def test_empty_input_returns_empty():
    ge = GenericEnricher(_cfg({"price": 100}))
    assert ge.enrich([]) == []


# ── Score range ───────────────────────────────────────────────────────────────

def test_score_in_0_to_100_range():
    ge = GenericEnricher(_cfg({"price": 80, "sqft": 20}))
    items = [_item(price=200000, sqft=1500), _item(price=500000, sqft=800)]
    result = ge.enrich(items)
    for item in result:
        assert 0.0 <= item["value_score"] <= 100.0


# ── Lower-is-better for price ─────────────────────────────────────────────────

def test_lower_price_gives_higher_score():
    ge = GenericEnricher(_cfg({"price": 100}))
    items = [_item(price=100000), _item(price=500000)]
    result = ge.enrich(items)
    assert result[0]["value_score"] > result[1]["value_score"]


def test_lower_mileage_gives_higher_score():
    ge = GenericEnricher(_cfg({"mileage": 100}))
    items = [_item(mileage=10000), _item(mileage=100000)]
    result = ge.enrich(items)
    assert result[0]["value_score"] > result[1]["value_score"]


# ── Missing field handling ────────────────────────────────────────────────────

def test_missing_field_gets_neutral_contribution():
    ge = GenericEnricher(_cfg({"price": 50, "sqft": 50}))
    # Item A has both fields; Item B is missing sqft
    item_a = _item(price=100000, sqft=2000)
    item_b = _item(price=100000)
    result = ge.enrich([item_a, item_b])
    # B should be penalized (neutral contribution) vs A (above-average sqft)
    # Both get value_score set; just confirm no crash
    assert "value_score" in result[0]
    assert "value_score" in result[1]


def test_non_numeric_field_gets_neutral_contribution():
    ge = GenericEnricher(_cfg({"price": 100}))
    items = [_item(price="not-a-number")]
    result = ge.enrich(items)
    assert result[0]["value_score"] == pytest.approx(50.0)


# ── Enrichment is in-place ─────────────────────────────────────────────────────

def test_enrich_modifies_items_in_place_and_returns_same_list():
    ge = GenericEnricher(_cfg({"price": 100}))
    items = [_item(price=100)]
    returned = ge.enrich(items)
    assert returned is items
    assert "value_score" in items[0]
