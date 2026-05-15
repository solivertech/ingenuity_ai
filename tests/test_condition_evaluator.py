"""Tests for alerts.condition_evaluator.ConditionEvaluator."""

import pytest
from alerts.condition_evaluator import ConditionEvaluator


def _config(conditions):
    class _Cfg:
        alert_conditions = conditions
    return _Cfg()


def _item(**kwargs):
    return dict(kwargs)


# ── No conditions ──────────────────────────────────────────────────────────────

def test_no_conditions_returns_empty():
    ev = ConditionEvaluator(None)
    assert ev.evaluate([_item(price=300000)]) == []


def test_empty_conditions_returns_empty():
    ev = ConditionEvaluator(_config([]))
    assert ev.evaluate([_item(price=300000)]) == []


# ── Threshold operator coverage ────────────────────────────────────────────────

@pytest.mark.parametrize("op,item_val,threshold,expect_triggered", [
    ("<=", 300000, 400000, True),
    ("<=", 400000, 400000, True),
    ("<=", 500000, 400000, False),
    ("<",  399999, 400000, True),
    ("<",  400000, 400000, False),
    (">=", 500000, 400000, True),
    (">=", 400000, 400000, True),
    (">=", 300000, 400000, False),
    (">",  400001, 400000, True),
    (">",  400000, 400000, False),
    ("==", "abc",  "abc",  True),
    ("==", "abc",  "xyz",  False),
    ("!=", "abc",  "xyz",  True),
    ("!=", "abc",  "abc",  False),
])
def test_threshold_operators(op, item_val, threshold, expect_triggered):
    cond = {"type": "threshold", "field": "price", "operator": op, "value": threshold}
    ev = ConditionEvaluator(_config([cond]))
    result = ev.evaluate([_item(price=item_val)])
    assert bool(result) == expect_triggered


def test_triggered_item_has_alert_reason():
    cond = {"type": "threshold", "field": "price", "operator": "<=", "value": 400000}
    ev = ConditionEvaluator(_config([cond]))
    result = ev.evaluate([_item(price=300000)])
    assert result[0]["alert_reason"] == "price <= 400000"


def test_triggered_item_is_a_copy():
    original = _item(price=300000)
    cond = {"type": "threshold", "field": "price", "operator": "<=", "value": 400000}
    ev = ConditionEvaluator(_config([cond]))
    result = ev.evaluate([original])
    assert result[0] is not original


def test_missing_field_skips_item():
    cond = {"type": "threshold", "field": "sqft", "operator": ">=", "value": 1000}
    ev = ConditionEvaluator(_config([cond]))
    assert ev.evaluate([_item(price=300000)]) == []


def test_unknown_type_skips_condition():
    cond = {"type": "appearance", "field": "price", "operator": "<=", "value": 400000}
    ev = ConditionEvaluator(_config([cond]))
    assert ev.evaluate([_item(price=300000)]) == []


def test_unknown_operator_skips_condition():
    cond = {"type": "threshold", "field": "price", "operator": "between", "value": 400000}
    ev = ConditionEvaluator(_config([cond]))
    assert ev.evaluate([_item(price=300000)]) == []


def test_multiple_conditions_first_match_triggers():
    conditions = [
        {"type": "threshold", "field": "price", "operator": "<=", "value": 200000},
        {"type": "threshold", "field": "price", "operator": "<=", "value": 400000},
    ]
    ev = ConditionEvaluator(_config(conditions))
    # price=300000 matches second condition only
    result = ev.evaluate([_item(price=300000)])
    assert len(result) == 1
    assert result[0]["alert_reason"] == "price <= 400000"


def test_multiple_items_independent_evaluation():
    cond = {"type": "threshold", "field": "price", "operator": "<=", "value": 400000}
    ev = ConditionEvaluator(_config([cond]))
    items = [_item(price=300000), _item(price=500000), _item(price=100000)]
    result = ev.evaluate(items)
    assert len(result) == 2  # 300k and 100k
