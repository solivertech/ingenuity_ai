"""Tests for scraping.pipeline.filter_engine.FilterEngine."""

import pytest
from scraping.pipeline.filter_engine import FilterEngine


def _cfg(rules):
    class _Cfg:
        filter_rules = rules
    return _Cfg()


def _item(**kwargs):
    return dict(kwargs)


# ── No rules ──────────────────────────────────────────────────────────────────

def test_no_rules_passes_everything():
    fe = FilterEngine(None)
    items = [_item(price=100), _item(price=999)]
    assert fe.apply(items) == items


def test_empty_rules_passes_everything():
    fe = FilterEngine(_cfg([]))
    items = [_item(price=100)]
    assert fe.apply(items) == items


# ── Operator coverage ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("op,item_val,threshold,expect_kept", [
    ("<=", 100, 200, True),
    ("<=", 200, 200, True),
    ("<=", 300, 200, False),
    ("<",  100, 200, True),
    ("<",  200, 200, False),
    (">=", 300, 200, True),
    (">=", 200, 200, True),
    (">=", 100, 200, False),
    (">",  300, 200, True),
    (">",  200, 200, False),
    ("==", 200, 200, True),
    ("==", 100, 200, False),
    ("!=", 100, 200, True),
    ("!=", 200, 200, False),
    ("contains",     "hello world", "world", True),
    ("contains",     "hello world", "xyz",   False),
    ("not_contains", "hello world", "xyz",   True),
    ("not_contains", "hello world", "world", False),
])
def test_operator(op, item_val, threshold, expect_kept):
    rule = {"field": "price", "operator": op, "value": threshold}
    fe = FilterEngine(_cfg([rule]))
    result = fe.apply([_item(price=item_val)])
    assert bool(result) == expect_kept


def test_missing_field_passes_item():
    rule = {"field": "sqft", "operator": ">=", "value": 1000}
    fe = FilterEngine(_cfg([rule]))
    # Item has no 'sqft' field — passes (can't evaluate)
    assert fe.apply([_item(price=500)]) == [_item(price=500)]


def test_unknown_operator_passes_item():
    rule = {"field": "price", "operator": "between", "value": 100}
    fe = FilterEngine(_cfg([rule]))
    assert fe.apply([_item(price=500)]) == [_item(price=500)]


# ── Profile rule override ─────────────────────────────────────────────────────

def test_profile_rules_applied_in_addition_to_domain_rules():
    domain_rule = {"field": "price",   "operator": "<=", "value": 400000}
    profile_rule = {"field": "bedrooms", "operator": ">=", "value": 3}
    fe = FilterEngine(_cfg([domain_rule]))

    items = [
        _item(price=300000, bedrooms=4),  # passes both
        _item(price=300000, bedrooms=2),  # fails profile rule
        _item(price=500000, bedrooms=4),  # fails domain rule
    ]
    result = fe.apply(items, profile_rules=[profile_rule])
    assert len(result) == 1
    assert result[0]["bedrooms"] == 4


# ── Multiple rules ────────────────────────────────────────────────────────────

def test_item_must_pass_all_rules():
    rules = [
        {"field": "price",  "operator": "<=", "value": 400000},
        {"field": "mileage", "operator": "<=", "value": 50000},
    ]
    fe = FilterEngine(_cfg(rules))
    items = [
        _item(price=300000, mileage=40000),   # passes both
        _item(price=300000, mileage=60000),   # fails mileage
        _item(price=500000, mileage=40000),   # fails price
    ]
    result = fe.apply(items)
    assert len(result) == 1
    assert result[0]["mileage"] == 40000


def test_multiple_items_filtered_independently():
    rule = {"field": "price", "operator": "<=", "value": 400000}
    fe = FilterEngine(_cfg([rule]))
    items = [_item(price=300000), _item(price=500000), _item(price=100000)]
    result = fe.apply(items)
    assert len(result) == 2
