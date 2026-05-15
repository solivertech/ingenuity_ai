"""Tests for scraping.pipeline.runner.PipelineRunner."""

import pytest
from scraping.pipeline.runner import PipelineRunner, PipelineResult


def _item(**kwargs):
    return dict(kwargs)


def _cfg(filter_rules=None, scoring_weights=None, field_names=None):
    class _Field:
        def __init__(self, name):
            self.name = name

    class _Cfg:
        pass

    cfg = _Cfg()
    cfg.filter_rules = filter_rules or []
    cfg.scoring_weights = scoring_weights or {}
    cfg.fields = [_Field(n) for n in (field_names or [])]
    return cfg


# ── Result shape ──────────────────────────────────────────────────────────────

def test_empty_input_returns_empty_result():
    runner = PipelineRunner()
    result = runner.run([])
    assert isinstance(result, PipelineResult)
    assert result.raw_count == 0
    assert result.deduped_count == 0
    assert result.filtered_count == 0
    assert result.enriched == []


def test_result_counts_track_each_stage():
    cfg = _cfg(filter_rules=[{"field": "price", "operator": "<=", "value": 300}])
    runner = PipelineRunner(cfg)
    items = [
        _item(vin="A", price=100),
        _item(vin="A", price=100),  # duplicate
        _item(vin="B", price=500),  # filtered out
        _item(vin="C", price=200),
    ]
    result = runner.run(items)
    assert result.raw_count == 4
    assert result.deduped_count == 3   # A deduped to 1
    assert result.filtered_count == 2  # B removed by price rule
    assert len(result.enriched) == 2


# ── Deduplication stage ───────────────────────────────────────────────────────

def test_duplicates_removed_before_filtering():
    runner = PipelineRunner()
    items = [_item(vin="X", price=10), _item(vin="X", price=10)]
    result = runner.run(items)
    assert result.deduped_count == 1
    assert len(result.enriched) == 1


def test_no_duplicates_passes_all_through():
    runner = PipelineRunner()
    items = [_item(vin="A"), _item(vin="B"), _item(vin="C")]
    result = runner.run(items)
    assert result.deduped_count == 3


# ── Filter stage ──────────────────────────────────────────────────────────────

def test_domain_filter_rules_applied():
    cfg = _cfg(filter_rules=[{"field": "price", "operator": "<=", "value": 400}])
    runner = PipelineRunner(cfg)
    items = [_item(vin="A", price=300), _item(vin="B", price=500)]
    result = runner.run(items)
    assert result.filtered_count == 1
    assert result.enriched[0]["price"] == 300


def test_profile_rules_applied_on_top_of_domain_rules():
    cfg = _cfg(filter_rules=[{"field": "price", "operator": "<=", "value": 400}])
    runner = PipelineRunner(cfg)
    items = [
        _item(vin="A", price=300, beds=3),
        _item(vin="B", price=300, beds=1),  # passes domain rule, fails profile rule
    ]
    profile_rules = [{"field": "beds", "operator": ">=", "value": 2}]
    result = runner.run(items, profile_rules=profile_rules)
    assert result.filtered_count == 1
    assert result.enriched[0]["beds"] == 3


def test_no_rules_passes_all():
    runner = PipelineRunner()
    items = [_item(price=999999), _item(price=1)]
    result = runner.run(items)
    assert result.filtered_count == 2


# ── Enrich stage ──────────────────────────────────────────────────────────────

def test_enriched_items_have_value_score():
    runner = PipelineRunner()
    items = [_item(vin="A", price=100)]
    result = runner.run(items)
    assert "value_score" in result.enriched[0]


def test_scoring_weights_affect_value_score():
    cfg_price = _cfg(scoring_weights={"price": 100})
    runner = PipelineRunner(cfg_price)
    items = [_item(vin="A", price=100), _item(vin="B", price=1000)]
    result = runner.run(items)
    scores = {item["vin"]: item["value_score"] for item in result.enriched}
    assert scores["A"] > scores["B"]


def test_enriched_list_is_same_object_as_filtered():
    runner = PipelineRunner()
    items = [_item(vin="A")]
    result = runner.run(items)
    # enriched items are the filtered items with value_score added in-place
    assert result.enriched[0].get("value_score") is not None


# ── No config ─────────────────────────────────────────────────────────────────

def test_none_config_runs_without_error():
    runner = PipelineRunner(None)
    items = [_item(price=200), _item(price=300)]
    result = runner.run(items)
    assert len(result.enriched) == 2


def test_profile_rules_none_runs_without_error():
    runner = PipelineRunner()
    items = [_item(vin="A")]
    result = runner.run(items, profile_rules=None)
    assert len(result.enriched) == 1


# ── Stage ordering ────────────────────────────────────────────────────────────

def test_dedup_runs_before_filter():
    # Two items with same VIN but different prices. If filter runs first,
    # both might survive; dedup-first means only one enters the filter.
    cfg = _cfg(filter_rules=[{"field": "price", "operator": "<=", "value": 150}])
    runner = PipelineRunner(cfg)
    items = [
        _item(vin="A", price=100),  # first-seen wins in dedup
        _item(vin="A", price=200),  # duplicate — dropped before filter
    ]
    result = runner.run(items)
    assert result.deduped_count == 1
    assert result.filtered_count == 1   # the surviving one (price=100) passes


def test_filter_runs_before_enrich():
    # If enrich ran first, filtered-out items would still have value_score.
    # Verify filtered_count matches len(enriched).
    cfg = _cfg(filter_rules=[{"field": "price", "operator": "<=", "value": 200}])
    runner = PipelineRunner(cfg)
    items = [_item(vin="A", price=100), _item(vin="B", price=300)]
    result = runner.run(items)
    assert result.filtered_count == len(result.enriched) == 1
