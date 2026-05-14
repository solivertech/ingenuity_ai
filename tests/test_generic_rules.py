"""
Tests for analysis/rules.py with generic (non-automotive) scoring weights,
mirroring how a DomainConfig.scoring_weights feeds into the pipeline.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analysis.rules import _value_score, enrich_listings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _listing(**kwargs) -> dict:
    base = {
        "make": "Generic", "model": "Item", "year": 2023,
        "price": 1000.0, "mileage": None, "trim": "",
        "shipping": None, "vin": "X1",
    }
    base.update(kwargs)
    return base


_NO_GROUP = {}  # empty group_averages — price component uses neutral mid-point


# ── Custom weights from DomainConfig.scoring_weights ─────────────────────────

_PRICE_ONLY_WEIGHTS = {"price": 100, "mileage": 0, "age": 0, "shipping": 0, "hybrid": 0}
_MILEAGE_ONLY_WEIGHTS = {"price": 0, "mileage": 100, "age": 0, "shipping": 0, "hybrid": 0}
_EQUAL_WEIGHTS = {"price": 20, "mileage": 20, "age": 20, "shipping": 20, "hybrid": 20}


def test_custom_weights_accepted_without_error():
    score = _value_score(
        _listing(), _NO_GROUP, 2025, scoring_weights=_PRICE_ONLY_WEIGHTS
    )
    assert 0.0 <= score <= 100.0


def test_price_only_weights_neutral_when_no_group_data():
    score = _value_score(
        _listing(price=500), _NO_GROUP, 2025, scoring_weights=_PRICE_ONLY_WEIGHTS
    )
    # No group average → neutral mid-point = 50 pts of 100
    assert score == 50.0


def test_price_only_weights_higher_for_below_average():
    group = {("Generic", "Item", 2023): 2000.0}
    cheap = _value_score(_listing(price=1000), group, 2025, scoring_weights=_PRICE_ONLY_WEIGHTS)
    expensive = _value_score(_listing(price=2500), group, 2025, scoring_weights=_PRICE_ONLY_WEIGHTS)
    assert cheap > expensive


def test_mileage_zero_weight_means_mileage_does_not_affect_score():
    score_low  = _value_score(_listing(mileage=1000),  _NO_GROUP, 2025, scoring_weights=_MILEAGE_ONLY_WEIGHTS)
    score_high = _value_score(_listing(mileage=80000), _NO_GROUP, 2025, scoring_weights=_MILEAGE_ONLY_WEIGHTS)
    # With only mileage weight, lower mileage should score higher
    assert score_low > score_high


def test_zero_price_weight_makes_price_irrelevant():
    group = {("Generic", "Item", 2023): 2000.0}
    cheap     = _value_score(_listing(price=100),   group, 2025, scoring_weights=_MILEAGE_ONLY_WEIGHTS)
    expensive = _value_score(_listing(price=10000), group, 2025, scoring_weights=_MILEAGE_ONLY_WEIGHTS)
    # Mileage-only weights — both listings have None mileage → same mileage score
    assert cheap == expensive


def test_equal_weights_sum_to_reasonable_range():
    score = _value_score(
        _listing(mileage=40000, year=2022), _NO_GROUP, 2025,
        min_year=2020, max_mileage=80000,
        scoring_weights=_EQUAL_WEIGHTS,
    )
    assert 0.0 <= score <= 100.0


def test_none_scoring_weights_falls_back_to_defaults():
    default_score = _value_score(_listing(), _NO_GROUP, 2025, scoring_weights=None)
    assert 0.0 <= default_score <= 100.0


def test_empty_scoring_weights_dict_falls_back_to_hardcoded_defaults():
    # Empty dict → all w.get("key", default) return the hardcoded defaults → neutral score
    score = _value_score(_listing(), _NO_GROUP, 2025, scoring_weights={})
    assert 0.0 <= score <= 100.0


# ── enrich_listings with custom scoring_weights ───────────────────────────────

def test_enrich_listings_passes_scoring_weights_through():
    listings = [_listing(price=500), _listing(price=2000)]
    group = {("Generic", "Item", 2023): 1000.0}
    enriched = enrich_listings(
        listings,
        max_year=2025,
        scoring_weights=_PRICE_ONLY_WEIGHTS,
    )
    assert all("value_score" in e for e in enriched)


def test_enrich_listings_custom_weights_cheaper_scores_higher():
    cheap_listing = _listing(price=200,  vin="A")
    pricey_listing = _listing(price=2000, vin="B")
    enriched = enrich_listings(
        [cheap_listing, pricey_listing],
        max_year=2025,
        scoring_weights=_PRICE_ONLY_WEIGHTS,
    )
    scores = {e["vin"]: e["value_score"] for e in enriched}
    assert scores["A"] > scores["B"]


def test_enrich_listings_all_scores_in_range():
    listings = [_listing(price=p) for p in [100, 500, 1000, 5000, 50000]]
    enriched = enrich_listings(listings, max_year=2025, scoring_weights=_EQUAL_WEIGHTS)
    for e in enriched:
        assert 0.0 <= e["value_score"] <= 100.0


def test_enrich_listings_with_domain_config_scoring_weights():
    from domains.base import DomainConfig
    cfg = DomainConfig(
        domain_id="test",
        display_name="Test",
        base_url="https://x.com",
        pagination_style="query_param",
        pagination_param="page",
        scoring_weights={"price": 60, "mileage": 30, "age": 10, "shipping": 0, "hybrid": 0},
    )
    listings = [_listing(price=500, mileage=10000), _listing(price=3000, mileage=70000)]
    enriched = enrich_listings(
        listings,
        max_year=2025,
        scoring_weights=cfg.scoring_weights,
    )
    assert all("value_score" in e for e in enriched)
    # cheaper + lower mileage should beat pricier + higher mileage
    assert enriched[0]["value_score"] > enriched[1]["value_score"]
